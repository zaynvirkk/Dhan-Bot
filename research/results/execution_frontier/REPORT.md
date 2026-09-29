# Execution and capital frontier — 28 September 2026

This pass directly tests whether a different enforceable order policy, puts, calls,
trend filters or bankroll allocation rescues the previously favorable overnight rules.
It does not claim to exhaust every F&O strategy. No live trading or deployment occurred.

Eight signal rules × three allocations × seven scenarios × three 90-calendar-day windows
= **504 attempted paths**. All start independently at INR 9,411.18. Dates are 23 December
2025–22 March 2026, 23 March–20 June 2026, and 21 June–18 September 2026.
All three windows have now been reused and are exploratory, not independent holdouts.

## What a limit can actually control

A fixed price cap and entry deadline can be specified before submitting an order.
The former whole-minute-high rejection is not an executable filter: a minute can open
below the cap, fill an order, and subsequently trade above it. The original May 29
example has a INR 212.10 cap, INR 204.45 open and INR 216.10 high. Rejecting the entire
bar can incorrectly omit the losing position. Nothing about that later high was
available when the order arrived.

The new base holds the fixed limit for three arrival bars; two-tick low penetration
models a fill at the limit, irrespective of the high. Entry timing is conservatively
the bar end. Volume-limited partial entry becomes UNKNOWN. This remains an OHLCV
scenario: no bid/ask queue, cancellation acknowledgement or subsecond fill is proved.

## Baseline at 95% allocation

| Rule | Dec–Mar | Mar–Jun | Jun–Sep | Trades across windows |
|---|---:|---:|---:|---|
| SELLOFF_CALL | 8453.62 | 7743.70 | 14615.88 | 3/4/5 |
| SELLOFF_PUT | 3744.00 | 7586.71 | 5060.64 | 3/2/1 |
| RALLY_PUT | 6795.08 | 1396.64 | 5058.63 | 1/2/1 |
| RALLY_CALL | 8014.13 | 15966.13 | 4005.25 | 1/2/2 |
| TWO_SIDED_REVERSAL | 8453.62 | 3650.92 | 12511.87 | 3/8/6 |
| TWO_SIDED_CONTINUATION | 3744.00 | 15923.89 | 2404.93 | 3/3/2 |
| TREND_PULLBACK | 8453.62 | 6990.11 | 12961.61 | 3/6/5 |
| TREND_CONTINUATION | 5015.11 | 10002.19 | 6728.72 | 1/2/1 |

Rule/allocation combinations profitable in all three base windows: **0 of 24**.
This is a bounded failure, not a theorem that puts, calls or reversal strategies never work.
At 25% allocation many paths cannot buy a qualifying lot; unchanged cash is not an edge.
At 50%, SELL_OFF_PUT (SELLOFF_PUT in the ledger) gives 9,468.82 / 11,001.02 / 9,411.18
in the base paths, with only 2 / 1 / 0 fills. The complete 25%/50% results and all
execution stresses are in the scoreboard and ledger, not omitted from ranking.

## Current broker margin survey

Read-only snapshot: available cash INR 9411.18; 0 positions.
Quoted 210 near-month stock futures; sampled the ten lowest quoted notionals.
Margin values are indicative for the current session, not historical margin paths.
A basket and its first purchased hedge leg must each fit; successful margin reads
do not guarantee acceptance, available liquidity or fill prices.

