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
