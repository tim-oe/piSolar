"""Thread-safe MySQL availability state for write spooling."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone


class DbState:
    """Tracks offline retry window after connection-class errors."""

    def __init__(self, offline_retry_seconds: int = 60) -> None:
        self._offline_retry_seconds = offline_retry_seconds
        self._lock = threading.Lock()
        self._offline_until: datetime | None = None

    def is_offline(self) -> bool:
        """True while inside the offline retry window."""
        with self._lock:
            if self._offline_until is None:
                return False
            until = self._offline_until
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < until

    def mark_offline(self) -> bool:
        """Start or extend the offline window. Returns True on first entry."""
        with self._lock:
            now = datetime.now(timezone.utc)
            already = self._offline_until is not None and now < self._offline_until
            self._offline_until = now + timedelta(seconds=self._offline_retry_seconds)
            return not already

    def mark_online(self) -> bool:
        """Clear the offline window. Returns True on offline-to-online transition."""
        with self._lock:
            if self._offline_until is None:
                return False
            self._offline_until = None
            return True
