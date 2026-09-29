# NIFTY expiry research

Run from the repository root. This package has no broker order endpoint.
The funded account was checked read-only on 20 September 2026: available and
withdrawable cash INR 9,411.18; no open positions. Private redacted receipts
are in `artifacts/private/gauntlet/expiry_research/account_*.json`.

The frozen [protocol](PROTOCOL.md) defines 12 independent candidate variants
and four blind controls. [Results](../results/expiry/REPORT.md),
[scoreboard](../results/expiry/scoreboard.csv) and
[ledgers](../results/expiry/ledger.csv) distinguish strictly reconciled inputs
from conditional reported-candle diagnostics. No result is an exchange fill.

## Reproduction

```bash
.venv/bin/python -m research.expiry.collect setup
.venv/bin/python -m research.expiry.collect plan
.venv/bin/python -m research.expiry.collect download
.venv/bin/python -m pytest tests/test_expiry_research.py -q
.venv/bin/python -m research.expiry.replay --period development --quality reported
.venv/bin/python -m research.expiry.replay --period development --quality strict
.venv/bin/python -m research.expiry.noise --period development --quality reported --controls 999
```

Repeat the replay and noise commands for `recent_validation`,
`older_validation` and `all`, then run:

```bash
.venv/bin/python -m research.expiry.report
```

The report checks current source/data hashes, cash chronology, whole-lot
quantities and trade arithmetic. Raw licensed data remains in ignored private
storage. Adding data changes the data digest and requires refreshing results.
Registration is a record of the rules before outcome inspection, not a
statistical guarantee or an operator permission gate.

## Sources and limits

- [Upstox exact expired instruments](https://upstox.com/developer/api-documentation/expired-instruments/): exact contract metadata and one-minute OHLCV/OI.
- NSE official daily F&O bhavcopies: prior-session listed contracts, historical lots and daily traded quantity reconciliation. Receipt URLs/hashes are retained privately.
- [NSE CAS modalities](https://www.nseindia.com/static/products-services/closing-auction-session): cash-auction and derivative session distinction.
- [NSE CAS archive](https://www.nseindia.com/static/reports/closing-auction-session-historical-data): the downloaded September 8 file contains 210 stock outcome rows, no observation timestamps and empty IEP/IEQ/imbalance fields. It cannot recreate a NIFTY indicative-index signal.
- [Downstox's own September 8 recording description](https://downstox.com/closing-auction/history/2026-09-08): describes captured stock snapshots; a complete certified NIFTY indicative-index plus option-book replay was not obtained.
- [Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf): motivates limiting trials and distinguishing retrospective selection from independent validation. This package does not claim to implement that paper's PBO estimator.

Bar timestamps imply availability at the minute's end, with additional
execution-delay scenarios. Original historical message-receipt timestamps,
spread/depth/queue state, OI dissemination delays and Dhan RMS decisions are
unavailable. Complete candle coverage and matching daily volume do not prove
that a particular order filled. The retrospective validation blocks precede
CAS; prospective validation is still required for the new regime.
