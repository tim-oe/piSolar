"""Tests for SpoolStore."""

import shutil
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from pisolar.config.spool_config import SpoolConfig
from pisolar.services.spool.spool_store import SpoolCapacityError, SpoolStore


def _usage(free: int):
    return type("Usage", (), {"total": 100, "used": 100 - free, "free": free})()


@pytest.fixture
def store(tmp_path):
    config = SpoolConfig(enabled=True, folder=str(tmp_path / "spool"))
    spool = SpoolStore(config)
    spool._evict_alerted = False
    spool._age_alerted = False
    return spool


class TestSpoolStore:
    def test_hourly_rotation(self, store):
        with patch.object(
            store,
            "_segment_name",
            side_effect=["20260101T01.jsonl", "20260101T02.jsonl"],
        ):
            store.append("solar_reading", '{"n": 1}')
            store.append("solar_reading", '{"n": 2}')
        names = [path.name for path in store.segments("solar_reading")]
        assert names == ["20260101T01.jsonl", "20260101T02.jsonl"]

    def test_draining_adopted_and_appends_use_new_file(self, store):
        store.append("solar_reading", "seed")
        claimed = store.claim_oldest("solar_reading")
        assert claimed is not None
        assert claimed.name.endswith(".draining")
        assert store.claim_oldest("solar_reading") == claimed
        store.append("solar_reading", "fresh")
        assert "seed" in claimed.read_text(encoding="utf-8")
        assert "fresh" not in claimed.read_text(encoding="utf-8")
        restored = store.release(claimed)
        assert restored.name.endswith(".jsonl")
        assert "seed" in restored.read_text(encoding="utf-8")
        assert "fresh" in restored.read_text(encoding="utf-8")

    def test_concurrent_appends_not_lost_across_claim(self, store):
        store.append("solar_reading", "seed")
        per_thread = 25

        def writer(index: int) -> None:
            for row in range(per_thread):
                store.append("solar_reading", f"row-{index}-{row}")

        threads = [threading.Thread(target=writer, args=(index,)) for index in range(4)]
        for thread in threads:
            thread.start()
        claimed = store.claim_oldest("solar_reading")
        for thread in threads:
            thread.join()
        lines: list[str] = []
        if claimed is not None and claimed.exists():
            lines.extend(claimed.read_text(encoding="utf-8").splitlines())
        for path in store.segments("solar_reading"):
            lines.extend(path.read_text(encoding="utf-8").splitlines())
        assert len([line for line in lines if line.strip()]) == 1 + 4 * per_thread

    def test_eviction_drops_oldest_spares_active_and_draining(self, store):
        alpha = store.folder / "alpha"
        beta = store.folder / "beta"
        alpha.mkdir(exist_ok=True)
        beta.mkdir(exist_ok=True)
        active_name = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(
            "%Y%m%dT%H"
        ) + ".jsonl"
        (alpha / "20200101T00.jsonl").write_text("old\n", encoding="utf-8")
        (beta / "20200101T01.jsonl.draining").write_text("drain\n", encoding="utf-8")
        (beta / "20200101T02.jsonl").write_text("next\n", encoding="utf-8")
        (alpha / active_name).write_text("active\n", encoding="utf-8")
        with (
            patch.object(store, "_segment_name", return_value=active_name),
            patch(
                "pisolar.services.spool.spool_store.shutil.disk_usage",
                side_effect=[_usage(5), _usage(5), _usage(90), _usage(90)],
            ),
        ):
            store.append("alpha", "incoming")
        assert not (alpha / "20200101T00.jsonl").exists()
        assert not (beta / "20200101T02.jsonl").exists()
        assert (beta / "20200101T01.jsonl.draining").exists()
        active = (alpha / active_name).read_text(encoding="utf-8")
        assert "active" in active
        assert "incoming" in active

    def test_append_fails_when_floor_cannot_be_preserved(self, store):
        active_name = "20260101T01.jsonl"
        alpha = store.folder / "alpha"
        alpha.mkdir(exist_ok=True)
        active = alpha / active_name
        active.write_text("current\n", encoding="utf-8")
        with (
            patch.object(store, "_segment_name", return_value=active_name),
            patch(
                "pisolar.services.spool.spool_store.shutil.disk_usage",
                return_value=_usage(5),
            ),
        ):
            with pytest.raises(SpoolCapacityError):
                store.append("alpha", "incoming")
        assert active.read_text(encoding="utf-8") == "current\n"

    def test_eviction_error_logs_once_until_empty(self, store):
        alpha = store.folder / "alpha"
        alpha.mkdir(exist_ok=True)
        (alpha / "20200101T00.jsonl").write_text("old\n", encoding="utf-8")
        (alpha / "20200101T01.jsonl").write_text("next\n", encoding="utf-8")
        with (
            patch.object(store, "_segment_name", return_value="20260101T01.jsonl"),
            patch(
                "pisolar.services.spool.spool_store.shutil.disk_usage",
                side_effect=[_usage(5), _usage(5), _usage(90), _usage(90)],
            ),
            patch.object(store._logger, "error") as mock_error,
        ):
            store.append("alpha", "incoming")
        mock_error.assert_called_once()

    def test_age_warning_latches_until_empty(self, store):
        alpha = store.folder / "alpha"
        alpha.mkdir(exist_ok=True)
        (alpha / "20200101T00.jsonl").write_text("old\n", encoding="utf-8")
        with (
            patch(
                "pisolar.services.spool.spool_store.shutil.disk_usage",
                return_value=_usage(90),
            ),
            patch.object(store._logger, "warning") as mock_warning,
        ):
            store.append("alpha", "a")
            store.append("alpha", "b")
            assert mock_warning.call_count == 1
            shutil.rmtree(alpha)
            store.reset_alerts_if_empty()
            alpha.mkdir()
            (alpha / "20200101T00.jsonl").write_text("old\n", encoding="utf-8")
            store.append("alpha", "c")
            assert mock_warning.call_count == 2
