# Final bounded F&O search — no funded candidate

Completed 26–27 September 2026. **No strategy is recommended for live trading.**

This pass reviews the major economic families, checks actual current Dhan capital requirements, and adds eight registered NIFTY late-expiry/long-volatility variants. It does not claim exhaustive testing of every strategy or completed coverage of all earlier nine broad families.

Each variant starts independently with **INR 9,411.18** in **23 March–20 June** and **21 June–18 September 2026**, two 90-calendar-day windows (59/63 sessions, 13 expiries each). Both windows were already used in research and are not independent holdouts.

| Variant | Earlier bankroll | Recent bankroll | Recent trades / wins | Recent max drawdown |
|---|---:|---:|---:|---:|
| EXPIRY_STRADDLE_1445 | 3,658.90 | 6,561.01 | 6 / 0 | 30.3% |
| EXPIRY_STRADDLE_1500 | 1,973.80 | 4,098.98 | 8 / 0 | 56.4% |
| EXPIRY_STRADDLE_1515 | 3,030.60 | 6,203.96 | 7 / 1 | 62.0% |
| EXPIRY_STRANGLE_1500 | 158.12 | 2,898.68 | 9 / 0 | 69.2% |
| EXPIRY_STRANGLE_1515 | 150.56 | 1,328.02 | 7 / 2 | 94.5% |
| EXPIRY_CHEAP_STRADDLE_1500 | 7,408.23 | 8,792.79 | 1 / 0 | 6.6% |
| ORDINARY_CHEAP_STRADDLE_1000 | 9,411.18 | 9,411.18 | 0 / 0 | 0.0% |
| EXPIRY_LATE_OI_EVACUATION | 9,411.18 | 9,411.18 | 0 / 0 | 0.0% |

**These are conditional reported-candle simulations, not actual executions.** All 16 primary strict-source paths remain UNKNOWN where an input fails audit. Unchanged balances in the conditional table have no filled trades and supply no profit evidence.

Computed **112 scenarios**: primary, two-/three-minute delay, next-open-plus-1%, extra exit slippage and best-trade deletion, plus separate strict primary paths. No same variant/scenario grows cash in both windows. No primary variant doubles its bankroll. Time-to-doubling is therefore not reached, not zero. The conditional control screen failed before its registered 999-path noise test; no new p-value or significance claim is made.

The largest alternative-model balance is INR 10,753.76 for the cheap-straddle rule in the earlier window with next-open-plus-1% entries. It does not survive as a winner in the recent window. This isolated result is retained in scoreboard.csv, not used to change the rule.

Many adverse-model pair entries fill only one leg. Those attempts incur a paid unwind; they are not discarded as no-trades. Minute highs and traded volumes cannot establish the exact probability of such fills. The alternative entry model also has no two-window winner.

Data: 341 exact option contract-days, 11 additional API request batches. Of these, 243 match NSE daily volume and 98 do not; 12 contain off-tick prices (categories overlap). 239 have neither type of issue. Warm-up uses only earlier index history. No source mismatch is repaired by future outcomes. Historical queue, spread, depth and subminute latency are absent.

The final code reserves exit charges even at tiny remaining cash, latches exit orders, caps liquidation attempts at three minutes, and makes unresolved holdings UNKNOWN. See [implementation notes](../../finalsearch/NOTES.md) for accounting corrections discovered during verification. Fixed strategy thresholds and clocks were not optimized.

## Fresh account and capital checks

Authenticated read-only Dhan calls verify INR 9,411.18 available and zero positions. The market was closed; the returned quotes are from 25 September and displayed quantities are zero. No order was submitted, and the calls do not establish fills or live latency.

| Current example, one lot | Indicative margin (INR) | Fits INR 9,411.18? |
|---|---:|---|
| NIFTY_FUTURE | 170,548.95 | No |
| BANKNIFTY_FUTURE | 189,055.73 | No |
| GOLDPETAL_FUTURE | 1,415.19 | Yes, before buffers |
| GOLDTEN_FUTURE | 14,113.02 | No |
| CRUDEOILM_FUTURE | 27,645.38 | No |
| NATGASMINI_FUTURE | 13,475.00 | No |
| SILVERMIC_FUTURE | 30,182.50 | No |
| NAKED_SHORT_CALL | 170,126.12 | No |
| CALL_DEBIT_50 | 37,893.96 | No |
| CALL_CREDIT_50 | 39,673.01 | No |
| PUT_CREDIT_50 | 36,855.26 | No |
| IRON_FLY_50 | 73,605.22 | No |
| LONG_BUTTERFLY_50 | 72,511.92 | No |
| CALL_CALENDAR | 58,013.93 | No |
| LONG_STRADDLE | 12,740.00 | No |

The small net debit or maximum payoff loss of a spread is **not** its broker margin. These are specific current-session examples, not historical margin or proof about every possible spread. Gold Petal is an affordable futures exception; it has no validated strategy result or confirmed commodity-account eligibility in this pass.

## Decision and scope

The prior 80 NIFTY variants and two 90-day event variants still have no qualified winner. The eight additions do not supply one. Stop this rapid all-in multiplication search without arming the funded account. This decision does not assert that every F&O strategy is unprofitable; larger-capital carry/volatility/trend strategies and untested families have different evidence and requirements.

[Full mechanism review and primary sources](../../finalsearch/RESEARCH.md) · [Frozen protocol](../../finalsearch/PROTOCOL.md) · [Reproduce](../../finalsearch/README.md) · [All scenarios](scoreboard.csv) · [Trade ledger](ledger.json) · [Capital receipts](capital.json)

Validated resolved trade rows across scenarios: 590. Tests demonstrate accounting and information boundaries, not real-market profitability.

Source SHA-256: `39483f66a107d732efa7c120845e2d4a0c98744db30619970dbfdbf1dbd6fb36`
Input SHA-256: `4716097ce7f3544ea7fdbd6580ec44004f7f154ddb586c15070f172c2e060edf`
