"""Refresh the commissioning daemon before market sessions; never restart a funded engine."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import sys

from .config import load_config, load_mandate
from .domain import ContractError


def refresh_read_only(config_path: str) -> None:
    config = load_config(config_path)
    mandate = load_mandate(Path(config["state_dir"]) / "mandate.json")
    if config["live_order_authority"] or mandate.live_order_authority:
        raise ContractError("scheduled commissioning restart refuses live authority")
    if os.environ.get("DHAN_ACCESS_TOKEN") or not all(os.environ.get(key) for key in ("DHAN_PIN", "DHAN_TOTP_SECRET")):
        raise ContractError("scheduled login refresh requires PIN/TOTP without a fixed access token")
    environment = subprocess.run(
        ["systemctl", "show", "dhan-cas.service", "--property=Environment", "--value"],
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout
    values = dict(item.split("=", 1) for item in shlex.split(environment) if "=" in item)
    if values.get("DHAN_BROKER_READ_ONLY") != "1":
        raise ContractError("scheduled commissioning restart requires the broker read-only interlock")
    subprocess.run(["systemctl", "restart", "dhan-cas.service"], check=True, timeout=45)
    print("Read-only daemon restarted for fresh PIN/TOTP authentication; orders remain disabled.")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ContractError("provide the production configuration path")
        refresh_read_only(sys.argv[1])
    except (ContractError, OSError, subprocess.SubprocessError) as exc:
        print(f"Session refresh failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
