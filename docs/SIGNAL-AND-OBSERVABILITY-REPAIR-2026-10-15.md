# Signal and operational evidence repairs, 15 October

Today generated zero actual trades and zero gross trading P&L. The three orders
were connection checks, not strategy entries:65units at INR0.05, two low-OI
rejections and one exchange cancellation, all zero-fill. The second rejection
reused the same November20050PE rejected in the morning. The existing
[route-selector repair](ROUTE-SELECTION-REPAIR-2026-10-15.md) addresses that defect.
Funding, deployed source, qualified routing, current inputs, a valid setup and
an actual fill are separate facts. None alone establishes the others.

## Confirmed defects repaired

| Defect | Resulting behavior |
| --- | --- |
|A briefly stale option quote deleted its fitted history.|Keep valid earlier history for up to90seconds, bounded to96contracts/600observations each. Only the current nearest24eligible contracts can produce entries. Stale quotes still cannot trade. Real socket/epoch resets clear history.|
|A single unusable futures book erased all prior fit observations.|Invalidate current futures permission immediately while retaining valid earlier same-epoch observations. Accept recovery only from a usable newly received packet. Duplicate packets cannot refresh freshness. A recovered quote can equal the pre-error quote without being mistaken for an adjacent duplicate.|
|No usable option books could appear as a completed NO_SIGNAL.|Return UNKNOWN / OPTIONS_FEED_UNAVAILABLE. It is missing information, not evidence that a strategy found no setup.|
|Spread, depth, budget and projected edge failures shared one misleading cost label.|Expose distinct execution rejection reasons and their observed cash/depth/net-margin values. Entry limits, spread/depth requirements, costs and thresholds are unchanged.|
|A successful reconnect erased the preceding exception.|Keep a bounded sanitized event history, including error class, transport close codes, keepalive-timeout flag and provider disconnect code when supplied. Never retain exception strings, URLs, headers, tokens or arbitrary close reasons.|
|The simulator swallowed explicit provider disconnect packets.|Allow the transport to invalidate the epoch and reconnect; malformed framing still invalidates quotes without inventing a connection.|
|After-close missing-futures records evicted in-session decisions from the dashboard's query limit.|Use recorded exchange-session bounds to query seconds decisions in UTC/IST before applying the display limit. A missing calendar retains the older bounded behavior rather than inventing hours.|
|A short UI ring was the only detailed health history.|Add separate append-only daily health receipts, with a16MiB/day cap and seven-day retention. Preserve damaged evidence, expose unavailable/cap status and continue current dashboard updates if recording fails. The240-event UI ring remains bounded. This does not reconstruct earlier missing history.|
|Orders did not identify their purpose.|Label connection checks versus strategy orders using exact private broker-order-ID matches to ledger ownership, then discard IDs before projection. Unmatched/manual orders remain unverified. Price or contract name never determines purpose.|
|An updated dashboard could conceal an older funded process.|Publish a runtime repair revision/source commit and show a trader-update warning when the funded publisher predates the required revision. This display never changes financial authority.|

Connection events are queued into the existing durable recorder independently
of the limited flat-position market-frame recording window. If its bounded
queue cannot accept them, recording failure remains visible; it cannot create
entry permission. A previous event can remain historically visible after the
current connection recovers without being labelled a current outage.

The data source uses Dhan's documented FULL binary layout. Its connection
protocol supplies server pings and explicit disconnect reason codes; current
data freshness remains a separate entry requirement. See the official
[feed specification](https://dhanhq.co/docs/v2/live-market-feed/) and
[order specification](https://dhanhq.co/docs/v2/orders/). No particular cause is
assigned to today's14reconnects: a bounded scan of the latest300,000ledger rows
found250,059market frames and no explicit disconnect packet at their start.
This is partial evidence, not proof that no provider error occurred elsewhere.

## Rechecking the no-signal claim

The independent calculation uses375freshly fetched completed NIFTY minute bars,
not the strategy's own evaluation function. All58recorded pullback decisions
match the recalculated30-minute trend and10-minute movement. None satisfies
the necessary trend-plus-opposing-pullback condition. The pullback no-signal
result is independently corroborated.

For the four quote-driven seconds rules, the old and repaired kernels were also
compared chronologically over108,324archived records /5,422sampled decision
seconds, using the same INR7,805.94model bankroll and95%cash budget. Both produce
zero qualifying entry episodes. The repaired history sees more mathematical
strike discrepancies, but cash, depth and conditional net-margin checks reject
them. It does not convert them into alleged profits.

This comparison is a diagnostic, **not an execution backtest**. The archive is
sampled, has no socket epochs or invalid packets, and excludes official event
receipt history. It covers an afternoon subset and a continuous-epoch scenario;
current same-day contract metadata supplies identity/lot sizes, with historical
price bands omitted equally from both scenarios. It does not reproduce the
entire funded universe, every intrasecond update, the simulator's single actual
recorded signal, or exchange queue position. No fills or profit are credited.
The repaired kernel cannot prove the absence of opportunities in missing data.

Reproduction, with the private local sampled market archive:

```bash
.venv/bin/python research/seconds_repair_review.py --archive /path/to/archive.jsonl
```

The [diagnostic result](../research/results/seconds_repair_review_20261015/diagnostic_comparison.json)
records the kernel/archive hashes and limitations. The original
[complete-session audit](../research/results/session_review_20261015_full/REPORT.md)
preserves actual orders, fills, activation times and all58decisions.

## Deployment and live limits

These are software repairs, not a new profitability result. They do not fund
additional strategies, widen a trading window, weaken an entry condition,
increase capital or grant another route attempt. The selected seven names and
their existing mandate are preserved. Historical disabled strategies are not
silently re-enabled after examining today's market.

Read-side deployment and the read-only simulator can run the repaired source
without changing the funded trader. The dashboard explicitly reports the
remaining funded-runtime update. The operator's existing upgrade command is:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python /opt/sablestone-dhan-dashboard/current/ops/activate-seconds.py --apply
```

There is no extra-attempt flag in that command. Today's used3of3attempts are
preserved. An actual new-session broker-route qualification and live input
observations remain necessary. Software tests and an after-close deployment
cannot establish those future outcomes or guarantee profitable trading.
