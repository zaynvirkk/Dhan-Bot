# Rebound validation — registered 27 September 2026

Parent: NIFTY_SELLOFF_REBOUND_1510 in research/broader. Preserve that experiment.
This is a deployment qualification attempt, not a search for new thresholds.
No orders, deployment, subscriptions, cloud changes or automatic activation.

## Locked candidate and data partitions

At 15:10 IST use only the completed 15:09 NIFTY bar and 09:15 open.
Buy CE only if close/open - 1 <= -0.0075. Nearest expiry strictly later than
the next scheduled trading session; nearest ATM then at most three OTM.
Prior published exchange contracts define the eligible chain. Actual dated
lot, tick and freeze are checked against broker metadata. Whole lots,
95% of available bankroll including fees, reserve three exit slices,
known three-minute minimum volume participation 5%, OI at least ten lots,
fixed entry limit known close +5%. All paths start independently at 9411.18.

The original March 23–June 20 and June 21–September 18 windows remain discovery.
First additional 90-calendar-day retrospective validation: December 23, 2025
through March 22, 2026. Some February/March underlying history was previously
used as warm-up; this is previously unscored strategy history, not a claim of
a pristine prospective holdout. No option outcomes in this interval may be
used to change thresholds or pick a substitute validation interval. If a
provider lacks history, that evidence is UNKNOWN, not a failed strategy or
permission to choose more flattering dates. A separate prospective period
starts after this registration; it cannot be manufactured today.

## Version 2 monitoring correction

Monitor ALL completed option minutes through the actual derivatives close:
15:30 before 3 August 2026; 15:40 thereafter (NSE FAOP74467). Resume at the
next trading session's first completed minute. Entry one full minute after
decision at adverse high, or a declared alternative open plus 1%. Exits after
a completed close reaches 2x or 0.5x actual entry, with one full minute
processing delay, low minus 1%, up to three volume-limited slices. Timed
liquidation starts next session at 15:10 (known before entry). A trigger near
the close remains latched through the overnight closure and executes at
the next eligible minute; no assumption of an overnight stop fill. Partial
exit orders remain pending through closure. Never reset a pending stop.
Minute-bar fills remain scenarios, not actual exchange executions.

No second entry on a day on which a preceding position exits, preserving
the parent's cash/busy policy. Fixed limits and quantities precede future
execution data. No retry at a farther strike after a limit miss. Unresolved
positions or missing holding bars stop a path with final bankroll null.
Zero-trade bars can be carried only when the complete official daily volume
matches the source. Mark the resulting quote as zero volume. Missing data
cannot be used to reject an otherwise losing trade and continue the bankroll.

Keep the parent's conservative current fee envelope for direct comparisons;
label pre-effective-date fee use explicitly. It is not an exact historical
broker invoice. Re-run dated actual rates separately before qualification.

## Registered falsification checks

For each partition run: base, three-minute processing, twice exit slippage,
open-plus-1% entry, best-profit trade deletion with full chronological sizing,
and strict source audit. Reconstruct full relevant selected/rejected contract
paths from Dhan separately when available; match actual strike and expiry at
every rolling observation. Never splice a rolling ATM stream as a fixed
contract or average disagreeing duplicate values. Report price, tick, OHLC
range and total traded-volume differences against official NSE records.

Compare to 999 fixed-seed random CE-entry date selections, matched on entry
clock, expiry distance and prior-only 20-session realized-volatility bucket.
Matching candidates are chosen without option outcome data. Preserve signal
count and chronological capital/busy constraints. Report unsupported matches
and missing control outcomes as uncertainty bounds. Random side on original
event dates is a separate control. Prior search multiplicity is >=144;
no raw p-value will be presented as independent proof after that search.

## Decision gates and work order

1. V1: collect the registered additional period and full-session tapes;
   preserve original results, record hashes and coverage failures.
2. V2: replay unchanged signal under the corrected monitoring and execution
   stresses; independently reconstruct relevant Dhan paths and noise controls.
3. V3: implement a connected overnight production candidate only if evidence
   passes; test durable recovery, stale data, authentication, partial fills,
   wrong account/contract, duplicate sends, cash caps and disarming.
4. V4: read-only account/cloud preflight and order-free live shadow collection;
   market-hours observations and prospective outcomes remain dated evidence.
5. V5: only a qualifying concrete build may request funded deployment approval.

Qualification requires positive base and registered execution-stress results
across discovery and additional validation, resolved material source conflicts,
credible matched-control evidence plus independent prospective evidence,
and passing connected operational tests. A negative or unresolved gate means
NO LIVE QUALIFIER. Do not optimize a failed rule until it passes, build a
funded trader around a failed candidate, or ask approval to bypass a gate.

Exact software acceptance: `.venv/bin/python -m pytest -q tests/test_rebound_validation.py`.
Then full `.venv/bin/python -m pytest -q`. Cover future-bar exclusion,
contract identity, full-session late triggers, overnight pending exits,
unknown holding/partial exits, unchanged original evidence, chronological
whole-lot cash, and matched-control construction. Tests prove behavior only.
