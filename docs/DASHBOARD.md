# Private dashboard

The dashboard implementation is ready for deployment. The HTTPS endpoint has
**not yet been published or verified** from this development session: GitHub
network access, local browser sockets and writable GCP credentials are unavailable.

Target: **https://dhan.34.100.255.111.sslip.io** on the existing
`sablestone-dhan-cas` VM in `asia-south1-a`, project
`project-cead8bae-10ea-4ea9-875`. Do not treat this target as a working dashboard
until the deployment command completes and login is verified.

## Publish and deploy

From this repository in a normal terminal with working GitHub and gcloud login:

```bash
./ops/deploy_dashboard.sh
```

This checks the existing VM/IP, pushes the committed `main` branch, transfers a
Git bundle, installs an isolated dashboard release, opens 80/443 for the targeted
VM, starts Caddy HTTPS and verifies that an unauthenticated public request returns
401 with a valid TLS certificate. It creates no new VM and never activates or
restarts the trading service. It refuses an unexpected IP, conflicting listener,
modified source or incompatible existing firewall rule.

The deployment requires sudo on the VM and permissions to manage its network
tags and firewall. DNS for the selected hostname must resolve to 34.100.255.111.
Caddy obtains/renews its certificate automatically. The IP-based DNS provider
remains an external dependency; no custom domain was purchased.

## Sign in

```bash
gcloud compute ssh sablestone-dhan-cas \
  --zone=asia-south1-a --project=project-cead8bae-10ea-4ea9-875 \
  --tunnel-through-iap
sudo cat /etc/sablestone-dhan-dashboard/login.txt
```

Open the target HTTPS URL and use `operator` with the separate generated password.
Retrieve the password privately in your SSH terminal; do not paste it into public
logs. Installation preserves it on later releases. There is no default password.
The server stores a SHA-256 verifier for a generated 256-bit random secret, not a
user-selected low-entropy password. All assets and account routes require login.

## What the page shows

- Available cash and P&L fields actually returned by the broker; missing is unknown.
- Freshness of the bot heartbeat and its reported entry authority.
- Last explicit Dhan/Upstox/metadata/IP/route connection checks and their dates.
- Open broker positions and recent broker orders.
- Persisted order intents, fills and incident timestamps from the bot's ledger.
- Copyable operator commands for preflight, activation and pausing new entries.

The page polls every five seconds. The account collector runs fifteen seconds
after its previous run completes (up to twenty seconds for a failed broker read).
Runtime snapshots older than fifteen seconds, account snapshots older than sixty
seconds and explicit connection checks older than fifteen minutes are marked
stale. Broker errors retain the previous observation with a failure indication.
An empty verified response and an unavailable response have different displays.

Connection checks are historical observations, not a continuously sampled socket
health claim. The last known Dhan depth check failed; this dashboard does not fix
or conceal that failure. Empty broker position lists do not prove zero lifetime
P&L. Recorded fill fees may omit later contract-note adjustments. There is no
invented equity curve and no claim that CAS_LAG_V1 is proven profitable.

## Isolation and operations

- Trader: `/opt/sablestone-dhan-cas-bot`, unchanged by dashboard installation.
- Dashboard: `/opt/sablestone-dhan-dashboard/releases/<commit>` and `current`.
- Collector: `sablestone` user, explicitly read-only broker adapter and OS read-only
  trader files, using the existing cached token. It never mints or rotates tokens.
- Web: separate `dhan-dashboard` user, no trader keys or ledger access, network
  limited to localhost. It reads only an allowlisted JSON projection.
- Caddy: separate user, automatic HTTPS, reverse proxy to `127.0.0.1:8088`.
- Snapshot: `/var/lib/sablestone-dhan-dashboard/snapshot.json` (0640).
- Credentials: `/etc/sablestone-dhan-dashboard/`, root-only plaintext login record.

There are no trading mutation endpoints. No provider response payloads, account
identifiers, tokens or raw incident text are exported. Existing trader startup,
verification, allocation, exit management and authority remain independent.

```bash
sudo systemctl status dhan-dashboard dhan-dashboard-collect.timer dhan-dashboard-caddy
sudo journalctl -u dhan-dashboard-collect -u dhan-dashboard -u dhan-dashboard-caddy -n 40
```

If the collector fails, inspect those logs locally. An expired cached token must
be fixed through the existing broker/session workflow, never by putting keys into
the web server. To roll back only the dashboard, point `current` to the prior
release printed by installation, then restart the three dashboard units. Do not
modify the trader checkout to install the dashboard.

## Operator-run real-money activation

The currently installed strategy is **NIFTY CAS_LAG_V1**. These commands enable
that implementation; they do not install a different research strategy. First,
on the VM:

```bash
sudo systemctl start dhan-cas-connections.service
sudo cat /var/lib/sablestone-dhan/connections.json
sudo /opt/sablestone-dhan-cas-bot/.venv/bin/python \
  /opt/sablestone-dhan-cas-bot/ops/activate-live.py --capital available --check-only
```

Resolve failed feeds and preflight checks. If source verification is outdated,
run the deployed bot's verification and inspect the result; do not bypass it.
Then the operator can enable real orders with:

```bash
sudo /opt/sablestone-dhan-cas-bot/.venv/bin/python \
  /opt/sablestone-dhan-cas-bot/ops/activate-live.py --capital available
```

This allocates available reusable cash and enables automatic orders, including
the existing bounded order-route probe. It preserves the standing sizing rules
and refuses to reset an existing trading ledger. Read a fresh status afterward:

```bash
sudo cat /var/lib/sablestone-dhan/status.json
```

To pause new entries while preserving exit/reconciliation handling:

```bash
sudo -u sablestone /opt/sablestone-dhan-cas-bot/.venv/bin/dhan-cas \
  disarm --config /etc/sablestone-dhan/production.toml --new-entries
```

Dashboard development and tests have not executed these activation commands.

## Validation

`python3 -m pytest tests/test_dashboard.py` passes 27 authentication, projection,
staleness, decimal, read-only ledger and read-only broker tests. The broker test
uses an HTTP mock and verifies GET-only calls; it is not live provider evidence.
The full suite reports 297 passed and 6 failed; all six failures require local
HTTP/WebSocket listeners which this sandbox denies. No full-suite verification
receipt was issued. JavaScript and shell syntax checks pass. Desktop/mobile browser rendering and
public TLS/login checks still require an unrestricted environment: Chromium
cannot launch and the browser bridge cannot be reached in this session.

Source references: [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https),
[Gunicorn 26.2.0](https://pypi.org/project/gunicorn/26.2.0/),
[IP-based DNS](https://sslip.io/).
