#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.lock"
"$ROOT/.venv/bin/pip" install -e "$ROOT"
"$ROOT/.venv/bin/python" -m dhan_cas_bot selftest
echo "Installed software only. Configure a mandate and broker credentials before enabling service."
