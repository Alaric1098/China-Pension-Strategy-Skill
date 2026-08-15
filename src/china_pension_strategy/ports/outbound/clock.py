"""Outbound clock boundary for deterministic time injection."""

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """Boundary for sources of the current time."""

    def now_utc(self) -> datetime:
        """Return the current instant as a timezone-aware UTC datetime."""


class SystemClock:
    """Wall clock that reads the current time from the operating system."""

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)
