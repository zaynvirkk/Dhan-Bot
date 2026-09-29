# Reproduce the ninety-day event extension

This extends the two frozen event variants to 21 June–18 September 2026,
with warm-up from 15 May. The inspected July–September period is reused;
these results are not an untouched holdout. See [protocol](PROTOCOL.md).

From the repository root, using the existing private source cache and
configured read-only historical-data credentials:

```bash
.venv/bin/python -m unittest tests.test_event90_research
.venv/bin/python -m research.event90.experiment bootstrap
.venv/bin/python -m research.event90.experiment recover_bans
.venv/bin/python -m research.event90.experiment market
.venv/bin/python -m research.event90.experiment filings
.venv/bin/python -m research.event90.experiment signals
.venv/bin/python -m research.event90.experiment compile
.venv/bin/python -m research.event90.report
```

Market history and attachment collection may run independently. All later
stages depend on their completed outputs. The new scope lives under ignored
`artifacts/private/gauntlet/event90`; existing raw option responses are reused.
Older inputs and results are preserved. No order or deployment endpoint is
part of the collector or replay.

The report compares the complete reference replay with the compiled replay
for nine paths per engine, including random-direction paths. It emits all
signal decisions, four execution scenarios, strict data-coverage diagnostics,
best-profitable-trade deletion where applicable and 999 random-side controls
per bot. These controls preserve chronological cash and whole-lot constraints.
Unresolved random paths widen the reported rank bounds.

Only the explicitly specified attachment-category variant is tested. Missing
ban records, tape gaps, ambiguous filings, historical broker restrictions and
unobserved execution conditions prevent a whole-family bankroll or live
approval. [Results](../results/event90/FINDINGS.md) and their source/input
digests are generated after the replay; fixture tests are not market evidence.
