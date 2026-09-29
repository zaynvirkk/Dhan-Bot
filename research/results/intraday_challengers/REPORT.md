# Intraday challengers — one new recent-period leader

Completed 27 September 2026. Eight new signals plus the two original signal benchmarks, each with three frozen exits: **30 variants / 360 scenario paths**. Each starts independently with **INR 9,411.18**. Windows are **23 March–20 June** and **21 June–18 September 2026**, 90 calendar days each, with 46/50 ordinary NIFTY sessions. Both periods have already been used for research; neither is a holdout.

**GAP_FADE_DOUBLE reaches INR 12,566.43 (+33.53%) in the recent window, beating the previous INR 11,908.11 best by INR 658.32.** It has five signals, four modeled trades, three wins, one loss and one limit miss. This is a conditional historical-model leader; it does not qualify for funded trading.

The rule waits for a gap of at least 0.5% from the previous close, then 25–100% retracement toward the gap fill, three persistent minute closes and matching futures direction. It buys the closest affordable weekly option from ATM through three OTM strikes. The exit triggers at a completed 2x premium close, a 50% loss, or scheduled close; processing delay and adverse liquidation can reduce the realized payoff.

| Variant | Earlier final INR | Recent final INR | Recent trades / wins | Recent delete-best INR |
|---|---:|---:|---:|---:|
| GAP_FADE_DOUBLE | 7,544.54 | 12,566.43 | 4 / 3 | 9,275.76 |
| SKEW_UNWIND_DOUBLE | 9,411.18 | 11,908.11 | 1 / 1 | 9,411.18 |
| CHAIN_UNWIND_DOUBLE | 2,708.99 | 10,603.30 | 9 / 4 | 4,961.24 |
| OPEN_DRIVE_SWING | 4,051.14 | 9,831.50 | 10 / 4 | 8,118.57 |
| SKEW_UNWIND_FAST | 9,411.18 | 9,669.55 | 1 / 1 | 9,411.18 |
| TREND_PULLBACK_FAST | 9,623.88 | 9,500.24 | 1 / 1 | 9,411.18 |
| FIRST_LAST_SWING | 6,969.20 | 9,460.05 | 1 / 1 | 9,411.18 |
| FIRST_LAST_DOUBLE | 6,375.69 | 9,460.05 | 1 / 1 | 9,411.18 |
| VOLUME_REVERSAL_FAST | 7,334.80 | 9,411.18 | 0 / 0 | 9,411.18 |
| VOLUME_REVERSAL_SWING | 5,514.31 | 9,411.18 | 0 / 0 | 9,411.18 |
| VOLUME_REVERSAL_DOUBLE | 7,250.33 | 9,411.18 | 0 / 0 | 9,411.18 |
| TREND_PULLBACK_DOUBLE | 9,175.57 | 9,123.39 | 1 / 0 | 9,123.39 |
| TREND_PULLBACK_SWING | 8,481.37 | 8,825.52 | 1 / 0 | 8,825.52 |
| SKEW_UNWIND_SWING | 9,411.18 | 8,394.84 | 1 / 0 | 8,394.84 |
| FIRST_LAST_FAST | 7,310.29 | 8,380.25 | 1 / 0 | 8,380.25 |
| SECTOR_CATCHUP_SWING | 9,411.18 | 8,024.26 | 1 / 0 | 8,024.26 |
| OPEN_DRIVE_FAST | 5,616.25 | 7,846.33 | 10 / 4 | 6,546.27 |
| SECTOR_CATCHUP_FAST | 9,411.18 | 7,793.61 | 1 / 0 | 7,793.61 |
| SECTOR_CATCHUP_DOUBLE | 9,411.18 | 7,699.39 | 1 / 0 | 7,699.39 |
| GAP_FADE_FAST | 8,199.73 | 6,903.44 | 4 / 1 | 6,700.18 |
| CHAIN_UNWIND_FAST | 3,949.65 | 6,090.34 | 9 / 3 | 6,329.46 |
| GAP_FADE_SWING | 10,262.90 | 6,040.30 | 4 / 0 | 6,040.30 |
| CHAIN_UNWIND_SWING | 3,787.57 | 5,036.09 | 9 / 3 | 4,672.81 |
| RANGE_FAILURE_FAST | 3,768.89 | 4,662.08 | 11 / 1 | 3,562.56 |
| RANGE_FAILURE_SWING | 4,230.43 | 3,593.19 | 9 / 1 | 3,335.36 |
| RANGE_FAILURE_DOUBLE | 3,557.01 | 3,526.17 | 14 / 5 | 4,261.37 |
| AFTERNOON_COMPRESSION_FAST | 7,028.64 | 3,363.04 | 11 / 1 | 2,994.85 |
| AFTERNOON_COMPRESSION_SWING | 5,438.11 | 2,390.02 | 9 / 1 | 2,177.52 |
| AFTERNOON_COMPRESSION_DOUBLE | 4,228.83 | 1,819.83 | 8 / 1 | 1,872.37 |
| OPEN_DRIVE_DOUBLE | 4,048.91 | 1,590.92 | 9 / 2 | 1,047.11 |

