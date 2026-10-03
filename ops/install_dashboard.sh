#!/usr/bin/env bash
# Installs an isolated monitoring release. Never changes the trader or its authority.
set -euo pipefail
[[ $EUID = 0 ]] || { echo 'Run this installer with sudo on the existing VM.' >&2; exit 2; }
DASH_SHA=${1:?Pass the exact source commit}
DASH_HOST=${2:-dhan.34.100.255.111.sslip.io}
[[ $DASH_SHA =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ $DASH_HOST = dhan.34.100.255.111.sslip.io ]] || { echo 'Unexpected dashboard hostname.' >&2; exit 2; }
DASH_SOURCE=$(cd "$(dirname "$0")/.." && pwd -P)
[[ $(git -c safe.directory="$DASH_SOURCE" -C "$DASH_SOURCE" rev-parse HEAD) = "$DASH_SHA" ]] || exit 2
git -c safe.directory="$DASH_SOURCE" -C "$DASH_SOURCE" diff --quiet HEAD -- || { echo 'Source has tracked modifications.' >&2; exit 2; }
id sablestone >/dev/null
[[ -f /etc/sablestone-dhan/production.toml ]] || { echo 'Existing trader configuration missing.' >&2; exit 2; }
# Do not replace an unrelated web server or an existing Caddy installation.
if ! test -f /etc/sablestone-dhan-dashboard/Caddyfile; then
  if ss -H -ltn '( sport = :80 or sport = :443 or sport = :8088 )' | read -r _; then
    echo 'A web listener already occupies dashboard ports; nothing was changed.' >&2; exit 2
  fi
  if systemctl is-enabled --quiet caddy.service 2>/dev/null; then
    echo 'Existing Caddy service needs an explicit configuration merge.' >&2; exit 2
  fi
fi
python3 - "$DASH_HOST" <<'PY'
import socket,sys
ips={r[4][0] for r in socket.getaddrinfo(sys.argv[1], 443, type=socket.SOCK_STREAM)}
if ips != {'34.100.255.111'}: raise SystemExit('Dashboard DNS does not resolve exclusively to the expected VM')
PY
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv caddy nodejs
# The package may auto-start its default site. The dedicated dashboard unit owns HTTPS.
systemctl disable --now caddy.service
id dhan-dashboard >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin dhan-dashboard
install -d -m 0755 /opt/sablestone-dhan-dashboard/releases
DASH_RELEASE=/opt/sablestone-dhan-dashboard/releases/$DASH_SHA
if [[ ! -f "$DASH_RELEASE/.ready" ]]; then
  install -d -m 0755 "$DASH_RELEASE"
  git -c safe.directory="$DASH_SOURCE" -C "$DASH_SOURCE" archive "$DASH_SHA" | tar -x -C "$DASH_RELEASE"
  python3 -m venv "$DASH_RELEASE/.venv"
  "$DASH_RELEASE/.venv/bin/pip" install --disable-pip-version-check -q -r "$DASH_RELEASE/requirements-dashboard.lock"
  "$DASH_RELEASE/.venv/bin/pip" install --disable-pip-version-check -q --no-deps "$DASH_RELEASE"
  (cd "$DASH_RELEASE" && .venv/bin/python -m pytest tests/test_dashboard.py tests/test_dashboard_streaming.py)
  touch "$DASH_RELEASE/.ready"
