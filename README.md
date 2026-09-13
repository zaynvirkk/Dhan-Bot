# SableStone Dhan CAS Bot

Current release: cloud commissioning, trading disabled. See
[deployment and operating status](docs/CLOUD-DEPLOYMENT.md).
The retained CP tests verify individual components; they do not certify the
full Rev 4 trading lifecycle. Full automatic exits, lifecycle-wide capital
enforcement, recovery/arming behavior and live final-settlement qualification
still require integration work before real-money activation.

This is the new Dhan execution service specified by the governing Rev 4
contract at [`docs/BUILD-DEPLOY-PLAN.md`](docs/BUILD-DEPLOY-PLAN.md).
The folder is intentionally independent of the old Edge Lab implementation.

The bot owns Dhan instrument selection, five-level option books, MARGIN
LIMIT-IOC orders, order updates, fills, positions, funds and settlement
reconciliation. Upstox V3 is used only for the official NIFTY CAS state and
IEP signal named by the strategy contract. The Dhan future is optional
telemetry and never an entry gate.

The service is safe by default. Configuration starts with `AUTO_LIVE` disabled,
real network writes disabled, and a local simulator available for verification.
No credential, live feed, broker order, account change or deployment is needed
to run the test suite.

## Commissioning the one remaining operator-controlled layer

The repository never contains broker secrets. Copy `.env.example` to `.env`,
set `UPSTOX_ANALYTICS_TOKEN` and either `DHAN_ACCESS_TOKEN` or `DHAN_PIN` plus
`DHAN_TOTP_SECRET`, and keep the file mode `0600`. TOTP is used only once at
startup to mint Dhan's 24-hour access token; all Dhan REST/WebSocket calls use
that token. Copy `production.example.toml` to `production.toml` and fill in the
Dhan account ID and the permanent public IP already whitelisted at Dhan. The
service constructs the documented Dhan market/order socket URLs when their
fields are left empty. Upstox authorization is performed for each socket
connection so reconnects do not reuse its one-use redirect URL.

Run the non-writing gate before arming:

```bash
cp .env.example .env && chmod 600 .env
cp production.example.toml production.toml
.venv/bin/dhan-cas verify --state-dir state
ops/preflight.sh
```

`preflight` checks configuration presence only; it does not prove authentication
or trading readiness. `check-connections` performs bounded, write-disabled
broker and feed checks. Keep live authority false in this commissioning
release. The intended funded release must prove a bounded one-lot route probe
and its matching order-update event before permitting strategy entries.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m dhan_cas_bot selftest
.venv/bin/python -m dhan_cas_bot verify --state-dir state
```

The production command surface is:

```bash
dhan-cas configure --config production.toml --mandate mandate.json
dhan-cas enable --config production.toml
dhan-cas run --mode AUTO_LIVE --config production.toml
dhan-cas status --config production.toml --json
dhan-cas disarm --config production.toml --new-entries
dhan-cas reconcile --config production.toml --through-settlement
```

`run` refuses to write unless explicit live authority, current broker account
facts, a valid standing mandate and a verified Dhan route are all present.
It also requires the digest-bound `software_verified.json` marker produced by
the local acceptance run; editing configuration or restarting cannot create
that marker.
Offline configuration and tests cannot grant that authority.
