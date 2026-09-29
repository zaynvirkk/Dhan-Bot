#!/usr/bin/env python3
"""Replay fatal execution defects against isolated copies of production source."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
CASES=(
    ("intent_before_post", "orders.py", 'self.ledger.record_attempt(attempt_id, intent.intent_id, "STARTED", {})', 'pass  # injected: no durable send attempt', "tests/test_production_lifecycles.py::test_up_down_up_executes_real_buy_sell_lifecycles_and_compounds"),
    ("pending_snapshot", "engine.py", 'if snapshot["unresolved"] or totals["unresolved"] or ledger.pending_intents():', 'if snapshot["unresolved"]:', "tests/test_release_boundaries.py::test_stale_flat_snapshot_cannot_close_a_just_sent_intent"),
    ("dispatch_disarm", "orders.py", 'if pre_dispatch is not None and not pre_dispatch():', 'if False:', "tests/test_release_boundaries.py::test_waiting_oms_lock_rechecks_disarm_before_network"),
    ("readonly_boundary", "broker.py", 'if not self.allow_writes:', 'if False:', "tests/test_cloud_runtime.py::test_vm_readonly_boundary_blocks_even_authorized_broker"),
    ("market_reconnect_persistence", "engine.py", 'self.books.clear()\n        self.streaks.clear()', 'self.books.clear()', "tests/test_strategy_audit.py::test_market_only_reconnect_requires_two_new_contract_observations"),
    ("interrupted_lag", "engine.py", 'self.streaks.pop(inst.security_id, None)', 'pass', "tests/test_strategy_audit.py::test_book_loses_then_regains_lag_without_new_index_events"),
    ("funds_exit_isolation", "runtime.py", 'self.status.reason = "ACCOUNT_FUNDS_UNAVAILABLE:"+type(exc).__name__', 'raise', "tests/test_strategy_audit.py::test_cash_endpoint_failure_blocks_buys_but_not_exit_management"),
    ("freeze_exit_reserve", "orders.py", 'child_size = intent.instrument.freeze_qty // intent.instrument.lot_size * intent.instrument.lot_size', 'child_size = intent.instrument.freeze_qty', "tests/test_strategy_audit.py::test_rate_reserve_uses_lot_rounded_freeze_children"),
    ("expired_order_guard", "engine.py", 'if expired and totals["quantity"]:', 'if False:', "tests/test_strategy_audit.py::test_expiry_close_does_not_send_orders_for_still_reported_expired_position"),
    ("snapshot_reference", "feeds.py", 'self.snapshot_epoch = self.protocol.epoch.id\n            return False', 'self.snapshot_epoch = self.protocol.epoch.id\n            return frame.type == 1', "tests/test_connected_service.py::test_connected_service_snapshot_cannot_supply_fifth_reference_observation"),
    ("fee_rounding_reserve", "risk.py", 'return value.quantize(quantum, rounding=ROUND_CEILING) + (children-1)*quantum', 'return value', "tests/test_strategy_audit.py::test_cash_reservation_covers_published_rates_and_tax_rounding"),
    ("fill_identity_scope", "ledger.py", 'identity = json.dumps([fill.order_id, fill.trade_id], separators=(",", ":"))', 'identity = fill.trade_id', "tests/test_strategy_audit.py::test_fill_identity_is_scoped_to_broker_order"),
    ("order_writer_noop", "broker.py", 'return await self._request("POST", "/orders", json=request)', 'return {"orderId":"no-op", "orderStatus":"PENDING"}', "tests/test_connected_service.py::test_connected_service_qualifies_route_freezes_reference_buys_and_exits"),
    ("entry_gate_never_opens", "runtime.py", 'return bool(self.mandate.live_order_authority', 'return bool(False and self.mandate.live_order_authority', "tests/test_production_lifecycles.py::test_up_down_up_executes_real_buy_sell_lifecycles_and_compounds"),
    ("recovery_rotation", "service.py", 'if not ledger.order_lock.locked():', 'if runtime.status.state != "RECOVERING" and not ledger.order_lock.locked():', "tests/test_connected_service.py::test_reconciliation_outage_does_not_prevent_token_rotation_with_exposure"),
)


def main():
    killed=[]
    for name,source,before,after,test in CASES:
        with tempfile.TemporaryDirectory(prefix="dhan-mutation-") as directory:
            root=Path(directory)
            shutil.copytree(ROOT/"dhan_cas_bot",root/"dhan_cas_bot",ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT/"tests",root/"tests",ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copyfile(ROOT/"pyproject.toml",root/"pyproject.toml")
            path=root/"dhan_cas_bot"/source
            content=path.read_text()
            if content.count(before)!=1: raise RuntimeError("mutation anchor drift: "+name)
            path.write_text(content.replace(before,after))
            env={**os.environ,"PYTHONPATH":str(root)}
            result=subprocess.run([sys.executable,"-m","pytest","-q",test,"--junitxml=case.xml"],cwd=root,env=env,capture_output=True,text=True,timeout=30)
            report=root/"case.xml"
            cases=list(ET.parse(report).iter("testcase")) if report.exists() else []
            # A collection/import error is not evidence that an oracle caught
            # the altered behavior. Require a failed, actually executed case.
            if result.returncode!=1 or len(cases)!=1 or cases[0].find("failure") is None:
                raise RuntimeError("mutation survived or did not execute: "+name+"\n"+result.stdout[-3000:])
            killed.append(name)
    print(json.dumps({"mutations_killed":killed,"writes_to_brokers":False}))


if __name__=="__main__": main()
