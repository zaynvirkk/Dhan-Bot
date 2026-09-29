# Noise audit and filing-content extension — 20 September 2026

This extends the frozen July 20–September 18 discovery experiment. The original
execution and signal thresholds remain unchanged. It does not relabel this
already examined interval as a holdout. No orders, spending or live activation.

1. Compile both directions at every original candidate timestamp, including
   losers. Preserve exact-contract identity for an unchanged forced-flow side;
   a flipped control uses the original selector. Orders and quantities depend
   on contemporaneous data and the current independent bankroll. Compilation
   stores future bars only for the execution simulator, never for selection.
2. Reproduce the existing baseline and five seeded controls exactly before
   trusting the accelerated implementation. Then run 999 matched-side paths
   per active strategy using seeds 0–998. For a completed baseline, report the
   fraction of completed controls that outperform it and lower/upper rank
   bounds treating unresolved controls as all below/all above. A stopped
   baseline has no terminal-return rank. These are conditional simulation
   diagnostics, not valid population p-values or clean-universe evidence.
3. Separately test post-signal underlying direction at fixed 15-minute horizon;
   report 5/30-minute sensitivity without selecting the best horizon. Entry
   reference is the next full minute OPEN, after the completed signal bar.
   Label price returns, not option returns. Aggregate simultaneous observations
   by date; use day-block sign randomization (9,999 draws) and day-block bootstrap
   confidence intervals (9,999 draws). Adjust primary 15-minute tests across
   all nine families using Holm's procedure; absent/no-signal families have
   no estimate, not a zero effect. This tests a conditional sign-symmetry null,
   not the event-time selection advantage or out-of-sample profitability.
4. Extend event information coverage by retrieving ALL 2,924 unique original
   attachments in the 726 qualifying and 2,199 ambiguous NSE F&O metadata
   records, rather than choosing named winners. Preserve dissemination time,
   content hash, parse failures and provenance. Missing/scanned/encrypted or
   ambiguous documents remain UNKNOWN.
5. Freeze content categories before parsing: financial results; actual business
   acquisitions; material orders; guidance; regulatory decisions; KMP/senior
   management changes. Exclude SAST/insider ownership reporting from business
   acquisitions. A category match is a reproducible classifier, not an expert
   judgment of materiality. New signals from this extension remain discovery
   and are never counted as independent confirmation of the original model.

The five original zero-signal variants remain separate NO_SAMPLE findings.
Their narrower universes are unchanged until their missing inputs are actually
obtained. Historical order/depth and IEP paths, account-specific RMS, and a
genuinely untouched validation period remain distinct coverage requirements.

## Input-coverage amendment before content replay

At 23:55 UTC September 19 (September 20 IST), an outcome-independent inventory
of exchange subject categories found explicit mergers, regulatory actions and
other operating disclosures outside the old metadata regex. Before any content-
variant bankroll was computed, `noise/universe.py` froze 33 additional subject
categories for collection. This adds 515 announcement records / 490 distinct attachment references (one
already in the original set), bringing the extraction pass to 3,413 references.
The six original content-classification regex categories and price/execution
rules remain unchanged. Merely collecting a credit-rating or business-update
attachment does not automatically qualify it; unrecognized content stays UNKNOWN.
Remaining administrative/reposted metadata categories are still outside scope.
This coverage amendment is disclosed discovery work, not an unchanged holdout.

The two content variants also receive 999 matched random-side controls each,
using the same execution and unresolved-path rules. They remain separate from
the 3,996 original controls, for 5,994 total controls if all six active variants
finish. No positive revised bankroll can win on discovery returns alone.
