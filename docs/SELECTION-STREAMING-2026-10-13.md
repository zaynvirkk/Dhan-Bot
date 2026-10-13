# Funded selection and streaming update

Operator request: compare simultaneous opportunities using available evidence,
reduce market-input latency, audit the VM and make the decision visible.

All 137 existing NIFTY configurations remain registered and enabled under the
same account, capital limits, bounded route qualification and single writer.
This update does not supply a new profitability qualification for those rules.

## Selection

Entry preparation considers every currently eligible and executable minute
candidate before committing an intent. A qualified auction candidate participates
in the same comparison before its own entry can consume shared capital.
Missing option minutes, stale books, insufficient depth or unaffordable whole
lots cannot receive a score or borrow a hypothetical fill.

For a candidate with at least three consistent, filled, closed historical
lifecycles, estimate gross return and holding time exclusively from those past
fills. Reprice the current whole-lot exposure, conservative buy/sell fees and
entry-limit-to-bid friction reserve, then rank positive estimated net rupees per
holding minute. Report sample/session counts and return standard error. These
small, correlated live samples do not establish a repeatable edge.

If no positive measured candidate exists, contradictory unmeasured call and put
signals cause abstention. Same-side unmeasured candidates use lower execution
friction, then a shorter holding limit; the UI labels this an experimental
fallback and leaves estimated profit unknown. Alternate exits of one family
receive no extra votes or concurrent positions. A standalone auction opportunity
retains its original qualified pricing-discrepancy gate; its implied intrinsic
value is not presented as a guaranteed future return.

Persist the comparison with the entry and in session metadata. Actual dispatch
still rechecks permission, time, current book identity and freshness. LIMIT IOC,
partial-fill reconciliation, idempotency, position ownership and exit latches
remain unchanged. No retry converts a missed limit into a price-insensitive bet.

## Input path

The existing Upstox full subscription now supplies validated completed NIFTY
I1 candles to the minute worker. Reject initial snapshots, forming/future bars,
stale timestamps, invalid ranges, conflicting revisions and disconnected epochs.
Only a contiguous, previously fetched history baseline can use the stream.
New completed bars wake the worker; REST repairs startup and gaps. Do not
construct highs/lows from sampled last prices or infer futures OI from index ticks.

Historical/chart requests use two-minute overlap repair rather than downloading
the full session repeatedly. Replace omissions in that overlap; a failed request
invalidates its cache. Account-wide, process-local data admission spaces chart
and option-chain POST requests independently of order dispatch. Core evaluations
and candidate option history publish before optional features. Quotes and fills
continue on native WebSockets; futures OI, auxiliary candles, calendars and
published institutional/chain inputs retain their appropriate bounded REST reads.

## Dashboard and limits

The new selection section explains the last comparison, chosen strategy,
executable quantity, limit, friction, estimated rupees/minute or missing evidence.
It distinguishes the closed exchange from an unavailable input and keeps the
last decision after restart. Detailed family checks remain collapsible.

The production domain remains NIFTY options. Research descriptions of company
events, other underlyings, cash, futures bets and multi-leg strategies are not
implemented by renaming these 137 configurations. Verified exchange sessions,
contract identities and strategy-specific researched windows remain binding;
continuous monitoring does not mean continuous trading outside those rules.

Deployment and actual VM/browser verification are recorded in the portfolio
work log. Tests prove software behavior; only broker receipts prove fills, and
final invoices are required to confirm net profit.
