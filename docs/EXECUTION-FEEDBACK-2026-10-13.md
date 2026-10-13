# Execution feedback and faster independent inputs

Operator scope: inspect funded production, improve selection/execution and the
dashboard, push and deploy under the existing mandate. This change does not
claim that a profitable future trade is knowable.

## What changed

The arbiter previously compared conditional returns from filled closed trades.
It now also examines the latest 30 reconciled, dispatched, terminal entry
opportunities per strategy, bounded by a 256-lifecycle scan. A cancelled or
rejected zero-fill opportunity contributes zero completion, without being
invented as a realised monetary loss. Partial fills contribute their executed
quantity divided by requested quantity. Never-sent, unresolved, open, future
attempts/fills and pre-dispatch aborts are excluded. Multiple broker attempts
on one intent do not multiply its requested quantity.

Candidate conditional net cash still subtracts current entry/exit charges and
book friction. The comparison's cash-per-holding-minute estimate is multiplied
by observed average quantity completion. Missing completion remains unknown;
it never becomes 100%. A known negative conditional edge cannot become an
unknown experimental winner merely because completion history is missing.
This is a conservative ranking heuristic, not a calibrated future probability
or a full model of unsuccessful-order wall time and changing market regimes.

Unranked same-side execution remains explicitly experimental. Contradictory
unranked sides abstain. A sole qualified auction candidate retains its original
auction, cash, depth and authority checks. Marketable limit prices, IOC
semantics, route-probe caps, capital caps and idempotent recovery are unchanged.

Independent auxiliary features now run with at most three concurrent collectors
and existing broker data admission. A slow publication request no longer
serializes every feature. Trend and institutional collectors share one locked,
cached daily-history request. Failures retain source-local backoff and absent
features; they do not create zero-valued or stale successful inputs. Completed
bars and publication receipt boundaries remain binding.

The dashboard shows live execution feedback even when no new candidate
comparison exists: completed filled trades, sessions, recent fill opportunities,
quantity completion, estimated net mean and standard error. Candidate rows
distinguish conditional cash from fill-adjusted cash/minute. One-session
evidence is expressly insufficient to establish repeatability. The closed empty
state no longer claims that a missing comparison is retained below.

## Evidence and limits

Pre-change read-only broker check: cash INR 10,697.52, zero open or pending
exposure, 66 broker orders, 69 fill records, 37 closed lifecycles, zero incidents.
Dispatched closed BUY intents included 25 CANCELLED and 16 FILLED records;
these are intents, not the new opportunity denominator. Sixteen filled closed
CAS lifecycles were from one session, with estimated mean net return about 1%
and standard error about 2.81%. Final broker fees and repeatable profitability
remain unknown.

Counterexamples in `tests/test_execution_feedback.py` cover zero/partial fills,
future/open/prepared exclusions, unknown completion, selection reversal on
execution quality through the real OMS path, loss veto, concurrent feature
reads, deduplicated daily history and private/nonfinite projection. The actual
dashboard DOM test covers completion/uncertainty copy and missing comparisons.
Full release verification and funded installation rerun the existing acceptance
and mutation cases. Software checks are not fills or strategy profitability.

All 137 supported NIFTY configurations remain enabled under shared capital;
original stock-event, cash, other-index and multi-leg ideas are not implicitly
implemented by this release. Actual market-stream latency and selection impact
require subsequent open-session receipts. Further expansion needs timestamped
historical data, cost-complete chronological replay and holdout results, not
indicator variants promoted because their target is large.
