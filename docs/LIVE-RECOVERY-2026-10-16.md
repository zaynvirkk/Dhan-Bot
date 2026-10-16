# 16 October live recovery repair

The morning account read confirmed one real non-expiry futures-catchup round
trip: 65 NIFTY 23,000 PE bought at106.30 and sold at108.95, gross INR172.25.
Cash changed from7805.94 to7924.03; itemized final charges were still pending.
Five other strategy buys and one connection check cancelled without fills.
These are different outcomes, not eight failed trades or proof of repeatability.

The first inspection found current route proof but intermittent stale account
reconciliation, seconds inputs alternating between unavailable and warmup, and
repeated Dhan market client keepalive timeouts. The short follow-up saw ten
fresh account observations out of twelve. No positions or pending orders were
reported in those checks. After-hours reconnect totals are not all current
session outages; the recorded market keepalive failures did occur after open.

## Repairs and behavioral evidence

- Dhan market data answers its documented server pings automatically and uses
  a thirty-second fallback client deadline instead of five seconds. The
  fallback remains bounded for a silently broken connection; other sockets
  retain their original keepalive. A real local WebSocket server receives its
  pong, then sends a quote. This does not extend executable-quote freshness.
  See the [provider contract](https://dhanhq.co/docs/v2/live-market-feed/).
- Ordered frame processing yields after sixteen frames, preserving every
  frame and its original receipt time. Previously a decoder with no suspension
  could drain the queue before another ready task ran. The exact regression
  failed on the original source; the repaired path services the waiting task
  within sixteen frames and still processes all two hundred.
- Seconds discovery no longer recomputes every closed lifecycle on every
  packet. Its budget cache lasts at most the existing quarter-second evaluation
  interval; a new funds object or reconciliation revision invalidates it
  immediately. A real rule fixture still finds the affordable strike, rejects
  it immediately after a balance reduction, and checks monetary revisions.
  Actual submission continues to read funds and calculate allocation afresh.
- Orders, trades and positions GETs start together under the existing shared
  REST scheduler and revision fence. A stalled orders read cannot prevent the
  positions request from starting. Failure or cancellation cancels and joins
  the whole batch; incomplete results never certify an account. The stalled
  cash test now waits for the independent position receipt rather than relying
  on the incidental scheduling order of the first cash callback.
- A stale account now reports ACCOUNT_REFRESH_REQUIRED rather than retaining
  an old ENTRY_SUBMITTED reason. A finished lifecycle explicitly reports a
  closed position or cancelled entry without fills. Recovery clears its own
  temporary reason after a successful reconciliation; durable history remains.
- Runtime revision5 distinguishes the repaired trader from an older process.
  A newly deployed dashboard cannot claim that an older funded process already
  contains these changes.

The first five new counterexamples failed on the original production source.
Additional cases cover cancellation cleanup, actual provider-style pongs,
balance reductions and revision invalidation. Tests use local synthetic
brokers; none of these receipts is a market-profit or guaranteed-fill result.

## Deployment scope

The operator explicitly requested this repair and production deployment.
Preserve the seven selected funded engines, existing capital, mandate,
profit-exit retention and probe attempt/money limits. Reconcile actual account
obligations before the funded source switch and recover them on startup.
Do not grant attempts, erase history, widen entry limits or force a trade.

Before completion, verify the installed and funded sources agree, revision5
and source-bound software verification are current, account/positions/orders
are reconciled, and the new socket acquires genuine route proof within its
remaining allowance. Observe usable futures history and transport health after
warmup. Broker refusal, future outages, unmatched IOC orders and absence of a
qualifying setup remain possible; this release cannot guarantee profit or the
absence of every undiscovered defect.

The final local source-bound verification passed662 tests, including all60
acceptance cases, and killed all15 production guard mutations. Its source
digest is a9d2dc91122376182c81fcae2456768b07e0ee8be94b963d73bf677c13a2aca8.
Deployment and current live observations must be verified separately.

The first VM installation passed94 installer cases and switched the read-side
release, but its startup HTTP check raised an uncaught socket timeout. The
funded process was untouched. Deployment verification now retries socket
timeouts on both unauthenticated and authenticated reads within finite limits,
requests the compact status response, and still rejects missing authentication
or non-read-only/stale status. Three exact regression cases cover recovery,
unprotected responses and exhausted retry limits.
