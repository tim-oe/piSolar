"""Hourly JSON-lines spool store, one directory per table."""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pisolar.config.spool_config import SpoolConfig
from pisolar.logging_config import get_logger

__all__ = ["SpoolCapacityError", "SpoolStore"]

_SEGMENT_RE = re.compile(r"^\d{8}T\d{2}\.jsonl$")


class SpoolCapacityError(OSError):
    """The configured free-space floor cannot be preserved."""


class SpoolStore:
    """Append-only hourly segments with claim/replay via ``.draining`` renames."""

    def __init__(self, config: SpoolConfig) -> None:
        self._config = config
        self._folder = Path(config.folder)
        self._min_free_pct = config.min_free_pct
        self._warn_age_hours = config.warn_age_hours
        self._logger = get_logger("services.spool")
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._capacity_lock = threading.Lock()
        self._evict_alerted = False
        self._age_alerted = False
        self._folder.mkdir(parents=True, exist_ok=True)

    def append(self, table: str, line: str) -> None:
        segment_name = self._segment_name()
        with self._capacity_lock:
            self._evict_until_fit(segment_name)
            self._warn_if_old()
            directory = self._folder / table
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / segment_name
            with self._lock(table):
                self._write_line(path, line)

    def segments(self, table: str) -> list[Path]:
        directory = self._folder / table
        if not directory.is_dir():
            return []
        found = [path for path in directory.iterdir() if _SEGMENT_RE.match(path.name)]
        return sorted(found, key=lambda path: path.name)

    def tables(self) -> list[str]:
        if not self._folder.is_dir():
            return []
        return sorted(path.name for path in self._folder.iterdir() if path.is_dir())

    def draining_segments(self, table: str) -> list[Path]:
        directory = self._folder / table
        if not directory.is_dir():
            return []
        return sorted(directory.glob("*.jsonl.draining"), key=lambda path: path.name)

    def depth(self, table: str) -> int:
        """Count pending hourly segments and in-progress drains for a table."""
        return len(self.segments(table)) + len(self.draining_segments(table))

    @property
    def folder(self) -> Path:
        return self._folder

    def claim_oldest(self, table: str) -> Path | None:
        directory = self._folder / table
        if not directory.is_dir():
            return None
        with self._lock(table):
            draining = sorted(
                directory.glob("*.jsonl.draining"), key=lambda path: path.name
            )
            if draining:
                return draining[0]
            pending = self.segments(table)
            if not pending:
                return None
            oldest = pending[0]
            dest = oldest.with_name(oldest.name + ".draining")
            oldest.rename(dest)
            return dest

    def release(self, path: Path) -> Path:
        table = path.parent.name
        with self._lock(table):
            if path.name.endswith(".draining"):
                restored = path.with_name(path.name[: -len(".draining")])
                if restored.exists():
                    temporary = restored.with_name(restored.name + ".release.tmp")
                    with temporary.open("wb") as output:
                        for source in (path, restored):
                            with source.open("rb") as input_handle:
                                shutil.copyfileobj(input_handle, output)
                        output.flush()
                        os.fsync(output.fileno())
                    os.replace(temporary, restored)
                    path.unlink()
                else:
                    path.rename(restored)
                return restored
            return path

    def complete(self, path: Path) -> None:
        table = path.parent.name
        with self._lock(table):
            path.unlink(missing_ok=True)

    def rewrite_remainder(self, path: Path, lines: list[str]) -> None:
        table = path.parent.name
        temporary = path.parent / (path.name + ".tmp")
        with self._lock(table):
            with temporary.open("w", encoding="utf-8") as handle:
                for line in lines:
                    handle.write(line if line.endswith("\n") else line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)

    def quarantine(self, table: str, line: str, reason: str) -> None:
        directory = self._folder / table
        directory.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"reason": reason, "line": line})
        with self._lock(table):
            self._write_line(directory / "rejected.jsonl", payload)

    def reset_alerts_if_empty(self) -> None:
        if self._has_pending():
            return
        self._evict_alerted = False
        self._age_alerted = False

    def _has_pending(self) -> bool:
        for table in self.tables():
            directory = self._folder / table
            if self.segments(table) or list(directory.glob("*.jsonl.draining")):
                return True
        return False

    def _segment_name(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H") + ".jsonl"

    def _lock(self, table: str) -> threading.Lock:
        with self._locks_guard:
            if table not in self._locks:
                self._locks[table] = threading.Lock()
            return self._locks[table]

    def _write_line(self, path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line if line.endswith("\n") else line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _evict_until_fit(self, segment_name: str) -> None:
        while self._free_pct() < self._min_free_pct:
            victim = self._oldest_evictable(segment_name)
            if victim is None:
                self._logger.error("spool cannot free disk; no evictable segment")
                raise SpoolCapacityError(
                    f"cannot preserve {self._min_free_pct}% free space "
                    "without deleting an active segment"
                )
            victim_table = victim.parent.name
            with self._lock(victim_table):
                if not victim.is_file() or not _SEGMENT_RE.match(victim.name):
                    continue
                rows = self._row_count(victim)
                victim.unlink()
            if not self._evict_alerted:
                self._logger.error(
                    "evicted spool segment %s (%s rows); further evictions "
                    "will be suppressed until the spool empties",
                    victim,
                    rows,
                )
                self._evict_alerted = True

    def _oldest_evictable(self, segment_name: str) -> Path | None:
        candidates: list[Path] = []
        for name in self.tables():
            for path in self.segments(name):
                if path.name == segment_name:
                    continue
                candidates.append(path)
        if not candidates:
            return None
        candidates.sort(key=lambda path: path.name)
        return candidates[0]

    def _warn_if_old(self) -> None:
        if self._age_alerted:
            return
        oldest = self._oldest_segment()
        if oldest is None:
            return
        started = datetime.strptime(oldest.name[:11], "%Y%m%dT%H").replace(
            tzinfo=timezone.utc
        )
        if datetime.now(timezone.utc) - started <= timedelta(
            hours=self._warn_age_hours
        ):
            return
        self._age_alerted = True
        self._logger.warning(
            "oldest spool segment %s is older than %s hours",
            oldest.name,
            self._warn_age_hours,
        )

    def _oldest_segment(self) -> Path | None:
        found: list[Path] = []
        for table in self.tables():
            found.extend(self.segments(table))
        if not found:
            return None
        found.sort(key=lambda path: path.name)
        return found[0]

    def _free_pct(self) -> float:
        self._folder.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(self._folder)
        if usage.total == 0:
            return 100.0
        return 100.0 * usage.free / usage.total

    @staticmethod
    def _row_count(path: Path) -> int:
        with path.open(encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