fi
install -d -m 0755 -o root -g root /etc/sablestone-dhan-dashboard
install -d -m 2750 -o sablestone -g dhan-dashboard /var/lib/sablestone-dhan-dashboard
# Generate once. Neither plaintext nor its hash is written to the release or logs.
python3 - <<'PY'
import grp,hashlib,json,os,secrets
from pathlib import Path
root=Path('/etc/sablestone-dhan-dashboard'); auth=root/'auth.json'; login=root/'login.txt'
if not auth.exists():
    token=secrets.token_urlsafe(32)
    with os.fdopen(os.open(login,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
        f.write('URL: https://dhan.34.100.255.111.sslip.io\nUsername: operator\nPassword: '+token+'\n')
    with os.fdopen(os.open(auth,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640),'w') as f:
        os.fchmod(f.fileno(),0o640)
        f.write(json.dumps({'username':'operator','password_sha256':hashlib.sha256(token.encode()).hexdigest()}))
    os.chown(auth,0,grp.getgrnam('dhan-dashboard').gr_gid)
if not login.is_file(): raise SystemExit('Dashboard login record missing; investigate instead of rotating automatically')
if auth.stat().st_mode & 0o007 or login.stat().st_mode & 0o077:
    raise SystemExit('Dashboard credential permissions are too broad')
PY
cat > /etc/sablestone-dhan-dashboard/Caddyfile <<'CADDY'
{
    admin off
}
dhan.34.100.255.111.sslip.io {
    header Strict-Transport-Security "max-age=31536000"
    request_body {
        max_size 1KB
    }
    reverse_proxy 127.0.0.1:8088
}
CADDY
chmod 0644 /etc/sablestone-dhan-dashboard/Caddyfile
/usr/bin/caddy validate --config /etc/sablestone-dhan-dashboard/Caddyfile --adapter caddyfile
for unit in dhan-dashboard.service dhan-dashboard-collect.service dhan-dashboard-collect.timer dhan-dashboard-caddy.service; do
  install -m 0644 "$DASH_RELEASE/ops/$unit" "/etc/systemd/system/$unit"
done
# Check credentials before switching the web release. Broker secrets are never loaded.
sudo -u dhan-dashboard "$DASH_RELEASE/.venv/bin/python" -c 'from dhan_cas_bot.dashboard.app import create_app; create_app()'
DASH_PREVIOUS=$(readlink /opt/sablestone-dhan-dashboard/current || true)
ln -s "$DASH_RELEASE" /opt/sablestone-dhan-dashboard/current.next
mv -Tf /opt/sablestone-dhan-dashboard/current.next /opt/sablestone-dhan-dashboard/current
systemctl daemon-reload
systemctl disable --now dhan-dashboard-collect.timer
systemctl enable dhan-dashboard.service dhan-dashboard-collect.service dhan-dashboard-caddy.service
systemctl restart dhan-dashboard.service
# Record a projection even if the cached broker token has expired.
systemctl restart dhan-dashboard-collect.service
systemctl restart dhan-dashboard-caddy.service
python3 - <<'PY'
import base64,json,time,urllib.error,urllib.request
from pathlib import Path
password=next(line.split('Password: ',1)[1] for line in Path('/etc/sablestone-dhan-dashboard/login.txt').read_text().splitlines() if line.startswith('Password: '))
for attempt in range(10):
    try:
        urllib.request.urlopen('http://127.0.0.1:8088/api/status',timeout=2)
    except urllib.error.HTTPError as e:
        if e.code != 401: raise
        break
    except urllib.error.URLError:
        if attempt==9: raise
        time.sleep(1)
    else: raise SystemExit('Dashboard must require authentication')
headers={'Authorization':'Basic '+base64.b64encode(('operator:'+password).encode()).decode()}
for attempt in range(15):
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8088/api/status',headers=headers),timeout=5) as response:
            snapshot=json.load(response)
        if snapshot.get('collector', {}).get('fresh'): break
    except (urllib.error.HTTPError, urllib.error.URLError):
        pass
    if attempt == 14: raise SystemExit('Dashboard collector did not publish a fresh snapshot')
    time.sleep(1)
assert snapshot['available'] and snapshot['writes_to_broker'] is False
print('Authenticated local status verified; broker account current:',snapshot['account_read_ok'])
PY
printf 'Dashboard release installed: %s\nPrevious dashboard release: %s\n' "$DASH_SHA" "${DASH_PREVIOUS:-none}"
echo 'Public TLS/authentication still require external verification. No trader service or authority was changed.'
echo 'Retrieve the separate dashboard login privately: sudo cat /etc/sablestone-dhan-dashboard/login.txt'
