# Broader search: overnight, stock selection and holding periods

26 frozen variants, 260 scenario paths attempted. Each independently starts with **INR 9,411.18**. Both **23 March–20 June** and **21 June–18 September 2026** span 90 calendar days (59 and 63 trading sessions). These periods have already been used for discovery; they are not holdouts. UNKNOWN means the path cannot be scored, not that it stayed at the starting balance.

Universe: 146 official NSE archive sessions including warm-up, historical F&O membership (221 stocks in the dated union), 214 distinct stocks meeting at least one past-only selector and minute history for the 151 stocks selected by a top rank. The ranked stock is fixed before its option affordability is known; an expensive top pick cannot be replaced with a later winner.

| Strategy | Earlier final INR | Recent final INR | Recent trades / wins | Recent delete-best INR |
|---|---:|---:|---:|---:|
| NIFTY_SELLOFF_REBOUND_1510 | 14,663.22 | 16,762.25 | 5 / 4 | 9,592.86 |
| NIFTY_SELLOFF_REBOUND_0930 | 9,256.78 | 12,732.73 | 3 / 1 | 8,713.83 |
| OI_SQUEEZE_CASH5 | 10,342.25 | 10,949.47 | 9 / 5 | 8,552.35 |
| VOLUME_BREAKOUT_CASH5 | 9,459.87 | 9,303.92 | 10 / 5 | 9,608.06 |
| TREND_DIP_CASH5 | 10,295.67 | 9,068.58 | 9 / 5 | 8,659.70 |
| TREND_DIP_CASH1 | 8,598.39 | 8,980.02 | 24 / 8 | 8,770.67 |
| SMOOTH_MOMENTUM_CASH5 | 10,312.10 | 8,979.16 | 9 / 3 | 9,519.25 |
| OI_BUILD_CASH5 | 8,959.80 | 8,598.53 | 8 / 4 | 7,630.07 |
| MOMENTUM20_CASH5 | 11,449.95 | 8,393.67 | 9 / 3 | 7,551.56 |
| MOMENTUM20_CASH1 | 8,510.94 | 7,831.71 | 28 / 12 | 7,685.67 |
| OI_BUILD_CASH1 | 9,520.21 | 7,775.91 | 17 / 4 | 7,743.98 |
| VOLUME_BREAKOUT_CASH1 | 10,511.07 | 7,707.15 | 28 / 8 | 7,593.54 |
| SMOOTH_MOMENTUM_CASH1 | 8,402.74 | 7,074.94 | 28 / 7 | 6,788.08 |
| OI_SQUEEZE_CASH1 | 9,781.67 | 6,822.20 | 22 / 4 | 6,659.08 |
| SMOOTH_MOMENTUM_CALL5 | UNKNOWN | 5,422.13 | 1 / 0 | 5,422.13 |
| NIFTY_DAY_CONTINUATION_0930 | 3,943.12 | 3,527.84 | 5 / 0 | 3,527.84 |
| NIFTY_DAY_CONTINUATION_1510 | 16,818.43 | 2,413.99 | 3 / 0 | 2,413.99 |
| NIFTY_UNCONDITIONAL_1510 | 2,796.51 | 2,401.94 | 9 / 3 | 2,056.17 |
| NIFTY_TREND_ALIGNMENT_1510 | 5,359.25 | 2,036.96 | 5 / 2 | 2,326.85 |
| NIFTY_TREND_ALIGNMENT_0930 | 1,975.65 | 1,920.23 | 5 / 1 | 6,815.75 |
| NIFTY_UNCONDITIONAL_0930 | 1,745.20 | 1,860.80 | 20 / 8 | 2,091.50 |
| MOMENTUM20_CALL5 | UNKNOWN | UNKNOWN | 0 / 0 | UNKNOWN |
| TREND_DIP_CALL5 | UNKNOWN | UNKNOWN | 0 / 0 | UNKNOWN |
| VOLUME_BREAKOUT_CALL5 | UNKNOWN | UNKNOWN | 0 / 0 | UNKNOWN |
| OI_SQUEEZE_CALL5 | 7,536.03 | UNKNOWN | 1 / 0 | UNKNOWN |
| OI_BUILD_CALL5 | UNKNOWN | UNKNOWN | 1 / 0 | UNKNOWN |

## Interpretation

