# Multi-source 90-day NIFTY experiment — registration 20 September 2026

Each strategy starts independently with INR 9,411.18. Primary window:
21 June–18 September 2026 (90 calendar days); earlier comparison:
23 March–20 June 2026 (90 calendar days). These overlap previously researched
history and are retrospective comparisons, not untouched holdouts. No live
orders, paid subscriptions or engine activation. Expiry-only strategies see
all sessions but can act only on actual exchange expiry dates.

The old six NIFTY signals and their TARGET/TRAIL exits remain comparison
baselines. Eight additional mechanisms use the actually retrievable fields:

* FUTURE_TREND: spot 15-minute move >=0.10%, futures move agrees, future
  close is beyond its session VWAP in that direction. Scan every five minutes
  10:00–15:10; one first signal per day. VWAP uses completed candle typical
  prices and volume, explicitly an approximation to trade VWAP.
* FUTURE_OI: same, plus same future OI rises >=1% over five minutes.
* BASIS_LEAD: future five-minute move >=0.10%, future/spot basis changes
  >=0.05% in that direction, two latest spot close changes confirm direction.
* IV_CHEAP_TREND: FUTURE_TREND plus Dhan ATM IV <= annualized realized
  volatility of the last 30 completed spot minute returns, and India VIX is
  no lower than 15 minutes earlier. No historical Greek is invented.
* SKEW_UNWIND: same exact ATM option premium +25% and OI -8% in three
  minutes, opposite same-strike premium -10%, futures five-minute direction
  agrees. Strike identity must exist at both observations.
* SECTOR_CONFIRM: NIFTY 15-minute move >=0.10%, bank and IT index
  15-minute moves each >=0.05% in the same direction.
* GIFT_CATCHUP: two-minute-delayed GIFT 15-minute move >=0.15%, NIFTY
  has moved less than half that amount in the same direction, and its last
  two close changes confirm. No before-launch Upstox feed is assumed.
* CHAIN_UNWIND: fixed current ATM and its two nearest strikes, each observed
  now and five minutes ago at the SAME identities: selected-side aggregate
  OI -5%, opposite +5%, ATM premium +15%, future direction agrees.

New signals are scored both as expiry-only and ordinary-session-only strategies,
each under TARGET and TRAIL. This is 32 new variants plus 12 old comparisons.
No threshold tuning after outcomes. Paired nested rules are ablations: futures
trend vs futures+OI vs futures+IV/VIX. Combined filters need not be independent.

Data: exact dated NSE instruments/lot sizes and Upstox fixed-contract option and
future candles; Dhan rolling minute OHLC/OI/IV/strike/spot; Upstox NIFTY,
bank/IT/VIX and GIFT candles. Relative-strike series must be decoded to timestamp,
expiry and absolute strike before computing changes. Dhan/Upstox quote
disagreements and absent fields remain visible, never forward/backfilled from
future observations. Future near-month identity comes from prior NSE data.
All completed inputs must be available by decision time; OI/IV reporting lag
is additionally stressed by five minutes. GIFT has an explicit two-minute age
allowance; missing vendor history means UNKNOWN, not zero signals.

Contract selection, fixed order limits/whole lots, fees, adverse high entry,
low-minus-1% exits, 5% participation, delayed order scenarios, partial exits and
best-trade deletion reuse the tested expiry execution kernel. Select nearest
known weekly expiry, ATM then at most three outward strikes, no hindsight
substitution when the fixed order misses. No final-session data enters a signal.
Strict volume reconciliation and complete reported-candle diagnostics are
separate. Missing signal inputs with a potentially earlier signal make that
strategy's path UNKNOWN. Cash cannot restart after ruin.

Results include all 90 calendar days and actual session/expiry counts, 1/2/3
minute execution delays, open+1% alternative, best-trade deletion, and matched
random direction controls. Multiplicity includes all 44 variants in this batch;
previous experiments make this a lower bound on total search multiplicity.
No absolute-best or live-profitable claim follows from winning this sample.

## Capability-audit additions, before any new outcome replay

Authenticated Upstox probes on this date returned historical five-minute PCR
and max-pain insights and FII/DII records. Register three additional rules:
PCR_CONFIRM = FUTURE_TREND plus PCR changes >=10% over five minutes in its
direction; PAIN_ESCAPE = FUTURE_TREND plus two completed spot closes crossing
and remaining beyond the last known max-pain level (the previous third close
was on the other side); INSTITUTIONAL_ALIGN = FUTURE_TREND plus change in
FII index-futures net long contracts and DII cash net buying have that direction.
Institutional rows are available only at the second following NSE session open;
no EOD summary is used on its own trade date. Historical restatements remain
an uncertainty. PCR/max-pain timestamps receive one full bucket (five minutes)
of assumed publication delay; five-minute extra lag is also tested. Use only
intraday insights, never the response's terminal summary.

This makes 11 new mechanisms x two session types x two exits + 12 baselines =
56 comparisons. The initial 44-trial count above is historical registration;
the final correction is at least 56. Direction controls: 499 per evaluable
variant/window; a profitable candidate surviving BOTH windows and best-trade
deletion must get 3,999 controls before a significance claim. This limited
permutation screen cannot certify subtle effects.

The capability audit also found HTTP-200/null responses for older intraday
analytics. Register two separately named prior-day alternatives BEFORE any
outcome replay: PUBLISHED_PCR applies the same 10% directional PCR-change filter
to the prior published NSE OI and its daily change, for today's exact expiry;
PUBLISHED_PAIN uses the max-pain strike calculated from that same prior complete
chain. These are distinct strategies, not hidden repairs of missing intraday
PCR/max-pain. Both require FUTURE_TREND and retain the same crossing rule for
pain. Total comparison count is now 64. Today's EOD OI never enters these rules.

## Post-collection data audit

Before interpreting the completed replay, the price-grid audit found off-tick
OHLC observations in 40 contract-days. Strict audit paths now also become
UNKNOWN on off-tick prices, invalid OHLC bounds or duplicate bars. Reported
diagnostics preserve the original values and no thresholds or trade rules
change. Whole-day quality gates are retrospective evidence checks, not
tradable information that lets the bot skip a losing day. Both modes are
replayed under the updated source digest.
