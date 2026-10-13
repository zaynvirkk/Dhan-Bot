# Market and entry audit, 13 October 2026

## Observed account and market

At 10:00 IST the funded service has current order-route proof, enabled real-money
authority and usable Dhan option, Dhan order and Upstox signal sockets. Broker
cash is INR 8,822.36, positions are zero, and the durable fill count is zero.
Today's qualification order is cancelled with zero filled quantity; it is not
a strategy trade. All three configured strategies are active. Previously named
research hypotheses are not additional deployed engines.

The broker reports NIFTY LTP 22,568.15, completed close 22,567.55, session open
22,364.15 and previous close 22,363.35. The move from the open is approximately
+0.91%; the opening gap is approximately +0.0036%. Current contract metadata
confirms NIFTY expiry today. This excludes the morning non-expiry gap experiment;
the selloff/rebound condition is not met, and no auction value is available yet.
Same-day 22,550 CE and PE have affordable one-lot asks and substantial displayed
quantity. That establishes quote availability, not a qualifying or profitable
trade. Public search quotes conflicted with broker observations and were not
used as current prices.

## Yesterday's real signal

Persisted strategy observations establish a CALL signal at 15:10 IST on
12 October: NIFTY 22,308.65, down 1.25945% from the open. The signal required
an option surviving the next session's exit, with minimum expiry 14 October.
No strategy lifecycle or strategy order was created. The consumed signal records
ENTRY_DEADLINE_MISSED. The old version did not retain the preceding candidate
rejection, so its precise blocker is unknown. The current runtime's global reason
cannot explain an earlier process's decision.

Signal evaluation was recorded at 15:10:04.833 IST. This disproves the assumption
that no signal had occurred; it does not prove that processing delay caused the
miss. Historical order-book frames exist around the entry window. Historical
reconstruction uses current contract metadata cross-checked against recorded
security IDs; the prior complete instrument-master payload was not archived.

Read-only Dhan minute history reconstructs the three completed candles available
at the signal. For the eligible 19 October calls, all four pass the policy's
volume/OI gate. Recorded entry-window depth contains 39–40 matching observations
per contract and adequate displayed quantity within the fixed limit. These are
sampled book observations, not an executed order or a guaranteed queue fill.
The blocking cash geometry under the unchanged policy is:

| Strike | Fixed entry limit | One-lot cash with entry/exit reserve | Budget |
| --- | ---: | ---: | ---: |
| 22,300 CE | INR 217.10 | INR 14,269.84 | INR 8,381.24 |
| 22,350 CE | INR 187.95 | INR 12,366.72 | INR 8,381.24 |
| 22,400 CE | INR 161.45 | INR 10,637.04 | INR 8,381.24 |
| 22,450 CE | INR 137.80 | INR 9,092.84 | INR 8,381.24 |

No permitted contract can pass funding at these frozen limits. This independently
establishes an affordability barrier; it does not retrospectively replace the
missing recorded blocker with invented telemetry. A farther strike or shorter
expiry would be a different selection experiment, requiring its own executable
replay before being described as an improvement in profitability.

## Repair

The selector previously required a current quote before computing one-lot
affordability. Missing or stale quotes for an unaffordable nearest contract could
therefore block a cheaper contract. It now computes cash including fees and exit
reserve from already-completed option candles first. Unaffordable contracts are
skipped without requiring a quote; an affordable contract must still have a
current usable book. Selection retains its actual expiry, nearest-strike order,
four-candidate limit, volume/OI, spread, depth, fixed-price and deadline rules.
This regression establishes a real defect, not that it caused yesterday's miss.

Each qualifying signal now retains its binding assessment and contract checks.
On an expired entry window, the consumed record preserves the preceding reason.
The dashboard projects only allowlisted history and shows the last qualifying
signal separately from current checks, including skipped entry and candidate
costs. Missing historical reasons remain unknown. A recorded order decision does
not appear as a fill. The dashboard remains read-only.

## Verification and rollout

Negative execution tests were added before the selector change. They demonstrate
an affordable farther candidate remains reachable past an unaffordable contract,
while a stale quote on that affordable candidate still prevents ordering. A
missed-window test verifies persistence of the binding reason. Dashboard tests
cover private-field filtering, unknown legacy reasons and separation of a
historical CALL signal from current Waiting status.

Local and VM funded verification pass 452 cases including 60 acceptance cases
and 15 guard mutations. Release `197c4f829eff890cbadf49ddb9f84090d2404d4e`
is pushed to GitHub and applied directly. The first upgrade preflight rejects
the restarted read-only monitor's stale observation before changing the trader.
After the monitor publishes fresh inputs, the guarded retry succeeds. The
existing mandate, capital allocation and probe caps are preserved.

