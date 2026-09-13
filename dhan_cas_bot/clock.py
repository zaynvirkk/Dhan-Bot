from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time

from .domain import ContractError


@dataclass(frozen=True)
class Clock:
    utc: datetime
    monotonic_ns: int
    uncertainty_ms: int


def sample_clock(uncertainty_ms: int) -> Clock:
    if uncertainty_ms < 0:
        raise ContractError("clock uncertainty cannot be negative")
    return Clock(datetime.now(timezone.utc), time.monotonic_ns(), uncertainty_ms)


def require_reference_clock(uncertainty_ms: int) -> None:
    if uncertainty_ms > 100:
        raise ContractError("clock uncertainty exceeds CAS_LAG_V1 100ms bound")
