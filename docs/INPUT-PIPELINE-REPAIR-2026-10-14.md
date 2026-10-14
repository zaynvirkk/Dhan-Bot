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

## Deployment and subsequent open-position audit

Funded source 0aa2957 was installed after a verified-flat maintenance window.
The saved operator response authorized one additional qualification attempt
today only, with the INR 100 daily and INR 500 lifetime money caps preserved.
Attempt three was cancelled with zero fill and established the new order-socket
route. The persistent mandate was restored to two attempts for future sessions.
The running session retains its already authorized three-attempt ceiling.
Funded verification passed 521 tests, 60 acceptance cases and 15 guard mutations.
Follow-up dashboard releases do not restart the funded process (PID 368043).
The compact collector separates live projections from the retained history,
reducing the observed snapshot from about 1.52 MB to 125 KB. The final preceding
local suite passed 524 cases; these are software checks, not profit evidence.

The bot actually bought 65 units of NIFTY 22,750 CE at INR 122.65 at 11:51 IST,
using ORDINARY_PUBLISHED_PCR_TRAIL. Gross premium was INR 7,972.25. Broker cash
fell from INR 10,531.72 to INR 2,539.47; the additional initial INR 20 debit is
not evidence that all final order charges have settled. Four same-side candidate
rules were compared on execution friction and holding duration. No measured
profit ranking existed for these rules; this was experimental execution-quality
selection, not a demonstrated maximum-profit decision.

At 13:43 IST there was one open lot, no pending order, no exit latch or submitted
sell, and broker unrealised P&L was minus INR 2,577.25. A read-only replay of the
held contract through 13:44 showed a highest completed close of INR 137 at
12:05; its recorded 50% trailing threshold was therefore INR 68.50. No completed
close had crossed that threshold. The policy has no fixed target and a scheduled
15:34 exit. It permits giving back profit and about INR 3,520 loss from entry
before fees at that threshold; a quote reaching positive P&L is not a profit lock.
The dashboard now projects this recorded policy, actual weighted entry and exit
latch separately, without inventing a current trailing price or exporting private
payloads. This is visibility only; the held trade's policy was not changed.

Infrastructure remains imperfect: the market socket had 34 reconnects by 13:45,
although all three sockets were connected at the inspected snapshots. Twenty-nine
of thirty subsequent observations had fresh trader reconciliation; one was stale.
The unchanged five-second validity gate correctly blocks new entries in that gap.
Current diagnostics do not retain enough disconnection detail to establish a
root cause for every reconnect. A dashboard request failure means that browser
cannot establish current status; it does not prove the trader stopped.

The recorder was growing by approximately 273 KB/sec, with about 3.6 GB remaining
on a 20 GB boot disk. The existing disk and ext4 filesystem were expanded online
to 40 GB, yielding 22.7 GiB free at 13:49 without a funded restart (same PID,
zero restarts). This prevents the immediate storage constraint; retention and
provider-disconnect/refresh-duration improvements still require separate work.
No live position was closed, replaced, or given a different stop during this audit.
