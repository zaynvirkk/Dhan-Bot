from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from .domain import ContractError


def source_digest(root: str | Path) -> str:
    root = Path(root)
    digest = sha256()
    files = sorted([*root.glob("dhan_cas_bot/**/*.py"), *root.glob("tests/**/*.py"), *root.glob("ops/*"), *root.glob("schemas/*"), root / "pyproject.toml", root / "requirements.lock", root / "MANIFEST.json"])
    for path in files:
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def run_verification(root: str | Path, state_dir: str | Path) -> dict:
    """A marker follows a passing, skip-free execution, never a supplied count."""
    root, state_dir = Path(root).resolve(), Path(state_dir).resolve()
    (state_dir / "software_verified.json").unlink(missing_ok=True)
    before = source_digest(root)
    with tempfile.TemporaryDirectory(prefix="dhan-verify-") as temporary:
        report = Path(temporary) / "pytest.xml"
        process = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests", f"--junitxml={report}"],
            cwd=root, capture_output=True, text=True,
        )
        if process.returncode or not report.exists():
            raise ContractError("offline verification failed; run python -m pytest -q tests for details")
        cases = list(ET.parse(report).iter("testcase"))
        cp_cases = [case for case in cases if ".acceptance.cas." in case.get("classname", "")]
        if len(cp_cases) < 60 or any(list(case) for case in cases):
            raise ContractError("verification requires all 60 CP cases, with no skipped or failed tests")
        required={"test_connected_service_qualifies_route_freezes_reference_buys_and_exits","test_up_down_up_executes_real_buy_sell_lifecycles_and_compounds","test_accepted_lost_response_restart_reconciles_once_and_exits_without_signal","test_exercise_cash_remains_pending_until_exact_broker_receipt","test_waiting_oms_lock_rechecks_disarm_before_network"}
        if not required <= {case.get("name") for case in cases}:
            raise ContractError("connected production-path acceptance cases are missing")
    mutations=subprocess.run([sys.executable,str(root/"ops/verify-mutations.py")],cwd=root,capture_output=True,text=True)
    if mutations.returncode:
        raise ContractError("production guard mutation verification failed")
    if before != source_digest(root):
        raise ContractError("source changed during verification")
    return write_verification(root, state_dir, case_count=len(cp_cases), total_count=len(cases), mutations=json.loads(mutations.stdout)["mutations_killed"])


def write_verification(root: str | Path, state_dir: str | Path, *, case_count: int, total_count=None, mutations=None) -> dict:
    if case_count < 60:
        raise ContractError("verification marker requires all 60 CP cases")
    marker = {"source_digest": source_digest(root), "case_count": case_count, "total_count":total_count or case_count, "mutations_killed":mutations or [], "writes": False, "kind": "offline_acceptance"}
    path = Path(state_dir); path.mkdir(parents=True, exist_ok=True)
    (path / "software_verified.json").write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
    return marker


def current_verification(root: str | Path, state_dir: str | Path) -> bool:
    path = Path(state_dir) / "software_verified.json"
    if not path.exists():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return value.get("source_digest") == source_digest(root) and value.get("case_count", 0) >= 60 and value.get("writes") is False
