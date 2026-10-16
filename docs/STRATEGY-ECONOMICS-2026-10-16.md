# Strategy changes after the first live ordinary session

The 16 October receipts contain four completed one-lot trades and eleven
dispatched strategy entries. All four average exit prices were below their
original model target. Three trades exited on lost usable inputs; one exited
on directional failure. A forecast discrepancy is not a forecast of cash profit.
The [session review](SESSION-REVIEW-2026-10-16.md) retains the complete original
order audit and its missing-data limits.

## Changes and why

1. **Choose among qualifying contracts.** Each seconds engine now compares all
   currently eligible contracts and chooses the largest conditional net cash
   headroom after the existing conservative costs. It previously stopped at
   the first qualifying nearby strike. Equal scores retain the deterministic
   nearest-strike order. No retrospective strike or future high is used.
2. **Bound the IOC ceiling by the current spread.** The two-tick ceiling often
   left almost no room after a 249–1,307ms-old committed quote. The new upper
   allowance is the larger of two ticks or one currently quoted spread,
   tick aligned. A binary search selects the highest price that still passes
   the unchanged budget and conditional net-edge gates; it falls back toward
   the original ceiling when cash or edge is tight. This is a maximum price,
   never an assumed fill. Spread, depth, band, freshness, whole-lot, route,
   identity, updated-target, deadline and reconciliation checks still apply.
   There is no extra retry or unrestricted market order.
3. **Separate emergency reserves from expected costs.** Dhan charges options
   brokerage per executed order, not per zero-fill IOC request. The four live
   trades each had one filled buy and one filled sell, including the trade
   with three unfilled sell retries. Ranking uses prior filled-order counts,
   rounded up and bounded by current freeze slicing, and never estimates fees
   below the current fee envelope or comparable historical cost fraction.
   Unknown history keeps the older conservative fallback. Entry allocation
   and its three-exit cash reserve are unchanged.
4. **Avoid charging the same spread twice.** Realized gross returns already
   include historical crossing and slippage. Where actual entry decisions
   supply comparable friction observations, penalise only a wider current
   limit-to-bid gap. Missing comparable observations retain the full penalty;
   a tighter spread never earns an invented positive bonus.
5. **Protect net gains using liquidation costs.** The existing 50% profit
   ratchet uses the fee estimate for the remaining executable sale, including
   freeze slicing, rather than three hypothetical filled retries. Previous
   partial sales and their costs remain in reconciled totals. Its two-times-cost
   activation threshold, retention, finite bid depth, two adverse ticks and
   stale-quote rejection are unchanged. Earlier input-loss/directional/stop
   exits still take precedence.
6. **Include order latency in speed comparisons.** Filled holding time alone
   understated the interval when an entry request was waiting for execution.
   Scoring now uses at least first dispatch through final observed exit fill.
   This is an active-interval comparison, not an earnings-per-wall-clock-minute
   forecast; waiting for signals and final account availability are not inferred.
7. **Keep later charges out of earlier feedback.** Ranking now computes cost
   observations using only charges published by the evaluation time. This fixes
   a reproduced historical-information leak without changing live accounting.

## Recorded-decision comparison

A read-only diagnostic rebuilt all eleven original committed option books,
signals and capital observations and applied each policy at its original
timestamp. All eleven still pass the cash/net-edge assessment for that selected
contract. Ten would allow a higher IOC ceiling, by ₹0.05–₹0.25 per option unit,
at most ₹16.25 additional premium for the recorded 65-unit lot. Actual fills
would depend on the then-current exchange book; none are invented here.

The persisted 14:25 futures-catch-up comparison estimated −₹50.64 under the old
cost/spread assumptions. Applying the corrected model to the same recorded
quantity, limit and friction gives approximately +₹17.56 conditional estimated
net, before multiplying by its prior 37.5% entry-quantity completion. This is a
correction to a model estimate, not a previously missed ₹17.56 profit. Only
three prior filled futures trades from one session support it; their estimated
net-return standard error exceeds their mean return. It does not establish alpha.

Existing archive coverage cannot reconstruct alternate-strike books, exchange
queues or all intervening option quotes before each entry. Therefore this is
an eleven-decision feasibility/estimation comparison, not an alternate-bankroll
backtest or proof that the cancelled orders would now fill profitably.

## Validation and next evidence

Exact negative cases failed before the fixes for first-contract selection,
spread-bounded pricing, affordability fallback, filled-order costs, duplicate
friction, larger reported costs, profit-ratchet activation, future charge leakage,
order latency and safe dashboard projection. Existing production OMS cases
continue to test actual rule → intent → synthetic fill → exit → reconciled flat.

Next live evidence must compare fill completion, realized slippage, net costs,
input-loss exits, target realization and peak-to-exit giveback. The already
deployed dedicated futures input and continuous bounded recorder supply that
evidence. No return, fill or statistical-confidence guarantee follows from this
software repair, and no 90-day completed gauntlet is claimed.

Primary mechanics: [Dhan pricing](https://dhan.co/pricing/),
[Dhan order API](https://dhanhq.co/docs/v2/orders/). Safe diagnostic receipt:
`/tmp/dhan-strategy-counterfactual.json`; raw account configuration and tokens
are never exported. The funded seven-strategy roster, allocated capital,
normal route allowance and probe-money limits are preserved.
