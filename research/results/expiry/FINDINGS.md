# NIFTY expiry decision — 20 September 2026

**No strategy qualifies for the funded live bot.** The recent long-option variants lose money or make no trades. The only positive older candidate fails its extra-year and best-trade-deletion checks.

The Dhan account read confirms INR 9,411.18 available and withdrawable, with no open positions. Research did not place any orders. Every candidate starts with that same amount.

| Recent-period strategy | 2x target ending cash | Trailing-exit ending cash |
|---|---:|---:|
| Opening-range breakout | 1,112.37 | 510.17 |
| Afternoon breakout | 868.79 | 549.74 |
| Failed afternoon breakout | 9,411.18 — no fills | 9,411.18 — no fills |
| Selective 14:45 trend | 9,411.18 — no signals | 9,411.18 — no signals |
| Option acceleration | 2,169.57 | 2,169.57 |
| Acceleration plus OI decline | 2,169.57 | 2,169.57 |

These are **conditional reported-candle diagnostics** for July 20–September 18, not actual historical executions. Strict reconciled results retain UNKNOWN where archive discrepancies affect a path. No-fill balances are not profits.

The selective 14:45 trend/trailing rule initially reached INR 31,436.13 over October 2025–March 2026, with one loss and one 6.94x option trade. Deleting that winner leaves INR 5,143.23. Its additional October 2024–September 2025 check ends at INR 5,099.55. Over the full 101-expiry chronology it makes three trades, ends at INR 15,938.86, and falls to INR 2,817.04 without the best trade. Random direction matches or exceeds that full result in approximately 42.9% of controls. This is weak evidence for repeatability.

The twelve-variant batch covers 48 expiries; the unchanged trend candidate adds 53 earlier expiries. There are 51,948 conditional random-side paths across the primary and extension comparisons, with no new independent market observations created by simulation. Minimum Holm-adjusted primary-batch value: 0.300. The controls test direction/selection conditional on signal times; they do not establish that the timing rule is causal.

Execution scenarios include one/two/three full-minute delays, adverse-high or open-plus-1% entries, adverse stop precedence, low-minus-1% liquidations, fixed whole lots, a 5% participation ceiling and full fees. A performance-only binary search replaces decrementing lot sizing; exact before/after comparisons and boundary tests verify identical decisions and balances.

Some failed paths show a small negative net cash balance after final fees or repeated partial liquidation charges. This is modeled ruin plus a fee debit, not additional tradable capital or a successful strategy. The system does not replenish such balances. It also illustrates why the 5% reserve cannot guarantee coverage of every liquidation cost.

Data: 568 exact option contract-days and 213,780 minute rows, all expected minutes present. Of the original 552 contract-days, 408 reconcile exactly with NSE volume and 144 do not; all 16 additional-year contract-days have discrepancies. Reported-candle scenarios retain those trades and losses rather than selectively dropping them. Spread/depth, receipt-time OI and historical broker RMS remain unverified.

CAS is still a separate information problem: the inspected NSE September 8 CSV has 210 stock outcome rows with no observation timestamps and blank IEP/IEQ/imbalance fields. It cannot reconstruct the indicative NIFTY path. Regular spot is therefore never substituted for auction IEP.

A separate read-only margin check examined one-lot NIFTY September 22 23,350/23,400 call debit and credit spreads. Dhan returned indicative requirements of INR 36,115.30 and INR 37,893.70, above the funded balance. These are current-session examples using last reported prices while the market is closed, not historical expiry-day margin or proof about every possible spread.

Changing thresholds until this dataset produces a winner would turn the test into selection bias. The evidence supports collecting genuinely new auction/quote/receipt data for a separately frozen mechanism; it does not support enabling any of these tested rules with real funds.

Detailed artifacts: [all expiry results](REPORT.md), [scoreboard](scoreboard.csv), [primary ledgers](ledger.csv), [additional-year results](extension/REPORT.md), [additional-year ledgers](extension/ledger.csv). The original nine-family gauntlet and noise audit are preserved separately.

Current research source SHA-256: `681d142dbb1819b7aa61b0b52230cc189cbf4c61580e391fb0d1bf5a3e112200`.
