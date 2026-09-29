# Reproduce the intraday challengers

From the repository root, using the already populated multifeature/expiry
historical cache (private data and configured read-only Upstox access):

```bash
.venv/bin/python -m research.intraday_challengers.experiment prepare
.venv/bin/python -m research.intraday_challengers.experiment collect
.venv/bin/pytest tests/test_intraday_challengers.py
.venv/bin/python -m research.intraday_challengers.experiment evaluate
.venv/bin/python -m research.intraday_challengers.experiment controls
.venv/bin/python -m research.intraday_challengers.report
```

No command places orders. Historical HTTP reads use the existing bounded,
cached, allowlisted data client. Credentials are never part of public results.
Raw inputs are under `artifacts/private/gauntlet/`; results and ledgers are in
`research/results/intraday_challengers/`. Report generation rejects source or
data drift and verifies the original protocol registration hash.

The signal definitions were frozen before evaluating new option outcomes.
The sole implementation correction before outcome replay converted an even
sample median volume from float to Decimal. No thresholds were tuned after
seeing results. Existing experiments and their results are preserved.

Compared with the old benchmark execution model, this pass triggers all
target/stop orders on completed closes and executes only after processing
delay, reserves three exit slices' fees, and reruns the original benchmark
signals identically. It does not reproduce a resting target order. Candidate
order size and strike cannot depend on any subsequent bar; missing history
and incomplete liquidation remain UNKNOWN.
