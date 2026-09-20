from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self.at = at.astimezone(UTC)

    def now(self) -> datetime:
        return self.at

    def advance_to(self, at: datetime) -> None:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self.at = at.astimezone(UTC)
