# Funded route recovery, 12 October 2026

## Observed execution boundary

The VM is receiving usable index and option observations, with current broker
cash INR 8,822.36, zero positions and zero recorded fills. The durable aggregate
inspection finds two historical route-check intents (one rejected, one cancelled),
zero strategy lifecycles and zero stored qualifying directional signals. There
are three configured engines: GAP_FADE_DOUBLE, NIFTY_SELLOFF_REBOUND_1510 and
CAS_LAG_V1. The other previously named research candidates are not deployed bots.

Today's +0.323% opening gap fails the 0.5% morning rule. Rebound checks at 15:10
IST; today's indicative selloff condition passing before that time is not an
entry decision. The next loaded NIFTY expiry is 13 October.

## Recovery repair

Order-route proof must be current to the order socket connection. A restart
invalidates old proof; the original one-attempt allowance prevented a new probe
once today's allowance was used. Restricting rebound qualification to 15:05–15:10
also left repaired services blocked between strategy windows.

Source release `687d7335369e867b6549e8ce4ea1211230307d33` permits bounded
qualification during the verified open exchange session before rebound's 15:10
decision. It still rejects missing, stale, holiday and closed calendars; does not
move strategy entry times; and does not permit extra attempts beyond the saved
mandate. CAS-only and gap-only route scheduling is preserved.

The operator's follow-up instruction to fix/restart and do what is necessary
authorizes one additional bounded route attempt. Only the per-session attempt
limit changes from one to two. The INR 100 session and INR 500 lifetime probe
cash caps, capital allocation, other mandate fields, durable counters and trading
strategy rules are preserved. No counters or history are reset.

Runtime/dashboard expose used attempts and the saved limit independently from
trading authority and route proof. Missing counts remain unknown.

## Software and rollout evidence

The midday qualification regression fails before the scheduling repair.
Production-session replay demonstrates fresh proof after an order reconnect with
two permitted attempts, and no extra order under an exhausted one-attempt
allowance. Local verification passes 447 cases including 60 acceptance cases and
15 guard mutations. Covered source digest:
`31978e29046b091d4d23d3a8303a64d12fc544a8194d5bc8327e98239f272c04`.

GitHub/dashboard deployment verifies 60 local and 79 installed dashboard checks,
private current account reads and public HTTPS authentication. The first funded
upgrade fails an existing invalid-frame replay check before switching the
service. Its mandate change is rolled back; old PID 329313 remains running.
The isolated replay passes on the VM. A complete guarded retry retains actual
subprocess output without weakening its results or changing any acceptance
command. The guarded retry passes all 447 cases, 60 acceptance cases and 15
mutation checks, then applies the funded upgrade successfully.

## Verified live outcome

At 13:34 IST the current trader receives two native Dhan order notifications and
reconciles the new qualification order. Broker route proof becomes true; state
is ARMED_WAITING_SIGNAL with funded account, enabled write authority and current
software verification. The funded service runs PID 332639 on release `687d733`
with zero automatic restarts. The saved per-session allowance is two and both
attempts are now used. No further restart or attempt is performed.

At 13:40 IST a fresh broker snapshot reports INR 8,822.36 available cash, zero
positions and two cancelled buy qualification orders, both filled quantity zero.
The durable ledger has three historical qualification intents, zero fills and
zero incidents. Broker P&L is unreported, not assumed zero.

The authenticated browser at 13:36 IST shows the actual new release: available
cash INR 8,822.36, zero positions/fills, Trading authority enabled and Funded
trader: watching configured strategies. The previous unverified-route blocker
is cleared. Strategy rows retain the actual inputs and scheduled checks; the
morning window is finished and rebound waits for 15:10 IST. No strategy entry
has yet been submitted or filled.

Final inspection confirms the installed covered-source digest above and current
verification marker match. Funded trader, dashboard, collector, daily monitor
and HTTPS proxy services are running with zero automatic restarts. The durable
6 October attempt remains one; today's attempts are two with recorded entry
debit reservation INR 55.78. These accounting counters are not realized broker
fees or profit. The aggregate historical probe spending counter remains INR
27.89. No history was reset to obtain the second attempt.

No profitability or strategy fill is credited by software verification or by
a cancelled zero-fill qualification order.
