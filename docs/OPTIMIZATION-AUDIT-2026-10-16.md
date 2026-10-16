# WebSocket, API and execution optimization audit — 16 October

At15:21IST funded817a781/PID424919/revision6 still had all three sockets
connected and no reconnect, framing/book rejection or failed reconciliation.
Fresh Dhan requests returned no API errors, INR7,964.55 cash, no open position
and no pending order. No order was forced during this audit.

The reconnect fault is repaired, but latency remains imperfect. Rolling512
samples had decision p95/p99 732/999ms, market-to-decision p95/p99 251/445ms,
and reconciliation p95/p99 2.75/4.29s. Ten submission measurements had local
decision-to-submit p95 546ms and broker ACK p95 250ms. These are current-process
observations, not a permanent service guarantee. Brief stale futures inputs
and account refreshes correctly block entries; their strict limits remain.
The VM had17GB free; ledger7.57GB/WAL6.1MB. No records were deleted or database
rewritten. Raw data retention needs capacity monitoring, not an invented
estimate of how many future sessions fit.

## Reproduced repairs

- Five seconds-strategy evaluation receipts were committed in five separate
  FULL transactions. The SQL trace regression failed before repair. One atomic
  observation batch now retains all five receipts in one commit. Financial
  intent/fill/order durability remains unchanged. Batch failure cannot mark
  history complete or leave a partial five-strategy snapshot.
- A refreshed signal could keep the same episode while its target worsened;
  candidate and pre-dispatch checks accepted the old optimistic target. Both
  exact regressions failed with original15/refreshed12. The same episode,
  contract/expiry/side and a finite positive refreshed target at least as good
  as the original are now required. Equal/better forecasts retain the original
  conservative target. This can reject more signals; higher returns are not
  established by a software test.
- Changing evaluation timestamps alone caused unchanged NO_SIGNAL decisions to
  trigger history work and fill the recent journal. The negative regression
  now passes: non-signal timestamp changes are ignored for history state-change
  detection. Actual state/reason changes, fresh SIGNAL timestamps and periodic
  minute samples remain. Current dashboard snapshots still refresh and full
  strategy receipts remain in the ledger.

## Other paths inspected

HTTP clients are reused. Account reads have bounded priority scheduling;
unknown order outcomes are reconciled, not blindly resubmitted. Market queues
remain bounded/ordered and yield to pongs and order updates. Provider pings
receive automatic pongs; watchdogs and true receipt timestamps remain. Dynamic
subscriptions retain held/pending contracts and full active CAS expiry
coverage, adding before removal in100-instrument batches. Authenticated SSE
streams are bounded and renew after20s to recheck browser authentication;
this is independent of trading sockets. Broker reconciliation still requires
funds/position/fill API observations even when order updates use WebSockets.

## Deployment boundary

Revision7 identifies these repairs. Exact counterexamples preceded changes;
focused quote/OMS/history/dashboard tests pass. Full verification and live
installation remain separate evidence. The current trader continues while the
release is prepared. Today's three authorized route checks are consumed, so
the funded switch waits for the provider-reported session close. No fourth
attempt, extra spending, new strategy or freshness relaxation is granted.
Normal next-session route allowance stays two. Seven funded strategies, profit
retention and all other capital/entry/execution gates remain unchanged.

Closed-session activation must distinguish real-money authority from a closed
exchange and pending next-session order-socket qualification. It cannot prove
future fills or profit. Current deployment truth is recorded in portfolio
STATE/CURRENT and the live runtime; earlier source observations above remain
historical evidence.

The bounded recent-lifecycle audit also found SECONDS_INPUT_LOST recorded for
both post-upgrade filled trades. Their gross gains did not establish positive
net cash after costs. This makes input/decision latency an execution concern,
not just a cosmetic dashboard issue. The guard remains protective; disabling
it would hide the missing input rather than fix delivery. Quantified active-
market latency after this new repair still needs actual next-session evidence.

Frozen local source verification passed675 tests, including all60 acceptance
cases, and rejected all15 injected execution defects. Source digest:
`5e1565eed7b50836cc85bfa0aa658aa23bbe73ea77a0364337e0084daa3417f9`.
