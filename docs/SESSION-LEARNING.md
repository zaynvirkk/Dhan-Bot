# Session learning and replay

Before changing trading behavior, read the dashboard History → Sessions & lessons,
`dashboard/lessons.json`, the latest session review, and matching regression cases.
These are evidence and engineering memory, not permission to change capital,
reactivate a losing engine or assert that tomorrow will be profitable.

The broker-reconciled ledger retains actual intents, orders, fills and charges.
The read-only collector builds `learning.json` every 30 seconds and merges dated
outcomes into `session-memory.json` in its own dashboard state directory. Earlier
sessions survive the bounded 5,000-lifecycle query window. Failed reads preserve
the last review as STALE; unavailable final charges never become zero. Compact
health findings survive the seven-day diagnostic receipt retention. The 240-event
UI ring is not the learning store. Cash observations are in `learning-cash.json`;
their first/last timestamps define the observed interval, not an invented opening
balance or strategy net P&L. These files belong in the existing private backup.

The source-controlled lesson list records the 13 October auction gain, 14 October
PCR loss, and 16 October input-loss/IOC problems. The underlying financial totals
are rebuilt from actual receipts, rather than using these notes as P&L inputs.
Changes to lessons and browser assets are now included in the release digest.
The existing execution arbiter still uses previously closed executions; this
release does not introduce automatic model training or unreviewed policy changes.

## Input-path repair

Seconds strategies have a dedicated Dhan futures WebSocket, separate from option
subscription traffic. It runs the same strict FULL decoder and 1.5-second receipt
freshness bound. Disconnects and rejected packets revoke permission; reconnects
reset the fit. Options retain their own epoch. A repeated valid future-book
receipt refreshes availability without inventing a price move. Order permissions,
route proof, cash, spread/depth, target and exit guards remain.

Nonfinancial one-second evaluation receipts use the existing bounded asynchronous
observation writer. Financial intent/fill/order transactions remain FULL durable.
An observation queue failure still blocks new entries while management continues.
Input-loss latches now retain safe futures-age diagnostics for later attribution.

The exact cancelled-ping/late-pong counterexample failed with websockets13.1 and
passes with pinned14.2. The [upstream changelog](https://websockets.readthedocs.io/en/15.0.1/project/changelog.html#id5)
documents that fix and the handshake exception wrapping. The transport still uses
bounded watchdogs and answers provider pings. It does not hide errors or suppress
reconnection. The 15.x automatic proxy change is not introduced here.

## Continuous bounded replay

Whenever subscribed feed data arrives, including bootstrap/pre-open observations
used by the first live fit, options, the dedicated future and Upstox input receipts
are compressed off the
quote callback into private `state/replay/replay-YYYY-MM-DD.jsonl.gz` files.
Each receipt includes actual receipt time, processing time, role, epoch and a
capture-instance/sequence identity. Identical bytes are retained as separate
receipts. `replay_journal.read_capture(path)` reads concatenated gzip batches.
This covers subscribed contracts, not an unobserved entire F&O universe.

Raw capture is limited to512MiB compressed per day, reserves1GiB disk, uses a
bounded queue, and retains14 days of only its own dated files. It never deletes
broker records, the existing ledger, daily outcome memory or lesson notes.
Capacity/write/queue failure is visible and prevents new entries; exit/recovery
obligations remain. System → Input & replay health shows state and queued work.
These limits bound storage; actual next-session compression/latency/capacity must
be measured. Private raw frames never reach the dashboard or GitHub.

## Validation boundary

Exact regressions cover the late pong, independent production futures socket,
repeated valid receipts, malformed packets, capture preservation/cap, missing
charges, failed account reads, persistent older sessions, stale review fallback,
quote-callback observation I/O and digest coverage. Full software verification,
VM installation, standing funded activation and actual broker observations are
separate evidence. After-close handshakes cannot prove active-market latency,
future fills or profitability. Monday's measured results must update this record.
