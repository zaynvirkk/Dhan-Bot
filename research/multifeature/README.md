# Multi-source NIFTY research

Read the [results](../results/multifeature90/REPORT.md),
[registered rules](PROTOCOL.md) and [broker field inventory](CAPABILITIES.md).
This batch evaluates 64 separately funded variants in two consecutive
90-calendar-day windows. It is retrospective research, with conditional
candle fills and explicit UNKNOWN paths, not a live execution system.

Run from the repository root with the existing private data cache:

```bash
.venv/bin/python -m pytest tests/test_multifeature90.py tests/test_expiry_research.py tests/test_gauntlet.py tests/test_noise.py -q
.venv/bin/python -m research.multifeature.coverage
.venv/bin/python -m research.multifeature.replay --period earlier --quality reported
.venv/bin/python -m research.multifeature.replay --period earlier --quality strict
.venv/bin/python -m research.multifeature.replay --period recent --quality reported
.venv/bin/python -m research.multifeature.replay --period recent --quality strict
.venv/bin/python -m research.multifeature.noise
.venv/bin/python -m research.multifeature.report
```

Data acquisition is separate from replay. The ordered stages are
`research.multifeature.collect indexes`, `instruments`, `futures`, `dhan`,
`market`, then `research.multifeature.signals`, then
`research.multifeature.collect outcomes`. Run them with `.venv/bin/python -m`.
Account-access probes use `research.multifeature.audit`. Provider reads use
configured credentials without putting secrets in results. Research endpoints
are allowlisted and have no order submission path. Authentication uses the
shared Dhan session-token cache; repeatedly minting new tokens can invalidate
an in-progress collector's token.

Raw responses stay under Git-ignored `artifacts/private/gauntlet/`.
Exact option files reuse the existing expiry-research cache; futures and
derived features live in `multifeature90`. Source and input digests bind the
replay, controls and generated reports. Changing cached inputs or covered
source requires fresh replays and controls. Fixtures prove code behavior;
provider responses establish retrieved data, and neither proves a trade fill.

Each scope uses the same original bankroll, fees, whole-lot and volume limits.
No-trade cash is not profitable evidence. Removing the best trade reruns the
whole chronology, including later affordability. Missing history never earns
zero P&L by default. Strict retrospective quality gates invalidate affected
paths; the simulated bot cannot use a future audit to avoid a losing trade.

The original nine broad event/flow families are preserved separately. This
batch does not claim complete 90-day coverage of those full-universe families.
