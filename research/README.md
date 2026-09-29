# Strategy gauntlet

The [execution/capital frontier](results/execution_frontier/REPORT.md) directly
tests fixed resting limits, both CE/PE directions, symmetric reversal and
continuation, trend filters and 25%/50%/95% allocations. Twenty-four
rule/allocation combinations × seven scenarios × three reused 90-day windows
give 504 attempted paths; none profits in all three base windows. Forty-six
read-only margin checks broaden coverage beyond one NIFTY spread example.
Ten subsequent cash intraday margin probes succeed after earlier credential
renewal failures: sampled 4x long/short exposure fits current cash.
[Mechanism inventory](execution_frontier/RESEARCH.md) keeps
untested cash, event-volatility and commodity lanes distinct from failed tests.

The [rebound qualification](results/rebound_validation/REPORT.md) tests the
conditional leader over an additional 90-day period with full-session
monitoring, dated fees, alternate fills, matched-date controls and Dhan
reconstruction. It fails the funded qualification gates: additional-period
INR 8,570.94 with dated fees; earlier alternative entry INR 8,255.83.
The favorable discovery results remain conditional. No live activation.
[Reproduce](rebound_validation/README.md).

The [broader search](results/broader/REPORT.md) adds 26 variants across two
90-day windows: overnight options, cross-sectional stock signals and longer
holds. The conditional recent leader is NIFTY overnight selloff-rebound at
INR 16,762.25; earlier INR 14,663.22. Stress and noise results, unresolved data,
3,996 controls and the full ledger are reported. No funded qualifier.
[Reproduce](broader/README.md); all 227 tests pass.

The [final bounded search](results/finalsearch/REPORT.md), completed 27 September,
adds eight late-expiry/long-volatility variants, 112 scenarios and actual Dhan
capital checks. None profits in both 90-day windows. The
[mechanism review](finalsearch/RESEARCH.md) distinguishes failed tests, capital
constraints and untested families. No funded activation is recommended.
[Reproduce](finalsearch/README.md); all 209 tests pass.

The [ninety-day event extension](results/event90/FINDINGS.md) replays the two
frozen attachment-based event variants from 21 June to 18 September. The
intraday primary model ends at INR 3,453.01; the overnight model reaches
INR 3,913.33 before an unresolved exit, so its final bankroll is UNKNOWN.
Completed 1,998 random-side controls and nine full/compiled parity checks per
engine. Neither qualifies for live trading. Three ban dates, inconsistent
option histories and historical execution conditions remain unresolved.
[Reproduce this extension](event90/README.md); the earlier period is reused,
not a new independent holdout.

The [latest NIFTY reversal/compression experiment](results/readiness/REPORT.md)
adds 16 variants, 320 execution scenarios and 13,972 random-direction paths
over the same two 90-calendar-day windows. None profits in both windows;
none qualifies for funded use. [Current API/cloud readiness](../docs/RELEASE-READINESS.md)
records real read-only checks and the separate remaining deployment obstacles.

The latest [multi-source NIFTY findings](results/multifeature90/FINDINGS.md)
cover 64 variants in two consecutive 90-calendar-day windows. None establishes
a repeatable edge. See the [actual broker field inventory](multifeature/CAPABILITIES.md)
and [reproduction commands](multifeature/README.md). Missing paths remain UNKNOWN;
this is not full 90-day validation of the earlier nine broad families.

The previous [NIFTY expiry findings](results/expiry/FINDINGS.md) cover twelve
fixed variants, 48 expiries and an additional 53-expiry check of the only
positive older candidate. No strategy qualifies for funded live execution.
Reproduction and data limits: [expiry research](expiry/README.md).

Read [STATUS.md](STATUS.md) and [the protocol](gauntlet/PROTOCOL.md) before using
any result. The nine bounded discovery variants have a reproducible comparison;
the full-family validation remains incomplete and no strategy is a validated winner.

The collector uses the already configured Upstox analytics token for allowlisted
historical GET requests. It never submits broker orders. Licensed raw responses,
publication records and replay ledgers live under ignored `artifacts/private/gauntlet/`.

From the repository root:

```bash
.venv/bin/python -m pytest tests/test_gauntlet.py
.venv/bin/python -m research.gauntlet.nonexpiry run --limit 21415 --batch
.venv/bin/python -m research.gauntlet.reconcile_forced
.venv/bin/python -m research.gauntlet.forced
.venv/bin/python -m research.run_suite --wait-for-reconciliation
.venv/bin/python -m research.report
.venv/bin/python -m research.status
.venv/bin/python -m research.snapshot_inputs
```

The non-expiry scan resumes completed contract-days. Inspect
`nonexpiry_progress.json` and its `UNKNOWN` records before reusing results.
An authentication error or three consecutive source failures stops that batch;
reconnection is not fabricated. No paid subscription or account change is made.

The finishing sweep resumes completed runs only when source, signal and ban-list
digests still match. It runs every declared family independently, plus delays,
best-trade deletion and five random-side diagnostics for variants with signals.
The other candidate input files must already exist; no missing source is treated
as an empty strategy. Implemented scopes are narrower than the requested full families.

For a single replay, use `.venv/bin/python -m research.gauntlet.replay --engine
EVENT_CONTINUATION --delay 1 --delete-best` (on one command line).
`--delay 2`, `--delay 3` and `--open-model` are explicit execution scenarios.
One-minute source candles cannot identify subsecond or 1/3/5-second fills.

Tests prove deterministic information boundaries and accounting behavior,
not profitability, completeness of market data or actual order execution.

The report validates every ledger's cash arithmetic and chronology before writing
derived CSVs. It retains unresolved paths and gap records. A last resolved cash
balance before an unliquidated position is never a terminal bankroll. No-trade
subvariants cannot be selected as profitable winners.

The follow-up [noise-audit protocol](noise/PROTOCOL.md) adds 999 independently
compounded random-side controls per active original variant, day-clustered
underlying-return diagnostics, and original NSE attachment classification.
It does not reuse the discovery period as an untouched holdout.
The two expanded event variants receive 999 additional controls each. The full
noise pass has 5,994 controls across the original and revised variants; they
are reported separately, with unresolved paths retained.

Run the following in order (the direction and filing collectors may run while
the original observations compile; complete compilation before starting paths):

```bash
.venv/bin/python -m research.noise.compile
.venv/bin/python -m research.noise.paths
.venv/bin/python -m research.noise.direction
.venv/bin/python -m research.noise.filings
.venv/bin/python -m research.noise.content
.venv/bin/python -m research.noise.report
.venv/bin/python -m pytest tests/test_gauntlet.py tests/test_noise.py
```

The attachment collector uses a shared two-request-per-second ceiling and ten
workers, reads bounded PDF/XML archives without extracting archive paths, and
retains corrupt/unreadable references as UNKNOWN. Existing valid text is reused
when raw/text hashes match. It never uses future returns to choose documents.
The content extension redirects its candidate files and full replay outputs to
the private `noise/` subdirectory, preserving the original v5 results.

Derived results: [noise audit](results/NOISE-AUDIT.md),
[all control paths](results/noise_paths.csv),
[directional statistics](results/directional_noise.csv), and
[filing coverage](results/filing_coverage.json). These remain conditional model
results; historical queue fills, complete broad-family coverage and independent
validation are not established by passing software tests.
