# Reversal, compression and prior-position concentration experiment

Registered 21 September 2026 before this batch's signals/outcomes. This is a
retrospective extension, not a fresh holdout. Existing unsuccessful experiments
remain in the search history. The objective is a separately funded strategy,
starting with INR 9,411.18; no broker orders or funded activation are authorized.

Same two 90-calendar-day windows: 23 March–20 June and 21 June–18 September
2026. Every new rule is split into expiry/ordinary sessions and TARGET/TRAIL,
for 16 variants. Use the existing whole-lot, fees, fixed-limit, partial-fill,
50%-premium-stop and 2x target/50%-trailing execution model. First qualifying
signal per day, including losing and unfillable signals; scan completed minute
bars 10:00 through 15:10. No retry or later strike substitution after an order
miss. Latest data cannot be used to skip a historically missing earlier signal.

Four signal definitions:

* FAILED_ORB: Three consecutive spot closes have broken the completed first
  thirty-minute range by at least 0.05%. After that first break, two completed
  closes return inside that fixed range. Trade opposite the first break only
  if futures' last two price changes agree, and last-three-minute futures
  volume is at least twice three times the preceding twenty-minute median.
  The broken-side state can be formed before 10:00; earliest order signal 10:00.
* VWAP_RECLAIM: Fifteen prior futures closes, ending two minutes before the
  decision, are all on one side of their own then-known session VWAP. The
  latest two futures closes cross and stay on the other side of their own
  current VWAP; last two spot changes agree. Same futures-volume confirmation.
  VWAP approximates traded VWAP with completed typical price times bar volume.
* COMPRESSION_BREAK: Spot range across the preceding thirty bars (excluding
  the latest three) is at most 0.10% of its middle. Latest three spot closes
  all break one edge by at least 0.02%; futures three-minute direction agrees
  and the same futures-volume confirmation holds. No future daily range,
  percentile or optimized threshold enters the rule.
* PRIOR_OI_WALL: At 09:30 select the largest prior published CE OI and PE OI
  strikes within 200 points of then-known spot, ties to lower strike. Freeze
  those two identities. Spot crosses and stays beyond the corresponding
  strike for two closes (up CE/down PE), futures three-minute direction
  agrees, same absolute option's Dhan OI falls at least 8% and premium rises
  at least 25% in three minutes. OI does not identify dealer gamma or prove
  short covering. No final OI or today's largest-position list is used.

Replays: strict and reported data modes, 1/2/3-minute order delays,
open-plus-1% alternative, and best-trade deletion with full resimulation.
499 random-side controls per evaluable variant/window, 3,999 if positive in
both windows after best-trade deletion. Holm correction includes these 16
plus at least the previous 64 comparisons (80 minimum); the entire prior
conversation increases that search burden. No winner without repeatable
net profit, execution stability, complete input coverage and new prospective
evidence. No claim of exhaustive coverage of all possible strategies.

Source signals use existing authenticated Dhan/Upstox history. New option
tapes are requested for both sides after first signals are fixed. Strict
NSE-volume and price-grid audits are retrospective evidence checks, never
live no-trade filters. All outcome receipts retain data/source digests.
