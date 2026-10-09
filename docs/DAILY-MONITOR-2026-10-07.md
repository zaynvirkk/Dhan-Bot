# Daily strategy deployment, 7 October 2026

Update, 9 October: the operator applied the session-strategy upgrade. All three
strategies loaded, but a launch-path mismatch blocked source verification.
See [the startup repair](SERVICE-LAUNCH-REPAIR-2026-10-09.md) for the cause and
corrective operator command. Dashboard deployment by itself does not change
the funded service.

This release adds an isolated live-data monitor for `GAP_FADE_DOUBLE` and
`NIFTY_SELLOFF_REBOUND_1510`. It uses the same pure rules as the session runtime,
without an OMS, order endpoint or access to the trading ledger. Minute inputs
refresh during the session; the exchange calendar refreshes hourly and contract
metadata daily. Out-of-hours prices are excluded from its session summary.
The dashboard labels each row as read-only monitoring or trading-service data;
its History stores those sources separately. Missing/stale input is unknown.

These remain experimental rules with losing validation paths. This deployment
is a software/data compatibility repair, not evidence of a profitable strategy.

## Live findings

On 7 October the Dhan data plan recovered to Active, valid through 8 November.
Same-token REST quotes returned eight of eight requested options with positive
prices and bid/ask books. Subsequent connection diagnostics passed Dhan options,
Upstox and the order socket. The account snapshot showed INR 8,822.36 and zero
open positions; the cause of the balance change was not investigated here.

Authenticated minute reads found two actual adapter incompatibilities:

- Dhan encodes integral timestamps, volume and OI as decimal-valued JSON numbers.
  The parser now accepts exact finite integral `Decimal` values, while rejecting
  fractional values, booleans, duplicates and nonfinite numbers.
- Upstox reports NSE cash closing at 15:30 and NFO closing at 15:40. NIFTY minute
  history supports the former boundary. The calendar now records both and uses
  the cash boundary for gap-fade's prior close. It never substitutes an arbitrary
  earlier price when the exact required minute is missing.

Chart reads overfetch one minute at the opening boundary and then restrict
accepted availability timestamps to the requested period and receipt time.
A late/out-of-session provider row cannot supply a session close or a signal.

References: [Dhan charts](https://dhanhq.co/docs/v2/historical-data/),
[Upstox session calendar](https://upstox.com/developer/api-documentation/get-market-timings/).

## Operator upgrade of the existing funded service

After this release is installed, run on the existing VM:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python \
  /opt/sablestone-dhan-dashboard/current/ops/upgrade-session-strategies.py
```

The default command checks the existing funded mandate, a fresh observer with
opening/prior-close data, account flatness and pending orders. It runs full
software verification, including production mutation tests. It does not change
service configuration or place orders.

The operator can apply the reviewed upgrade with:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python \
  /opt/sablestone-dhan-dashboard/current/ops/upgrade-session-strategies.py --apply
```

That explicit command stops the existing trader, locks its writer, rechecks the
flat account, adds the three strategy names to the existing configuration and
points systemd at this immutable release. It preserves the mandate, capital,
credentials and trading ledger. It updates the software-verification marker
from an actual passing run. Failure during installation restores the previous
configuration. The existing funded authority is retained, so this command can
cause subsequent automatic broker orders, including the configured route probe.
No signal/fill/profit is promised. The dashboard must subsequently report the
three strategies from the **trading service**, not just the read-only monitor.

The assistant does not execute `--apply`. Real-money execution is an operator
step; the isolated observer/dashboard deployment can be performed separately.

## Software verification

`.venv/bin/dhan-cas verify --state-dir /tmp/dhan-daily-verify-20261007`
passed 421 tests, including all 60 acceptance cases, and killed all 15 production
mutations. Covered-source digest:
`b9224124ecb6402c4d87662001a731aee668292cedde785a8f9739b929dd1e08`.
Browser lifecycle tests verify that an observer signal cannot enable trading
and that stale observer data becomes unknown. This is software evidence only.
