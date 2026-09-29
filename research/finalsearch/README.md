# Reproduce the final bounded search

Read [PROTOCOL.md](PROTOCOL.md), [NOTES.md](NOTES.md) and
[RESEARCH.md](RESEARCH.md). Actual results: [REPORT.md](../results/finalsearch/REPORT.md).

From the repository root, using the previously collected, private historical
inputs from the multifeature and expiry experiments:

```bash
.venv/bin/python -m research.finalsearch.experiment prepare
.venv/bin/python -m research.finalsearch.experiment collect
.venv/bin/python -m research.finalsearch.experiment replay
.venv/bin/python -m research.finalsearch.report
.venv/bin/python -m pytest tests/test_finalsearch_research.py -q
```

Collection calls only allowlisted historical market-data endpoints and reuses
audited exact-contract tapes. Raw licensed data remains in ignored artifacts.
Plan construction registers rules before option-outcome inspection. The
report checks source/input/protocol hashes and every resolved cash/lot ledger.

The read-only current-capital experiment is separately reproducible with
`.venv/bin/python -m research.finalsearch.capital`. It requires the saved Dhan
authentication and current public instrument master. It calls funds, positions,
quotes and margin calculators, **never orders**. Its September 2026 contract
sample must be refreshed before reuse at another date; current margins are
session-specific. No credential or account identifier belongs in public output.

No repeat run of this retrospective experiment creates an independent holdout.
There is no automatic deployment or order path in this package.
