# Literature-derived test queue

28 September 2026. **Specifications for research, not live recommendations.**
These have no new backtested bankrolls. A status of READY means sufficiently
defined for an implementation experiment, not proven profitable. Common data,
execution and inference boundaries are in PROTOCOL.md and REVIEW.md.

## 1. Fixed late-day price direction — READY FOR REGISTRATION

Sources L06–L08 and L12 motivate two distinct, low-complexity signal baselines:

- **Opening-return sign:** sign of previous session's close to today's completed
  first 30 minutes.
- **Rest-of-day sign:** sign of previous session's close to the most recent
  completed bar at entry decision.

Proposed Indian cash adaptation: decide at 14:45 IST, submit only afterward,
exit on a preset 15:15 decision with subsequent execution. These times are our
fixed implementation choices for an intraday cash test, not the paper's optimal
window and not a claim about current auto-square-off rules. Verify dated broker
cutoffs before using them. Missing signal or unchanged reference means no trade.

Predeclare universe and selection using prior information only. Initial
universe: historically eligible liquid F&O equities, top ten by preceding
20-session rupee turnover. Evaluate each independently and a one-position
selector based solely on that prior turnover order; report all attempted
selectors. Never pick the best-performing stock after the replay.

Compare long-only cash, separately funded same-day cash long/short, and index
option translation as distinct implementations. One account cannot short an
index value. Borrow/margin restrictions, lot size, spread and cash settlement
must be enforced per implementation. Do not silently use 4x leverage for all
historical dates because a current probe accepted it. Include unlevered cash as
the funding baseline.

The price rules do not require the unresolved gamma formula. Do not add gamma,
OI, volume, trend or volatility filters until the base experiment and its
no-skill controls are registered. Fixed time-of-day long and lagged random-side
controls separate a direction edge from an unconditional closing drift.

## 2. Hourly BB/RSI cash rule — SPECIFICATION INCOMPLETE

S02 motivates this comparator, but the exact RSI period, smoothing, exit
threshold and intrabar band-touch semantics must be recovered or explicitly
declared as our own variant. Do not call a guessed version a faithful
replication. Hourly indicators require warm-up and session-anchored bars; trades
use subsequent executable observations. Charge every turnover and carry event.

## 3. Monthly cross-sectional momentum — CAPITAL-ADAPTATION PENDING

L09 provides a reproducible formation signal: at month end, rank the return
from t−12 to t−1 and hold in t+1. First reproduce the factor arithmetically.
Then separately test an affordable long-only cash portfolio with integer shares
and a predeclared maximum number of holdings. This adaptation loses the
original short hedge and cannot inherit its factor return. Include market
exposure and same-universe passive comparisons. Requires multi-year data,
delistings and point-in-time membership; three months is inadequate.

## 4. Earnings-surprise drift — DATA/TIMING SPECIFICATION PENDING

L10/A24 motivate post-announcement cash holdings rather than an overnight news
gamble. Use original quarterly EPS and comparable prior-year EPS; adjust splits
causally. Thresholds must be fitted only on older announcements, not ranks of
all companies that will announce later in the quarter. Earliest entry day +2;
evaluate the source's longer horizon before trying short-dated options. Preserve
negative-surprise controls even when shorting is infeasible. No retrospective
event classification or requirement that future returns be nonzero.

## 5. Pairs and commodity momentum — REPRODUCTION/CAPITAL PENDING

A20 needs full methods before freezing pair formation, entry, exit and costs.
L15 needs reconstruction of roll returns, turnover-cost arithmetic and return
units. Model concurrent contracts and daily margin calls; do not apply reported
percentage returns to unused cash or net option premium. An affordable Gold
Petal contract does not reproduce a 13-commodity long/short portfolio.

## 6. NIFTY option-position/variance signals — ACCESS/DEFINITION PENDING

A19/A21/A27/A28 remain distinct hypotheses. Net-long participant stock is not
daily flow; neither is dealer gamma. A variance risk premium does not by itself
make naked selling fundable. Any bounded-risk spread must retain its hedge,
both-leg costs, actual payoff and portfolio margin. Do not count hypothetical
premium yield as return on maximum loss or collateral. Review these bodies
before adding another search grid.

## What would qualify an experiment for a deployment decision

Each implementation needs a chronological ledger starting at the actual funded
balance, at least 90 calendar days and enough independent opportunities, all
costs, failed/unfilled orders, data-quality bounds and a truly reserved test.
Existing examined windows are development data. Require net economic evidence
against matched controls, sensitivity to execution and capital, concentration
analysis, and market-hours read-only observation before proposing a funded
deployment. Do not require profit in every quarter as a statistical theorem;
do require a defensible positive expectation and tolerable path under the
operator's chosen allocation.
