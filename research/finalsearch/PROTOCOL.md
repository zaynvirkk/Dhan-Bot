# Final bounded F&O search — registered 26 September 2026

Objective: highest net whole-lot bankroll growth per elapsed calendar time from
INR 9,411.18, accompanied by drawdown, affordability, execution uncertainty and
repeatability. No finite search establishes an absolute maximum or perfect bot.
Research and read-only broker requests only. No order submission or deployment.

First screen the distinct economic exposures: directional futures/options;
long volatility/event convexity; short volatility/credit spreads; debit spreads;
calendar/diagonal spreads; covered calls/collars; cash-futures carry/conversions;
relative value/pairs/dispersion; auction/forced flows; cross-market momentum;
commodity micro/mini contracts; currency contracts. Current broker margin is a
feasibility observation, not historical margin or fill evidence. Existing
negative experiments remain intact; incomplete families are not called tested.

## New expiry/volatility experiment

Two reused 90-calendar-day windows: 23 March–20 June and 21 June–18 September
2026. They contain 59/63 sessions and 13 expiries each. They are NOT holdouts.
All timestamps IST. Each strategy/window starts independently with INR 9,411.18.

Eight frozen variants:

1. EXPIRY_STRADDLE_1445: closest common CE/PE strike at 14:45.
2. EXPIRY_STRADDLE_1500: same at 15:00.
3. EXPIRY_STRADDLE_1515: same at 15:15.
4. EXPIRY_STRANGLE_1500: one available strike farther OTM on each side at 15:00.
5. EXPIRY_STRANGLE_1515: same at 15:15.
6. EXPIRY_CHEAP_STRADDLE_1500: same ATM pair, but its completed-bar combined
   premium must be below 80% of the median absolute spot displacement from
   15:00 to 15:25 in the preceding 20 trading sessions. This is a past-only
   payoff forecast, not a claim that IV is mispriced. Missing baseline = UNKNOWN.
7. ORDINARY_CHEAP_STRADDLE_1000: nearest weekly ATM pair at 10:00 on non-expiry
   days, same comparison using historical 10:00–15:25 displacement.
8. EXPIRY_LATE_OI_EVACUATION: first signal between 15:10 and 15:19 inclusive.
   Spot crosses an ATM/one-step OTM strike within three completed minutes and
   the last two closes stay newly intrinsic; same-strike premium +25%, OI -8%,
   three-minute volume >=4 times median of preceding ten nonoverlapping
   three-minute blocks. Both sides inspected; ties sort absolute distance then
   CE before PE. No inference of dealer inventory or aggression from OI alone.

Universe/lot/expiry/strike identity comes from previously published NSE files
and exact historical Upstox contracts. No reselection based on future prices.
Bars are available at end, never at start. Expiry flow uses spot only before
15:20; no historical auction fields are fabricated. Only whole lots, 95% cash
inclusive of conservative per-child charges; quantity limited to 5% of each
leg's minimum volume in its last three completed minutes; OI >=10 lots.
Buy limits = completed option close *1.05 rounded up to tick. Limits and basket
quantity fixed before the next full-minute entry bar. Adverse entry uses each
leg's bar high (a scenario, not an ask quote); if it exceeds limit, that leg
misses. A partially filled basket unwinds filled legs from the next minute,
paying actual modeled entry/exit costs; it cannot turn into a free no-trade.

For a completed pair, a combined 2x target or 50% premium loss is detected only
from simultaneous completed closes; both exits begin the next full minute at
adverse lows, with 5% per-bar participation. No sum of asynchronous highs is
counted as a basket target. Single-leg variant uses the same completed-close
logic. Scheduled liquidation begins 15:25 before 3 August, 15:35 from 3 August,
and has three minutes (25–27 or 35–37). MARGIN product is assumed eligible for
index options; no exercise settlement or fresh stock-option expiry entries.
No missing holding minute or insufficient liquidation volume becomes a flat
cash outcome: stop that path UNKNOWN, showing last resolved bankroll separately.
Mark-to-market drawdown uses simultaneous closes; it is a model drawdown.

Primary: one-minute processing delay, adverse high/low fills. Stress: two and
three minutes; next-bar open plus 1% alternative; extra 1% exit-price haircut.
Delete the best profitable trade and rerun the entire cash-dependent path.
Report strict audited paths separately from conditional reported-candle paths.
Historical source-volume or tick mismatches are not repaired by hindsight.

If any variant profits in both windows, require positive delay and best-trade
deletion results, then compare with 999 seeded matched random entry-time paths
(for fixed-clock pairs) or random direction (for directional signals), with
family-wise correction across at least the existing 80 + these 8 variants.
Failure to meet the initial screen ends this bounded search for that variant;
it does not prove the entire family has no possible edge. No return table from
these reused periods can by itself authorize funded trading.
