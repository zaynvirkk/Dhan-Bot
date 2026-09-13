#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
exec "$ROOT/.venv/bin/dhan-cas" preflight --config "${CONFIG_PATH:-$ROOT/production.toml}"
