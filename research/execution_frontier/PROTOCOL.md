# Execution and capital frontier — 28 September 2026

Register before this pass's new outcomes. Preserve every previous experiment.
The previous two discovery windows and added validation window are now ALL
reused retrospective data. This pass is exploration, never an untouched test.
Independent INR 9,411.18 starts for each strategy/allocation/window.

## Mechanisms and exposures

At 15:10, use only completed NIFTY bars. A shock is a session return from
09:15 open of at least 0.75% in absolute value. Eight rules:

1. SELLOFF_CALL: buy CE after a negative shock (prior rebound benchmark).
2. SELLOFF_PUT: buy PE after a negative shock (downside continuation).
3. RALLY_PUT: buy PE after a positive shock (symmetric reversal).
4. RALLY_CALL: buy CE after a positive shock (upside continuation).
5. TWO_SIDED_REVERSAL: CE after negative, PE after positive.
6. TWO_SIDED_CONTINUATION: PE after negative, CE after positive.
7. TREND_PULLBACK: reversal only when the shock opposes the preceding
   twenty-session close-to-close trend, excluding today's close.
8. TREND_CONTINUATION: continuation only when shock and that trend agree.

For each use 25%, 50% and 95% of then-current cash as the inclusive entry
budget. No borrowing or fractional lots. Keep the closest affordable ATM
through three OTM fixed contract, expiry strictly after the next session;
one position at a time, no same-day re-entry after exit. Liquidation next
session 15:10, or delayed completed-close 2x / 0.5x premium trigger. Monitor
the full dated derivatives session and carry pending exits through closure.
Date-correct fee model. Reserve up to three exit slices.

## Order policy is determined before outcomes

Base: known last close +5% buy limit, one-minute processing, resting for
three complete arrival bars. Charge the fixed limit if traded low passes
at least two ticks below it. Do not reject a possible fill because that
minute's high exceeds the limit. This is a bar-based fill scenario, not a
queue or ask reconstruction. Fill time is conservatively reported at that
bar's end; monitoring begins in the following bar. A touch does not fill.
No repricing, changing strike, quantity resizing or retrospective retries.

Seven scenarios per rule/allocation/window: base rest3; arrival-open+1%
single-bar scenario (no subsequent retry); three-minute processing rest3;
twice exit slippage; tighter +1% fixed limit rest3; strict source audits;
delete best profitable base trade and rerun all later selection/sizing.
Total 8 x 3 x 7 x 3 = 504 attempted chronological paths.

Known three-minute minimum volume caps size at 5%, known OI >=ten lots.
If the fill minute cannot support the entire order under the same volume
cap, mark UNKNOWN_PARTIAL_ENTRY rather than skip the potentially losing
position. Minute volume is not liquidity available at a particular price.
Missing holding bars or unsettled exits stop the bankroll, never become
profitable/no-trade evidence. This study does not claim exact IOC support
or subminute execution from minute bars.

## Feasibility beyond long index options

Read-only Dhan quote/margin survey: sampled narrow call/put debit and credit
verticals across available NSE indices; near-month index futures; lowest
quoted-notional stock futures; small commodity contracts. No orders. Compare
reported basket margin and standalone first hedge leg to actual cash; both
are necessary, neither sufficient. A current affordable sample is not a
historically affordable strategy. Do not conclude all spreads fail from a
few samples. No net-debit-only or theoretical-max-loss-only margin fiction.

Review scheduled-event volatility, stock long/short momentum/reversal,
commodity micro-futures trend, short volatility, relative value and cash
intraday leverage as distinct mechanisms. State actual tested coverage and
the precise missing inputs; do not label untested mechanisms losers.

## Interpretation and validation

No strategy is live-qualified by this exploration. Rank all windows,
execution sensitivity, trade count and drawdown, not only maximum recent
cash. Multiplicity now exceeds 168 strategy/exposure combinations plus
execution alternatives. A newly positive rule requires separately frozen
validation and market-hours execution evidence.

Tests: time-of-information exclusion; limit touch versus penetration;
high above limit does not erase a possible fill; partial entry UNKNOWN;
deadline misses; calls/puts symmetry; trend excludes today's close;
whole-lot allocation and fees; unresolved exposure stops compounding.
Full existing suite supplements these exact cases. All source/input hashes
and complete ledgers saved; software tests are not profitability evidence.