## Does the new leader survive?

| Check | GAP_FADE_DOUBLE final INR |
|---|---:|
| earlier / primary | 7,544.54 |
| recent / primary | 12,566.43 |
| recent / delay2 | 10,197.70 |
| recent / delay3 | 3,780.44 |
| recent / open_plus_1pct | 7,247.40 |
| recent / delete_best | 9,275.76 |
| recent / strict | UNKNOWN |

The extra-minute results change both which orders fill and later bankroll-dependent sizing. The seemingly more favorable open-plus-1% model fills a losing trade missed by the adverse-high model; adverse individual prices do not guarantee a lower whole-strategy result when limit misses select different trades.

Recent modeled mark drawdown is 45.85%. Deleting the best profitable day reruns the full chronological path, including changed strike choice and size, rather than subtracting one P&L. Earlier primary loses money. The +33.53% result is not robust.

## Noise controls

GAP_FADE_DOUBLE: **120 of 999 matched-time random-side paths do at least as well**; 0 unresolved. Smoothed randomization tail probability 0.121; conservative correction across at least 118 tested variants: 1.000. This test does not establish an edge.

TREND_PULLBACK_FAST is the only primary variant positive in both reused windows: INR 9,623.88 / INR 9,500.24, with just one filled trade in each. Its earlier delay and alternative-entry paths lose money; deleting each sole winner returns the start. It is not evidence of a repeatable profitable strategy.

Benchmark comparison: SKEW_UNWIND_DOUBLE still gives INR 11,908.11. CHAIN_UNWIND_DOUBLE gives INR 10,603.30 under this completed-close exit model (the previous resting-target result was INR 10,843.71). All candidates within this experiment use the same execution rules.

## Data and verification

Fetched 34 additional read-only historical API batches. Replayed 838 exact option contract-days: 607 match NSE daily volume, 231 differ; 18 contain off-tick prices (overlapping categories), leaving 599 without either issue. No mismatch was repaired or silently treated as no-trade. All 60 primary reported-candle paths resolve; 54 of 60 strict paths are UNKNOWN. Of the six resolved strict paths, three FIRST_LAST exit variants lose money in the earlier window and three SKEW_UNWIND variants have no fills there. Historical bid/ask/depth and exact fill probability remain unavailable.

Validated 1148 resolved scenario-trade rows for cash continuity, exact charges, whole lots, entry budgets, fixed limits, participation and chronological timestamps. Eight new deterministic tests cover future-data invariance, paid partial exits, target delay, entry-bar ordering, missing data and fee reserves. Tests prove simulator behavior, not market profitability.

Primary positive in both windows: TREND_PULLBACK_FAST. Candidates surviving all registered profitability/quality gates: none. No funded orders, cloud deployment or account changes were made.

[Frozen rules](../../intraday_challengers/PROTOCOL.md) · [Reproduce](../../intraday_challengers/README.md) · [All scenarios](scoreboard.csv) · [Ledger](ledger.json) · [Controls](controls.json)

Source SHA-256: `5a8bc6f6a91fc033edb955e18c13b2b75759e2a8d886a6af460e3952c71a9dd1`
Input SHA-256: `02293737846b943fe1befdb28f0c83572cdd008e567e150407b24a4ca4e78500`
