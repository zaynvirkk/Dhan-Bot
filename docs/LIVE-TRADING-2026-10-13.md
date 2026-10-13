# Live auction execution and feed-status correction

## Observed transition

At 15:20 IST on 13 October, authenticated current status reports enabled
real-money authority, verified broker route and current Dhan option books.
Both Upstox and Dhan frames are arriving, but the accepted strategy-input
timestamp remains at the provider's CTS_CLOSE reference boundary, 15:15.
The phase is CTS_CLOSE and no official indicative index value is accepted yet.
The dashboard incorrectly treats this as a general live-market-data outage.

The funded service is PID 338550, active with zero restarts. Its source remains
197c4f8. Only GAP_FADE_DOUBLE, NIFTY_SELLOFF_REBOUND_1510 and CAS_LAG_V1 are
implemented and configured. Their time/session eligibility is part of each
experimental strategy, not a service startup schedule. Other named research
hypotheses are not deployed engines. This presentation repair does not change
entry rules or convert time-specific hypotheses into all-session strategies.

## Real broker fills

The provider subsequently enters CAS_LM_START and disseminates an official
indicative index value. At 15:22 IST the broker reports filled BUY and SELL
orders, including NIFTY October 22,850 CE, quantity 3,510 on each side, as well
as further 22,700 CE executions. The displayed order limits are not substituted
for execution prices. Persisted individual fills are actual recorded executions;
their count includes partial fills and is not a count of completed bets.

| Observation (IST) | Available cash | Open positions | Dhan realised P&L | Dhan unrealised P&L | Recorded fills |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12:16 | INR 8,822.36 | 0 | not claimed | not claimed | 0 |
| 15:23:32 | INR 3,479.87 | 1 | INR 4,338.75 | INR -1,651.00 | 58 |
| 15:24:40 | INR 10,697.52 | 0 | INR 2,791.75 | INR 0.00 | 69 |

These are dated broker/ledger observations, not final net profit after contract
note adjustments. Available cash during execution can reflect committed funds;
it is not a complete portfolio valuation. Open positions and P&L can change
between observations. No profitable repeatable edge follows from one auction.
Both qualification orders remain cancelled with zero fills; they are distinct
from these strategy executions. Incident count remains zero at these checks.

## Presentation correction

Release 9547fd5 separates recent received/processed Upstox frames from accepted
strategy input. After a provider-confirmed frozen reference, a missing current
auction value is reported as auction-entry eligibility, not transport failure.
The live-connection row says Receiving frames and retains the accepted-input age.
Stale index transport and stale option books still warn, even if a socket remains
connected. Delayed processing and disconnected sockets retain their errors.

The exact negative browser fixture reproduces the original misleading warning.
Additional cases preserve warnings for stopped index frames and stale books.
Focused Python dashboard tests and the actual page/stream DOM checks pass.
Full verification passes 457 cases including 60 acceptance cases and 15 mutation
guards. The VM installer passes 83 dashboard cases and verifies authenticated
local status and mandatory public HTTPS authentication. Release
9547fd5b4fe375050e32bc9c58752119364d676e is pushed and deployed directly.

At 15:28 IST authenticated desktop and 390px mobile browser inspection confirms
the new deployed feed logic, no misleading market-data warning, a current open
event stream, AVAILABLE history, enabled authority and verified route. Both
layouts have no document overflow. All three sockets are connected without a
current error. The funded PID remains 338550 with zero restarts. Dhan reports
INR 10,697.52 available cash, no open position, INR 2,791.75 realised and INR 0.00
unrealised P&L. The ledger has 69 fill records and zero incidents. Device metrics
and focus emulation are restored after inspection. These dated results are not
guaranteed final net profit or a proof of strategy repeatability.

## Provider-confirmed auction closure

After the provider reports CAS_STOP, recent frames no longer imply eligibility
for new auction entries. The first presentation repair still warns about absent
accepted strategy input and labels the auction Waiting in this phase. Exact
negative DOM fixtures reproduce both errors before the follow-up repair.
Release 702fbea94862fa57fe1be7def9b32d744783aaeb makes that distinction explicit:
receiving frames are separated from closed auction eligibility, and the strategy
row says Closed with exit/settlement handling explained. Actual stale books and
transport failures remain visible. The scoped Python dashboard cases (62) and
page/stream DOM cases pass. No funded Python source or entry rule changes.

The Google Cloud IAP connection fails twice during deployment. On the second
attempt the remote installer completes despite the local broken-pipe result.
An independent SSH check confirms the current release is 702fbea, its installed
check marker exists, dashboard/collector/HTTPS/daily monitor are active, and the
funded service remains PID 338550 with zero restarts. Public status still requires
authentication (HTTP 401), and local login is reachable.

At 15:43 IST a cache-bypassing authenticated browser request and actual deployed
DOM confirm enabled authority, current account/runtime/collector observations,
verified broker route/software, CAS_STOP and a Closed auction row. The dashboard
reports an idle session after market close; its informational notice is hidden,
and the dashboard event stream is open. Cash remains INR 10,697.52, realised P&L
INR 2,791.75, unrealised zero, no positions, 69 fill records and zero incidents.
This is a dated broker observation, not final net profit after reconciliation.
The final desktop view is inspected and browser focus emulation is restored.
