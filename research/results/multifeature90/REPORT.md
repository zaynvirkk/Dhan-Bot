# Multi-source NIFTY 90-day experiment

**Conditional research only. No live winner is certified by candle-model P&L.**

Each of 64 variants starts independently with INR 9,411.18 in each consecutive 90-calendar-day window: 23 March–20 June and 21 June–18 September 2026. The same dates were previously examined, so these are retrospective comparisons, not untouched holdouts.

Computed 1536 execution scenarios and 45,908 conditional random-side paths. Raw option contract-day audits: {'UNKNOWN_VOLUME_MISMATCH': 347, 'UNKNOWN_OFF_TICK_PRICE': 40, 'RECONCILED': 1015}.

Variants passing both-window profit, best-trade deletion and multiplicity screen: none. This screen does not verify actual historical fills or account-specific RMS.

| Strategy | Earlier cash | Recent cash | Recent trades | Recent without best | Recent +5m feature lag |
|---|---:|---:|---:|---:|---:|
| EXPIRY_BASIS_LEAD_TARGET | 16,177.78 | 8,873.55 | 2 | 6,299.34 | 8,873.55 |
| EXPIRY_BASIS_LEAD_TRAIL | 8,217.63 | 6,156.02 | 2 | 6,637.19 | 6,156.02 |
| EXPIRY_CHAIN_UNWIND_TARGET | 1,279.99 | 4,673.53 | 6 | 2,920.73 | 11,981.37 |
| EXPIRY_CHAIN_UNWIND_TRAIL | 744.14 | 2,970.93 | 6 | 2,254.29 | 2,346.15 |
| EXPIRY_FUTURE_OI_TARGET | 9,411.18 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_FUTURE_OI_TRAIL | 9,411.18 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_FUTURE_TREND_TARGET | 1,068.77 | 2,781.16 | 7 | 2,141.00 | 2,781.16 |
| EXPIRY_FUTURE_TREND_TRAIL | 701.17 | 2,826.88 | 7 | 2,874.14 | 2,826.88 |
| EXPIRY_GIFT_CATCHUP_TARGET | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| EXPIRY_GIFT_CATCHUP_TRAIL | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| EXPIRY_INSTITUTIONAL_ALIGN_TARGET | UNKNOWN | 3,212.32 | 3 | 3,877.55 | 3,212.32 |
| EXPIRY_INSTITUTIONAL_ALIGN_TRAIL | UNKNOWN | 5,050.31 | 3 | 5,684.55 | 5,050.31 |
| EXPIRY_IV_CHEAP_TREND_TARGET | UNKNOWN | 6,762.33 | 1 | 9,411.18 | 9,411.18 |
| EXPIRY_IV_CHEAP_TREND_TRAIL | UNKNOWN | 6,762.33 | 1 | 9,411.18 | 9,411.18 |
| EXPIRY_LATE_BREAK_TARGET | 1,198.95 | 232.88 | 8 | 315.67 | 232.88 |
| EXPIRY_LATE_BREAK_TRAIL | 2,293.49 | 220.83 | 7 | 315.67 | 220.83 |
| EXPIRY_LATE_FADE_TARGET | 2,934.32 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_LATE_FADE_TRAIL | 3,168.22 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_OPTION_ACCEL_OI_TARGET | 1,427.48 | 2,169.57 | 2 | 4,816.85 | 2,169.57 |
| EXPIRY_OPTION_ACCEL_OI_TRAIL | 1,427.48 | 2,169.57 | 2 | 4,816.85 | 2,169.57 |
| EXPIRY_OPTION_ACCEL_TARGET | 1,490.78 | 2,169.57 | 2 | 4,816.85 | 2,169.57 |
| EXPIRY_OPTION_ACCEL_TRAIL | 1,490.78 | 2,169.57 | 2 | 4,816.85 | 2,169.57 |
| EXPIRY_ORB30_TARGET | 1,783.70 | 590.13 | 5 | 1,423.33 | 590.13 |
| EXPIRY_ORB30_TRAIL | 541.49 | 1,107.36 | 6 | 891.23 | 1,107.36 |
| EXPIRY_PAIN_ESCAPE_TARGET | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| EXPIRY_PAIN_ESCAPE_TRAIL | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| EXPIRY_PCR_CONFIRM_TARGET | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| EXPIRY_PCR_CONFIRM_TRAIL | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| EXPIRY_PUBLISHED_PAIN_TARGET | 9,411.18 | 16,579.28 | 1 | 9,411.18 | 16,579.28 |
| EXPIRY_PUBLISHED_PAIN_TRAIL | 9,411.18 | 8,930.01 | 1 | 9,411.18 | 8,930.01 |
| EXPIRY_PUBLISHED_PCR_TARGET | 4,091.37 | 2,320.38 | 3 | 3,899.39 | 2,320.38 |
| EXPIRY_PUBLISHED_PCR_TRAIL | 4,306.86 | 3,212.35 | 3 | 4,242.33 | 3,212.35 |
| EXPIRY_SECTOR_CONFIRM_TARGET | 1,508.52 | 6,444.35 | 5 | 3,779.42 | 6,444.35 |
| EXPIRY_SECTOR_CONFIRM_TRAIL | 1,392.01 | 3,928.96 | 5 | 3,400.91 | 3,928.96 |
| EXPIRY_SKEW_UNWIND_TARGET | 2,407.29 | 2,101.32 | 5 | 1,372.76 | 2,448.94 |
| EXPIRY_SKEW_UNWIND_TRAIL | 4,277.72 | 1,728.04 | 5 | 1,437.72 | 2,448.94 |
| EXPIRY_TREND1445_TARGET | 9,411.18 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| EXPIRY_TREND1445_TRAIL | 9,411.18 | 9,411.18 | 0 | 9,411.18 | 9,411.18 |
| ORDINARY_BASIS_LEAD_TARGET | 3,925.37 | 5,231.18 | 5 | 4,698.30 | 5,231.18 |
| ORDINARY_BASIS_LEAD_TRAIL | 4,536.11 | 4,760.13 | 5 | 4,227.25 | 4,760.13 |
| ORDINARY_CHAIN_UNWIND_TARGET | 2,616.71 | 10,843.71 | 9 | 4,961.24 | 3,115.61 |
| ORDINARY_CHAIN_UNWIND_TRAIL | 3,936.91 | 8,468.26 | 9 | 5,152.91 | 2,058.03 |
| ORDINARY_FUTURE_OI_TARGET | 9,411.18 | 7,859.77 | 1 | 9,411.18 | 9,411.18 |
| ORDINARY_FUTURE_OI_TRAIL | 9,411.18 | 7,859.77 | 1 | 9,411.18 | 9,411.18 |
| ORDINARY_FUTURE_TREND_TARGET | 2,350.65 | 1,274.23 | 16 | 1,228.19 | 1,274.23 |
| ORDINARY_FUTURE_TREND_TRAIL | 1,928.19 | 1,559.16 | 13 | 1,031.95 | 1,559.16 |
| ORDINARY_GIFT_CATCHUP_TARGET | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| ORDINARY_GIFT_CATCHUP_TRAIL | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| ORDINARY_INSTITUTIONAL_ALIGN_TARGET | UNKNOWN | 4,068.74 | 15 | 5,064.30 | 4,068.74 |
| ORDINARY_INSTITUTIONAL_ALIGN_TRAIL | UNKNOWN | 3,548.74 | 14 | 2,276.41 | 3,548.74 |
| ORDINARY_IV_CHEAP_TREND_TARGET | 8,381.88 | 7,471.01 | 5 | 6,108.33 | 7,471.01 |
| ORDINARY_IV_CHEAP_TREND_TRAIL | 8,381.88 | 7,471.01 | 5 | 6,108.33 | 7,471.01 |
| ORDINARY_PAIN_ESCAPE_TARGET | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| ORDINARY_PAIN_ESCAPE_TRAIL | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| ORDINARY_PCR_CONFIRM_TARGET | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| ORDINARY_PCR_CONFIRM_TRAIL | UNKNOWN | UNKNOWN | 0 | UNKNOWN | UNKNOWN |
| ORDINARY_PUBLISHED_PAIN_TARGET | 9,993.05 | 6,212.76 | 2 | 7,505.55 | 6,212.76 |
| ORDINARY_PUBLISHED_PAIN_TRAIL | 9,993.05 | 6,212.76 | 2 | 7,505.55 | 6,212.76 |
| ORDINARY_PUBLISHED_PCR_TARGET | 2,940.95 | 3,637.10 | 21 | 1,817.73 | 3,637.10 |
| ORDINARY_PUBLISHED_PCR_TRAIL | 2,485.34 | 1,408.99 | 11 | 1,693.29 | 1,408.99 |
| ORDINARY_SECTOR_CONFIRM_TARGET | 1,966.21 | 1,775.50 | 18 | 1,784.28 | 1,775.50 |
| ORDINARY_SECTOR_CONFIRM_TRAIL | 2,354.35 | 996.61 | 13 | 2,034.15 | 996.61 |
| ORDINARY_SKEW_UNWIND_TARGET | 9,411.18 | 11,908.11 | 1 | 9,411.18 | 9,991.45 |
| ORDINARY_SKEW_UNWIND_TRAIL | 9,411.18 | 11,908.11 | 1 | 9,411.18 | 9,991.45 |

