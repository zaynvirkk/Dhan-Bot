# Intraday challengers — frozen before this experiment's option outcomes

Operator request: find more strategies beating the recent conditional INR
10,843.71 and INR 11,908.11 results. Research only; no funded orders. These are
model profits, not exchange executions or evidence of repeatable profitability.

Reuse two 90-calendar-day windows, 23 March–20 June and 21 June–18 September
2026, ordinary NIFTY sessions only (46 and 50 sessions). Neither window is an
untouched holdout. Each variant/window starts independently with INR 9,411.18.
Do not select a winner by pooling bankrolls, excluding losing days, or changing
parameters after viewing these outcomes. A recent-period record and a robust
candidate are different results. At least 88 prior variants have been examined.

Eight new hypotheses, evaluated every five minutes, first signal per day only:

1. OPEN_DRIVE, 09:45–10:30: spot displacement from 09:15 open >=0.35%,
   last three minute closes increasing in its direction, futures five-minute
   return agrees and futures price is beyond session VWAP in that direction.
2. GAP_FADE, 09:45–11:30: gap from previous final close >=0.5%; at least
   25% of gap retraced from today's open, no more than 100%; three closes
   persist toward the gap fill; five-minute futures confirms.
3. FIRST_LAST, 14:45: first half-hour return >=0.2%; current spot remains on
   that side of open, futures five-minute direction and three closes confirm.
4. TREND_PULLBACK, 10:00–14:45: 30-minute spot return >=0.25%, latest
   ten-minute return opposite that trend, last three closes resume the trend,
   futures five-minute direction agrees. All four conditions required.
5. VOLUME_REVERSAL, 10:00–14:45: spot 15-minute move >=0.2%; latest
   completed three-minute futures volume >=3 times the median of preceding
   ten three-minute blocks; newest three spot closes move against the
   15-minute displacement; futures one-minute return confirms reversal.
6. SECTOR_CATCHUP, 10:00–14:45: BANK and IT both move >=0.2% in the same
   direction over 15 minutes; NIFTY has moved less than half the smaller sector
   move in that direction; last three spot closes and futures five-minute
   return confirm catching up. No fitted contemporaneous regression.
7. RANGE_FAILURE, 10:00–14:45: a close within the preceding 15 minutes
   exceeded the completed 09:15–09:45 range by >=0.05% of spot; latest close
   is back inside that range; last three closes and futures five-minute return
   agree with reversal. If both sides qualify, CE is the fixed tie break.
8. AFTERNOON_COMPRESSION, 13:30–14:45: the 30 minutes ending three minutes
   ago have high-low range <=0.15% of spot; the newest three closes all break
   the same boundary, futures five-minute direction confirms.

Also reuse the exact original CHAIN_UNWIND and SKEW_UNWIND first signals
(including their UNKNOWN states) as benchmarks, without modifying their rules.
Three exits per signal family, 30 variants total, not 30 independent edges:
FAST: +25% / -15%, maximum 30 minutes; SWING: +50% / -25%, 60 minutes;
DOUBLE: +100% / -50%, until scheduled close. Thresholds use completed option
closes, then processing delay; no high-touch target fills. This differs from
the old resting-target model, so rerun both benchmarks with the same new model.

Bars become available at end. Known instrument universe/lot/strike metadata
must exist before selection. Closest ATM, then at most three OTM strikes,
nearest weekly expiry already selected by historical universe. Fixed order
limit = last completed close *1.05, rounded up. Quantity set before the entry
bar: whole lots, <=95% cash inclusive of buy charges, 5% of minimum volume in
last three completed minutes, OI >=10 lots. Additionally reserve fees for three
exit slices. No re-selection after a missed limit. Simulate entry at the high
of the next full minute after a one-minute processing delay; higher than the
fixed limit means missed. No sub-minute latency precision is claimed.

Target/stop closes trigger liquidation after one-minute processing delay;
the entry bar's completed close may trigger, but its earlier low cannot.
Exit at adverse low minus 1%, rounded down, with 5% volume participation and
at most three minutes to finish; partial fills incur actual per-slice fees.
Timed liquidation begins after maximum holding period, capped at 15:24 before
3 August and 15:34 thereafter. Missing selection/holding bars or unresolved
exit capacity stop a path UNKNOWN; never count them as no-trades. Failed
source audits are UNKNOWN in strict mode and explicitly conditional in
reported-candle mode; never repair prices or hide volume/tick mismatches.

Evaluate primary, two/three-minute processing delay, entry open plus 1%,
and delete-best-profitable-day with full chronological re-sizing. Strict primary
also reported. For any recent primary result >11,908.11, run 999 fixed-seed
random-side controls at the same signal times under the same cash/execution
rules, and report unresolved controls separately with conservative probability
bounds. Family-wise correction uses at least 118 tested variants; controls are
diagnostics on reused data, not holdout evidence. A live candidate must also
profit in earlier, both delay, and best-deletion paths; source reconciliation
and new untouched forward evidence remain required before deployment.

Inspired in part by first/last-half-hour intraday momentum literature:
https://www.sciencedirect.com/science/article/pii/S138641812100001X .
This is motivation for a hypothesis, not evidence of Indian option profits.
