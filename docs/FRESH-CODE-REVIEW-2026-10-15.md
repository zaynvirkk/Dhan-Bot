# Fresh production-path review, 15 October

This pass traced the selected seven engines from protocol decoding and calendar
admission through signal discovery, allocation, selection, durable order intent,
broker reconciliation, fills, exits, restart and token rotation. It found four
additional reproducible defects. Repairing them establishes software behavior;
it does not establish a profitable strategy or tomorrow's exchange fills.

## Reproduced defects and repairs

### A rejected connection check could strand an unused attempt

The service recorded a failed order-socket epoch permanently. Even after REST
reconciliation confirmed a zero-fill rejection, a remaining authorized attempt
could not run without reconnecting the socket. The production-session regression
first timed out waiting for the second request on the original source.

An epoch can now retry after a two-second monotonic cooldown only when the
latest probe belongs to that epoch/account/session, both its local intent and
broker order are definitively REJECTED, and all probe quantities/reservations
are zero with no unresolved intent. The ordinary session admission, current
account, fresh books, order-echo proof, liquidity selection and remaining money
caps still apply. The rejected contract is excluded. Explicit per-session
attempt availability is checked before constructing another qualifier.

An unknown HTTP result, pending intent, foreign account, old epoch/date,
future-dated intent or any recorded fill cannot satisfy the retry predicate.
The normal two-attempt limit and INR100 daily/INR500 lifetime money caps remain.
No attempt is refunded or granted. A deterministic session clock now also
timestamps the probe intent, so expiry/date exclusions and route receipts use
the same clock as the service and replay.

Production-session tests cover rejection followed by a different accepted
zero-fill check, and two rejections exhausting the existing allowance without
a third request. Pure negative cases cover unresolved/foreign/filled/old/future
or superseded evidence. Fixtures submit only to a synthetic broker.

### A late rejection could block a newly connected socket

If the order socket reconnected while a probe's HTTP request was pending, its
eventual failure was assigned to whichever epoch was current when the response
arrived. That could block the new socket using the previous socket's rejection.
The new current-epoch retry checks would correctly refuse that mismatched
evidence, stranding the remaining attempt again.

A real transport-queue test first timed out after reconnecting during the
synthetic rejection response. Failure bookkeeping now uses the epoch captured
when that attempt began. The test reaches a different second contract, proves
the new socket, remains zero-fill and consumes exactly two attempts. An old
request cannot qualify or poison a new epoch simply because its HTTP reply is late.

### Exit code could confuse a closed intraday row with the held position

ExitManager selected the first matching security ID before checking product
identity. A zero-quantity INTRADAY record preceding the held MARGIN row could
therefore block a valid reduction. It also performed a duplicate positions GET
before the OMS's existing serialized position check.

The negative fixture first failed with a real MARGIN holding behind that closed
row. ExitManager now delegates position admission to the existing OMS check,
which matches NSE_FNO/MARGIN and pending sells under the writer lock. The
fixture passes with one positions GET instead of two. Whole-lot and freeze
limits, durable intents, pending-sell reservation and the final oversell check
remain. Existing insufficient-position regressions still reject sales.

This removes one avoidable HTTP wait. It does not guarantee that displayed bid
depth or a limit price survives the remaining network delay.

### An old bankroll could hide newly affordable seconds setups

Seconds discovery retained the budget from its previous candidate. If that old
budget rejected every setup, no candidate reached the code that refreshed it.
A larger reconciled bankroll could therefore remain invisible indefinitely.

The regression supplies real prior quote history and the actual fitted-response
rule. With an old INR100 filter and current reconciled INR7,805 cash, the old
source returns no signal. Repaired discovery uses the current allocation from
the existing account reader: it rejects the unaffordable nearest strike and
finds the next affordable strike. A subsequent cash reduction removes the
signal again. This test creates no order intent.

The cached balance is only a discovery filter. Actual submission still fetches
funds, computes the capped allocation again, and checks current authority,
reconciliation, input age, price limits, depth, spread and fee reserves. No
extra polling request or weaker cash check was introduced.

## Independent positive path and live checks

A separate causal synthetic quote sequence now exercises the actual rule and
production shared OMS without replacing signal generation: BUY request, matching
broker fill, a later executable quote causing SELL, matching sale fill and flat
ledger. That proves the path is reachable in a fixture, not that a historical
or future market will supply those prices.

The request/status/market adapters were cross-checked against Dhan's current
[order contract](https://dhanhq.co/docs/v2/orders/),
[order updates](https://dhanhq.co/docs/v2/order-update/) and
[FULL feed specification](https://dhanhq.co/docs/v2/live-market-feed/).
IOC cancellation is not an executed trade; order acknowledgement/socket echo
does not fabricate an exchange trade ID or fill. Ambiguous writes remain
reconciliation obligations rather than automatically repeated orders.

At22:35IST a fresh read-only VM check reports INR7,805.94, no positions or
pending orders, the same three zero-fill connection checks and no API errors.
The operator-upgraded `df38627` funded process is active with its own current
software proof, seven funded names, current account and connected sockets.
The earlier token repair has now renewed successfully: the cached credential
was issued at19:48IST and Dhan reports validity until16October19:48. That is a
real renewal observation, not merely configured PIN/TOTP presence.

## Deployment boundary

Runtime repair revision4 distinguishes this pass from the already activated
revision3. Publishing a new dashboard/read-side release does not replace or
restart the funded trader. The operator source switch remains:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python /opt/sablestone-dhan-dashboard/current/ops/activate-seconds.py --apply
```

No extra-attempt flag is needed. The assistant does not run that financial
activation or send real orders. After the operator switch, funded/dashboard
sources and revision4 must agree. Friday's fresh accepted route, usable quotes
and qualifying setup still need to occur; no forced entry or profit is promised.
