# Completed candle and order readiness repair

## Incident and live evidence

The account repair did not establish that every directional engine had usable
minute history. Two ordinary sector-confirmation variants observed a put at
10:10 IST on 14 October but expired without submission because option candles
were unavailable. At 10:50, 51 configured variants lacked completed-bar inputs.
Socket connectivity is distinct from candle coverage and execution permission.

A bounded real, read-only chart check reproduced the core defect. A cold Dhan
futures or option request returned all five recent completed minutes. An
incremental request with the old one-minute lower-bound overlap returned only
four, and replacing that interval deleted the omitted cached minute. Subsequent
requests accumulated holes even while current quotes and candles arrived.
The response excluded the bar starting at the requested lower bound.

The repaired source was then evaluated against the real authenticated APIs,
without installing a writer or submitting an order: three successive futures
and three successive option requests retained all 119 completed session minutes
through 11:14 IST, with zero gaps. This verifies the observed endpoint boundary
behavior; it is not execution or profitability evidence.

## Production changes

- Cached chart updates overfetch two minutes before the completed-bar replacement
  boundary. Cold session requests retain their existing opening boundary. Rows
  outside the requested observation window and forming candles remain excluded.
  Explicit provider omissions are still removed; no cached or synthetic candle
  can conceal a genuine hole.
- Core NIFTY and futures reads are concurrent. Evaluation retains the completed
  minute requested at the start of the batch; slow reads cannot relabel it as a
  newer minute. Actual receipt time still governs calendar, source availability
  and the unchanged 90-second input ceiling. Expired dispatch windows stay expired.
- Relevant actual option contracts are loaded before signals arrive. The bounded
  watch set includes ATM/outward candidates, adjacent chain contracts, frozen
  acceleration anchors, published OI walls and existing position obligations.
  Three concurrent reads and an 18-contract bound prevent a universe-wide scan.
- Auxiliary indices/publications run independently with lower read priority,
  receipt-time checks, timeouts and bounded retries. Completion cannot create
  an immediate request storm. An individual failed source cannot erase unrelated
  completed sources. Cancellation and session changes discard obsolete work.
- Missing current core candles trigger a bounded five-second retry, while quotes
  and execution events continue through WebSockets. No order endpoint is retried
  because a data request failed.
- Runtime and dashboard report latest completed core minutes, whole-session holes,
  first missing timestamps and watched-contract three-minute readiness. Fresh,
  missing and stale observations remain distinct. Provider payloads and secrets
  are excluded. Execution reasons are specific to each strategy's durable signal
  and assessment, rather than copying the latest engine-wide reason to every row.

## Preserved constraints

Thresholds, trading windows, entry deadlines, stop/target policies, whole-lot
affordability, volume/OI requirements, quote freshness/spread/depth, authority,
capital and route budgets are unchanged. Expired morning signals are not replayed
after repair. CAS and existing-position management remain separate from optional
feature availability. One session of positive net results does not establish
repeatability; working data does not guarantee a qualifying trade or a fill.

Exact regression cases cover lower-bound exclusion over repeated updates, slow
auxiliary reads, crossing a minute boundary, stale core batches, per-strategy
execution attribution, request-storm prevention and safe dashboard projection.
Actual DOM cases distinguish quote connectivity from candle holes and demote
stale readiness. Full acceptance and source-mutation checks supplement these cases.
