# Private dashboard

The 30 September dashboard release is deployed. The 1 October streaming
optimizations described below are implemented locally and are **not deployed**.
Live behavior was last verified on 30 September 2026.
See the [deployment verification](DASHBOARD-DEPLOYMENT-2026-09-30.md) and
[browser access fix](DASHBOARD-ACCESS-2026-09-30.md).

URL: **https://dhan.34.100.255.111.sslip.io** on the existing
`sablestone-dhan-cas` VM in `asia-south1-a`, project
`project-cead8bae-10ea-4ea9-875`. HTTPS certificate validation, mandatory login,
authenticated data and desktop/mobile behavior have been verified.

## Publish and deploy

From this repository in a normal terminal with working GitHub and gcloud login:

```bash
./ops/deploy_dashboard.sh
```

This checks the existing VM/IP, pushes the committed `main` branch, transfers a
Git bundle, installs an isolated dashboard release, opens 80/443 for the targeted
VM, starts Caddy HTTPS and verifies that an unauthenticated account API request
returns 401 with a valid TLS certificate. It creates no new VM and never activates or
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
user-selected low-entropy password. The sign-in page and its stylesheet are public;
account data and dashboard assets require authentication. Browser sign-in uses an
8-hour signed, Secure, HttpOnly, SameSite=Strict cookie. Login and logout accept
only same-origin form submissions. Password rotation invalidates existing sessions.
Signing out clears this browser’s cookie and leaves the trading service running.
Explicit Basic headers still work for monitoring scripts, but the server never
sends a browser HTTP-authentication challenge: a VPN extension answering every
challenge caused Brave to fail with ERR_TOO_MANY_RETRIES.

## What the page shows

- Available cash and P&L fields actually returned by the broker; missing is unknown.
- Freshness of the bot heartbeat and its reported entry authority.
- Last explicit Dhan/Upstox/metadata/IP/route connection checks and their dates.
- Open broker positions and recent broker orders.
- Persisted order intents, fills and incident timestamps from the bot's ledger.
- Copyable operator commands for preflight, activation and pausing new entries.

The updated page receives authenticated server-sent events once a second,
with a five-second polling fallback if the stream stops. Hidden tabs disconnect;
visible tabs reconnect and fetch a current snapshot. A finite 20-second stream
renews authentication, emits an expiry event when a cookie expires, and leaves
worker capacity for normal requests. Observation ages are recalculated each time.
A delayed failed poll cannot overwrite a newer pushed observation.

The collector is now a persistent, separately supervised service. It projects
local status each second and reads the trader's sanitized
`account-observation.json`, retaining the actual observation timestamp. It checks
the broker independently every five minutes when shared observations exist.
That check cannot stall local publication. With an older trader that does not
publish shared observations, the collector falls back to independent broker
reads fifteen seconds after completion. The installer disables the old timer.

Runtime snapshots older than forty-five seconds, account snapshots older than
sixty seconds and explicit connection checks older than fifteen minutes are
marked stale. These dashboard thresholds describe observation age; they are
not execution guards. Broker errors retain earlier values with a failure label.
Missing observations remain different from verified empty responses.

The Timing and entry checks disclosure shows rolling p95 timings, sample counts,
and the current process's decision-evaluation counters. These are operational
measurements, not win rates or evidence that rejected candidates were profitable.
See [streaming implementation and validation](STREAMING-OPTIMIZATIONS-2026-10-04.md).

Connection checks are historical observations, not a continuously sampled socket
health claim. The 30 September 02:57 IST checks passed all seven connections,
including 50 decoded Dhan depth packets. The order-update socket was connected;
no funded order-route execution was performed. Empty broker position lists do not prove zero lifetime
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
sudo systemctl status dhan-dashboard dhan-dashboard-collect dhan-dashboard-caddy
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

## Historical validation of the deployed 30 September release

`python3 -m pytest tests/test_dashboard.py` passes 50 authentication, projection,
staleness, decimal, read-only ledger/broker and firewall-scope tests. The complete
suite passed 326 tests with networking available during this access fix. The final
installed dashboard release passed all 50 dashboard tests. JavaScript/shell syntax and packaged assets are verified.

The real HTTPS site was tested in Chromium at 1440px desktop and 390px mobile:
mandatory authentication, account data, tabs, keyboard navigation, filtering,
activation-guide disclosure and mobile overflow checks passed with no JavaScript
errors. A browser-only failed-fetch fixture correctly marked data historical and
removed health badges. Desktop/mobile screenshots were inspected. The collector
uses genuine read-only account calls; the negative fixture never alters the broker.

The first deployment exposed a timing mismatch between the collector cadence and
heartbeat expiry. The heartbeat threshold is now 45 seconds, tested across the
normal 35-second collection interval and expired at 46 seconds. Repeat deployment
also validates equivalent GCP representations of TCP 80/443 without widening the
allowed ports, network, sources or VM target tag.

Source references: [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https),
[Gunicorn 26.2.0](https://pypi.org/project/gunicorn/26.2.0/),
[IP-based DNS](https://sslip.io/).

For the pending streaming release, see [publication and operator update steps](RELEASE-2026-10-04.md).
