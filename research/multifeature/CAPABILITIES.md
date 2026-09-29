# Broker data audit — 20 September 2026

The bot's information set is larger than the old price/OI tests. It is also
larger than either broker's historical archive. These distinctions are enforced
in the new research, with authenticated response shapes in
`research/results/multifeature90/capability_probes.json`. No endpoint in this
research can submit orders or alerts. Live quotes below were inspected while
the market was closed; this verifies schema/access, not execution quality.

| Data family | Dhan | Upstox | Historical use in this batch |
|---|---|---|---|
| Spot/index price, OHLC | Historical/live | Historical/live, includes VIX and sector indices | Completed NIFTY, bank, IT and VIX candles |
| Exact expired future price, volume, OI | Historical API subject to instrument support | Exact expired future metadata and candles | Prior NSE near-month identity; exact Upstox candles |
| Expired option price, volume, OI | Rolling ATM-relative history | Exact expired contract history | Exact Upstox execution tape; Dhan identity-aligned features |
| Historical IV and spot with options | Rolling options returns IV/spot/strike | Expired candles have no IV column | Dhan IV, matched to absolute strike/time; no synthetic fill prices |
| Option chain, Greeks, previous OI, best bid/ask | Current chain | Current chain and Greeks/feed modes | Live snapshots cannot be inserted into old decisions |
| Depth and total buy/sell quantities | Live 5/20/200 levels, eligibility/subscription limits | Live 5 levels or 30 with Plus, limits | No retrieved historical depth or queue; fills remain modeled |
| Trade quantity/time, quote time, feed receive time | Live feed | Live feed/currentTs | Minute history cannot resolve 1s vs 3s latency or receipt-time OI |
| Full-chain dated OI | Rolling subset, direct chain current | Dated OI API, per-strike totals | Daily values available next session, never within their own day |
| Intraday PCR and max pain | Derivable only with adequate chain history | Historical insights API actually returns data for recent dates | Empty older responses stay UNKNOWN; no terminal summary leakage |
| FII/DII positions and flows | No equivalent endpoint found in current documented list | Market APIs, advertised from April 2026 | Second-following-session availability assumption; revisions unverified |
| Smartlists: affordable options, IV/OI movers | Scanner can be constructed from quotes | Current ranked options/futures/MTF lists | No historical membership archive; today's list cannot select old trades |
| Company news | Not in documented Dhan data APIs | News API, **past seven days only** | Not a 90-day event archive; NSE/BSE original dissemination needed |
| Fundamentals, ratios, shareholding, corporate actions, competitors | Not equivalent in data API catalog | Fundamentals APIs | No verified historical as-of vintages; revised/latest values excluded |
| Global markets: GIFT, oil, FX, indices | Other exchange/segment support does not imply these feeds | Global instruments and current/history APIs | GIFT retrieved; two-minute buffer; no assumed access before 11 May launch |
| CAS IEP/IEQ/imbalance/reference/status | Specific feed availability must be verified | Current V3 quote/feed documents fields, launched 4 September | No adequate timestamped historical IEP/depth archive; CAS rule unscored |
| Lot, tick, expiry, freeze, segment | Instrument master | Exact expired/current metadata | Prior NSE listing + exact metadata; current master alone insufficient |
| Funds, positions, margin, bans/RMS | Execution account truth | Separate unfunded-account state | Historical eligibility/capacity assumptions disclosed; no account writes |
| Order acknowledgement, fills, partial fills | Order/postback/websocket | Order/websocket | Only real order receipts calibrate execution; none manufactured |

More variables do not automatically establish an edge. IV, Greeks, premiums,
PCR and OI transformations are often related. This batch compares explicit
mechanisms and nested filters instead of treating correlated inputs as
independent confirmations. It covers NIFTY expiry and ordinary sessions, not
every stock, commodity, currency or every possible rule exposed by these APIs.

The earlier nine named broad event/flow families remain separate research.
News/event bots still need full original publication archives; scheduled-event
volatility needs advance-known schedules and prior comparable outcomes;
passive/OFS needs prior disclosed terms/weights/flows; sector/global mechanisms
need pre-period relationships and feed-age assumptions. This NIFTY batch does
not silently claim a 90-day full-universe rerun of those families.

Primary documentation inspected:

* [Dhan data catalog and limits](https://dhanhq.co/docs/v2/)
* [Dhan expired options](https://dhanhq.co/docs/v2/expired-options-data/)
* [Dhan option chain](https://dhanhq.co/docs/v2/option-chain/)
* [Dhan live depth](https://dhanhq.co/docs/v2/full-market-depth/)
* [Upstox exact-contract backtesting](https://upstox.com/developer/api-documentation/backtesting/)
* [Upstox market information](https://upstox.com/developer/api-documentation/market-information/)
* [Upstox news, seven-day limit](https://upstox.com/developer/api-documentation/get-news/)
* [Upstox fundamentals](https://upstox.com/developer/api-documentation/fundamentals/)
* [Upstox FII date support](https://upstox.com/developer/api-documentation/get-fii-data/)
* [Upstox current feed fields](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/)
* [Upstox global launch/refresh intervals](https://upstox.com/developer/api-documentation/announcements/global-instruments/)

Public documentation plus account probes are evidence of feature availability,
not complete historical coverage. Licensed raw responses remain private.

## Retrieved-data reconciliation

The exact-contract option sample contains 1,362 contract-days and 513,870
minute observations. All have the expected minute count. Daily volume agrees
with the NSE file for 1,015 contract-days; 347 differ. Forty contract-days also
contain off-tick OHLC. Strict audit paths reject affected tapes; reported
diagnostics keep the received values and explicitly remain conditional.

There are 410,148 Dhan/Upstox observations matched by minute, side and absolute
strike at the inferred nearest weekly expiry. Of those, 249,645 closes differ
by more than one tick, but the median absolute difference is only INR 0.10,
the median relative difference is 0.17%, and the 95th percentile is 1.25%.
Dhan's close is inside the corresponding Upstox minute range in 409,119 cases.
These differences do not establish the cause or invalidate every candle.

Testing either adjacent minute worsens agreement: median relative differences
rise to about 1.8%. No timestamp shift was applied to the actual strategies.
This is an audit, not permission to use a later candle at an earlier decision.
See [alignment audit](../results/multifeature90/alignment_audit.json),
[coverage](../results/multifeature90/data_coverage.json), and
[price-grid observations](../results/multifeature90/price_grid_audit.json).

All 244 dated PCR/max-pain requests succeeded at the HTTP layer, but only nine
sessions contain intraday insights. Empty responses are not usable historical
data. Separately registered prior-day NSE-chain rules cover that different
information set; they do not repair the intraday variants by substitution.
