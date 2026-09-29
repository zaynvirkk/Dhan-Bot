# Index-options API audit — 29 September 2026

The operator ended the literature review and requested index-option bot work.
This audit identifies available instruments and the information boundary before
decisions. It does not select or activate a new trading strategy.

## Verified instrument inventory

Parsed the saved detailed Dhan master from the 27 September account/margin
inspection. Its SHA256 matches the original receipt:
`3e628064bb7b738c1afc6d24c8b00831bd53b9608cee1c027d94e2d817c2b034`.
The [machine-readable catalogue](index-options-catalog-2026-09-29.json) retains
source time, per-expiry lot sizes, exchange, permissions and mapping status.
This is dated broker inventory, not today's authenticated tradability check.

| Exchange | Underlying | Symbol | Lot in saved master | IDX_I quote ID |
|---|---|---|---:|---|
| NSE | Nifty 50 | NIFTY | 65 | 13 |
| NSE | Nifty Bank | BANKNIFTY | 30 | 25 |
| NSE | Nifty Financial Services | FINNIFTY | 60 | 27 |
| NSE | Nifty Midcap Select | MIDCPNIFTY | 120 | 442 |
| NSE | Nifty Next 50 | NIFTYNXT50 | 25 | 38 |
| NSE | Nifty India FPI 150 | NIFTYFPI | 1,100 | Unresolved |
| BSE | Sensex | SENSEX | 20 | 51 |
| BSE | Bankex | BANKEX | 30 | 69 |
| BSE | Sensex 50 | SENSEX50 | 75 | 83 (SNSX50 index row) |
| BSE | Focused IT | FOCIT | 45 | 850 |

Both CE and PE contracts occur for all ten families. MCXBULLDEX also occurs as
an MCX index option, separately from equity indices. Its lot field is 1; do not
interpret that as a one-rupee premium multiplier. Commodity contract valuation,
settlement and session rules need their own adapter.

The marketing options page lists seven equity indices, whereas the actual
saved master has ten. NSE now lists NIFTYFPI derivatives, and Dhan's September
expiry page lists SENSEX50 and FOCIT. Inventory discovery must filter OPTIDX
contracts, not use a static marketing list or include every published index.

Source links: [Dhan master documentation](https://dhanhq.co/docs/v2/instruments/),
[NSE NIFTYFPI specification](https://www.nseindia.com/static/products-services/equity-derivatives-nifty-india-fpi),
[Dhan September calendar](https://dhan.co/blog/news/upcoming-fno-expiry-for-september-2026/),
[MCX BULLDEX specification index](https://www.mcxindia.com/products/index/MCXBULLDEX).

**Identity correction:** NIFTY option rows contain underlying ID 26000, but
the index quote/chain request uses Dhan IDX_I ID 13. BSE has similar differences.
Resolve the index row separately and verify returned contract security IDs.
The saved master does not resolve NIFTYFPI/MCXBULLDEX index quote IDs; these
remain UNKNOWN rather than guessing an ID. Never choose NIFTYFPI via a NIFTY
substring match.

## Required decision inputs and routes

| Input | Route / treatment |
|---|---|
| Current contracts | Detailed master: exact exchange/security ID, CE/PE, strike, lot, tick, expiry, broker buy/sell indicator; obtain freeze limits separately |
| Expiry calendar | POST `/v2/optionchain/expirylist`; use returned dates including holiday adjustments |
| Surface context | POST `/v2/optionchain`: IV, four Greeks, OI, previous OI, cumulative volume, top bid/ask and quantities; documented cadence one request per three seconds per unique chain |
| Fast execution/flow observations | FULL WebSocket: five-level bid/ask, LTP/LTQ/LTT, average price, cumulative volume, total buy/sell quantities, OI and OHLC |
| Extra depth | Separate 20/200-level WebSockets, documented for NSE equity/derivatives only; entitlement and live availability unverified here |
| Direction/context | Time-aligned spot and near futures observations, basis, completed-bar momentum, futures VWAP, volatility, expiry/session clock; constituent breadth or cross-market data only when actually available |
| Account/execution state | Profile, funds, positions, pending orders, margin estimate, order/fill updates, spread, executable depth, latency and fees |

Sources: [option chain](https://dhanhq.co/docs/v2/option-chain/),
[live feed](https://dhanhq.co/docs/v2/live-market-feed/),
[full depth](https://dhanhq.co/docs/v2/full-market-depth/),
[market quote](https://dhanhq.co/docs/v2/market-quote/).

OI is not signed dealer positioning or an aggressor-side feed. Cumulative volume
must be differenced within a session; do not count the same last trade on every
depth update. Greeks and IV are model estimates, and chain responses do not
provide a timestamp for every feature. Store request/receipt time and source
age, retain unknowns, and never equate LTT with a book/OI timestamp. A price
index has no traded volume; use futures or a specified constituent aggregate
for volume-based features. Only completed candles are available as final OHLC.

Upstox remains the auxiliary provider, with exact-contract historical candles
and an independent live feed. Its news/fundamental endpoints are not a complete
historical information archive; the [existing mapping](../research/literature/API_INPUTS.md)
records those limits. Data unavailable through either provider cannot be
silently synthesized before a decision.

## Changes and verification

1. Added a dynamic catalogue parser. It distinguishes exchange-scoped IDs,
   tracks per-expiry lot changes, excludes expired contracts, rejects malformed
   or duplicate metadata and leaves missing index mappings unresolved.
2. Corrected FULL decoding from 163 bytes/depth offset 63 to **162 bytes/offset
   62**, matching the [official Dhan Python SDK](https://github.com/dhan-oss/DhanHQ-py/blob/main/src/dhanhq/marketfeed.py).
   Updated the old padded fixtures and added an independently packed SDK-format
   regression case. Unknown/padded layouts fail instead of being guessed.
3. Retained observed market statistics with the book and its receipt timestamp.
   Used unsigned quantity/time fields as in the SDK; price fields remain
   Decimal and reject nonfinite values. Missing day close remains None.

Exact command: `python3 -m pytest tests/test_index_market_data.py tests/test_protocols.py tests/test_release_boundaries.py`
— **33 passed**. Full `python3 -m pytest`: **270 passed, 6 failed**. All six
failures occur when creating local socket listeners in this restricted runtime
(one reconnect test and five connected-service cases). They are not counted as
passed or evidence of functioning provider connections.

Fresh DNS probes for images.dhan.co, auth.dhan.co, api.dhan.co and api.upstox.com
all returned `gaierror`. An initial HTTP/auth probe was interrupted after it
failed to return; it yielded no usable receipt. No authentication failure is
inferred from that. Today's account state, live Greeks, executable depth and
broker latency remain UNKNOWN. The most recent successful saved account check
is 27 September: INR 9,411.18, active derivatives/data, no positions/orders/trades.

The production strategy and routing still implement NIFTY CAS. This work does
not convert it into the later selloff/rebound research candidate, add live BSE
routing, wire chain Greeks into a decision model, or establish profitability.
The rebound's favourable earlier model results did not survive all subsequent
execution/period checks. See [the latest experiment](../research/results/execution_frontier/REPORT.md).
No order, cloud change, subscription purchase or deployment was made.
