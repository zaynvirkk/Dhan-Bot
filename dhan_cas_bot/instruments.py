from __future__ import annotations

from csv import DictReader
from datetime import date, datetime
from decimal import Decimal
from io import TextIOBase
from typing import Iterable

from .domain import ContractError, Instrument, OptionType, RuleSnapshot, Segment


def is_nifty_option(row: dict) -> bool:
    native = row.get("EXCH_ID") == "NSE" and row.get("SEGMENT") == "D"
    normalized = row.get("SEGMENT") == "NSE_FNO"
    return (native or normalized) and row.get("INSTRUMENT") == "OPTIDX" and str(row.get("UNDERLYING_SYMBOL", "")).upper() == "NIFTY"


def integer_field(value: str) -> int:
    exact = Decimal(value)
    if not exact.is_finite() or exact != exact.to_integral_value():
        raise ContractError("instrument quantity must be a finite integer")
    return int(exact)


def parse_date(value: str) -> date:
    value = value.strip().split()[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    raise ContractError(f"unsupported date: {value}")


def load_dhan_master(stream: TextIOBase, *, expiry: date, freeze_by_security: dict[str, int] | None = None) -> list[Instrument]:
    required = {"SEGMENT", "SECURITY_ID", "INSTRUMENT", "UNDERLYING_SYMBOL", "SM_EXPIRY_DATE", "OPTION_TYPE", "STRIKE_PRICE", "LOT_SIZE", "TICK_SIZE"}
    result: list[Instrument] = []
    for row in DictReader(stream):
        if not required <= set(row):
            raise ContractError("Dhan master missing required columns")
        if not is_nifty_option(row):
            continue
        option = row["OPTION_TYPE"].upper()
        if option not in {"CE", "PE"} or parse_date(row["SM_EXPIRY_DATE"]) != expiry:
            continue
        security_id = row["SECURITY_ID"].strip()
        exchange_freeze = int((freeze_by_security or {}).get(security_id, (freeze_by_security or {}).get("__NIFTY__", 0)))
        dhan_freeze = integer_field(row.get("SM_FREEZE_QTY") or "0")
        freeze = min(x for x in (exchange_freeze, dhan_freeze) if x > 0) if exchange_freeze > 0 and dhan_freeze > 0 else max(exchange_freeze, dhan_freeze)
        if freeze <= 0:
            raise ContractError(f"missing current freeze for {security_id}")
        result.append(Instrument(security_id, "NIFTY", Segment.NSE_FNO, expiry, OptionType(option), Decimal(row["STRIKE_PRICE"]), integer_field(row["LOT_SIZE"]), Decimal(row["TICK_SIZE"]), freeze, Decimal(row["SM_LOWER_LIMIT"]) if row.get("SM_LOWER_LIMIT") else None, Decimal(row["SM_UPPER_LIMIT"]) if row.get("SM_UPPER_LIMIT") else None))
    if not result:
        raise ContractError("no current NIFTY options resolved")
    return result


def rule_snapshot(source: str, raw_bytes: bytes, retrieved_at: datetime, effective_from: date, *, lot_size: int, tick_size: Decimal, freeze_qty: int) -> RuleSnapshot:
    import hashlib
    return RuleSnapshot(source, hashlib.sha256(raw_bytes).hexdigest(), retrieved_at, effective_from, None, lot_size, tick_size, freeze_qty)
