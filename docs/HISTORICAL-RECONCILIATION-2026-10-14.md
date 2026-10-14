# Historical order reconciliation and cash explanation

## Confirmed incident

On 14 October the dashboard retained a stale independent account snapshot and
called it a failed broker read. Direct funds/positions/orders reads succeeded,
but funded account reconciliation repeatedly failed after the trading-date
rollover. Dhan's historical endpoint returned 32 order-level execution rows for
13 October, while the durable bot ledger contained 69 individual execution
fills. All 32 historical orders exactly matched recorded quantity, turnover,
account, side, security, product and segment, but supplied different trade IDs.
Replaying these summaries as new fills correctly triggered the quantity guard.

The dashboard fallback could then wait five minutes because the shared source
had been healthy when its check completed. A successful check expiring after
60 seconds was incorrectly labelled BROKER_READ_FAILED. The stale funded
failure reason also survived an otherwise successful later reconciliation.

## Repair

Historical data through yesterday is kept separate from today's live trades.
A terminal order with a complete local fill quantity may accept a historical
summary only when quantity and turnover match exactly and every supplied
identity field agrees. The summary corroborates the existing fills; it cannot
create another fill or change recorded execution prices/quantities. Incomplete
or unresolved execution still follows ordinary fill-identity reconciliation.
Foreign identity, changed quantity/turnover and invalid charges fail closed.

An additive `order_charges` table records matched reported fees separately.
Receipts are idempotent and cannot lower already recognised charges. Risk
accounting uses the maximum of per-fill fees, order-level reported fees and
the existing conservative estimate; it does not add the same fee twice.
Missing fee components cannot establish a complete charge receipt. Existing
ledger files upgrade through CREATE TABLE IF NOT EXISTS; no fills are reset.

Successful account reconciliation clears only its own previous account-read
failure. Dashboard checks reassess shared-source availability every 15 seconds
without repeating HTTP requests while the shared source is healthy. Fresh,
stale, failed and unavailable observations have different user messages. A
fresh independent balance cannot conceal stale funded reconciliation.

The money view reports gross results, broker-reported charges and net results
for recorded closed bot trades. Net results remain unavailable until all
covered executed orders have complete charge receipts. This is historical bot
execution evidence, distinct from the broker's current-day position P&L.

## Verified cash arithmetic before deployment

Dhan historical execution rows report gross turnover difference INR 2,791.75:

| Charge | INR |
| --- | ---: |
| Brokerage | 640.00 |
| STT | 208.00 |
| Service tax/GST field | 132.7716 |
| Exchange transaction charges | 97.3500 |
| Stamp duty | 4.00 |
| SEBI tax | 0.2700 |
| Total | 1,082.3916 |

Gross minus these charges rounds to INR 1,709.36, matching the broker ledger's
posted credit. Opening ledger balance INR 8,822.36 plus that credit equals
INR 10,531.72, matching available/start-of-day/withdrawable funds with zero
utilised margin or blocked payout. This is INR 165.80 below the previous
evening's available balance, consistent with final settlement rather than a
new trade loss. No subscription deduction is inferred from the difference.

## Verification boundaries

Exact fixtures exercise the actual OMS and ledger with multiple individual
fills followed by a differently identified aggregate history row, repeated
receipts, conflicting account/economics, nonfinite/negative fees, conservative
cost floors and recovery reason clearing. Collector and real DOM cases cover
expired successful checks, fallback readiness, incomplete charge coverage and
the distinction between fresh cash and funded reconciliation. All fixture
orders use synthetic accounts. Deployment preserves authority, capital and
route-probe caps and requires a flat actual broker account. Full release
acceptance and mutation checks supplement these cases.

This fixes an observed reconciliation defect. It does not establish that every
possible bug is absent or that one session's strategy results are repeatable.