Recent primary strategies exceeding the prior INR 12,566.43 benchmark: NIFTY_SELLOFF_REBOUND_1510, NIFTY_SELLOFF_REBOUND_0930.
Primary profit in both reused windows: OI_SQUEEZE_CASH5, NIFTY_SELLOFF_REBOUND_1510.
Positive in both windows under every registered stress and strict data check: none.

A favorable final balance is conditional on a minute-bar model. No strategy here has historical order-book execution receipts, and repeated use of the same windows prevents an independent validation claim. Best-trade deletion reruns the full chronology and bankroll-dependent selection. All comparisons use whole shares/lots, costs and cash left by earlier trades. No capital reset after losses.

## Overnight rebound candidate

At 15:10, use the last completed NIFTY bar. If it is at least 0.75% below the 09:15 session open, choose a call in the nearest expiry strictly after the next trading session. Search ATM through three OTM strikes for the closest affordable liquid whole lot. Size at most 95% including entry fees and reserve exit charges. Keep a fixed +5% limit; simulate entry one full minute later. Exit by the next session at 15:10, or after a completed premium close reaches 2x / loses 50%, with delayed adverse liquidation. The target and stop are not guaranteed fills.

| Check | Earlier INR | Recent INR |
|---|---:|---:|
| primary | 14,663.22 | 16,762.25 |
| delay3 | 10,048.67 | 16,638.71 |
| slippage2 | 14,159.69 | 16,088.54 |
| delete_best | 10,029.17 | 9,592.86 |
| strict | UNKNOWN | UNKNOWN |

The earlier/recent base paths have four/five filled trades. Positive reported stress paths are encouraging, but the small number of events, repeated search over these periods and unresolved strict data audit prevent a live-profit claim. The next-morning version is a separate frozen variant; the earlier window loses.

## Execution assumptions and limits

A fixed limit and quantity are chosen from completed bars before entry. Entry occurs after one full minute (three in stress), using a later adverse high; exits use later adverse lows and bounded partial liquidation. A completed premium close, not a future candle high, triggers the target. An overnight gap can pass a stop and lose much more. Monitoring ends at 15:15 and resumes with completed bars next session, as registered; this is not a full-session live design. A pessimistic individual price is not a guaranteed lower bound on strategy returns: limit misses change which trades occur. Minute volume does not establish available ask/bid or queue priority.

Cash delivery is unleveraged and includes taxes and DP fees; sale proceeds are not recycled on the same day. CALL5 avoids stock delivery-margin windows using the frozen seven-calendar-day buffer beyond planned exit. Current ban-list uncertainty stops a stock-option path. Missing holding/exit data also stops a path. Corporate-action adjustments are not manufactured. Mark drawdown is a modeled adverse mark relative to resolved equity peaks, not tick-exact account drawdown.

## Evidence quality

Inspected 3349 stock/option session tapes. Issue counts overlap: `{'CASH_VOLUME_MISMATCH': 1110, 'CASH_RANGE_MISMATCH': 1, 'OFF_TICK': 85, 'VOLUME_MISMATCH': 407}`. Reported scenarios relax only the specified source volume/tick reconciliation; strict scenarios stop at those failures. Neither label establishes true historical spread or fillability.

| Strategy / period | Unresolved primary boundary |
|---|---|
| MOMENTUM20_CALL5 / earlier | ['2026-03-27', 'ValueError:UNKNOWN_DECISION_BARS'] |
| MOMENTUM20_CALL5 / recent | ['2026-06-29', 'ValueError:MISSING_EXACT_METADATA:NSE_FO/36345/28-07-2026'] |
| SMOOTH_MOMENTUM_CALL5 / earlier | ['2026-03-30', 'ValueError:UNKNOWN_DECISION_BARS'] |
| TREND_DIP_CALL5 / earlier | ['2026-05-13', 'ValueError:MISSING_EXACT_METADATA:NSE_FO/110817/30-06-2026'] |
| TREND_DIP_CALL5 / recent | ['2026-06-24', 'ValueError:UNKNOWN_DECISION_BARS'] |
| VOLUME_BREAKOUT_CALL5 / earlier | ['2026-04-02', 'ValueError:UNKNOWN_EXIT_CAPACITY'] |
| VOLUME_BREAKOUT_CALL5 / recent | ['2026-06-29', 'ValueError:MISSING_EXACT_METADATA:NSE_FO/36345/28-07-2026'] |
| OI_SQUEEZE_CALL5 / recent | ['2026-07-14', 'ValueError:MISSING_EXACT_METADATA:NSE_FO/43653/25-08-2026'] |
| OI_BUILD_CALL5 / earlier | ['2026-04-02', 'ValueError:UNKNOWN_DECISION_BARS'] |
| OI_BUILD_CALL5 / recent | ['2026-08-03', 'ValueError:UNKNOWN_EXIT_CAPACITY'] |

