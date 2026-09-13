# Google Cloud deployment

Repository: https://github.com/zaynvirkk/Dhan-Bot

Project: `project-cead8bae-10ea-4ea9-875`

Deployed VM: `sablestone-dhan-cas`, zone `asia-south1-a`, Ubuntu 24.04,
`e2-small`, 20 GB balanced disk. Network `dhan-cas-network`, subnet
`dhan-cas-mumbai`, reserved address `sablestone-dhan-cas-ip`.
The reserved public IPv4 is **34.100.255.111**. This is the address to register
as Dhan's Primary IP for this VM; registration has not been performed.
SSH is restricted to IAP (`35.235.240.0/20`). The VM has no attached cloud
service account. It makes outbound HTTPS/WebSocket connections.

Source is installed at `/opt/sablestone-dhan-cas-bot`; operator configuration
and secrets live at `/etc/sablestone-dhan` with directory mode 0750
(`root:sablestone`). The config is 0640; the secret file is root-only 0600
and systemd loads it before changing to the service user.
State lives at `/var/lib/sablestone-dhan`, owned by the `sablestone` service
user. Neither secrets nor live state are published to GitHub.

## Operation

```bash
gcloud compute ssh sablestone-dhan-cas --zone=asia-south1-a \
  --project=project-cead8bae-10ea-4ea9-875 --tunnel-through-iap
sudo systemctl start dhan-cas-connections.service
sudo journalctl -u dhan-cas-connections.service --no-pager -n 30
sudo cat /var/lib/sablestone-dhan/connections.json
```

The connection check uses existing credentials to authenticate, read account
state, subscribe to feeds and ping the order socket. It never places an order.
An order socket connection is not a successful OMS route proof. Missing IEP
outside CAS and absence of depth packets outside market hours remain unknown.

The `dhan-cas-connections.timer` runs the bounded check at 14:50 IST weekdays.
The `dhan-cas-session-refresh.timer` restarts the read-only daemon at 14:55 IST
weekdays so PIN/TOTP supplies a fresh session token and metadata before CAS.
It refuses to restart if either authority flag permits orders, the broker
read-only interlock is absent, or a fixed token replaces PIN/TOTP. This is
commissioning scheduling; funded in-process credential rotation remains open.
The `dhan-cas.service` daemon is enabled and running with
`DHAN_BROKER_READ_ONLY=1` at the broker boundary. Both configuration and mandate retain false live
authority; a template bankroll of zero is not a funded mandate.

## Release boundary

The earlier 79-test success did not establish complete production readiness.
Review found missing entry-budget/lifecycle integration, automatic exit
integration, route-proof races, and incomplete recovery/disarm enforcement.
The cloud deployment is for genuine provider commissioning, not approval to
arm this revision with money. These defects remain development work.
Also unresolved: funded in-process token renewal beyond the initial
24-hour token lifetime and explicit price-unit conversion for the native
Dhan instrument master's tick field (observed raw value `5.0000`). Do not use
that unqualified field to construct funded orders.

`dhan-cas verify` now executes the installed tests and requires successful,
skip-free CP cases before writing the source-bound offline marker. That marker
is a component-test receipt, not a broker, settlement or profitability proof.

No broker PIN, TOTP seed, token, account profile, wallet balance, or private
connection report belongs in a Git commit, startup metadata, or this document.

## Deployment evidence — 2026-09-13

Runtime revision `5c2b1ea` is installed on the VM. All 86 component tests pass
on the actual Ubuntu VM. The daemon reports `active/running` with zero
restarts; its systemd environment independently forces broker writes off.
The weekday connection timer is enabled. These observations are deployment
and component evidence, not completed Rev 4 strategy acceptance.

The separate connection check completed successfully at 12:58:22 UTC:
Dhan PIN/TOTP login and account reads passed, Upstox delivered two protobuf
frames including the NIFTY index, and both Dhan WebSockets connected. Egress
matched the reserved address. The market socket timed out waiting for usable
depth (`NO_DATA`, `book_verified=false`); no CAS status, IEP or order-route
event was observed. The report explicitly retains `trading_ready=false` and
`writes=false`. Starting the daemon and check simultaneously had caused an
authentication failure; the separately run check succeeded. Authentication
coordination remains part of the token lifecycle work above.

Recheck at 15:56 UTC reproduced successful authentication, account reads and
all three socket connections. Market depth and CAS indication remained
unobserved; broker IP registration was still unresolved. The daemon had
remained active with zero restarts since 12:54 UTC. The pre-session refresh
guard adds five regression cases, bringing the suite to 91 component tests.
Token-generation contract: [Dhan authentication documentation](https://dhanhq.co/docs/v2/authentication/).
