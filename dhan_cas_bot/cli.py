from __future__ import annotations

import argparse
import asyncio
import json
import os
import httpx
from pathlib import Path
import tempfile
from decimal import Decimal
from datetime import datetime, timezone

from .config import load_config, load_mandate, write_examples
from .domain import ContractError
from .ledger import Ledger
from .risk import lifecycle_ceiling, worst_case_entry_cash
from .release import run_verification, current_verification


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dhan-cas")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")
    verify = sub.add_parser("verify")
    verify.add_argument("--state-dir", default="state")
    for name in ("configure", "enable", "preflight", "check-connections", "run", "status", "disarm", "reconcile"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", default="production.toml")
        if name in {"configure"}:
            cmd.add_argument("--mandate", required=True)
        if name == "run": cmd.add_argument("--mode", default="AUTO_LIVE")
        if name == "status": cmd.add_argument("--json", action="store_true")
        if name == "disarm": cmd.add_argument("--new-entries", action="store_true")
        if name == "reconcile": cmd.add_argument("--through-settlement", action="store_true")
    return p


def selftest() -> dict:
    assert lifecycle_ceiling(Decimal("9411.18")) == Decimal("9411.18")
    assert lifecycle_ceiling(Decimal("40000")) == Decimal("10000.00")
    assert worst_case_entry_cash(845, Decimal("11"), 1) > 0
    return {"software_verified": True, "writes": False, "live": False}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "selftest":
            print(json.dumps(selftest(), sort_keys=True))
            return 0
        if args.command == "verify":
            print(json.dumps(run_verification(Path(__file__).resolve().parents[1], args.state_dir), sort_keys=True))
            return 0
        config = load_config(args.config)
        project_root = Path(__file__).resolve().parents[1]
        if args.command == "check-connections":
            from .commissioning import check_connections
            report = asyncio.run(check_connections(config))
            print(json.dumps(report, sort_keys=True))
            return 0 if report["connected"] else 2
        if args.command == "configure":
            mandate = load_mandate(args.mandate)
            if mandate.account_id != config["account_id"]:
                raise ContractError("config and mandate account differ")
            path = Path(config["state_dir"]); path.mkdir(parents=True, exist_ok=True)
            Ledger(path / "ledger.sqlite3").put_mandate(mandate)
            (path / "mandate.json").write_text(Path(args.mandate).read_text(encoding="utf-8"), encoding="utf-8")
            print(json.dumps({"configured": True, "live_order_authority": mandate.live_order_authority}))
            return 0
        if args.command == "status":
            status_path = Path(config["state_dir"]) / "status.json"
            value = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {"state": "UNINITIALIZED", "software_verified": False, "live_order_authority": config["live_order_authority"], "writes": False}
            print(json.dumps(value, sort_keys=True) if args.json else value)
            return 0
        if args.command == "enable":
            if not config["live_order_authority"]:
                print(json.dumps({"enabled": False, "reason": "live_order_authority=false"}))
                return 0
            state = Path(config["state_dir"])
            if not (state / "mandate.json").exists():
                raise ContractError("cannot enable: configure a standing mandate first")
            mandate = load_mandate(state / "mandate.json")
            if mandate.account_id != config["account_id"] or not mandate.live_order_authority or mandate.allocated_capital <= 0:
                raise ContractError("cannot enable: funded, authorized mandate for this account required")
            if os.environ.get("DHAN_BROKER_READ_ONLY", "").lower() in {"1", "true"}:
                raise ContractError("cannot enable: process has DHAN_BROKER_READ_ONLY interlock")
            if not current_verification(project_root, state):
                raise ContractError("cannot enable: current source has no valid offline verification marker")
            if not config.get("expected_egress_ip"):
                raise ContractError("cannot enable: expected_egress_ip must be the Dhan-whitelisted address")
            state.mkdir(parents=True, exist_ok=True)
            ledger = Ledger(state / "ledger.sqlite3")
            try:
                ledger.put_metadata("disarmed", False)
                ledger.put_metadata("operator_enabled_at", datetime.now(timezone.utc).isoformat())
            finally:
                ledger.close()
            # The running service owns observed status. Enabling cannot invent
            # an observed route proof, live feed, or a running daemon.
            print(json.dumps({"enabled": True, "mode": "AUTO_LIVE", "route_verified": False, "service_start_required": True}))
            return 0
        if args.command == "preflight":
            state = Path(config["state_dir"])
            checks = {
                "mandate": (state / "mandate.json").exists(),
                "software_verified": current_verification(project_root, state),
                "expected_egress_ip": bool(config.get("expected_egress_ip")),
                "dhan_auth": bool(os.environ.get("DHAN_ACCESS_TOKEN")) or bool(os.environ.get("DHAN_PIN") and os.environ.get("DHAN_TOTP_SECRET")),
                "upstox_analytics_token": bool(os.environ.get("UPSTOX_ANALYTICS_TOKEN")),
            }
            print(json.dumps({"ready": all(checks.values()), "writes": False, "checks": checks}, sort_keys=True))
            return 0 if all(checks.values()) else 2
        if args.command == "disarm":
            Path(config["state_dir"]).mkdir(parents=True, exist_ok=True)
            ledger = Ledger(Path(config["state_dir"]) / "ledger.sqlite3")
            try: ledger.put_metadata("disarmed", True)
            finally: ledger.close()
            print(json.dumps({"disarmed": True, "new_entries": False, "exit_management_preserved": True}))
            return 0
        if args.command == "reconcile":
            from .auth import session_token
            from .broker import DhanBroker
            async def inspect_account():
                token = await session_token(config, Path(config["state_dir"]))
                broker = DhanBroker(config["account_id"], token, config["dhan_api_base"], allow_writes=False)
                try:
                    orders, trades, positions, funds = await asyncio.gather(broker.orders(), broker.trades(), broker.positions(), broker.funds())
                    ledger = Ledger(Path(config["state_dir"]) / "ledger.sqlite3")
                    try:
                        ledger.put_metadata("reconcile_requested", True)
                        pending = len(ledger.pending_intents())
                        unsettled = ledger.db.execute("SELECT COUNT(*) FROM lifecycles WHERE state!='CLOSED'").fetchone()[0]
                    finally: ledger.close()
                    return {"broker_snapshot_read": True, "account_matches": funds.broker_account == config["account_id"], "orders": len(orders), "trades": len(trades), "open_positions": sum(bool(int(p.get("netQty",p.get("netQuantity",0)))) for p in positions), "pending_intents": pending, "unclosed_lifecycles": unsettled, "service_reconciliation_requested": True, "settlement_complete": not pending and not unsettled, "writes": False}
                finally: await broker.close()
            result = asyncio.run(inspect_account())
            print(json.dumps(result, sort_keys=True))
            return 0 if result["settlement_complete"] else 2
        if args.command == "run":
            if args.mode != "AUTO_LIVE": raise ContractError("only AUTO_LIVE is supported")
            asyncio.run(__import__("dhan_cas_bot.service", fromlist=["run_service"]).run_service(args.config))
            return 0
        print(json.dumps({"command": args.command, "status": "reconciliation requires configured broker credentials"}))
        return 0
    except httpx.HTTPError as exc:
        print(json.dumps({"error": "provider_request_failed", "error_type": type(exc).__name__}))
        return 2
    except (OSError, ValueError, ContractError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