## Noise checks

The 999 paths per case are seeded Monte Carlo direction assignments on the same historical signal dates, not 999 independent market events. Small signal counts produce repeated direction patterns. These controls test the direction choice conditional on the registered event clock; they do not establish that the event timing beats matched random trading times or validate the strategy out of sample.

NIFTY_SELLOFF_REBOUND_0930 / recent: 20/999 random-side paths meet or exceed INR 12732.73; 0 unresolved controls. Tail probability bounded by [0.021, 0.021], conservative multiplicity correction over at least 144 variants: 1.000.
NIFTY_SELLOFF_REBOUND_1510 / earlier: 156/999 random-side paths meet or exceed INR 14663.22; 0 unresolved controls. Tail probability bounded by [0.157, 0.157], conservative multiplicity correction over at least 144 variants: 1.000.
NIFTY_SELLOFF_REBOUND_1510 / recent: 20/999 random-side paths meet or exceed INR 16762.25; 0 unresolved controls. Tail probability bounded by [0.021, 0.021], conservative multiplicity correction over at least 144 variants: 1.000.
NIFTY_DAY_CONTINUATION_1510 / earlier: 236/999 random-side paths meet or exceed INR 16818.43; 0 unresolved controls. Tail probability bounded by [0.237, 0.237], conservative multiplicity correction over at least 144 variants: 1.000.

Dhan cross-check: 27/27 selected decision/entry/final-exit minutes match timestamp and strike; 0 have identical OHLC across feeds. Expiry uses the prior published contract calendar and the requested Dhan weekly expiry code. This bounded comparison does not repair full-session volume discrepancies or prove fills. [Cross-broker details](crosscheck.json).
Dhan's high stays below the fixed entry limit in 9/9 entry snapshots; 18/18 entry/final-exit snapshots meet the modeled 5% volume cap. Maximum observed absolute close difference is INR 0.70. These checks do not establish same quotes, targets or intervening holding paths. One initial authentication attempt failed; a bounded retry succeeded.

## Source corrections preserved

The initial cash snapshot is retained as `cash_before_source_reconciliation.json`. NSE circular [CMTR73856](https://nsearchives.nseindia.com/content/circulars/CMTR73856.pdf), published 22 April, scheduled VEDL special pre-open until 10:00 on 30 April. Its missing 09:15–09:29 bars are therefore a known unavailable 09:30 entry, not an unexplained missing-data gain/loss. No replacement stock is chosen. Missing metadata on a farther option is now evaluated only if deterministic selection reaches that strike; nearer known contracts are not invalidated by unused farther data. A further data-routing correction requests the same exchange token and expiry from the expired-history endpoint when cached active metadata predates expiry. The first option run is retained as `options_before_expiry_route_reconciliation.json`. All corrections were replayed under unchanged signal/exit thresholds.

## Other economic mechanisms

The [mechanism review](../../broader/RESEARCH.md) also covers short volatility, spreads, carry, auction flows, cross-market signals and commodity micro contracts. Dhan returned **55,598 actual Gold Petal minute bars** for the recent window. The tested Upstox expired commodity lookup returned HTTP 400 UDAPI100011. Historical margin paths, exact active/front-contract coverage, MCX daily-volume reconciliation and account eligibility remain unverified. Gold Petal is **unscored**, not rejected as unprofitable. Current initial margin cannot be applied retroactively.

## Reproducibility

Validated 1789 resolved scenario trade rows: chronological bankroll, fees, whole lots, 95% pre-entry budgets, fixed limits, timestamps and observed volume participation. 210 unaffected scenario paths exactly match their retained pre-correction runs. All source/input hashes and the original registration hash are checked by report generation. Software tests do not prove a market edge. No live orders, deployment or spending occurred.

[Frozen protocol](../../broader/PROTOCOL.md) · [Reproduction](../../broader/README.md) · [All 260 paths](scoreboard.csv) · [Ledger](ledger.json) · [Controls](controls.json)

Source SHA-256: `404fab8fa53a716eeefe82da66e279ab2915b5f81364c77943eba2ba5cab81a3`
