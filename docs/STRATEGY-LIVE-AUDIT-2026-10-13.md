# Strategy inventory and funded-service audit — 13 October 2026

## Conclusion

Real-money execution is working. **All three implemented engines are enabled;
only CAS has recorded fills. The other research strategies are not live.**
An enabled engine is not a promise of a qualifying signal, a fill or profit.
The audit checks production source, saved authority, the VM, broker records,
the signed-in dashboard and the repository's research scoreboards. It does not
declare every discussed hypothesis implemented or statistically validated.

## Implemented engines and actual executions

The production strategy registry accepts exactly these three names. Contracts
are NIFTY NSE index options, both CE and PE where the strategy permits them.
The production trader does not implement the whole stock/index/futures F&O
universe discussed in the research conversation.

| Engine | Saved real-money authority | Actual filled lifecycles on 13 October | Eligibility and direction |
| --- | --- | ---: | --- |
| GAP_FADE_DOUBLE | Enabled | 0 | Ordinary, non-expiry regular sessions; 09:45–11:30, every five minutes; gap, retracement, three completed closes and futures confirmation; CE or PE |
| NIFTY_SELLOFF_REBOUND_1510 | Enabled | 0 | Completed 15:10 observation, decline at least 0.75% from open; CE; contract must survive the planned next-session exit |
| CAS_LAG_V1 | Enabled | 16, all closed | Contract-confirmed expiry and provider-confirmed auction phase, persistent official indicative input and executable option-book checks; CE or PE |

The windows belong to the implemented signal definitions. Removing them would
create different strategies. Exchange-session availability is obtained from the
calendar, and actual contract dates determine expiry; a weekday alone does not
authorize an entry. Services and connections run continuously, including exit,
recovery and account observation outside entry windows. REST requests for
completed minute candles remain necessary for the two candle-based engines.

CAS is not the earlier EXPIRY_FORCED_FLOW research strategy. That separate rule
requires the specified premium/OI/volume conditions and has no production path.

## Broker and ledger reconciliation

After the auction, the current Dhan account reports:

| Observation | Value |
| --- | ---: |
| Available cash | INR 10,697.52 |
| Open positions | 0 |
| Dhan realised P&L | INR 2,791.75 |
| Dhan unrealised P&L | INR 0.00 |
| Current-day broker order records | 66 |
| Current-day trade/fill records | 69 |
| Pending intents / unclosed lifecycles | 0 / 0 |
| Runtime incidents recorded | 0 |

The 69 partial-fill records map to **32 executed CAS orders and 16 filled,
closed CAS lifecycles**. They are not 69 completed bets. There are 37 closed CAS
lifecycles when unfilled attempts are included. The 64 CAS order records include
cancelled attempts; today's other two broker orders are unfilled route probes.
Historical qualification records in the ledger are not all today's orders.

CAS bought and sold exactly 8,515 option units. Recorded buy turnover is
INR 135,606.25; sell turnover is INR 138,398.00. Their difference of
INR 2,791.75 matches broker-reported realised P&L. Broker reconciliation reports
settlement complete, matching account state and no unresolved execution.
Available cash is not a substitute for marked equity or a final contract note.

