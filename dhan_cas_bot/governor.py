from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

from .domain import ContractError


@dataclass
class RateGovernor:
    """Persistent counters are written by the caller; this class handles windows."""

    limits: tuple[tuple[str, int, int], ...] = (("second", 10, 1), ("minute", 250, 60), ("hour", 1000, 3600), ("day", 7000, 86400))

    def __post_init__(self) -> None:
        self.events: deque[datetime] = deque()

    def admit(self, now: datetime, count: int = 1) -> None:
        if count <= 0:
            raise ContractError("rate count must be positive")
        horizon = max(seconds for _, _, seconds in self.limits)
        while self.events and (now - self.events[0]).total_seconds() >= horizon:
            self.events.popleft()
        for _, limit, seconds in self.limits:
            recent = sum((now - event).total_seconds() < seconds for event in self.events)
            if recent + count > limit:
                raise ContractError(f"Dhan rate bucket exhausted: {seconds}s")
        for _ in range(count):
            self.events.append(now)
