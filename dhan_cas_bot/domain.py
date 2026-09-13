from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping
import hashlib
import json
import math


class ContractError(ValueError):
    """A malformed or unsafe contract value."""


def dec(value: Any, field_name: str, *, allow_negative: bool = False) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ContractError(f"{field_name} must be an exact decimal string/integer")
    if not isinstance(value, (str, int, Decimal)):
        raise ContractError(f"{field_name} must be an exact decimal string/integer")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ContractError(f"{field_name} is not decimal") from exc
    if not result.is_finite():
        raise ContractError(f"{field_name} must be finite")
    if not allow_negative and result < 0:
        raise ContractError(f"{field_name} cannot be negative")
    return result


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def digest(value: Any) -> str:
    raw = json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


class Segment(str, Enum):
    NSE_FNO = "NSE_FNO"
    NSE_INDEX = "NSE_INDEX"


class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"


class CasPhase(str, Enum):
    CTS_CLOSE = "CTS_CLOSE"
    CAS_LM_START = "CAS_LM_START"
    CAS_M_STOP = "CAS_M_STOP"
    CAS_STOP = "CAS_STOP"
    UNKNOWN = "UNKNOWN"


class LifecycleState(str, Enum):
    FLAT = "FLAT"
    ENTRY_PENDING = "ENTRY_PENDING"
    POSITION_OPEN = "POSITION_OPEN"
    EXIT_PENDING = "EXIT_PENDING"
    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
    SETTLED = "SETTLED"
    SEND_UNKNOWN = "SEND_UNKNOWN"


@dataclass(frozen=True)
class Instrument:
    security_id: str
    underlying: str
    segment: Segment
    expiry: date
    option_type: OptionType
    strike: Decimal
    lot_size: int
    tick_size: Decimal
    freeze_qty: int
    lower_limit: Decimal | None = None
    upper_limit: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.security_id or self.segment is not Segment.NSE_FNO or self.underlying.upper() != "NIFTY":
            raise ContractError("instrument is not an NSE NIFTY option")
        if self.lot_size <= 0 or self.freeze_qty < self.lot_size:
            raise ContractError("freeze quantity must permit at least one lot")
        if self.tick_size <= 0 or self.strike < 0:
            raise ContractError("invalid instrument price metadata")

    def tick(self, price: Decimal) -> int:
        quotient = price / self.tick_size
        if quotient != quotient.to_integral_value():
            raise ContractError(f"price {price} is not tick aligned")
        return int(quotient)


@dataclass(frozen=True)
class Level:
    price: Decimal
    quantity: int

    def __post_init__(self) -> None:
        if self.price <= 0 or self.quantity < 0:
            raise ContractError("invalid book level")


@dataclass(frozen=True)
class OptionBook:
    instrument: Instrument
    bids: tuple[Level, ...]
    asks: tuple[Level, ...]
    epoch: str
    received_ns: int
    provider_ts_ms: int | None = None

    def __post_init__(self) -> None:
        if len(self.bids) > 5 or len(self.asks) > 5:
            raise ContractError("Dhan Full book must have at most five levels")
        if not self.epoch or self.received_ns <= 0:
            raise ContractError("book identity is required")

    @property
    def top_bid(self) -> Level | None:
        return next((x for x in self.bids if x.quantity > 0), None)

    @property
    def top_ask(self) -> Level | None:
        return next((x for x in self.asks if x.quantity > 0), None)


@dataclass(frozen=True)
class IndexObservation:
    value: Decimal
    provider_ts_ms: int
    received_ns: int
    epoch: str
    receiver_seq: int
    frame_kind: str = "live_feed"
    raw_identity: str = ""
    wrapper_present: bool = True

    def __post_init__(self) -> None:
        if self.value <= 0 or self.provider_ts_ms < 0 or self.received_ns <= 0 or self.receiver_seq < 0:
            raise ContractError("invalid index observation")
        if self.frame_kind != "live_feed" or not self.wrapper_present:
            raise ContractError("reference observations require a live IEP/LTP frame")


@dataclass(frozen=True)
class CasStatus:
    phase: CasPhase
    updated_time_ms: int
    trading_date: date
    epoch: str


@dataclass(frozen=True)
class RuleSnapshot:
    source: str
    raw_digest: str
    retrieved_at: datetime
    effective_from: date
    effective_until: date | None
    lot_size: int
    tick_size: Decimal
    freeze_qty: int
    broker_entry_cutoff: datetime | None = None
    product: str = "NSE_FNO:MARGIN"


@dataclass(frozen=True)
class Mandate:
    account_id: str
    strategy_id: str = "CAS_LAG_V1"
    allocated_capital: Decimal = Decimal("0")
    cumulative_entry_debit_cap: Decimal | None = None
    debit_cap_scope: str = "none"
    reinvest_realized_profit: bool = True
    equity_ceiling: Decimal | None = None
    probe_max_attempts_per_session: int = 1
    probe_entry_debit_cap_per_session: Decimal = Decimal("0")
    probe_spending_cap_per_mandate: Decimal = Decimal("0")
    live_order_authority: bool = False
    valid_until: datetime | None = None

    def validate(self) -> None:
        if not self.account_id or self.strategy_id != "CAS_LAG_V1":
            raise ContractError("invalid mandate identity")
        if self.allocated_capital < 0:
            raise ContractError("allocated capital cannot be negative")
        if self.cumulative_entry_debit_cap is not None and self.cumulative_entry_debit_cap < 0:
            raise ContractError("entry debit cap cannot be negative")
        if self.debit_cap_scope not in {"none", "session", "mandate"}:
            raise ContractError("invalid debit cap scope")
        if self.cumulative_entry_debit_cap is None and self.debit_cap_scope != "none":
            raise ContractError("null debit cap requires scope none")
        if self.cumulative_entry_debit_cap is not None and self.debit_cap_scope == "none":
            raise ContractError("finite debit cap requires session or mandate scope")
        if self.probe_max_attempts_per_session <= 0:
            raise ContractError("probe attempts must be positive")
        if self.probe_entry_debit_cap_per_session <= 0 or self.probe_spending_cap_per_mandate <= 0:
            raise ContractError("probe budgets must be finite and positive")
        if self.equity_ceiling is not None and self.equity_ceiling <= 0:
            raise ContractError("equity ceiling must be positive")


@dataclass(frozen=True)
class FundsSnapshot:
    observed_at: datetime
    spendable_cash: Decimal
    strategy_equity: Decimal
    withdrawable_cash: Decimal
    collateral: Decimal
    broker_account: str

    def __post_init__(self) -> None:
        for value in (self.spendable_cash, self.strategy_equity, self.withdrawable_cash, self.collateral):
            if not value.is_finite():
                raise ContractError("funds must be finite")


@dataclass(frozen=True)
class Fill:
    trade_id: str
    order_id: str
    security_id: str
    quantity: int
    price: Decimal
    fees: Decimal
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not self.trade_id or not self.order_id or self.quantity <= 0 or self.price <= 0 or self.fees < 0:
            raise ContractError("invalid fill")


@dataclass(frozen=True)
class Intent:
    intent_id: str
    side: str
    instrument: Instrument
    quantity: int
    limit_price: Decimal
    client_order_id: str
    created_at: datetime
    lifecycle_id: str
    order_kind: str = "IOC"

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"} or self.quantity <= 0:
            raise ContractError("invalid intent")
        if self.limit_price <= 0 or self.order_kind != "IOC":
            raise ContractError("only positive LIMIT IOC intents are supported")
        if self.quantity % self.instrument.lot_size:
            raise ContractError("intent quantity must be whole lots")
