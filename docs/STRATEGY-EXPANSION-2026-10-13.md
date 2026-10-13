# Funded NIFTY strategy expansion, 13 October 2026

The operator explicitly requested production integration and activation of the
additional strategies, rather than another three-engine status audit. This
release expands the single funded service to 137 named NIFTY configurations:
41 recorded rule families and CAS. These are experimental executable rules, not
137 independently proven profitable bots. Exit variants and historical aliases
share a family consumption record so they cannot retry the same bet under a
second label after an unfilled IOC.

## Production behavior

The registry covers opening drive, gap reversal, first/last-session direction,
trend pullback, volume reversal, sector catch-up, failed opening/late ranges,
afternoon compression, futures trend/OI, basis lead, IV versus realized volatility,
sector confirmation, delayed GIFT catch-up, option/chain OI unwind, PCR and
max-pain crossings, lagged institutional alignment, prior published chain/walls,
VWAP reclaim, expiry acceleration, overnight continuation and reversal rules.
CAS preserves its existing official-indicative-index execution path.

Both CE and PE signals use actual next eligible contracts, whole lots, current
Dhan depth, the existing capital ceiling, charge reserves and LIMIT IOC orders.
One shared account writer and one unresolved lifecycle prevent simultaneous
all-in orders. An unfillable engine no longer prevents another qualifying signal
from being considered. A submitted family is not retried by its exit variants.

Eligible signals are ranked using up to 30 already closed filled executions per
configuration, excluding unfilled attempts, open/unresolved exposure and future
receipts. Three filled closed lifecycles are required for a measured score.
Positive measured returns rank before unknown configurations; measured losing
configurations rank last. Unknown strategies have deterministic selection order,
not invented profitability. Scores use estimated conservative charges until
final broker charges are available. A qualified CAS opportunity with a measured
positive score competes before unranked minute signals; no qualifying CAS order
falls through to the other engines. Ranking is cached for five seconds and funds
are read once per admission pass rather than once per variant.

FAST exits use 1.25x/.85x and a 30-minute hold; SWING uses 1.5x/.75x and 60 minutes;
DOUBLE/TARGET uses 2x/.5x. TRAIL ratchets the completed-close peak with a .5x stop.
Completed-close triggers submit only after the next minute; real sell fills come
from current books and reconciliation. These live policies are not falsely
represented as the earlier research kernel's high-touch target fills.

Rules retain their defined observation windows. Enabling a rule does not remove
its hypothesis or authorize entries while the exchange is closed. Calendar dates
and actual expiries remain provider-derived. Historical `_0930` overnight names
mean NEXT-SESSION EXIT at 09:30: source replay entered these at 15:10, not 09:30.
That source ambiguity is corrected in the production binding.

## Live input boundaries

Dhan minute OHLC/OI, actual absolute option identities and verified contract
metadata supply the principal inputs. BANK, IT and VIX security IDs are resolved
from exact INDEX rows of the current detailed master, not guessed derivative IDs.
Near-ATM CE/PE histories include chain neighbours and the frozen 14:45 expiry
anchor. Dhan current IV retains its actual receipt time; it is not backdated into
a historical minute. GIFT candles use the published global instrument key and
the rule's additional two-minute delay. Upstox insights admit only complete
five-minute buckets with an additional bucket delay; terminal daily summaries
are excluded. FII/DII rows are delayed two verified prior sessions. The prior
NSE F&O bhavcopy supplies complete-chain PCR, max pain and prior OI walls.

Optional source errors remove only their dependent feature. They do not fabricate
zero or globally block unrelated spot/futures rules. Reconciliation, exit handling,
software binding, broker account, route, freshness and capital checks remain.

## Dashboard and limits

The dashboard no longer allowlists just three names or truncates to three rows.
It groups exit variants by family, with actual state, precise entry rule, observed
numeric inputs and historical fill-based selection score. Unknown source values
remain unknown. Signal rejection records cover every registered configuration.
Large history is bounded by bytes as well as sample count; family summaries keep
monitoring readable while full variant decisions remain in the durable ledger.
The dashboard remains read-only and contains no keys or raw provider responses.

This is the existing NIFTY-only order domain. The original nine stock/event,
passive-flow, scheduled-volatility and other non-NIFTY/multi-leg gauntlet ideas
are not silently represented by these rules: they need different contract,
physical-settlement, catalyst and/or multi-leg execution paths. Cash-equity,
leveraged-short and blind-option controls are not activated as NIFTY bots.
No new profitable backtest, guarantee of fills or future winner is claimed.

Deployment and current broker observations are recorded below after verification.

## First installed release

GitHub/main and dashboard release `c859819` deployed successfully. The installed
funded upgrade completed its full 472-test / 60-case / 15-mutation verification,
amended the strategy list to all 137 configurations, preserved the existing
mandate and restarted the funded trader from the immutable release. The signed-in
browser reports 137 configured names / 136 minute-engine evaluations plus CAS,
enabled armed authority, current software verification and AVAILABLE history.
The session is closed: route proof will refresh through the bounded automatic
qualification at the next verified open session, not an invented current proof.

Read-only VM input probes found usable calendar, 375 completed bars each for Bank,
IT and VIX, 763 GIFT bars, insights and prior trend. They exposed three integration
issues: optionchain requires a client-id header, institutional `from` denotes the
newest-row anchor, and the public archive download needed browser-compatible
headers. Explicit corrected read-only probes returned 235 IV strikes, current
October FII/DII records and the 1,150,222-byte official prior-session archive.
The recorded next eligible expiry is October 19, not a guessed Tuesday. Repairs
are source-bound and verified before the final funded update below.
