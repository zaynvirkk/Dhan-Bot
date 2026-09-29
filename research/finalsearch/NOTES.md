# Implementation and interpretation notes

The registered strategy thresholds and clocks were not optimized after outcomes.
During accounting verification, the first development replay exposed a tiny
negative cash balance when a nearly exhausted account bought very cheap options
but lacked enough cash to pay both exits. The final implementation retains the
95% premium/entry-cost cap and additionally reserves three minimum exit-charge
envelopes per leg. Each liquidation attempt is bounded to three minutes. This
fix can prevent fee-driven borrowing; it does not forgive a price loss. A
triggered exit is latched and cannot be postponed by a later price recovery.

The first diagnostic also exposed missing earlier warm-up sessions for the
twenty-session forecast. Previously collected Upstox index history before
23 March is now included as warm-up. Outcome-period rows were not changed.
The retained final source/input hashes and generated ledger identify the
corrected replay. The original protocol remains unmodified and hash-checked.

An entry priced at a minute high with a 5% limit is an adverse stress scenario,
not a reconstruction of actual fills. It can overstate one-leg fills and
unwinds. The next-open-plus-1% variant is also reported, and no variant under
that assumption profits in both windows either. Neither is a historical book.

The primary pair target uses simultaneous completed closes followed by delayed
sales. It does not claim an atomic exchange basket, combine asynchronous highs,
or assume a touched target fills. No implicit exercise or settlement proceeds.

Current Dhan margin examples use last reported prices while markets are closed.
Quote book quantities are zero after close. Their positive price fields do not
establish available depth. The margin API returns some confusing ancillary
fields (including zero userFundLimit on multi-leg responses); feasibility uses
the explicit totalMargin against separately fetched funds. No current margin
is projected backward. MCX eligibility and historical margin are unverified.

This is a completed bounded research pass, not exhaustive testing of every
possible F&O strategy, expiry, broker RMS rule or full-universe event family.
The absent independent holdout and historical book evidence are still absent.
No-live recommendation is not a mathematical proof that no profitable strategy
exists, nor a claim that a longer or wider search must find one.
