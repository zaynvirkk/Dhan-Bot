# Streaming optimization validation — 4 October 2026

Implementation began on 1 October and was completed locally on 4 October.
**Not deployed.** The production trader and its mandate, keys and account were
not changed. No live order or funded probe was used to validate this work.

## Implemented

1. Routine account reconciliation runs in a background worker. REST reads no
   longer own the order-writer lock. One shared account revision covers all
   order managers (entries, exits and route probes). A notification or attempted
   write invalidates any in-flight batch before it can change the ledger.
   Reconciliation applies under the writer lock with no intervening network await.
2. Validated, deduplicated Dhan order events immediately request reconciliation.
   Cumulative WebSocket quantities do not manufacture fills: broker trade IDs
   still establish each fill once. Reconnects invalidate earlier account evidence.
   Periodic reconciliation remains, nominally 0.4 seconds when busy and five
   seconds when idle, measured after reads complete.
3. The session wake flag is cleared before processing, preserving notifications
   received while processing awaits. Periodic clock checks also run separately.
4. The trader publishes a sanitized account observation with its original
   timestamp. The dashboard collector uses that projection and performs an
   independent broker check every five minutes. It keeps the legacy independent
   read path for older traders without the shared projection.
5. The collector publishes local observations each second without awaiting the
   independent broker check. Authenticated SSE pushes those snapshots to the page.
   Streams are bounded to 20 seconds, recheck session expiry, and reserve request
   capacity. Hidden tabs disconnect. Polling is the fallback, and stale source
   timestamps still remove current-status claims. Deployment scripts migrate the
   collector from a timer to a supervised persistent service.
6. Bounded telemetry records decision-cycle, feed-age-at-cycle, cycle-to-submit,
   HTTP response, first recorded fill, reconciliation, loop-delay and book-age
   measurements. The page shows p95 and sample counts; JSON also includes p50/p99.
   Entry-check counters distinguish confirmation, book depth, affordability,
   intrinsic gap, price limits and net edge. They count evaluations, including
   repeat checks, not unique signals or counterfactual profits.

## Execution invariants

Cash and prices remain Decimal. A buy retains its fresh cash preflight; a sell
retains its fresh broker-position check. Pending intents, partial fills, ambiguous
HTTP responses, durable reservations, debit caps, order limits and disarming
remain authoritative. No market order, retry-until-filled rule, signal threshold,
contract-selection rule or position-sizing change was introduced.

Account position evidence older than five monotonic seconds, a superseded
revision, or a failed reconciliation blocks decisions until refreshed. Failure of
only the cash endpoint blocks entries but permits management using successfully
reconciled positions; a slow cash failure does not age the subsequently read
position evidence. Mandatory write/preflight calls and exceptional settlement
checks still await the broker. There is no claim that every execution path is
free of network waits.

Measurements are process-local and bounded to 512 samples per metric. HTTP
response latency is not exchange matching latency. Fill recording includes
reconciliation delay. Feed-to-cycle numbers measure age of the latest received
feed message when the cycle starts, not an exchange-to-trade latency guarantee.

## Actual validation

- Full command: `.venv/bin/python -m pytest -q --tb=short`.
  345 tests collected: **339 passed, six failed at localhost socket creation**
  (`OSError: could not bind on any address out of [('127.0.0.1', 0)]`).
  These are the existing WebSocket reconnect test and five connected-service
  tests. They are unchanged and remain mandatory; this is not a passing full
  release verification.
- Final targeted command:
  `.venv/bin/python -m pytest tests/test_dashboard.py tests/test_dashboard_streaming.py tests/test_streaming_runtime.py tests/test_service_streaming.py -q -o addopts=''`:
  **69 passed in 34.69 seconds**.
- Six new production-session scenarios use the real service, HTTP adapter,
  official protobuf/binary decoders, strategy, order manager and ledger with
  synthetic HTTP/feed boundaries. They cover normal flow, partial fills, a cash
  outage, an outstanding slow account GET, day rotation and token rotation.
  They verify notification-before-HTTP-response and duplicate notifications.
  The slow-GET case completes signal processing, fresh cash validation and order
  submission before releasing the blocked routine account read.
- That in-process harness runs recorder I/O inline because the restricted runtime
  cannot provide normal socket-based thread wake-ups. It supplements, and does
  not replace, the genuine transport/recorder integration tests.
- Twelve existing production-source mutations whose oracles do not need sockets
  were rejected. The other three mutation cases require the blocked connected
  tests and were not credited. No verification marker was generated or bypassed.
- JavaScript syntax, actual page rendering through a DOM boundary, pushed updates,
  silent-stream fallback, visibility pause/resume, expiry and out-of-order failed
  poll recovery passed. Shell syntax and `git diff --check` passed.
- The design detector reported one advisory for existing em-dash placeholders.
  There was no new real-browser screenshot or live HTTPS verification.

The test commands used local fixtures only. Their timings and cash outcomes are
not live latency measurements or strategy-profitability evidence.

## Remaining release work

Run the unchanged full verification (including the six socket cases and all 15
mutation cases) in a network-capable environment before updating the funded
trader. Do not substitute a hand-written verification marker. Node.js 18+ is now
needed for the frontend lifecycle test; VM installers include `nodejs`.

The dashboard has an independent deployment script, `ops/deploy_dashboard.sh`.
It installs the dashboard/collector without restarting or arming the trader.
Deploying it alone gives push updates with the legacy account-read fallback;
the shared account projection and trading-loop changes require the corresponding
trader release. Validate SSE, account freshness and login/logout over the real
HTTPS route after deployment. If rolling back the dashboard, restore its matching
collector service/timer units as well as its code symlink.

Publication and operator steps are in [the release guide](RELEASE-2026-10-04.md).
