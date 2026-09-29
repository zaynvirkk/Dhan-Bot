# NIFTY expiry — bounded research results

Each variant starts independently with INR 9,411.18. These are minute-bar model results, not actual historical fills or a live-profitability claim.

Twelve registered variants; 48 expiries across three periods. Development was already contaminated by earlier research. Two retrospective validation blocks were opened after tests, without retuning. They precede CAS and cannot validate that new regime.

The table is the **reported-candles diagnostic**: volume discrepancies remain disclosed and unresolved. Strict reconciled results are in scoreboard.csv, with UNKNOWN terminal wealth wherever a discrepancy affects the path.

| Strategy | Development (9 expiries) | Apr–Jun validation (13) | Oct–Mar validation (26) | Entire chronology |
|---|---:|---:|---:|---:|
| BLIND_CE_TARGET | 2,417.60 (3 trades) | 656.46 (5 trades) | 525.25 (9 trades) | 48.86 (12 trades) |
| BLIND_CE_TRAIL | 2,596.23 (3 trades) | 1,464.23 (5 trades) | 198.47 (9 trades) | 25.10 (11 trades) |
| BLIND_PE_TARGET | 1,037.26 (3 trades) | 1,939.12 (3 trades) | 235.90 (8 trades) | -6.26 (11 trades) |
| BLIND_PE_TRAIL | 2,139.79 (3 trades) | 1,939.12 (3 trades) | 2,293.81 (8 trades) | 158.24 (15 trades) |
| LATE_BREAK_TARGET | 868.79 (6 trades) | 462.40 (8 trades) | 49.59 (11 trades) | -11.65 (12 trades) |
| LATE_BREAK_TRAIL | 549.74 (6 trades) | 818.86 (8 trades) | 49.49 (8 trades) | -11.75 (9 trades) |
| LATE_FADE_TARGET | 9,411.18 (0 trades) | 2,934.32 (2 trades) | 44.09 (7 trades) | -13.90 (8 trades) |
| LATE_FADE_TRAIL | 9,411.18 (0 trades) | 3,168.22 (2 trades) | 44.09 (7 trades) | -13.90 (8 trades) |
| OPTION_ACCEL_OI_TARGET | 2,169.57 (2 trades) | 1,975.13 (3 trades) | 192.18 (11 trades) | 28.59 (13 trades) |
| OPTION_ACCEL_OI_TRAIL | 2,169.57 (2 trades) | 1,975.13 (3 trades) | 2,406.90 (10 trades) | 192.48 (15 trades) |
| OPTION_ACCEL_TARGET | 2,169.57 (2 trades) | 1,694.50 (3 trades) | -0.99 (8 trades) | -0.99 (8 trades) |
| OPTION_ACCEL_TRAIL | 2,169.57 (2 trades) | 1,694.50 (3 trades) | -0.99 (8 trades) | -0.99 (8 trades) |
| ORB30_TARGET | 1,112.37 (5 trades) | 3,550.96 (10 trades) | 1,243.79 (10 trades) | 171.88 (13 trades) |
| ORB30_TRAIL | 510.17 (6 trades) | 3,792.87 (10 trades) | 576.75 (8 trades) | 157.81 (12 trades) |
| TREND1445_TARGET | 9,411.18 (0 trades) | 9,411.18 (0 trades) | 9,521.38 (2 trades) | 9,521.38 (2 trades) |
| TREND1445_TRAIL | 9,411.18 (0 trades) | 9,411.18 (0 trades) | 31,436.13 (2 trades) | 31,436.13 (2 trades) |

## Execution and uncertainty

The primary entry is the next full minute high after a one-minute delay, bounded by the submitted limit. Stops/timed exits use low minus 1%; simultaneous stop/target bars resolve against the trade. Alternate open-plus-1%, two/three-minute delays and full best-trade-deletion replays appear in scoreboard.csv. Targets require trade-through. Each order uses fixed whole lots, current conservative taxes/brokerage and a 5% volume participation cap.

Archive audit counts: `{"RECONCILED": 408, "UNKNOWN_VOLUME_MISMATCH": 144}`. Missing data or unresolved positions yield UNKNOWN terminal wealth. No-trade is reserved for an observed rule failure or a modeled limit/capacity rejection.

A reconciliation is a completeness check, not proof of bid/ask availability. Historical spread, depth, queue priority and second-level latency remain unknown. Earlier periods use the current conservative cost envelope, not historically exact invoices. Drawdowns include separate closed-trade and adverse intrabar marks.

## Signal versus noise

Matched random-side paths preserve signal times, whole-lot contract selection and independent bankroll compounding. They test incremental direction/selection conditional on those times; they do not prove timing predictability. Holm adjustment covers all twelve variants. An unresolved randomization makes its p-value UNKNOWN. Simulations are not additional independent market observations.

See *_noise.json for the full controls, ledger.csv for entries and exits, and PROTOCOL.md for frozen definitions. No threshold revision or profitable-strategy promotion follows from this report.

Source SHA-256: `681d142dbb1819b7aa61b0b52230cc189cbf4c61580e391fb0d1bf5a3e112200`. Dataset SHA-256: `771ea37034daca8eddd2feecedd9702b2bf4b799e4116ece2a584c87047af1fa`.
