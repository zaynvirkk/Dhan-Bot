# Independent strategy gauntlet, discovery specification

Initial signal rules recorded before computing strategy outcomes on 2026-09-19.
Execution corrections below are revision 3 and remain discovery work. Research only.
The comparison window is 2026-07-20 through 2026-09-18 (61 calendar days,
the original July 20 start retained); warm-up begins June 15. Each candidate
starts separately with INR 9,411.18. No pooled bankroll and no broker orders.

The pasted July–September examples have already influenced hypothesis design.
This entire window is a **discovery replay**, not an untouched holdout. Earlier
May examples are contaminated too. A champion requires subsequent unchanged
validation; maximizing nine in-sample bankrolls cannot establish an absolute best bot.

## Information and execution boundaries

Minute timestamps denote bar start. OHLCV/OI become usable only at bar end;
announcement knowledge begins at exchange dissemination, plus assumed ingestion
delay. No same-bar entry at an already observed low. Same-time relative volume
uses 20 *prior* sessions. No returns/OI changes across rolling strike identities.
Historical daily F&O files establish membership only for subsequent sessions.
Current master is an ISIN lookup, never proof of historical membership.

Every engine retains losing signals, rejected orders and unknown data. Missing
data is UNKNOWN, not a no-trade. Gaps capable of changing signals or trades
invalidate a full-period bankroll. Partial diagnostics are explicitly labeled.
Historical contract metadata does not prove contemporaneous broker eligibility;
dated exchange records and broker RMS restrictions must be checked separately.

Orders select an exact contract and freeze limit and whole-lot quantity using
information at decision time. Budget is 95% of cash, inclusive of entry fees;
the rest reserves exits. Nearest expiry eligible under Dhan RMS; nearest ATM
then outward at most ten strikes. No naked shorts, fractional lots or forced
strike selection based on future affordability. One open position per bot;
simultaneous candidates sort by timestamp, symbol, strike, option type.
No fresh stock-option entry on expiry day. Stock physical-delivery margin
requirements before expiry remain an additional eligibility audit.

Primary bar scenario: order limit = last known option close * 1.05, rounded
up to contract tick. Entry at next eligible bar HIGH only if <= frozen limit,
with quantity <= 5% of that bar's traded volume; otherwise modeled non-fill.
Past liquidity also gates order quantity. These are execution *assumptions*,
not evidence of displayed depth, spread or queue position. A missing bar is
unknown, not a modeled rejection. No target credited in the entry bar.
Target is 2x actual modeled premium; require a subsequent bar to trade at least
2% beyond target with sufficient volume. Invalidation exits at next bar LOW;
end-of-session exits are scheduled before close. Ambiguous stop/target order
is resolved adversely. Additional 1/2/3-bar delays and slippage stresses must
be reported; 1s versus 3s versus 5s is unidentifiable from minute candles.
Fees include Dhan brokerage per child, effective exchange/IPFT/SEBI charges,
GST, STT and stamp duty, using conservative rounding. Cash uses Decimal.

## Candidate rules

1. **EVENT_CONTINUATION**: a qualifying disclosure disseminated between the
previous regular-session close and today's open; direction from price. Three
consecutive completed bars with >=2.5% signed return from previous close,
>=1.5% signed return from session open, cumulative RVOL >=3, and no >50%
retrace of the event impulse. Futures price direction must agree. One first
signal per symbol/session. Material categories initially results, acquisition,
guidance, orders/contracts, regulatory action and senior-management change;
classification only uses original disclosed text, never subsequent returns.
2. **INTRADAY_EVENT**: qualifying disclosure during regular trading; reference
is median close of the five fully completed pre-publication bars. Three fully
post-publication bars must show >=2.5% displacement, RVOL >=3, positive signed
three-minute continuation and no >50% retrace. Futures direction agrees.
3. **EXPIRY_FORCED_FLOW**: expiring index options in final 60 minutes. A strike
cross from the non-intrinsic side followed by two completed underlying closes
beyond K; same contract premium +25% over 3 minutes, OI -8%, last 3-minute
volume >=4x mean of ten preceding non-overlapping 3-minute windows. Underlying
cross-back invalidates. This is an OI/price proxy, not proof of writer distress.
CAS version additionally requires actual timestamped official indicative index;
daily CAS summaries are insufficient.
4. **NONEXPIRY_FORCED_FLOW**: same frozen price/OI/volume cross rule on ordinary
sessions and non-expiring contracts, with identical execution model.
5. **PASSIVE_FLOW**: known index-change terms, estimated signed passive flow
>=20% of prior 20-session average traded value; effective session, after 14:30,
three completed closes in flow direction beyond opening range and RVOL >=3.
6. **SECTOR_SHOCK_LAG**: exposure graph/betas estimated only before test; lead
move >=3 prior-window standard deviations, target lag >=1 residual standard
deviation; enter after 3 completed target bars confirm predicted direction.
7. **SCHEDULED_EVENT_VOL**: calendar known before entry; 30 minutes before
scheduled release, ATM straddle cost/spot <75% of median absolute comparable
event move across >=8 prior events. Buy both legs only if full combined lots
and fees fit; target 2x combined cost; close 30 minutes after release. Events
outside cash session require a separately specified overnight policy, not an
implicit carry/physical-settlement assumption.
8. **BLOCK_OFS_DISLOCATION**: announced floor and offer size >=20% prior ADV;
effective session, after 09:30 three closes below floor with RVOL >=3 => PE,
or three closes above pre-announcement reference with RVOL >=3 => CE. Never
use the end-of-day block report as advance information.
9. **CROSS_MARKET_LEAD_LAG**: frozen pre-period lead/target relationships, same
lag test as sector engine, with external-source publication delays added.

