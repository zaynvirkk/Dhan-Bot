# Volatility shock owner replacement — 23 October 2026

Operator mandate: [complete supplied specification](VOLATILITY-SHOCK-MANDATE-2026-10-23.md).
Economic status: **unproven real-money experiment**. No historical profit or
predicted income is credited. Software checks exercise synthetic executions.

## Named policies

- Entry owner and sole intended scanned/funded roster: `VOLATILITY_SHOCK_V1`.
- Rules: `shock_v1`. A 0.30% five-minute shock must exceed twice its prior-only
  median; two completed closes must clear the prior 30-minute range by 0.02%,
  with extension no greater than 0.55%. Futures must confirm by 0.10% with
  three-minute volume at least 1.3 times prior disjoint windows.
- At least 35 contiguous same-session spot/future minutes; ordinary decisions
  09:50–14:45 IST, subject to actual calendar, 30-second age and expiry eligibility.
  Completed candles have actual receipt provenance. REST bootstrap/repair stays
  separate from the provider's completed index stream. No OHLC is made from LTP.
- `SHOCK_FULL_CASH_V1` uses up to all currently reconciled, mandate-permitted
  cash after entry costs and three-child exit-fee reserve. The generic legacy
  10,000/25% cap is unchanged. One entry is bounded by a freeze child and finite
  ask/bid capacity. No borrowing, deposits or consumption-counter reset.
- Live selection examines two actual expiries, each with two ITM, ATM and
  twelve OTM strikes; missing nearby books do not prohibit checking others.
  The bounded subscription union covers both sides plus held/pending contracts.
  Each selected contract has at least 60 minutes of trading left, spread <=1.5%,
  recent receipt and enough finite depth. No option-candle requirement.
- European Black–Scholes, zero interest/dividend assumptions, ACT/365 time,
  current-midpoint IV inversion and 10% IV reduction define **scenario only**.
  Scenario premium is rounded down to tick. Its ending-bankroll contribution
  ranks feasible contracts; proceeds >=1.8 times entry cash and gross gain >=3
  times estimated round-trip charges are admission hypotheses, not expectancy.
- IOC price is live ask plus no more than two ticks or 0.4%, whichever is less,
  tick-rounded within the cap. A fresh account, current futures direction, book
  identity and the 30-second deadline bind again at dispatch. No auto retry is
  enabled: a missed IOC consumes its episode; ambiguous sends reconcile first.
- Episodes and first-signal timestamps persist through restarts. Repeated
  qualifying minutes cannot renew the deadline. Reconnect consumes an incomplete
  episode; new entry also waits 15 minutes after a real position closes.

## Existing positions and exit ownership

`SHOCK_EXIT_V1` operates on actual average fills/paid cash and conservatively
priced finite bid ladders, never LTP. Only depth reachable by the actual existing IOC exit limit can establish an
executable liquidation profit or ratchet peak; deeper bids remain unavailable.
Premium stop is a 40% entry-cash loss; two post-entry closes back inside the original range or opposite five-minute
return >=0.20% invalidate. At +80% executable cash profit, persistent trailing
floor is max(40% of profit peak, peak minus 45% of entry cash), ratcheted upward.
There is no fixed 2x take-profit. A 45-minute no-momentum exit applies unless
at least +20% cash profit was observed; maximum exposure is 120 minutes or
the earlier verified flattening deadline (normal 15:15, shortened session
calendar close minus ten minutes). These are triggers, not guaranteed fills.

The generic `NET_PROFIT_RATCHET_V1` configuration is preserved for legacy owner
recovery but is not attached to shock lifecycles. Directional owner management
continues when an entry strategy is later disabled. Unknown/expired exposure
is preserved for reconciliation, never declared flat or settled without proof.
The official 7 December regime caps expiring-index trading at 15:30; expiry
valuation and same-day admission use the effective contract-specific cutoff.

## Cutover and rollback

1. Disarm new entries with the existing CLI; keep exits running. Reconcile a
   flat account and pending obligations; retain previous release/config privately.
2. Commit exactly the implementation, tests and mandate documentation, preserving
   unrelated local research. Install the immutable release through existing
   dashboard installer. Run complete acceptance and production guard mutations.
3. Use `ops/activate-profit-exit.py --scan-only VOLATILITY_SHOCK_V1
   --funded-only VOLATILITY_SHOCK_V1 --apply`. Its legacy global retain option
   does not attach a second exit policy. It does not place orders or reset the
   existing mandate. Do not add extra route attempts.
4. Enable the existing verified mandate with `dhan-cas enable`; verify current
   process source, roster, disarm flag, broker account, dashboard and calendar.
   Closed-market deployment is `DEPLOYED_IDLE`, not live-feed or fill proof.
5. On source/reconciliation/input integrity faults, disarm **new** entries.
   Preserve the new owner while an existing shock position needs managing.
   Never roll a shock position back to source that cannot manage its exit.

Validation covers causal gaps/future bars, both sides, maximum affordable lots,
fee reserve, stale/crossed/thin books, option-pricing identities, episode restart,
reconnect invalidation, live-future reversal, authority, existing OMS requests,
zero fills, stop sales, disabled-owner recovery and dashboard data isolation.
Existing CP cases and mutations remain required. No forced live order is used
to demonstrate installation; a naturally absent setup remains a valid outcome.
