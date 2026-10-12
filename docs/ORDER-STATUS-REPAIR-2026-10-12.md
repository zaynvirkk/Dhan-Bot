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
