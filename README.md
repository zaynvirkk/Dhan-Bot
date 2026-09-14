# SableStone Dhan CAS bot

Dhan executes the orders and supplies five-level option depth, positions,
fills and cash. Upstox V3 supplies the official `NSE_INDEX|Nifty 50` CAS status
and IEP. The governing strategy is [CAS_LAG_V1](docs/BUILD-DEPLOY-PLAN.md).

The service runs one `AUTO_LIVE` state machine. It recovers broker state first,
loads current expiry/lot/tick/freeze data, qualifies the order route before CAS,
freezes the pre-auction reference and evaluates individual option lag. It sizes
to finite depth and the standing bankroll rule, manages partial fills, exits,
adds and fresh reversal/re-lag lifecycles. A SQLite FULL/WAL ledger commits
intent and reservation before each POST; ambiguous sends are reconciled, never
blindly retried. New-entry disarming leaves reduction and settlement recovery
available. PIN/TOTP tokens are cached privately and renewed before expiry.

Official dated final-index publications can authorize post-stop residual
entries. Missing timely final publication leaves that capability unavailable.
Unmatched expiry credits remain settlement receivables and cannot finance a
new lifecycle. No fixture establishes that a future opportunity, fill or
profit will occur.

## Installed Google Cloud service

The project, VM, permanent IP, protected configuration and commands are in
[the deployment guide](docs/CLOUD-DEPLOYMENT.md). The environment is already
configured. Deployment alone does not enable real-money orders.

The final operator-run activation command on the VM is:

```bash
sudo /opt/sablestone-dhan-cas-bot/.venv/bin/python \
  /opt/sablestone-dhan-cas-bot/ops/activate-live.py --capital available
```

`available` allocates the reusable cash reported by Dhan at activation; an
exact rupee amount can be supplied instead. The helper checks the account,
funds, static whitelist, source verification and credentials before changing
configuration. It refuses to reset an existing trading ledger. Add
`--check-only` to check prerequisites without activating. Activation enables
automatic real orders, including the bounded pre-CAS route probe.

Subsequent decisions use the frozen lifecycle bankroll: below ₹40,000, at
most min(bankroll, ₹10,000); otherwise 25%, including entry fees. Partial exits
do not replenish the lifecycle allowance. Reconciled gains can finance a new
lifecycle according to the mandate.

## Development verification

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps -e .
.venv/bin/python -m pytest -q
.venv/bin/dhan-cas verify --state-dir state
```

`verify` runs the complete suite, including a production service connected to
local HTTP/WebSocket brokers, then injects four execution defects into isolated
copies and requires the tests to reject them. Its source digest covers the
Python implementation, generated protobuf, schema, tests, dependencies and
operation scripts. This is software evidence, not a live broker-route receipt.

Secrets belong only in `.env` locally or `/etc/sablestone-dhan/secrets.env` on
the VM, never in Git. Dhan authentication uses PIN/TOTP to obtain the access
token required by its REST and WebSocket APIs; a manually supplied token is
supported for development but not unattended activation.