| Structure | Reported margin | Fits current cash | First hedge fits |
|---|---:|---|---|
| NIFTYFPI_FUTURE | 187847.0 | False | n/a |
| BANKNIFTY_FUTURE | 189055.73 | False | n/a |
| FINNIFTY_FUTURE | 170718.84 | False | n/a |
| MIDCPNIFTY_FUTURE | 202726.8 | False | n/a |
| NIFTY_FUTURE | 170548.95 | False | n/a |
| NIFTYNXT50_FUTURE | 203478.0 | False | n/a |
| VEDL_FUTURE | 107288.96 | False | n/a |
| TATAELXSI_FUTURE | 82257.31 | False | n/a |
| RVNL_FUTURE | 101116.305 | False | n/a |
| INFY_FUTURE | 77310.0 | False | n/a |
| KPITTECH_FUTURE | 101368.06 | False | n/a |
| POLICYBZR_FUTURE | 148869.7 | False | n/a |
| PIIND_FUTURE | 79692.81 | False | n/a |
| VOLTAS_FUTURE | 85733.81 | False | n/a |
| ICICIPRULI_FUTURE | 76849.695 | False | n/a |
| FORCEMOT_FUTURE | 127594.125 | False | n/a |
| GOLDPETAL_FUTURE | 1415.1875 | True | n/a |
| GOLDTEN_FUTURE | 14113.025 | False | n/a |
| GOLDM_FUTURE | 140822.5 | False | n/a |
| SILVERMIC_FUTURE | 30182.5 | False | n/a |
| CRUDEOILM_FUTURE | 27645.375 | False | n/a |
| NATGASMINI_FUTURE | 13475.0 | False | n/a |
| NIFTYFPI_CALL_DEBIT | 140118.0 | False | False |
| NIFTYFPI_CALL_CREDIT | 141603.0 | False | False |
| NIFTYFPI_PUT_DEBIT | 33594.0 | False | True |
| NIFTYFPI_PUT_CREDIT | 48433.0 | False | False |
| BANKNIFTY_CALL_DEBIT | 41198.16 | False | True |
| BANKNIFTY_CALL_CREDIT | 42960.06 | False | True |
| BANKNIFTY_PUT_DEBIT | 42333.66 | False | True |
| BANKNIFTY_PUT_CREDIT | 43537.86 | False | True |
| FINNIFTY_CALL_DEBIT | 38017.92 | False | True |
| FINNIFTY_CALL_CREDIT | 39741.12 | False | True |
| FINNIFTY_PUT_DEBIT | 38137.92 | False | True |
| FINNIFTY_PUT_CREDIT | 38994.12 | False | True |
| MIDCPNIFTY_CALL_DEBIT | 42333.36 | False | True |
| MIDCPNIFTY_CALL_CREDIT | 44002.56 | False | True |
| MIDCPNIFTY_PUT_DEBIT | 43611.36 | False | False |
| MIDCPNIFTY_PUT_CREDIT | 45004.56 | False | True |
| NIFTY_CALL_DEBIT | 36122.71 | False | True |
| NIFTY_CALL_CREDIT | 38083.11 | False | True |
| NIFTY_PUT_DEBIT | 36584.21 | False | True |
| NIFTY_PUT_CREDIT | 38088.96 | False | True |
| NIFTYNXT50_CALL_DEBIT | 126916.5 | False | False |
| NIFTYNXT50_CALL_CREDIT | 52146.75 | False | True |
| NIFTYNXT50_PUT_DEBIT | 106139.5 | False | False |
| NIFTYNXT50_PUT_CREDIT | 107399.75 | False | False |

Cash intraday 4x checks completed: 10 of 10 planned.
The separate completed cash probe follows earlier renewal failures. Fresh authentication
and read-only margin requests succeed; the original failures remain preserved.

| Cash intraday side | Notional | Indicative margin | Fits cash |
|---|---:|---:|---|
| RELIANCE_CASH_4X_BUY | 36780 | 7356.0 | True |
| RELIANCE_CASH_4X_SELL | 36780 | 7356.0 | True |
| HDFCBANK_CASH_4X_BUY | 37515.6 | 7503.12 | True |
| HDFCBANK_CASH_4X_SELL | 37515.6 | 7503.12 | True |
| SBIN_CASH_4X_BUY | 37354 | 7470.8 | True |
| SBIN_CASH_4X_SELL | 37354 | 7470.8 | True |
| INFY_CASH_4X_BUY | 37007.4 | 7401.48 | True |
| INFY_CASH_4X_SELL | 37007.4 | 7401.48 | True |
| TCS_CASH_4X_BUY | 37476 | 7495.2 | True |
| TCS_CASH_4X_SELL | 37476 | 7495.2 | True |

These probes confirm a currently affordable long/short cash implementation.
They do not establish historical eligibility, margin stability, borrow availability
for overnight shorts, or a profitable stock signal. These are intraday products.
[Completed cash-margin receipts](cash_capital.json).

A sample that does not fit rules out that structure at this snapshot, not every
strike, expiry or alternative account size. Affordable Gold Petal or cash leverage
expands the feasible research set; it supplies no directional forecasting edge.
Cash intraday exposure and a long option premium are different financing arrangements.
Selling options or using futures requires dated broker margin and MTM paths.

## Verification and remaining coverage

479 resolved scenario-trade rows reconcile fees, cash, timing, expiry and allocation.
69 paths are explicitly UNKNOWN. Strict source checks do not become no-trade wins.
No newly profitable all-window base candidate exists to advance from this batch.
Untested scheduled-event volatility, dated-margin commodity/cash strategies and
synchronized multi-leg pricing remain unvalidated rather than rejected by these results.
The research inventory explains what each distinct mechanism still needs.

[Frozen protocol](../../execution_frontier/PROTOCOL.md), [full ledger](runs.json),
[scoreboard](scoreboard.csv), [margin receipts](capital.json),
[research inventory](../../execution_frontier/RESEARCH.md).

Primary current mechanics: [Dhan order API](https://dhanhq.co/docs/v2/orders/),
[indicative margin API](https://dhanhq.co/docs/v2/funds/),
[Dhan RMS and cash leverage](https://dhan.co/risk-management-policy/).

Source SHA-256: `51d5fea305d847e7f4829502013c3caa583032d9d64544c9b8985d389d7b56c0`