At 11:36 IST the funded service is PID 338550, active with zero restarts since
the upgrade, current software digest and fresh broker-route proof. All three
sockets are connected, with no pending messages or current error. Cash remains
INR 8,822.36, zero positions, zero fills, zero incidents and zero strategy
lifecycles. Both current-day qualification orders are cancelled with zero filled
quantity. The second of the two permitted route attempts completed after restart;
no limit was raised or counter reset. The matching funded source/marker digest is
`d4c4d419b63d89bc2caf9a37a8eb85d29e1a1adfa5cffacf9a74653f83568fee`.

Authenticated desktop/mobile inspection confirms the historical signal and
unknown legacy blocker are visible, with no document overflow. Further browser
checking exposes intermittent request timeouts: the live status/fallback path
transfers roughly 740 KB of retained history repeatedly. Compact authenticated
status and event modes now omit the journal from routine live transfers. The
browser preserves cached history, requests it once per minute, and can merge an
older journal response without replacing newer live authority. Default full
status remains compatible, and omission does not bypass authentication. This
read-only transport update does not restart the already-qualified trader.

Transport releases `ea03527` and `eeb1b5` are pushed and installed on the VM.
Finite authenticated status/journal responses negotiate gzip; live event streams
remain uncompressed. The full journal falls from 722,549 decoded bytes to 28,488
transferred bytes and loads in 1.75 seconds in the actual signed-in browser after
an uncached reload. History is AVAILABLE, live events are open and current, and
the browser reports enabled authority and fresh collection. An independent
authenticated request returns HTTP 200 with gzip; unauthenticated public status
still returns HTTP 401. Default and gzip-disabled responses retain full history.
The final local verification passes 454 tests, 60 acceptance cases and 15 mutation
guards, with digest
`712136e7480aa47025695b6ace6c6e99f5e4e5560c9276a11deb42482ba7fb11`.

At 12:00 IST the funded process remains PID 338550 with zero restarts. All three
sockets are connected, with no current errors or pending messages; current route
and software verification remain true. Cash is INR 8,822.36, fills and incidents
remain zero. The configured HTTPS service is dhan-dashboard-caddy.service, which
is active; the distribution's separate caddy.service is intentionally disabled.
NIFTY's latest displayed completed close is 22,516.95 at 11:58 IST, approximately
0.68% above the session open. This does not satisfy the selloff threshold. A
fresh read-only connection check is also requested to replace yesterday's
retained Upstox timeout diagnostics, separately from current live socket health.

No signal, missed fill, software check or route qualification is credited as
profitability. Infrastructure repair does not make the three experimental rules
a validated profitable strategy or implement the other research hypotheses.

## Final diagnostic repair and current confirmation

The refreshed legacy check still reports Upstox TimeoutError. A separate
read-only test authorizes, opens the socket and receives the NIFTY index in
1.26 seconds. Instrumented combined checking opens Upstox at 2.5 seconds, blocks
the event loop during contract parsing (12.23 seconds in load_dhan_master alone),
then stalls closing its temporary stream and expires the outer check. The actual
funded signal socket remains current. This is not evidence of a broker outage.

Release `e381a8375ca4947cb6dc49e4f192ee6d2bdd459b` moves contract resolution to
a worker thread and ends the bounded feed check on a usable positive NIFTY
snapshot. A status-only frame cannot pass. The existing read-only connection
unit now follows the current release; its read-only environment, account config
and state directory are preserved. No funded unit or mandate is changed.
Three negative cases cover snapshot completion, missing index rejection and
nonblocking contract parsing. Full local verification passes 457 cases including
60 acceptance cases and 15 mutations, digest
`6b8cf12d3613d54adc0de1b4649de5dcfbd0be22f20da3b86eb27758a1f61ec4`.
The VM installer passes 83 cases, then verifies private local status and public
HTTPS authentication.

At 12:16 IST the repaired real connection check exits successfully and all seven
checks PASS, including Upstox with an observed index frame. Signed-in browser
status shows fresh diagnostics, current open event stream, AVAILABLE history,
enabled authority, verified broker route and current software proof. The full
compressed status response is 28,174 bytes. The funded PID remains 338550 with
zero restarts, three connected sockets, zero current errors/pending messages,
INR 8,822.36 cash, zero positions, fills and incidents. Latest displayed completed
NIFTY close is 22,510.45 at 12:14 IST, approximately +0.65% from the open. Browser
focus emulation is restored after inspection. These are live infrastructure
observations, not trading-profit evidence.
