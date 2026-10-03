# Live connection health and scheduling update

Implemented locally on 4 October 2026. This report does not establish deployment,
current broker connectivity or profitable trading. The previous streaming release
was committed as 015536b; this update builds on it.

## Why the old warning persisted

The page's general banner used `connections.json`, a separate diagnostic report.
The timer runs weekdays at 09:20 UTC (14:50 IST), while that report becomes
historical after 900 seconds. Meanwhile the account collector and bot status can
remain current. Refreshing the page does not rerun those diagnostics. That design
produced the quoted warning after almost every scheduled-check freshness window,
including idle weekends. WebSocket adoption alone could not correct it.

The replacement separates Live connections from a dated Scheduled diagnostic
results disclosure. A fresh runtime report supplies each socket's connection
state, reconnect count, latest received/processed/accepted message timestamps,
pending-message count, oldest pending age, queue high-water mark and processing
duration. Missing observations from older trader releases are explicitly unknown.
Old successful or failed diagnostics remain visible without becoming current
socket assertions. A dashboard-only update cannot add telemetry to an old trader.

An idle session is reported by the running bot, not inferred from a browser's
clock or a hard-coded weekend calendar. Silence on an order stream is normal
when no orders change. During an active window, absence of accepted market data
for over five seconds is shown as awaiting fresh data. That is a display rule,
not a replacement for the strategy's stricter freshness and execution checks.
Connected sockets do not establish login acceptance, executable depth, route
qualification, a valid CAS signal or trading permission.

## WebSockets still need liveness observations

Ping/pong detects broken transport. The latest accepted message establishes data
age. A bot-status timestamp detects a stopped or stalled process. An authenticated
SSE pulse detects a broken dashboard stream. None can replace the others: an
open socket can deliver no usable data, and a working web server can serve a
stopped trader's old status. Pulses never advance broker/source timestamps unless
an actual new source observation supplies them.

## Implementation

- REST GET admission is shared by account/base URL within the process/event loop.
  Execution checks take priority over background reconciliation and routine cash
  reads; the existing 110ms request spacing remains. In-flight HTTP calls are
  neither cancelled nor automatically retried. This limiter does not coordinate
  other processes; the dashboard sidecar retains its sparse independent check.
- Cash and position reconciliation proceed independently. A slow/failed cash GET
  cannot hold up reconciled position management. Failures block new entries at
  once. Revisions are checked before publishing; an aged position batch is read
  again. Existing fresh buy/sell preflight and durable order accounting remain.
- Reconnect delay grows with jitter after short-lived connections. It resets only
  after at least 30 seconds and a processed message. Disconnect notification
  immediately clears connection authority, before a decoding backlog drains.
- Transport decoding uses a bounded FIFO queue. No strike confirmations or order
  events are coalesced. Receipt timestamps are captured before queue waiting and
  carried to strategy observations and raw recording. Queue metrics cover this
  application queue, not an inferred exchange/network backlog. The library's
  receive buffer is also bounded.
- SSE sends changed snapshots or compact source timestamp updates. Unchanged
  tables, diagnostic rows, timing panels and activity entries keep their DOM.
  Polling remains a failure fallback. Hidden tabs disconnect. Source staleness,
  out-of-order responses, session expiry and reconnects are still handled.
- Official-format synthetic frame tapes run through the production transport,
  decoders, strategy and order ledger, including bursts and reconnects alongside
  existing partial-fill, duplicate-notification, stalled-read and cash-outage
  cases. These are execution-behavior tests, not historical profit backtests or
  live network latency measurements.

## Validation and release boundary

The 356-case full run passed **350 tests** and failed **six unchanged localhost
socket integration cases** because this environment rejects socket creation with
EPERM (48.64 seconds). The focused dashboard/runtime/health suite passed **80 tests**
(40.89 seconds). The final clock-source correction was checked by rerunning the
two production burst/reconnect replays; both passed. This remains incomplete
release verification because the genuine socket cases cannot run here.

Twelve offline production-source mutation checks rejected their injected defects;
three socket-dependent checks remain uncredited. The full unmodified suite and
all fifteen mutation cases remain required for a trader verification receipt.
No marker was generated and no acceptance case was removed.

The browser bridge request could not connect; a separate socket probe returned
PermissionError/EPERM. This prevented Cloud Console inspection and live browser
validation. No credentials, account authority or running trader were changed.
The UI detector reported only existing em-dash unknown-value placeholders.

Use [the release guide](RELEASE-2026-10-04.md) for the separate dashboard deployment
and isolated trader verification. The new dashboard can be deployed independently,
but will honestly report live feed health unavailable until the operator installs
the verified matching trader release. Do not remove freshness checks to clear a
banner or rerun funded activation to install a monitoring update.
