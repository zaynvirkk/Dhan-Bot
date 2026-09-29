# Indian trading literature review

Started 2026-09-28 at the operator's explicit request. Status: ACTIVE, coverage
incomplete. This review reopens research, not live trading authority.

## Question

Which published, reproducible mechanisms could improve net terminal wealth
for a small Indian brokerage account, using information available before each
order? Separate stock/index signals from their cash, futures and option
implementations. A profitable underlying signal does not establish profitable
long options. Capital, tail losses, costs and execution are part of the claim.

## Search and coverage

Start with all eight operator URLs, deduplicate mirrors by DOI/title/authors,
then search primary publishers, authors' repositories, SSRN and Scholar.
Trace relevant references and later studies, including contrary findings.
Record search strings, access failures, full-text versus abstract-only status,
and an explicit remaining queue. No claim to have read every paper or exhausted
the literature. Search coverage is distinct from full-text methodological review.

Families: technical rules; intraday momentum/reversal and opening ranges;
overnight returns; cross-sectional momentum/value; earnings/disclosures;
pairs/statistical arbitrage; expiry/settlement; volatility risk premium and
event volatility; options information/OI; cross-market lead/lag; calendar and
passive flows; commodity/currency strategies; execution and research methods.

## Extraction and evaluation

For each retained paper record identity, version/date, sample/universe,
frequency, exact rule when disclosed, timing boundary, costs, shorting/margin,
validation and multiple-testing controls, source location, limitations and
applicability. UNKNOWN is not absent: do not infer full methodology from an
abstract, headline, reference list or citation count. Distinguish author's
reported result from our reproduction. Mirrors are one study, not replications.

Triage: REPLICATE (specific testable mechanism), CONTEXT (relevant but not an
executable claim), ACCESS_PENDING (insufficient body), or LOW_PRIORITY (reason
stated). This is a research queue, never a live-profit rating.

## Replication boundary

Freeze an implementable rule before testing. Track every tried specification;
purge overlapping labels and use only prior-time fitted features/relationships.
Already examined 2025-12-23 through 2026-09-18 windows are exploratory, not a
fresh holdout. Use point-in-time instruments, dated rules/costs, actual option
contracts, causal selection, whole lots and chronological cash accounting.
At least 90 days per strategy is a floor, not sufficient statistical evidence;
use longer, multiple regimes where data and signal frequency require it.
Evaluate fills with observable order rules; future high/volume must never
choose which orders to submit. Preserve partial/unknown executions as unknown.

No new backtest return is credited by this literature review. No purchases,
subscriptions, orders, deployment or broker mutations are authorized here.

## Persistence

Public notes and register live here. Downloaded source bodies and extraction
receipts are private research material under
`artifacts/private/gauntlet/literature/`; do not redistribute papers. Preserve
source URLs, hashes and read coverage. Continue from QUEUE.md, not memory.
