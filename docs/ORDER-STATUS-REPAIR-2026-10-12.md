# Dhan order status parsing repair — 12 October 2026

## Observed production failure

At 09:40 IST the funded trader submitted its existing automatic, nonmarketable
LIMIT-IOC route probe (one NIFTY put lot, premium limit INR 0.05).
Dhan REST reconciled CANCELLED, zero fills, no position. The current order
WebSocket carried matching order/correlation identities in the same connection
epoch, but supplied `Data.status: "Cancelled"`. Production accepted lower-camel
account/order identifiers but omitted the lower-camel status field. Consequently
route proof stayed false and new entries remained blocked.

The documentation example uses `Status`, while the observed live message uses
`status`. The adapter now accepts both and normalizes case. Route proof admits
only recognized, non-rejected states, still requires the matching current
connection epoch and reconciled zero position with no unresolved intents.
Missing, foreign-account, rejected and unknown updates cannot qualify entries.

## Verification and rollout

A production-session regression using the observed field shape first failed
on the unchanged parser. Five additional production-session scenarios cover
successful native messages and the four negative cases. The focused 20-case
suite passes. The complete 438-test suite, all 60 acceptance cases and 15
production guard mutations pass; installed rollout is recorded below after
the VM checks complete.

No strategy thresholds, money allocation, mandate, probe budget, ledger or
credentials are changed. Today's configured one-probe allowance is already
used; a restart cannot invent current-connection proof or reset that allowance.
The next eligible automatic probe is governed by the exchange calendar and
existing route windows. No executed strategy trade or profitability is claimed.

## Observed strategy and account state

At 09:45 IST GAP_FADE_DOUBLE correctly reported NO_SIGNAL: opening gap
+0.323%, below the 0.50% minimum, with 111.4% gap fill above the 100% maximum.
Persistence and falling-futures confirmation passed. The afternoon rebound
check remains scheduled for 15:10; today is not a NIFTY expiry session.
Available cash was INR 8,822.36, zero positions, zero executed trades.

## Installed outcome

Application release `c57221f8bd92b30c461327298a46c8f746daf4e6` is pushed to
GitHub and installed on the existing VM. Dashboard deployment passed 59 local
and 78 installed checks, public TLS/authentication, and authenticated status.
The funded-service upgrade was run directly under the operator's standing
authorization; the VM passed 438 tests, 60 acceptance cases and 15 mutations
before applying the release with the existing mandate preserved.

At 12:01 IST funded PID 329313 was running with zero restarts, software
verification true, armed broker writes, all three strategies and all three
sockets connected. Market/index observations were current; no metadata or
recorder error. Across 25 one-second samples, 24 account snapshots were fresh
and every reason string was empty. Dhan still reported INR 8,822.36, no
positions, and only today's cancelled zero-fill probe.

The signed-in dashboard was inspected in the actual browser: authenticated
status HTTP 200, current account/books/strategy inputs, opening-gap condition
failed, and selloff condition passed near noon but awaiting its 15:10 check.
Route proof is still false after the connection restart. The one-probe daily
allowance was not reset or increased. The operator was asked specifically
whether to allow two attempts per session under unchanged cash caps; no such
change is credited unless approved and actually applied. Otherwise the next
eligible probe is 13 October at 15:05 IST under the observed calendar.
