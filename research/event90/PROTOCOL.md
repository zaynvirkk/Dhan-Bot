# Ninety-day event-family extension — 21 September 2026

Continue the original EVENT_CONTINUATION and INTRADAY_EVENT tests over
21 June–18 September 2026 (90 calendar days). Warm-up starts 15 May. The
July–September part was previously inspected; this is an extension of the
denominator, not an independent holdout. Existing negative findings remain.

Keep the original three-minute 2.5% displacement, overnight 1.5% open
continuation, RVOL >=3 using twenty prior sessions, limited retracement,
futures confirmation, same first-signal/tie order and seven-day stock
delivery buffer. Use exactly the existing original-attachment classifier,
including its disclosed ambiguous/missing cases. No threshold tuning.
Each engine starts independently with INR 9,411.18 and one open position.
No outcome-selected symbols or events. Membership comes from the previous
published NSE F&O file; keys/ISIN are identity lookups only.

The original execution model remains frozen: 95% inclusive entry budget,
whole lots, known liquidity, precommitted last-close +5% limit, next-full-bar
adverse high, 5% participation, target 2x with trade-through, delayed underlying
invalidation and partial adverse liquidation before 15:17. Missing history
is UNKNOWN. Dated NSE security bans precede selection. Historical broker RMS,
book/depth and publication-to-bot latency are assumptions, not proven facts.

Run each engine's primary, two/three-minute delay, open-plus-1% and best-trade
deletion scenarios, plus a strict source-coverage scenario and 999 random-side
controls. Report every signal, including ambiguous events, failed futures
confirmation, unaffordability, non-fill and unknown outcomes. An unchanged
cash balance from unavailable evidence is never a passing result. No full-
family claim without a complete coverage denominator; no live approval from
these reused-period results. Noise correction includes the continuing search.

Use a separate artifact directory; do not rewrite earlier research inputs or
outcomes. Existing immutable-by-content raw files may be reused. Source and
input digests bind the new results. No orders, live activation, subscriptions
or deployment changes.
