"""Injected clock service. Tests override via dependency."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Returns an aware UTC datetime."""

    def today(self) -> date:
        """Returns the date in UTC."""

    def sleep(self, seconds: float) -> None:
        """Sleeps the given number of seconds (for jobs only; tests stub)."""


class SystemClock:
    """Production clock. All datetimes are returned in UTC."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)

    def today(self) -> date:
        return self.now().date()

    def sleep(self, seconds: float) -> None:
        import time

        time.sleep(seconds)


class FakeClock:
    """Test clock with explicit setters. Always UTC."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2025, 1, 1, tzinfo=UTC)

    def set(self, when: datetime) -> None:
        self._now = when.astimezone(UTC)

    def advance(self, seconds: float = 0, minutes: float = 0, hours: float = 0, days: float = 0) -> None:
        from datetime import timedelta

        delta = timedelta(
            seconds=seconds, minutes=minutes, hours=hours, days=days
        )
        self._now = self._now + delta

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def sleep(self, seconds: float) -> None:
        # No real sleeping in tests; advance the clock instead so jobs see the future.
        self.advance(seconds=seconds)
