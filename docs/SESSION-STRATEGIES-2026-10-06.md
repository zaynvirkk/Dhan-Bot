# Session strategy integration — 6 October 2026

This change implements the two earlier research candidates alongside CAS. It
does not establish an edge, change existing funded authority, or establish that
the VM runs these bytes. The gap-fade and rebound research both have losing
validation paths; their original reports remain unchanged.

## Strategies and eligibility

| Engine | Entry evaluation | Calendar and contract selection |
|---|---|---|
| `GAP_FADE_DOUBLE` | Every five minutes, 09:45–11:30 IST; gap at least 0.5%, 25–100% filled, three persistent closes and matching five-minute futures direction | Ordinary **non-expiry** NIFTY sessions, preserving the research scope; nearest actual expiry |
| `NIFTY_SELLOFF_REBOUND_1510` | At 15:10 IST, completed spot close at least 0.75% below the opening price; CE only | Contract expiry strictly beyond the next exchange session; exit deadline next session at 15:10 |
| `CAS_LAG_V1` | Existing official auction phase, reference, persistence, price and execution rules | Same-day expiry found in Dhan contract metadata; no weekday inference |

These clock windows are part of the hypotheses. Removing them would create new
strategies. Eligibility is checked every session, including holidays and shifted
expiries; NIFTY is not assumed to expire every day. A successful empty calendar
response means closed; a failed request means unknown.

Upstox's [date-specific market timings](https://upstox.com/developer/api-documentation/get-market-timings/)
provide the NFO session and previous/next sessions. The adapter checks intervening
dates rather than adding a weekday. Calendar responses refresh hourly and must
belong to the current date. Special opening sessions are excluded from gap-fade.
If the prior NIFTY closing minute is absent at the expected boundary, gap-fade
stays unknown; it does not substitute an earlier partial-session close. Real
calendar/spot closing-boundary alignment still needs provider verification.

[Dhan minute charts](https://dhanhq.co/docs/v2/historical-data/) supply spot,
futures and selected option bars. Incomplete bars, mismatched columns, duplicate
timestamps and invalid quantities are rejected. The worker refreshes completed
bars once a minute; option books and order updates keep using WebSockets. No
minute candle is represented as a tick or an exact fill. The adapter has been
tested against fixtures, not authenticated live provider responses in this run.

## Shared execution and recovery

- One account, one open lifecycle, one OMS and the existing capital ceiling.
  There is no independent bankroll for each enabled engine.
- Each lifecycle records its owning strategy and exit deadline. An old lifecycle
  with no strategy field remains CAS. CAS cannot manage a directional position.
- A new directional signal may select ATM through three OTM strikes, using only
  completed bars. Whole lots must fit the 95% cash budget, existing allocation
  limits, entry fees and a three-slice exit-fee reserve. Quantity is limited by
  depth, freeze quantity and 5% of the lowest volume of three completed minutes;
  OI must cover ten lots. Entry quotes must be at most two seconds old and the
  spread at most 8% of midpoint.
- Entry is a fixed LIMIT IOC at the known option close plus 5%, rounded up to the
  tick. Submission waits until one minute after the signal boundary and expires
  30 seconds later. A submitted or unfilled attempt is consumed across restart;
  it does not hop to another strike after a missed limit. Slower input retrieval
  can miss the trade. This is an explicit bounded runtime admission window.
- A completed close at 2x or 0.5x actual average entry latches an exit for one
  minute later. Gap-fade also exits six minutes before the calendar close;
  rebound exits the following exchange session at 15:10. Closure, restart,
  disarming and a temporarily missing book cannot erase the latched exit.
  Exits require an open session and current bid; wide spread alone does not
  block reduction. An expired remaining position requires broker clearing;
  neither a fill nor settlement cash is invented.
- Account reconciliation, current-source verification, route proof, clock,
  disk, operator authority and final pre-dispatch checks remain in force.
  Directional engines do not manufacture the official CAS signal flag.
- The route-probe window follows the configured engine: morning for gap-fade,
  15:05–15:10 for rebound, and the existing expiry afternoon window for CAS.
  The existing finite probe allowances still apply across those windows.

## Configuration and rollout status

Absent `strategies`, an existing installation continues with **CAS only**.
The additional explicit configuration is:

```toml
strategies = ["GAP_FADE_DOUBLE", "NIFTY_SELLOFF_REBOUND_1510", "CAS_LAG_V1"]
```

This line does not grant order authority. Existing live authority, mandate,
balances and private configuration were not read or changed by this work.
The first-activation helper is not an upgrade/migration command and must not
reset an existing trading history. Its older printed probe description describes
the CAS-only setup; the runtime strategy board is authoritative for configuration.

Dashboard rows report configured engines, completed input values, check time,
no-signal/waiting/unknown/disabled distinctions and actual expiry eligibility.
History includes those sampled checks. Last-entry records identify the owning
engine; there are no fabricated confidence scores or historical trades.

Run the exact full verification before a source rollout:

```bash
.venv/bin/dhan-cas verify --state-dir /tmp/dhan-strategies-verify
```

This environment cannot bind localhost sockets. Full verification failed on
seven transport/service socket tests; no new verification marker was written.
The focused production, fixture-transport, calendar, strategy, observer and UI
suite passed **117 tests**, including the expired-position guard. Exact receipts
are reported in the portfolio worklog.

GitHub publishing and VM deployment are separate. The GitHub app is available;
shell DNS is blocked. Google Cloud/VM access and authenticated market-data reads
have not been verified here. Before an operator starts the updated service,
the full socket suite and real read-only calendar/minute/contract checks must
pass on the intended host. This document is not a deployment or trading receipt.
