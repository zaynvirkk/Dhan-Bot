# Five experimental seconds strategies

The operator requested creation and production deployment of all five proposed
short-hold ideas. They are implemented as SECONDS_FUTURES_CATCHUP,
SECONDS_FAILED_BREAKOUT, SECONDS_FLOW_CONTINUATION, SECONDS_STRIKE_CATCHUP and
SECONDS_EVENT_IMPULSE. They are hypotheses, with no new profitability backtest
or actual funded execution credited by this change.

## Rules and inputs

The rules use Dhan FULL option quotes and current front-future trade observations
on the same receipt clock. Reconnects clear the rolling history. Each rule needs
at least a minute of fresh observations, except that missing event data remains
an explicit blocker. Futures LTT is a trade timestamp; option freshness uses
actual FULL-frame receipt time. A duplicate or stale print cannot renew a book.

- Futures catch-up fits the option's earlier response to futures using only the
  preceding 60–5 seconds, at least20 paired observations, absolute response
  0.1–0.9 and fit R²>=0.4. It looks for a two-second futures impulse >=0.02% and
  an option ask still below that conditional repricing reference after costs.
- Failed breakout observes the preceding60-second futures range, a break of at
  least0.01% in the latest5seconds, then a return inside and a reversing latest
  move. The earlier fitted response prices a conditional move toward range centre.
- Flow continuation requires three rising option midquotes, bid/ask quantity
  imbalance >=0.6 across those observations, at least10 lots of cumulative
  traded-volume growth over the anchor, and aligned futures. Displayed quantity
  alone is insufficient. The feed does not identify every aggressive trade or
  prove writer liquidation.
- Strike catch-up compares same-expiry, same-type, evenly spaced neighbours
  received within500ms. It preserves the median prior curvature from at least20
  matched observations before the latest5seconds; simple straight-line option
  pricing would incorrectly ignore normal convexity.
- Event impulse reads official NSE announcements for current NIFTY constituents.
  Only selected material subject categories and verified official attachment URLs
  qualify. Publication and actual HTTP receipt are separate; old, future and
  unrelated events are rejected. Direction comes from post-receipt futures,
  never headline sentiment. The public feed polls every10seconds when available;
  its delivery latency is part of the experiment. Unavailable sources block it.

The quote model's repricing reference is not intrinsic value, an expected return,
or an arbitrage guarantee. Thresholds are a new frozen experimental definition,
not values selected by inspecting profitable outcomes.

## Entry and exits

Only one whole NIFTY option lot is considered per entry. The closest qualifying
contract must have fresh two-sided quotes, spread<=1%, at least two lots on each
top level, and available cash for premium plus conservative entry/exit costs.
Entry limits allow two ticks beyond the observed ask. The conditional net margin
must exceed both INR50 and the conservative round-trip fee reserve. No missing
history or depth is made into zero cost. The signal's entry lifetime is5seconds;
all order prerequisites are rechecked immediately before dispatch.

Exits use current executable quotes: repricing reference reached, adverse
futures displacement of0.01%, lost fresh futures input, or a5% premium stop.
The existing net-profit ratchet applies when configured. A60-second exposure
ceiling and provider-derived session boundary remain safeguards. A stop or time
limit cannot guarantee a fill or prevent a larger gap loss. Existing minute/CAS
positions keep their own recorded policies, even if entry permission is removed.

The engines share the existing reconciled OMS, capital limits and one-position
constraint. Competing unknown opposite-side signals abstain. Execution quality
is an experimental fallback, not a profit estimate. No loss is hidden by resetting
cash, a counter or a lifecycle.

## Deployed observation versus money permission

`dhan-seconds-observer.service` is a separate live-data process with simulated
fills only. It has no order client, opens no order socket, cannot rotate secrets,
and does not change the funded configuration. Five independent model bankrolls
start from a fresh observed broker-cash amount. Results are not summed into a
combined account. Models persist across process restarts and retain unresolved
positions when exit data is missing.

Model entry/exit arrival is delayed one second, uses capped prices, requires
finite current depth, includes the conservative fee envelope, and records misses.
These are displayed-depth scenarios, not confirmed exchange fills. A sampled
500ms quote archive is capped at128MiB per session; this is not complete exchange
tick/depth history and cannot establish a90-day seconds-level backtest.

The dashboard explicitly separates simulations from funded strategies, broker
cash and actual closed-trade results. Missing, stale and unavailable inputs stay
visible. An official event endpoint rejecting access is not a passed event feed.

## Operator-run funded activation

The operator must execute the financial activation step. Deployment alone does
not add these five names to the existing funded service. The prepared command is:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python /opt/sablestone-dhan-dashboard/current/ops/activate-seconds.py --apply --extra-route-attempt-on 2026-10-15
```

This explicitly merges the five names with the existing scanned and funded
rosters, runs full source verification, reconciles obligations and upgrades the
funded service. It does not itself submit a strategy order. A newly connected
funded order socket must qualify before entries. The optional date argument is
an explicit operator grant of one additional attempt on that IST date only;
normal two-attempt limits resume automatically on other dates. Already-used
attempts and the INR100 daily/INR500 lifetime probe cash caps are preserved.
Omit the date flag when a normal attempt remains. A different/future date is
rejected before changing the service. Data/source/cash failures remain blockers.

This command is documented for the operator, not executed by the assistant.
Neither activation nor software verification establishes profitability.
