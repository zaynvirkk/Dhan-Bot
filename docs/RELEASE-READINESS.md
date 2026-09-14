# Release readiness — 2026-09-14

Version 0.2.0 implements the connected execution lifecycle that the previous
read-only deployment lacked. Local verification executed **113 tests**, with
no failures/skips, and killed four isolated production-source mutations.
The verified source digest is
`79937510e583dff3c88fd3a17045f1580bbfc121c8d002366bed253a54272737`.
This receipt includes 60 historical CP component cases; those 60 alone do not
represent complete connected acceptance of every statement in the build plan.

## What the verification actually exercises

The production service connects to three real local WebSocket servers and a
local HTTP broker. It authenticates subscriptions, decodes the full official
Upstox protobuf and concatenated 163-byte Dhan Full packets, proves a zero-fill
route when the order echo arrives before the HTTP response, freezes five
pre-boundary observations, sends an eligible BUY and later SELL, and reconciles
fills, flatness and cash. These are local fixtures, not real broker executions.

Connected lifecycle cases cover UP → DOWN → UP, identical numeric IEP values
with distinct event identity, fresh reconnect epochs, finite-depth/freeze
slicing, additions, partial entry/exit and frozen risk allowance, crash recovery
after broker acceptance with a lost HTTP response, duplicate/reordered fills,
persistent disarming, zero-bid emergency exits, stale cached flat snapshots,
and disarming while an order is waiting for the OMS lock.

Final-value cases reject foreign dates, duplicate index rows, non-finite values
and invalid publication times. They exercise residual entry without fabricated
IEP, entry cutoff before exit, durable disarm on final revision, finite sale
slices versus exercise, post-stop additions, next-day restart, and receipt-bound
settlement credit. An unexplained or absent credit does not close the receivable.

The mutation replay removes intent-before-send durability, pending-exposure
protection, the dispatch-time disarm check and the broker read-only boundary,
one at a time. Each altered implementation fails its connected assertion.

## Real external evidence and outstanding empirical facts

The actual Mumbai VM check at 04:31 UTC on September 14 verified Dhan PIN/TOTP
login, active data entitlement, account reads, the reserved egress address,
Upstox index snapshots, and both Dhan socket connections. The current master
identified September 15 expiry, 65-unit lots and 464 NIFTY option contracts;
the fetched NSE freeze publication returned 1,800 units. The native-master tick
adapter converts paise into rupees (`5.0000` → `0.0500`); the old deployed
revision's unconverted report must not be used for order pricing.

No usable live option depth, CAS IEP, accepted OMS write/epoch echo or settlement
cash receipt has yet been observed for this release. September 14 is an NSE
trading holiday, so it cannot provide today's CAS rehearsal. Tuesday's process
must observe these facts; no test count or socket handshake substitutes for them.

The final-value adapter uses the dated official NSE daily index-close CSV and
requires its publication timestamp, unique NIFTY row and trading date. Its
availability before the entry cutoff has **not** been established. If unavailable,
final-dependent entries stay disabled automatically. Expiry ledger narration
matching is deliberately exact; the actual Dhan voucher format remains to be
commissioned. Unmatched credits remain pending instead of becoming invented P&L.

The installed service retains read-only authority until the operator runs the
activation helper in [CLOUD-DEPLOYMENT.md](CLOUD-DEPLOYMENT.md). That command
checks prerequisites and installs the funded mandate using current reusable
cash. Actual order routing remains an automatic pre-CAS gate after activation.

## Source contracts checked

- [Dhan authentication and IP registration](https://dhanhq.co/docs/v2/authentication/)
- [Dhan orders, correlation lookup and fill identity](https://dhanhq.co/docs/v2/orders/)
- [Dhan ledger and historical trade statements](https://dhanhq.co/docs/v2/statements/)
- [Upstox V3 feed](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/) and [official protobuf](https://assets.upstox.com/feed/market-data-feed/v3/MarketDataFeed.proto)
- [NSE option settlement basis](https://www.nseindia.com/static/products-services/equity-derivatives-settlement-price)
- [NSE holiday calendar](https://www.nseindia.com/resources/exchange-communication-holidays?article_id=432919950.0)
- [SEBI circular list](https://sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&smid=&ssid=7): the September 12 CAS/settlement proposal remains a consultation in the material reviewed, not an enacted replacement regime.

This is engineering and deployment evidence. Profitable fills and bankroll
multiplication remain unproven market outcomes.