## Interpretation and remaining evidence

UNKNOWN is a missing-input or unresolved-execution path, not a cash balance of 9,411 and not a zero-profit result. No-signal/no-fill balances are not evidence of an edge. Reported-candle diagnostics retain source discrepancies; strict paths reject volume mismatches, off-tick OHLC, invalid bounds and duplicate bars. These retrospective audit gates mark a result UNKNOWN; they are not live no-trade signals. No future EOD OHLC/OI, current smartlists, revised fundamentals, or current depth is inserted into historical signals.

Cross-broker checks matched 410,148 minute observations at the inferred same expiry/absolute strike/time; 249,645 close prices differed by more than one tick. Some difference may reflect feed sampling or candle construction; its cause is unresolved. Forty exact-contract days also contain off-tick OHLC prices. These are preserved in reported diagnostics, not silently rounded into valid source trades. See [coverage audit](data_coverage.json) and [price-grid audit](price_grid_audit.json). NSE specifies a [Re 0.05 NIFTY option price step](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50).

Dhan IV comes from rolling strikes re-keyed to absolute strike/time. Its weekly expiry identity is inferred from the request and previous exchange contract schedule, not returned in each row. Premium/OI/IV publication timing remains an assumption, tested with added lag. Upstox PCR/max-pain history is incomplete. Prior-day chain alternatives are separately named and use only the previous published NSE chain.

Broker metadata, fees and the candle execution model constrain affordability; they do not prove historical bid/ask or queue fills. Same-bar ambiguity is adverse. Fees are a conservative current envelope, not reconstructed dated invoices. No position is rescued with added money. A small negative final net cash represents modeled ruin plus fees.

The 64-trial correction understates the entire conversation’s prior strategy search. Random controls test direction conditional on observed candidate times; they are not new independent market observations. Expiry-only strategies have roughly thirteen opportunities per 90-day window, far fewer than ninety independent trading trials.

This expanded batch covers NIFTY expiry and ordinary sessions. It does not claim a 90-day full-universe replay of every earlier event/flow family. Their additional timestamped sources remain separate. CAS IEP/order-book history remains unavailable for a 90-day replay.

[Broker field inventory](../../multifeature/CAPABILITIES.md) · [Scoreboard](scoreboard.csv) · [Trade ledger](ledger.csv)

Source SHA-256: `02f908b59a3a1212b81447ae9c72c2ab0c3490641ed4d6ee4c10cafba40da766`
Data SHA-256: `532fd29dd6b672443b34cbe2a1f54e22c9ab3a44c2970ecf4895615c0c946992`
