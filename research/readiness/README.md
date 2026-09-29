# Reproduce the readiness research

The [protocol](PROTOCOL.md) freezes four rules, each split into expiry and
ordinary sessions with two exit styles. Each uses both previously inspected
90-calendar-day windows. No new independent holdout is claimed.

Run from the repository root with the existing private input cache:

```bash
.venv/bin/python -m pytest tests/test_readiness_research.py -q
.venv/bin/python -m research.readiness.experiment prepare
.venv/bin/python -m research.readiness.experiment collect
.venv/bin/python -m research.readiness.experiment replay
.venv/bin/python -m research.readiness.experiment noise
.venv/bin/python -m research.readiness.report
```

`prepare` fixes every first signal and both-side contract requests before
`collect` retrieves new option tapes. Inputs under
`artifacts/private/gauntlet/multifeature90` come from the
[previous source collector](../multifeature/README.md). Credentials remain in
ignored private files. Outcome collection makes only market-history reads.

`replay` produces 320 scenarios. `noise` tests random directions at the same
signal times, including cash/lot/entry/exit path dependence. The report verifies
all source/input digests, whole lots, fees and ledger algebra. UNKNOWN does not
mean no trade. Reported-candle diagnostics retain source conflicts; strict
quality marks affected paths unresolved rather than skipping them.

[Individual bankrolls](../results/readiness/REPORT.md) ·
[Current live API/cloud audit](../../docs/RELEASE-READINESS.md).
Live audits happened while the market was closed; socket pings, stale depth
and REST request duration do not establish executable fills or order latency.
The production CAS daemon is a separate implementation, with a different
bankroll policy. There is no qualified strategy or funded deployment approval.