**Final profit after every charge remains unknown.** At 16:19 IST the dated,
paginated trade-history endpoint returns no same-day historical rows, while the
current trades endpoint returns 69. Charge totals are therefore unavailable,
not zero. The [Dhan statements API](https://dhanhq.co/docs/v2/statements/)
provides trade-level charge fields once the records are published. The audit
does not backsolve fees from a change in available cash.

## Research inventory: what is missing from production

The [machine-readable inventory](strategy-inventory-2026-10-13.json) collects
177 distinct identifiers from nine scoreboards. These include exit variants,
not 177 independent validated edges. Including the separately implemented CAS
engine gives 178 inventory entries: **3 live implementations and 175 research
identifiers without a production order path**. It records the scoreboards where
each identifier appears and whether it is implemented and enabled.

| Original gauntlet family | Production status |
| --- | --- |
| EVENT_CONTINUATION | Research only; no live event-classification-to-order path |
| INTRADAY_EVENT | Research only; no live timestamped-disclosure-to-order path |
| EXPIRY_FORCED_FLOW | Research only; not equivalent to CAS_LAG_V1 |
| NONEXPIRY_FORCED_FLOW | Research only |
| PASSIVE_FLOW | Research only; no production rebalance signal feed |
| SECTOR_SHOCK_LAG | Research only; no production exposure-graph signal path |
| SCHEDULED_EVENT_VOL | Research only; no production event/volatility entry path |
| BLOCK_OFS_DISLOCATION | Research only; no production announcement-to-order path |
| CROSS_MARKET_LEAD_LAG | Research only; the Upstox connection is not an implemented lead/lag engine |

The [recorded gauntlet](../research/results/GAUNTLET.md) withdraws the earlier
EVENT_CONTINUATION leadership claim. Event/intraday paths lose money in their
bounded models; unresolved data prevent a definitive full-family bankroll.
Zero-signal narrow tests are not evidence that a full family works.

Later [intraday experiments](../research/results/intraday_challengers/REPORT.md),
[rebound validation](../research/results/rebound_validation/REPORT.md),
[readiness experiments](../research/results/readiness/REPORT.md) and the
[execution frontier](../research/results/execution_frontier/REPORT.md) contain
additional candidates and variants. They do not certify live profitability:
gap-fade loses in the earlier window and deteriorates with delayed fills;
rebound fails additional validation and depends on execution assumptions;
the frontier finds no allocation profitable in all three reported windows.
These are dated research artifacts, not freshly rerun market backtests in this
operational audit. Current live CAS profit does not resolve their limitations.

Making those research families live requires actual production data adapters,
deterministic signals, contract selection and integration with the existing
execution/recovery path. Adding their names to configuration cannot do that.
This audit does not invent missing engines or change the operator's capital
allocation or current entry rules.

## VM, credentials, API and execution checks

The funded service remains on verified source `197c4f8`, PID **338550**, active
with **zero restarts** during the audit and read-side deployments. Runtime
software verification and the actual funded broker-route proof are true.
Config and mandate both enable authority; the funded process has no read-only
interlock. Allocated capital remains INR 9,411.18. Route-probe allowances remain
two attempts, INR 100 per session and INR 500 lifetime; no cap was increased.

Seven real read-only checks pass: Dhan authentication/F&O/data plan, account,
static-IP whitelist, contract metadata, Upstox signal socket, Dhan option socket
and Dhan order socket. The refreshed check finishes successfully at 16:24 IST.
Dhan reports an Active data plan, with validity through 8 November. The token
validity observed in that response is 14 October at 07:47. Saved PIN/TOTP renewal
material exists; source rotates sessions and reloads contracts/calendar on
day rollover. No secret value is published. Current authorization is verified;
future token renewal and future fills are not promised by that observation.

All three runtime sockets are connected with no current socket error or
queued messages. Provider CAS_STOP and an idle closed session are expected
after the auction. A temporary diagnostic order socket's `route_verified=false`
means that read-only check cannot certify a write route; it does not override
the separately recorded successful funded-route proof.

Source inspection confirms existing intent persistence before submission,
whole lots, Decimal money, freeze limits, fee/cash checks, partial-fill tracking,
ambiguous-submit reconciliation and restart recovery. The dashboard and daily
observer have separate read-only services; the public HTTPS endpoint requires
authentication (unauthenticated status returns HTTP 401). The dedicated
`dhan-dashboard-caddy.service` serves HTTPS; the unused distro `caddy.service`
is intentionally disabled.

The VM has about 1 GB available memory and 7 GB free disk, with roughly 63% disk
usage at the audit. Ledger size is about 2.7 GB plus a 64 MB WAL. A full read-only
SQLite quick check returns `ok`. These are dated capacity observations, not an
estimated retention horizon. Earlier all-day journal failures include prior
release activity and are not evidence that the current funded PID restarted.

## Latency and existing WebSockets

| Recorded process timing | Median | p95 |
| --- | ---: | ---: |
| Decision to submit | 573 ms | 1,196 ms |
| Order HTTP round trip | 227 ms | 515 ms |
| Submission to first fill recording | 2,260 ms | 3,265 ms |
| Option-book age at entry checks | 508 ms | 1,526 ms |

These measurements are from the current process's recorded counters. First
fill recording includes reconciliation/observation delay; it is not exchange
matching latency. Old post-close prices do not measure in-session execution
speed. A WebSocket being open is not proof of current usable input.

Upstox signals, Dhan option books and Dhan order updates already use WebSockets.
The [Dhan market protocol](https://dhanhq.co/docs/v2/live-market-feed/) still
requires ping/pong liveness handling; removing health timestamps would hide a
stalled connection. Faster submission must preserve cash/depth freshness and
ambiguous-order reconciliation. Latency measured today does not prove a
minute-candle backtest's historical queue position or subsecond fills.

## Repairs implemented and deployed during this audit

1. **Open positions versus closed records:** account diagnostics now derive
   explicit open exposure from `netQty`/`netQuantity`. Invalid or missing
   quantities fail rather than inventing zero. Browser diagnostics correctly
   show `0 open positions · 2 position records · 66 orders`, matching Money.
2. **Diagnostics freshness:** the old once-per-afternoon timer is replaced with
   a read-only check after boot and every ten minutes after completion. It runs
   for morning strategies too. The VM timer is enabled and active; successful
   checks remain within the dashboard's freshness window. The installer only
   refreshes an already enabled timer and never restarts the funded trader.
3. **History wording:** WAITING_EXCHANGE_SESSION is shown by name rather than
   Unknown state. During that state an inherited execution reason is explicitly
   a last recorded execution note, alongside the absence of new session entries.

Negative cases reproduce the position-count and closed-history mismatches before
repair. The timer case rejects the old afternoon-only schedule. Full local
verification passes **461 cases, including 60 acceptance cases and 15 killed
mutations**, with broker writes disabled. The final history-copy change passes
the actual JavaScript page/stream cases and scoped Python dashboard checks.
Dashboard installer checks also pass on the VM. Diagnostic release `80abcce`
and history follow-up `bde7887` are pushed and deployed; the funded release is
unchanged. Final authenticated browser/VM observations are recorded below.

At **16:30 IST**, an independent SSH check confirms current read-side release
`bde788771f721fe9612906a41c2ed246a7b75715`, its installed-check marker, and active
dashboard, collector, HTTPS and daily-monitor services. The funded PID remains
338550 with zero restarts. The diagnostic timer is enabled, with the next
automatic run scheduled for 16:34 IST after its successful 16:24 completion.

A cache-bypassing signed-in browser request and actual deployed DOM confirm
current account/runtime/collector, enabled and armed authority, verified route
and software, all three engines, AVAILABLE history and seven PASS checks.
The account count and ten-minute schedule wording match the fixes above.
History now says Waiting for an exchange session and labels the inherited
execution note. The event stream is open, the misleading notice is hidden and
the screenshot is inspected. Cash/P&L/fills remain as tabulated above; the
session is IDLE with provider CAS_STOP. Browser focus emulation is restored.

Exact full verification command: `.venv/bin/dhan-cas verify --state-dir
/tmp/dhan-audit-20261013-release-verify`; covered-source digest
`55357ac7789b360d151c2a4cd259f886d7ca6da7b7f8d62bc0af9a7c92750cb9`.
Actual DOM cases run with `node tests/dashboard_stream_test.cjs`. The final
read-side installer passes 83 scoped VM cases and public HTTPS authentication.

## Remaining improvements

- Reconcile final broker charges/contract-note totals once same-day dated
  history is published; report gross and settled net separately.
- Add a measured retention/archive plan for the growing ledger, preserving all
  authoritative orders/fills and information-timing evidence. Disk is not full;
  deleting execution history or guessing a growth rate is not a repair.
- Show realised performance by filled lifecycle and strategy after charge
  reconciliation, rather than treating partial fills as independent bets.
- Implement a research candidate only with its required live inputs and explicit
  execution/recovery integration. The existing failed/conditional validation
  does not support labelling every family profitable or forcing extra entries.

The operational repairs above are complete. These remaining items are identified
improvements, not claims that new production features were shipped in this audit.
