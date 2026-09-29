"""Discover index-option families from a dated detailed Dhan master.

This is inventory, not an execution allowlist. Account permissions, current
quotes, expiry, cash, freeze limits and (for MCX) multipliers remain separate.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TextIO

from .domain import ContractError
from .instruments import integer_field, parse_date


def index_catalog(stream: TextIO, *, as_of: date) -> list[dict]:
    reader = csv.DictReader(stream)
    required = {"EXCH_ID", "SEGMENT", "SECURITY_ID", "INSTRUMENT", "UNDERLYING_SYMBOL",
                "SM_EXPIRY_DATE", "LOT_SIZE", "OPTION_TYPE", "TICK_SIZE"}
    if not required <= set(reader.fieldnames or []):
        raise ContractError("detailed master columns missing")
    groups: dict[tuple[str, str], dict] = {}
    index_ids: dict[tuple[str, str], set[str]] = {}
    seen: set[tuple[str, str]] = set()
    for row in reader:
        exchange, segment = row["EXCH_ID"], row["SEGMENT"]
        symbol = row["UNDERLYING_SYMBOL"].strip().upper()
        if row["INSTRUMENT"] == "INDEX" and segment == "I":
            index_ids.setdefault((exchange, symbol), set()).add(row["SECURITY_ID"])
        if row["INSTRUMENT"] != "OPTIDX":
            continue
        if (exchange, segment) not in {("NSE", "D"), ("BSE", "D"), ("MCX", "M")}:
            raise ContractError("unsupported index-option segment")
        if not symbol or not row["SECURITY_ID"].isdigit():
            raise ContractError("invalid index-option identity")
        try:
            expiry = parse_date(row["SM_EXPIRY_DATE"])
            lot = integer_field(row["LOT_SIZE"])
            tick_raw = Decimal(row["TICK_SIZE"])
        except (ValueError, InvalidOperation, IndexError) as exc:
            raise ContractError("invalid index-option metadata") from exc
        if lot <= 0 or not tick_raw.is_finite() or tick_raw <= 0 or row["OPTION_TYPE"] not in {"CE", "PE"}:
            raise ContractError("invalid index-option specification")
        if expiry < as_of:
            continue
        identity = (exchange, row["SECURITY_ID"])
        if identity in seen:
            raise ContractError("duplicate index-option identity")
        seen.add(identity)
        g = groups.setdefault((exchange, symbol), {
            "exchange": exchange, "symbol": symbol,
            "exchange_segment": {"NSE": "NSE_FNO", "BSE": "BSE_FNO", "MCX": "MCX_COMM"}[exchange],
            "contracts": 0, "expiries": {}, "derivative_underlying_ids": set(),
            "buy_sell_indicators": set(), "option_types": set(),
        })
        g["contracts"] += 1
        g["expiries"].setdefault(expiry.isoformat(), set()).add(lot)
        # Preserve the raw field; it is not automatically a valid IDX_I ID.
        if row.get("UNDERLYING_SECURITY_ID"):
            g["derivative_underlying_ids"].add(row["UNDERLYING_SECURITY_ID"])
        g["buy_sell_indicators"].add(row.get("BUY_SELL_INDICATOR") or "UNKNOWN")
        g["option_types"].add(row["OPTION_TYPE"])
    if not groups:
        raise ContractError("no unexpired index options in master")
    out = []
    for (exchange, symbol), g in sorted(groups.items()):
        # Explicit alias from the master, never a fuzzy match (SENSEX is not
        # SENSEX50; NIFTY is not NIFTYFPI).
        index_symbol = "SNSX50" if (exchange, symbol) == ("BSE", "SENSEX50") else symbol
        ids = sorted(index_ids.get((exchange, index_symbol), set()))
        g["index_quote_security_id"] = ids[0] if len(ids) == 1 else None
        g["index_quote_mapping"] = "RESOLVED_FROM_INDEX_ROW" if len(ids) == 1 else "UNKNOWN"
        g["expiries"] = {k: sorted(v) for k, v in sorted(g["expiries"].items())}
        for field in ("derivative_underlying_ids", "buy_sell_indicators", "option_types"):
            g[field] = sorted(g[field])
        g["live_tradability"] = "UNVERIFIED"
        out.append(g)
    return out
