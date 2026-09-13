#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo 'Run with sudo on the dedicated Ubuntu VM.' >&2
  exit 2
fi
SOURCE_ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
[[ "$SOURCE_ROOT" = /opt/sablestone-dhan-cas-bot ]] || { echo 'Install the source at /opt/sablestone-dhan-cas-bot first.' >&2; exit 2; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv git chrony
id sablestone >/dev/null 2>&1 || useradd --system --home /var/lib/sablestone-dhan --shell /usr/sbin/nologin sablestone
install -d -m 0700 -o sablestone -g sablestone /var/lib/sablestone-dhan
install -d -m 0750 -o root -g sablestone /etc/sablestone-dhan
python3 -m venv "$SOURCE_ROOT/.venv"
"$SOURCE_ROOT/.venv/bin/pip" install --disable-pip-version-check -q -r "$SOURCE_ROOT/requirements.lock"
"$SOURCE_ROOT/.venv/bin/pip" install --disable-pip-version-check -q --no-deps -e "$SOURCE_ROOT"
install -m 0644 "$SOURCE_ROOT/ops/dhan-cas.service" /etc/systemd/system/dhan-cas.service
install -m 0644 "$SOURCE_ROOT/ops/dhan-cas-connections.service" /etc/systemd/system/dhan-cas-connections.service
install -m 0644 "$SOURCE_ROOT/ops/dhan-cas-connections.timer" /etc/systemd/system/dhan-cas-connections.timer
systemctl daemon-reload
systemctl enable --now chrony
echo 'Installed. Trading is disabled; configure secrets before starting connection checks.'
