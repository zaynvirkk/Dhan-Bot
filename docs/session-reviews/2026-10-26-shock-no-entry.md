# 26 October 2026: qualifying shock, no eligible option

Investigation used current VM status, the broker's funds/positions/day orders,
recorded completed-minute evaluations and the saved episode assessment. No
counterfactual gain is credited.

- Source before repair: 5249d19; sole funded/scanned engine VOLATILITY_SHOCK_V1.
- Broker read at 20:10 IST: cash INR 7,772.25; zero open positions and pending
  orders; active data subscription and F&O permission. Today's sole order was
  the 09:15 nonmarketable route check, subsequently cancelled without a fill.
- Completed observations: five qualifying CE minutes, 09:55 through 09:59,
  normalized into one contiguous episode. First observation arrived about
  0.30 seconds after the completed minute. Other open-session checks recorded
  SHOCK_RULE_NOT_MET, not missing input. Raw minutes are not independent bets.
- The retained assessment checked 30 contracts over 27 October/3 November.
  Affordable candidates existed. The best saved scenario was approximately
  1.725211 times entry cash, at 22,950 CE, 260 units, entry cash INR 6,514.35
  and exit reserve INR 94.66. It failed the frozen 1.8 scenario floor.
- These scenarios assume favorable continuation and stressed IV. They are not
  probabilities or expected returns. The supplied mandate explicitly says
  to abstain if none qualifies. No investment entry passed that assessment.
- The evening order socket is a different epoch after the 15:53 token refresh.
  Its unqualified route status does not prove a morning route failure. Closed
  markets also explain stale futures quotes now; connected is not fresh price.

## Confirmed defects and repair

1. A scenario-floor failure was collapsed into NO_AFFORDABLE_LIQUID_CONTRACT.
   Report the observed scenario gate instead, retaining all contract checks.
2. Reconnect invalidation overwrote already-consumed episode receipts, even
   their original lifecycle/reason fields. Preserve the first receipt and
   continue invalidating the dispatchable in-memory sample.
3. Restart lost candidate diagnostics from the live status despite retaining
   them in the ledger. Restore only today's most recent assessed episode for
   display, without restoring a dispatchable sample or permission.
4. The frontend prioritized an ordinary post-close route requalification over
   the closed session, and its truncated 256-check list hid the morning setup.
   Keep today's assessed setup visible with the actual scenario rejection;
   normal closed-session route waiting is distinct from rejection, exhausted
   attempts and unknown order outcomes. Missing prices remain unknown.

Exact regression cases cover receipt preservation, cold restore without
rearming, day boundaries, stage-specific rejection, and actual JavaScript
rendering of closed-session/active-session/next-day states. Deployment and live
verification are recorded in the portfolio worklog. No signal thresholds,
scenario pricing, exit rules, funded roster, probe allowances or bankroll limits
are changed. No new order was requested by the repair.
