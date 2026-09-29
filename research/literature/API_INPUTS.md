# What the literature requires from our feeds

Documentation checked 28 September 2026. This is a schema review, **not fresh
authenticated API testing**, a coverage guarantee, or authorization to trade.

| Research input | Available route | Remaining boundary |
|---|---|---|
| Completed underlying/futures bars | Existing Dhan/Upstox historical pipelines | Dated trading hours, dividends/splits, rolls, point-in-time eligible universe and gaps |
| Historical exact option path | Upstox expired-contract candles; Dhan rolling options as cross-check | Preserve fixed contract identity; a rolling ATM label can switch strikes |
| Option OI, volume, IV, spot | Dhan rolling option fields; Upstox candles include OI/volume | Fields alone do not reveal which participant bought/sold or the aggressor |
| Gamma proxy | Recalculate with observable option inputs and explicit model/position assumptions | Aggregate OI does not disclose signed dealer inventory; resolve L06's convention |
| Corporate news | Upstox now documents a News API with publication timestamp | Only past seven days documented; cannot backfill 90 days from this endpoint alone |
| EPS/fundamentals | Upstox now documents income statements and other fundamental endpoints | Do not backcast revised/latest financials; validate original filing content and release time |
| Precise historical announcement availability | Existing exchange filing archive pipeline | Verify dissemination/first observation, attachment version and timestamp zone |
| Investor-type signed option flow in L13/L16 | Their exchange research datasets | Ordinary broker candle schemas do not expose their investor/algorithm flags |
| Historical order book/queue | Dedicated historical feed or previously recorded live observations | Current depth cannot reconstruct the past; do not replace unknown fills with LTP |
| Daily participant positions | Dated exchange participant reports | Publication/availability lag; not an intraday participant-position tape |
| Pairs/commodity funding | Dated contracts plus broker margin/risk rules | Current affordability checks do not supply historical mark-to-market, collateral or delivery funding |

Two corrections to the old conversations:

1. Dhan's detailed strike parameter specifies **ATM ±10 for near-expiry index
   options and ±3 for other contracts**. The headline's broad ±10 wording is
   insufficient to assume full stock-option surfaces. Its documented response
   has prices, volume, OI, IV, strike and spot, not historical bid/ask queues.
   [Dhan expired options](https://dhanhq.co/docs/v2/expired-options-data/)
2. Upstox does now document news and fundamentals. Its news endpoint returns
   `published_time` in milliseconds but only a seven-day lookback. This helps
   prospective signal collection; it does not replace a point-in-time historical
   event archive. [News API](https://upstox.com/developer/api-documentation/get-news/),
   [fundamentals](https://upstox.com/developer/api-documentation/fundamentals/)

Upstox's historical expired response specifies timestamp at candle **start**,
then OHLC, volume and OI. Treat a one-minute candle as available only after its
completion plus modeled delivery delay. [Expired candles](https://upstox.com/developer/api-documentation/get-expired-historical-candle-data/)

For earnings drift, the income-statement schema must still be audited for
as-reported versus restated values and historical availability; existence of the
endpoint proves neither. [Income statement documentation](https://upstox.com/developer/api-documentation/get-income-statement/)

All source latency is distinct from order latency. A news article published at
10:00 and received at 10:04 is usable at 10:04 in a reconstruction of that feed.
Likewise, three one-minute confirmations are a signal delay, not a broker delay.
