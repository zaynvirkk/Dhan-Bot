# Additional NIFTY reversal and breakout experiment

Every variant starts independently with **INR 9,411.18** in each 90-calendar-day window: **23 March–20 June** and **21 June–18 September 2026**. Earlier/recent session counts are 59/63, with 13/13 expiries. These dates have already been examined; this is retrospective research, not a new holdout.

Computed **320 execution scenarios** and **13,972 random-direction paths**. Verified whole-lot and cash/P&L algebra for every resolved ledger row.

Positive in both reported-candle windows: **none**. Passing the stricter profit, delayed-fill, best-trade-deletion, data-quality and multiplicity screen: **none**. No live strategy is certified.

| Variant | Earlier bankroll | Recent bankroll | Recent trades | Recent without best | Recent +2-minute delay |
|---|---:|---:|---:|---:|---:|
| EXPIRY_COMPRESSION_BREAK_TARGET | 9,411.18 | 4,133.26 | 2 | 6,299.34 | 2,295.93 |
| EXPIRY_COMPRESSION_BREAK_TRAIL | 9,411.18 | 4,471.11 | 2 | 6,637.19 | 2,393.39 |
| EXPIRY_FAILED_ORB_TARGET | 1,250.37 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_FAILED_ORB_TRAIL | 1,990.66 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_PRIOR_OI_WALL_TARGET | 3,019.03 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_PRIOR_OI_WALL_TRAIL | 4,045.61 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_VWAP_RECLAIM_TARGET | 6,159.28 | 2,313.18 | 3 | 3,677.89 | 5,292.83 |
| EXPIRY_VWAP_RECLAIM_TRAIL | 6,373.68 | 3,367.24 | 3 | 3,567.51 | 29,268.06 |
| ORDINARY_COMPRESSION_BREAK_TARGET | 2,638.54 | 3,751.91 | 6 | 3,776.67 | 4,753.87 |
| ORDINARY_COMPRESSION_BREAK_TRAIL | 2,638.54 | 3,751.91 | 6 | 3,776.67 | 4,753.87 |
| ORDINARY_FAILED_ORB_TARGET | 7,600.78 | 6,801.53 | 11 | 3,567.66 | 3,702.72 |
| ORDINARY_FAILED_ORB_TRAIL | 11,763.15 | 3,373.77 | 11 | 2,294.44 | 2,171.81 |
| ORDINARY_PRIOR_OI_WALL_TARGET | 9,411.18 | 6,901.89 | 2 | 7,804.54 | 8,500.34 |
| ORDINARY_PRIOR_OI_WALL_TRAIL | 9,411.18 | 6,901.89 | 2 | 7,804.54 | 8,500.34 |
| ORDINARY_VWAP_RECLAIM_TARGET | 3,444.56 | 3,531.19 | 8 | 2,210.25 | 5,095.58 |
| ORDINARY_VWAP_RECLAIM_TRAIL | 3,444.56 | 3,531.19 | 8 | 2,210.25 | 4,378.21 |

## Evidence limits

The table is conditional on reported provider candles. Strict results and all misses are in [scoreboard.csv](scoreboard.csv) and [ledger.csv](ledger.csv). UNKNOWN is an unresolved path, not a no-trade day or an unchanged bankroll. A known unchanged balance with zero fills also provides no evidence of profit.

Exact-contract-day audits for this batch, including reused tapes: `{'UNKNOWN_VOLUME_MISMATCH': 200, 'UNKNOWN_OFF_TICK_PRICE': 24, 'RECONCILED': 606}`. Source disagreement, off-tick prices and missing order-time data are preserved; strict audit failures cannot be used to skip a historical loss and continue compounding.

Only completed bars enter signals. The first signal is fixed before collecting its option outcomes. ATM-relative rows are matched by absolute strike before computing OI changes. The bounded same-strike data does not establish historical publication latency or dealer positioning. Present depth cannot fill missing historical books.

Orders use a precommitted limit and whole-lot size, a fee reserve, adverse minute bars and 5% volume participation; fills and target touches remain assumptions. One-, two- and three-minute delays do not measure one-second execution. Current fee envelopes are conservative approximations, not historical broker invoices.

Random-direction controls condition on the observed first-signal timestamps. Holm correction counts at least 80 variants, while the wider conversation contains more research choices. It cannot transform a reused period into independent validation.

This batch extends NIFTY expiry and ordinary-session research. It does not complete all nine earlier full-universe strategies. The event families still need complete timestamped disclosures, and CAS requires indicative-price and book histories.

[Frozen rules](../../readiness/PROTOCOL.md) · [Previous 64-variant experiment](../multifeature90/FINDINGS.md)

Source SHA-256: `149109cd5167b25b70197cd151f808567bc7cf4f0e0b9bc8c1a57d3afc9b6125`
Data SHA-256: `df6741ae2d587d98e28b58ac500d0c4eae58168c675f5d8861965eca56573639`
