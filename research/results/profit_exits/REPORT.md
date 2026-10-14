# Profit protection comparison — 14 October 2026

The cost-aware profit floor reduces giveback in some scenarios, but **no tested
entry/exit variant grows the bankroll in both 90-day windows**. It is not a
profit-optimised or statistically qualified live strategy.

Each independent path starts with INR 9,411.18. Windows are 23 March–20 June
and 21 June–18 September 2026. The same 32 entry hypotheses compete with five
exits: original 50% premium trail, original 2x target, and net-profit retention
of 25%, 50% or 75%. Across two source-quality modes, both windows, primary,
two/three-minute entry delay and deleting the best trade, 2,560 scenarios ran.
These periods and hypotheses have already been researched; this comparison
is retrospective refinement, not a fresh untouched holdout or multiple-testing
adjusted proof. Strict unresolved paths do not receive invented terminal cash.

| Ordinary published PCR exit | Earlier model INR | Recent model INR |
|---|---:|---:|
| Existing premium trail | 2,485.34 | 1,408.99 |
| Existing 2x target | 2,940.95 | 3,637.10 |
| Retain 25% of peak net profit | 3,045.50 | 1,995.94 |
| Retain 50% of peak net profit | 3,801.11 | 1,905.56 |
| Retain 75% of peak net profit | 3,547.89 | 2,029.02 |

These are reported-candle model outputs. This strategy remains UNKNOWN in
strict mode from its first qualifying selection in each window. Tighter exits
cannot manufacture a profitable entry edge. Minute bars do not supply historic
bid/ask, queue priority, intrasecond latency, or guaranteed option fills.

NET_PROFIT_RATCHET_V1 activates after observed net liquidation profit exceeds
twice estimated trading costs, then raises a nondecreasing floor equal to the
configured fraction of observed peak net profit. It can trigger before any
clock exit, but a gap, stale feed, partial fill or missing depth can realise less
than the floor, including a loss. The candidate retains legacy loss/holding
limits as backstops; it is an additional profit-protection rule, not removal of
all existing risk exits. Retention is an explicit versioned parameter, not an
estimate of the chance of profit. The 50% example is not crowned as optimal.

Research ratchets from earlier completed closes with a 1% adverse liquidation
proxy, applies fee envelopes, and fills exits at adverse lows with bounded
volume participation. It never sells earlier in a candle using that candle's
future close. Missing holding/selection/capacity data remains UNKNOWN. The live
implementation instead requires fresh current books and sufficient finite bid
depth for the managed quantity, tracks total lifecycle net economics and latches
an exit through the existing reconciled OMS. Broker execution remains separate
from the model. Source/input hashes and complete chronological paths are in
comparison.json; the primary scoreboard is in scoreboard.csv.

The feature is **opt-in and not deployed/enabled on the funded process**.
Configuration for a later, explicitly chosen verified-flat release is:

```toml
profit_exit_policy = "NET_PROFIT_RATCHET_V1"
profit_exit_retain = "0.50"
```

New lifecycles freeze that policy. Existing lifecycle payloads are unchanged;
restoring a lifecycle with a recorded policy preserves its durable peak/floor.
Applying a policy to the currently losing trade retrospectively could force
an immediate loss-making exit and is not performed. The operator's latest
instruction is to assess recovery and not close solely because it is losing.

Fresh offline validation passed 540 tests, all 60 acceptance cases and all
15 required production guard mutations; no test was skipped. Fourteen exact
profit-policy cases cover net-cost activation, retained floors, gap losses,
sticky triggers, invalid configuration, stale/thin books, immediate real OMS
reduction in a fixture and candle look-ahead rejection. DOM checks preserve
legacy position-policy rendering. These checks establish implementation
behaviour only. No new funded release, activation or trader restart follows
from them; the open position remains on its existing recorded policy.

## Current-position assessment

At 14:08 IST Dhan reported the 19 October NIFTY 22,750 CE bid/ask as 84.75/84.95,
with 585 bid units and 910 ask units; the managed quantity is 65. Spot was
22,623.35, IV 11.5689%, delta 0.38664 and gamma 0.00121. Actual entry was 122.65.
Conservative fee-adjusted sale break-even is about 123.70, requiring a premium
rise of 38.95 from that bid. A local delta/gamma scenario with volatility/time
unchanged requires roughly 88.49 spot points, to 22,711.84. It is not an
exercise break-even calculation or a calibrated probability forecast; IV/time
changes, nonlinear sensitivities and fees alter the requirement.

A timestamp-bounded underlying proxy used all 124 complete archived sessions
through 18 September: from the completed 14:08 observation to the final 15:30
observation, 11 reached at least a 0.3934% rebound. Among 14 sessions with a
negative preceding 15-minute return and positive 30-minute return, two reached
it (14.3%, Wilson 95% interval approximately 4.0–39.9%). This small conditional
sample does not establish an option-profit probability. The archive does not
establish the remaining 15:30–15:34 window. Neither a low point estimate nor
lack of a current profit guarantees failure; neither justifies promising that
holding until break-even will work. No discretionary sell or funded restart
was made during this assessment.

At 14:27 IST a further real quote showed bid/ask 84.40/84.60, with 130 bid
units; conservative estimated liquidation P&L was minus INR 2,549.16. The
completed underlying returns were +0.0440% over five minutes, +0.0564% over
fifteen and -0.1463% over thirty. Direction had changed from the 14:08 pattern;
the earlier matched-session statistic is not a continuously updated forecast.
The contract still has time value, but no calibrated live model establishes
that it will recover, or that its probability of recovery is negligible.
The operator was asked separately whether holding past the existing 15:34
limit means accepting overnight exposure. No override was applied while
awaiting that clarification. The assessment is reproducible with:

```bash
.venv/bin/python -m research.recovery_scenarios --at 14:08 --cutoff 15:30 \
  --move 89 --spot 22623.35 --as-of 2026-10-14 \
  --output research/results/profit_exits/recovery_1408.json
.venv/bin/python -m research.profit_exits
```
