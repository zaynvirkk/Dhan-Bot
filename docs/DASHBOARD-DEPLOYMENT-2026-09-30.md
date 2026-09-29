# Private dashboard deployment — 30 September 2026

Live URL: **https://dhan.34.100.255.111.sslip.io**

Dashboard runtime commit: `e6751410a8b6739a2a543c9d6576cd786a1f09e1`.
Existing trader runtime remains `884178a01bd4c0a5ab211273fc921fa2c52d5c3a`.
Documentation updates after this runtime release do not alter its deployed code.

The operator selected the VM-based hostname and authorized publishing to GitHub
and the existing GCP VM. After network/filesystem access was restored, the
committed dashboard was pushed to `zaynvirkk/Dhan-Bot` main and installed on
`sablestone-dhan-cas`, `asia-south1-a`, project
`project-cead8bae-10ea-4ea9-875`, public IP `34.100.255.111`.

## Verified deployment behavior

- Separate dashboard release directory and virtual environment, Gunicorn on
  localhost:8088 and Caddy on public 80/443; no new VM.
- Dedicated dashboard user cannot read the broker's secret directory or state.
  Collector can read trader files and cached token, but broker writes are disabled.
- Firewall permits only TCP 80/443 under the dashboard's VM target tag. Repeat
  deployment accepts equivalent grouped/split GCP port records and rejects broader
  ports or a different network/target/source scope.
- Public HTTPS validates its certificate and returns 401 before login for HTML,
  API and static assets. Authenticated account/API reads succeed.
- A separate generated dashboard password is stored in the VM's private login
  file; later installation preserved it. No broker credentials were published.
- Dashboard, HTTPS proxy, collector timer and existing trader services are active.
  The trader checkout was not updated or restarted by dashboard installation.

## Fresh observations

The 30 September 02:57 IST read-only connection report passed all seven checks:
Dhan authentication/F&O permission, account, static egress/whitelist, contract
metadata, Upstox index feed, Dhan options depth and order-update socket. The Dhan
feed returned 50 decoded FULL depth packets. The earlier depth failure did not
recur in this check. This is a dated provider observation, not a perpetual-health
or executable-order claim. The order route remains unverified by a funded order.

Authenticated browser/account checks around 03:01 IST showed available cash
**INR 9,411.18**, zero open positions, zero broker orders and zero persisted order
intents/fills. Runtime reported `NO_TRADE_DAY`, `writes=false`,
`auto_live_armed=false`, 472 loaded contracts and 1ms clock uncertainty. These
are observed values; later dashboard values may change.

## Validation

The current local suite passes **313 tests**. The dashboard's **37 tests** also
pass against its installed release. Browser verification against the real HTTPS
site passed at 1440px desktop and 390px mobile with no JavaScript errors:

- authentication on HTML/API/assets;
- live account/authority rendering;
- order tabs, keyboard navigation and status filter;
- expandable activation instructions;
- no mobile document overflow;
- simulated browser fetch failure changes authority to unknown and removes green
  health badges while preserving historical observations.

Desktop and mobile screenshots were visually inspected. The browser failure
simulation affected only the test browser and did not change any live service.
Private logs, allowlisted snapshots, screenshots and browser assertions are kept
under `artifacts/private/dashboard-20260930/`, excluded from Git.

No real-money activation, order-route probe or trading order was performed.
The deployed strategy remains CAS_LAG_V1; this receipt establishes monitoring and
connectivity, not profitability. [Login and operator activation instructions](DASHBOARD.md)
are included both in the repository and in the dashboard's Activation guide.
