# Live feed and account recovery, 16 October 2026

The broker recorded a real non-expiry trade this morning: 65 NIFTY 19 October
23,000 PE bought at 106.30 and sold at 108.95, gross INR172.25. The captured
cash increase from INR7,805.94 to INR7,924.03 is INR118.09; final itemized
charges have not been reconciled, so this is not an audited net trade result.

## First deployed repair

Release 09db413 was installed and applied by the assistant under the operator's
explicit live repair authorization. It passed 662 software tests including 60
acceptance cases and 15 injected-defect checks. The installer also passed 94
VM checks. A previously uncaught local dashboard startup socket timeout now
retries within a bounded deadline, preserving authentication and collector
freshness requirements.

The release gives the ordered market decoder scheduling opportunities every
16 frames, uses a bounded 20/30-second market ping watchdog, starts independent
account reconciliation reads together under the existing revision fence, and
caches discovery allocation for at most 250 ms with immediate funds/revision
invalidation. Order placement still recalculates actual affordability. Closed
and cancelled entries cannot retain a misleading submitted status.

The funded upgrade created a new order socket. Its automatic zero-fill route
check at 10:06:46 IST succeeded and consumed today's second ordinary attempt.
The normal two-attempt allowance and INR100 daily/INR500 lifetime probe-money
caps were not changed. Seven existing strategies remained funded; no new
strategy, wider entry limit or loss rule was introduced.

The initial repair did not fully solve the live feed. Another keepalive timeout
occurred at 10:10:31 and 10:15:42 IST. The full 1,462-option stream held a full
65-message application queue while the separate 24-option observer had current
futures quotes. This was reported as an unresolved issue, not a completed fix.
Runtime CPU/IO weights of 1,000 gave the funded service priority over the
collector and observer without restarting or changing its trading policy.

## Follow-up repair

A read-only six-second mirror of the same full market subscription observed
5,798 messages, including 758 single 162-byte FULL snapshots declaring length
70. All 758 had zero bytes in the complete 100-byte depth region. No raw
credentials or market-frame bodies were printed or committed.

Previously each such empty snapshot invalidated all unrelated market history.
The framing layer now recognizes only this exact single-message, NSE-FNO,
positive-security-ID, empty-depth shape. It passes the original bytes unchanged
to the existing contract decoder, which rejects the invalid header and revokes
that contract's book. It never creates an executable quote or corrects a bad
header. Nonempty, concatenated, truncated, wrong-segment and unidentified bad
frames retain whole-message quarantine. Provider disconnects still reconnect.
The production-session regression verifies another contract survives, the
invalid contract cannot trade, and a subsequent valid quote restores it.

For the current seven-engine configuration, subscriptions follow independent
observed spot/futures anchors: 32 nearest contracts per anchor in the first
three expiries, while preserving every held or pending contract and the futures
instrument. Active CAS expiry sessions retain every same-day contract. Other
strategy configurations retain the broad subscription behavior. Additions go
before removals in batches of at most 100 over the existing socket. A failed
update cannot claim coverage; reconnect replays the desired window. No frame
coalescing, fabricated prices or freshness relaxation is used. Runtime revision
6 and the dashboard revision requirement expose a pending funded upgrade.

A focused nearest-strike window reduces market-data coverage away from its
anchors; it does not prove that every far-strike opportunity from a full chain
is observed. Existing selection, liquidity, affordability, signal and execution
rules remain necessary. An unknown anchor cannot invent a tradable chain.

Dhan's official [market-feed documentation](https://dhanhq.co/docs/v2/live-market-feed/)
requires at most 100 instruments per request and describes the 162-byte FULL
layout and server ping/pong. Its [request-code table](https://dhanhq.co/docs/v2/annexure/#feed-request-code)
assigns 21/22 to FULL subscription/unsubscription. The empty padded snapshot is
an observed exception, not a claim that the documented executable layout changed.

## Deployment boundary

The first release is funded and live. The follow-up must pass current-source
verification, installation and live observation before it can be called live.
A restart requires a new order-socket route check; today's two ordinary attempts
are already used. An additional dated attempt needs an explicit operator grant,
with the same daily/lifetime money caps. The existing funded service continues
while that bounded exception is pending. No test count, dashboard heartbeat or
software deployment guarantees a fill or profitable trade.

The follow-up frozen source passed 669 tests, including 60 acceptance cases,
and all 15 injected-defect checks. Digest:
`acf8e742e7510fe7f4a0624fb1a3cfa6f9c19aee2ca0f61e0bc41df2aa7bc7a4`.
This is software evidence; funded installation and feed stability are separate.

A subsequent read-only broker check at 10:28 IST confirmed a second filled
SECONDS_FUTURES_CATCHUP lifecycle: 65 NIFTY October 23,150 CE bought at 94.85
at 10:18:15 and sold at 96.45 at 10:18:19, gross INR104.00. Cash was INR7,975.49,
with no open position or pending order and 11 total orders today. Both actual
trades total INR276.25 gross; the cash change from INR7,805.94 is INR169.55,
not a final audited charges attribution. The full feed had reconnected five
times, so the outstanding transport repair was not marked resolved.