Unspecified or unavailable required inputs do not get silently replaced with
another strategy. Such candidates remain unscorable until those inputs exist.

## Evaluation

Report each independent terminal bankroll, trade count, premium 2x targets,
>=50% premium losses, drawdown, unaffordable/missed/unknown outcomes and source
coverage. Keep capacity constraints as bankroll grows. Best-trade deletion
requires a chronological rerun because subsequent sizing/selection changes.
Compare matched random-side/time controls under identical execution, report
day/company clustered uncertainty and correction for the number of strategies
tried. An earlier 0/174 equity test is not evidence against these option rules.
Insufficient independent observations means inconclusive, even with a large
sample bankroll. Historical model returns are never actual execution receipts.

## Execution revisions and current scope (2026-09-19)

Revisions are retained, not presented as untouched validation. Revision 1
exposed assumed tick sizes and insufficient exit capacity. Revision 2 uses
exact Upstox contract ticks/freeze quantities reconciled with the prior NSE
lot size, a **seven-calendar-day stock-expiry buffer**, and a planned liquidation
window from 15:10 through 15:17. This buffer changes the original near-expiry
stock strategy. It avoids assuming premium-only funding through delivery-margin
days; it is not proof of historical Dhan eligibility. Partial adverse exits
retain all unfilled quantity and incur fees per modeled child order.

Revision 3 corrects invalidation dispatch to one minute after information
availability, suppresses ambiguous same-minute target wins and binds results
to source/input digests. Changes to source or candidate files during a run
invalidate its result. Previously produced revision 1/2 files are historical
debugging evidence and cannot be used as current bankroll results.

The announcement variant uses **exchange metadata text**, not complete verified
material-event content. Ambiguous announcements remain separately identified;
excluding them defines a narrower strategy, not a successful full-data audit.
An absent option tape cannot be converted into a verified no-trade. Reported
cash is conditional on bar-model assumptions and the declared source scope.

The sector subvariant uses pre-period exchange industry labels for banks and
software companies, with index leads and coefficients fitted before July 20.
The cross-market subvariant is GIFT-to-NIFTY only, with an assumed two-minute
feed-age buffer; vendor refresh frequency is not an end-to-end latency guarantee.
The OFS scan currently covers the qualifying disclosed LICI offer only. The
expiry scan covers ordinary spot strike crossings in NSE index options and
cannot stand in for a CAS indicative-index or aggressive-order-flow replay.
The non-expiry queue covers 21,415 exact contract-days selected from persistent
underlying strike crossings, without option outcome selection. Data collection
is resumable; batching days for the same contract does not change its signals.

PASSIVE_FLOW still needs point-in-time weights, fund assets and flow estimates.
SCHEDULED_EVENT_VOL still needs the advance-known calendar and eight comparable
prior events per type. Neither has a full replay. BSE/MCX coverage, historical
broker bans/RMS, displayed depth, ingestion delays, random controls, holdout
testing and family-wide multiple-testing correction remain outstanding.

No candidate is currently eligible to win. A no-signal result in a narrow
subvariant is not a full-universe bankroll of INR 9,411.18 for that family.

Revision 4 completes the bounded nine-rule discovery comparison. Each broad
family is represented by the explicitly declared implemented universe. The
RBI variant tests NIFTY/BANKNIFTY at 09:30 on August 5 using eight prior RBI
events and the announced 10:00 release. The MSCI variant tests August Standard
Index constituent changes. A failed price/volume necessary condition rejects
it even when flow magnitude is unavailable; a passed condition would remain
UNKNOWN until flow estimates are supplied. Other scheduled/index events are
not implied to be covered.

Exchange daily traded quantities are used only to **audit** historical candle
completeness. If reported minute units exactly equal official daily lots times
lot size, absent minutes can be classified as no-trade minutes. They carry
forward prior observable price/OI, including prior published session data before
the first trade. This does not inject an EOD price, direction, volume signal or
position size into an earlier decision. Any quantity mismatch stays UNKNOWN.
The historical OI reporting delay remains a model assumption.

The replay records complete conditional paths across pre-entry data errors,
while withholding a full-coverage bankroll. Unknown open-position outcomes
always stop the path. Random-side controls preserve underlying and signal time;
they are diagnostics, not independent new strategies or untouched validation.

Revision 5 adds official NSE security-ban lists for all 44 tested sessions,
validated against their stated trade date. Fresh entries in banned names are
rejected before contract selection. Account-specific RMS beyond published
rules remains unknown. The baseline assumes option proceeds can fund later
option trades, consistent with Dhan's published same-day realized option-profit
facility; this is not a cross-segment funds-reuse assumption.
