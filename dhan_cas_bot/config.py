from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import tomllib

from .domain import ContractError, Mandate, dec


def load_config(path: str | Path) -> dict:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    required = {"state_dir", "live_order_authority", "account_id", "dhan_api_base", "expected_egress_ip"}
    if not required <= raw.keys():
        raise ContractError("configuration must explicitly define state_dir, authority, account and egress")
    if type(raw["live_order_authority"]) is not bool:
        raise ContractError("live_order_authority must be boolean")
    if not raw["account_id"]:
        raise ContractError("account_id is required")
    return raw


def load_mandate(path: str | Path) -> Mandate:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"account_id", "allocated_capital", "cumulative_entry_debit_cap", "debit_cap_scope", "reinvest_realized_profit", "probe_max_attempts_per_session", "probe_entry_debit_cap_per_session", "probe_spending_cap_per_mandate", "live_order_authority"}
    if set(data) != required:
        raise ContractError("mandate fields must be explicit")
    if any(type(data[field]) is not bool for field in ("live_order_authority", "reinvest_realized_profit")):
        raise ContractError("mandate authority and reinvestment must be booleans")
    if type(data["probe_max_attempts_per_session"]) is not int:
        raise ContractError("probe attempt allowance must be an integer")
    cap = data["cumulative_entry_debit_cap"]
    mandate = Mandate(data["account_id"], allocated_capital=dec(data["allocated_capital"], "allocated_capital"), cumulative_entry_debit_cap=None if cap is None else dec(cap, "cumulative_entry_debit_cap"), debit_cap_scope=data["debit_cap_scope"], reinvest_realized_profit=bool(data["reinvest_realized_profit"]), probe_max_attempts_per_session=int(data["probe_max_attempts_per_session"]), probe_entry_debit_cap_per_session=dec(data["probe_entry_debit_cap_per_session"], "probe_entry_debit_cap_per_session"), probe_spending_cap_per_mandate=dec(data["probe_spending_cap_per_mandate"], "probe_spending_cap_per_mandate"), live_order_authority=bool(data["live_order_authority"]))
    mandate.validate()
    return mandate


def write_examples(root: Path) -> None:
    (root / "production.example.toml").write_text("""state_dir = \"state\"\nlive_order_authority = false\naccount_id = \"REQUIRED\"\ndhan_api_base = \"https://api.dhan.co/v2\"\ndhan_auth_url = \"https://auth.dhan.co/app/generateAccessToken\"\nexpected_egress_ip = \"\"\nupstox_authorize_url = \"https://api.upstox.com/v3/feed/market-data-feed/authorize\"\ndhan_market_ws_url = \"\"\ndhan_order_ws_url = \"\"\n""", encoding="utf-8")
    (root / "mandate.example.json").write_text(json.dumps({"account_id":"REQUIRED","allocated_capital":"0","cumulative_entry_debit_cap":None,"debit_cap_scope":"none","reinvest_realized_profit":True,"probe_max_attempts_per_session":1,"probe_entry_debit_cap_per_session":"100.00","probe_spending_cap_per_mandate":"500.00","live_order_authority":False}, indent=2)+"\n", encoding="utf-8")
