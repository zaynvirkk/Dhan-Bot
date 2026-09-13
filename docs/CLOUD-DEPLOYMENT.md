# Google Cloud deployment

Repository: https://github.com/zaynvirkk/Dhan-Bot

Project: `project-cead8bae-10ea-4ea9-875`

Target: `sablestone-dhan-cas`, zone `asia-south1-a`, Ubuntu 24.04,
`e2-small`, 20 GB balanced disk. Network `dhan-cas-network`, subnet
`dhan-cas-mumbai`, reserved address `sablestone-dhan-cas-ip`.
SSH is restricted to IAP (`35.235.240.0/20`). The VM has no attached cloud
service account. It makes outbound HTTPS/WebSocket connections.

Source is installed at `/opt/sablestone-dhan-cas-bot`; operator configuration
and secrets live at `/etc/sablestone-dhan` with directory mode 0700.
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
The trading unit is installed but disabled and has `DHAN_BROKER_READ_ONLY=1`
at the broker boundary. Both configuration and mandate retain false live
authority; a template bankroll of zero is not a funded mandate.

## Release boundary

The earlier 79-test success did not establish complete production readiness.
Review found missing entry-budget/lifecycle integration, automatic exit
integration, route-proof races, and incomplete recovery/disarm enforcement.
The cloud deployment is for genuine provider commissioning, not approval to
arm this revision with money. These defects remain development work.

`dhan-cas verify` now executes the installed tests and requires successful,
skip-free CP cases before writing the source-bound offline marker. That marker
is a component-test receipt, not a broker, settlement or profitability proof.

No broker PIN, TOTP seed, token, account profile, wallet balance, or private
connection report belongs in a Git commit, startup metadata, or this document.
