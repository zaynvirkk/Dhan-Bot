# SABLESTONE | DHAN-BOT V2
## Volatility Shock Continuation — Implementation and Live-Execution Mandate

**Document version:** 1.0
**Prepared:** 23 October 2026 (IST)
**Target repository:** `https://github.com/zaynvirkk/Dhan-Bot`
**Inspected main commit:** `ecff8c207a40d3d3ee78228b0c8a1c74d7eca80a` (20 October 2026)
**Target new strategy ID:** `VOLATILITY_SHOCK_V1`
**Outcome required from Codex:** integrate the named strategy, replace CAS as the **only scanned and funded entry strategy**, preserve existing positions/history/execution safeguards, deploy to the existing VM using the project's guarded release workflow, and collect actual broker-reconciled results. **Do not fabricate results.**

> **Evidence boundary:** This is a deliberate high-risk, real-money trading experiment. The new strategy has **more opportunity coverage and a payoff profile more aligned with rapid bankroll growth** than CAS, but it has *not* been demonstrated to have higher expected profit or a positive edge. Historical spectacular option moves were identified retrospectively. Live trading is the selected source of economic evidence, not a guarantee of profitability. An all-in option purchase may lose the full premium and exhaust the bankroll. Do not claim otherwise.

---

## 0. Instructions to Codex: execute the specification, not a fresh ideation exercise

You are working in the actual repository and on its existing VM. Inspect current code and configuration before modifying anything, and detect if `main` or the running release has changed from the inspected commit. Preserve any later fixes. Implement **one** funded entry engine, `VOLATILITY_SHOCK_V1`. Do not add unrelated strategies, equities, BSE options, commodity futures, a new broker, an AI predictor, an external signal subscription, or a parallel order manager.

The operator has chosen **real-money discovery rather than a prolonged backtest/paper-trading stage**. Do not require weeks of paper performance, optimization tournaments, an invented signal confidence model, a target win rate or profitable simulation before allowing the operator's existing authority to fund the new engine. Equally, do **not** bypass the repository's existing source-verification, immutable-release, account-identity, whitelisted-egress, ledger, order-reconciliation, exchange-calendar, market-data freshness or position-recovery checks. Those checks verify operational correctness, *not* strategy profitability. Never disable them to force a trade.

The live-entry mandate remains bounded by existing explicit account-level authorization. Do not invent credentials, increase capital beyond authorized and broker-observed funds, reset consumption counters, grant extra broker route attempts, trade an unresolved or foreign position, or silently change existing account secrets. If the actual current VM lacks valid funded authority or is not in a reconciled flat state, install a safely inert release and report the exact blocker; do not fake success or trade through it.

The operator's sizing rule is intentional: **up to 100% of currently deployable strategy capital may be spent on one long-options entry**, including the existing reinvestment mechanism. Do not impose an arbitrary 10%, 20% or 25% allocation ceiling. Fees and any required cash reserve are non-investable; broker and exchange constraints still apply. One open position at a time. No naked option selling, leveraged short options or margin-financed positions.

### Definition of done

- Only `VOLATILITY_SHOCK_V1` can initiate new funded positions. CAS and every old research/scalp family remain in source and historical ledgers but cannot place new entries.
- The new strategy generates *causal* signals from completed market observations, selects an affordable liquid option using **current executable books**, submits a bounded IOC limit order through the existing OMS and manages the resulting real position through to broker-reconciled closure.
- Existing filled positions and pending obligations continue to be managed according to their recorded owner, even if the owner's new-entry strategy is now disabled.
- The dashboard displays the new strategy's decision explanation, selected instrument, entry budget, actual fills, entry and exit reasons, final charges and broker-reconciled net P&L. No model P&L is labeled actual.
- The new source is installed through the project's verified immutable release flow with no reset of the ledger. Existing trading service, token refresh and automatic restart continue. Broker-account/route admission must be genuinely healthy before any buy.
- A genuine live fill or a genuine rejection/no-signal is recorded truthfully. A lack of signals is *not* a deployment failure and must not be overridden with forced test trades.

---

## 1. Objective and why this replaces CAS as the funded engine

**Operator objective:** maximize achievable bankroll growth over a short horizon with an initial allocation around ₹7,000, and accept the possibility of total loss. Prefer a small number of high-upside directional option trades to frequent ₹50–₹200 net scalps. Reinvest broker-realized capital as it becomes spendable and reconciled. Do not optimize for Sharpe ratio, smooth daily income, minimum trades per day, or risk-parity allocation. Capital may remain idle when no qualifying setup exists; manufactured trades are not progress.

### The observed baseline

From the supplied 25 completed trades (13–19 October): **₹581.75 gross P&L, ₹1,631.86 reported fees, −₹1,050.11 net P&L**. CAS itself generated **+₹1,709.36 net** across 16 fills/round trips within **one** auction session. That one-session success is not evidence CAS is intrinsically bad. The combined system was negative because fees and adverse directional exposures overwhelmed gains, especially the 14 October PCR-trend position (−₹2,725.78 net). The fast engines also repeatedly exited after lost inputs and suffered canceled IOC entries.

**Do not write that `VOLATILITY_SHOCK_V1` is empirically superior or the “absolute best strategy.”** Its design is better aligned with the stated **payoff objective** for these reasons:

1. **Broader opportunity window.** CAS can initiate only in a narrow auction phase of an eligible expiry session; V1 watches regular NIFTY trading sessions.
2. **Large-move participation.** CAS targets a short-lived difference between auction reference and option pricing; V1 attempts to participate in a continuing underlying move, whose associated long-option premium may reprice by multiples.
3. **Holding policy matches payoff.** CAS and old seconds engines often trade for seconds; V1 can hold up to the relevant intraday end-time and uses a dynamic exit instead of mechanically selling every winner at 2×.
4. **No dependence on CAS settlement economics.** The published SEBI change effective **7 December 2026** modifies the link between auction and expiring derivative settlement. V1 uses regular price movement and must obey the revised session/expiry boundaries.
5. **Less dependence on microsecond-quality lead/lag estimates.** V1 uses completed one-minute direction and live books for execution; it still needs fresh feeds, but does not claim to capture a 2-second mispricing with 500–1,000 ms software delay.

These are design advantages **only**. The price can reverse, implied volatility can collapse, and options can lose 100% despite an initially correct directional interpretation.

### The specific opportunity mismatch discovered in the repo

On **12 October 2026 at 15:10 IST**, the bot recorded a bullish selloff-rebound signal but did not trade because its required **post-next-session expiry** and four near-strike choices cost more than its cash budget. The following day included very large option premium changes. That is evidence the old **strike/expiry eligibility may rule out useful convex opportunities**, *not* proof that a proposed new signal would have forecast or filled the winning contract. V1 therefore searches a broader feasible strike/expiry set. It does not inherit the old rebound setup by accident.

---

## 2. What the new strategy actually bets on

**Hypothesis:** after a statistically unusual five-minute price displacement that decisively breaks a preceding range, corroborating futures direction and volume sometimes precede an additional same-direction move. An affordable liquid near-expiry long call or put may then have nonlinear upside relative to the premium paid.

**Instrument:** long NIFTY index options on NSE/NFO only. Call when the breakout is up; put when it is down. No short position is used. No stock-index proxy substituted for NIFTY. Cash/index data and future direction are inputs, not separately traded instruments.

**Time frame:** 1-minute completed bars for signal; live Dhan FULL option books for trading/exit; current NIFTY front future for confirmation. Everything must be timestamped and joined on actual **availability time**. An “open/high/low/close for the minute” is unknown until that minute has ended. Never use an intraminute high or final candle close as if observable at the beginning of that minute.

**What V1 does not claim:** an observed 0.30% five-minute move guarantees continuation; a modeled 3× premium scenario is a forecast probability; a broker quote equals an executable fill; a historical 868% option rise could have been captured by a causal signal.

---

## 3. Exact V1 signal rule — no discretionary AI

Parameter values below are **explicit starting hypotheses**, not optimized or empirically validated thresholds. Treat them as a named immutable `shock_v1` configuration revision. Persist both the revision and actual contemporaneous inputs with every decision. Do not silently alter thresholds from outcomes during the trading session.

### 3.1 Inputs and readiness

Required fresh data:

- Date-specific NSE/NFO trading calendar and current authorized session.
- NIFTY spot/index completed one-minute OHLC bars, **at least 35 contiguous bars** for the day by the considered decision minute; first normal entry decision no earlier than **09:50 IST**. Completed-bar timestamps must agree with exchange/local receipt clocks.
- Contiguous current-session front-month NIFTY futures minute candles including volume and a live futures quote. Do not treat last-trade timestamp as a fresh book update.
- Broker-resolved current NIFTY option instrument master: exact listed expiries, lot sizes, tick size, strike, price bands, freeze limit, unique security IDs.
- Dhan FULL option books with bid, ask, finite price/quantity, valid quote receipt time, and enough depth for any proposed quantity.
- Current broker funds and reconciled flat account state prior to entry.

If the 35-bar warmup is missing, a bar is stale/ambiguous, a future is unavailable, or spot/future clocks disagree beyond current feed-age policy: **NO SIGNAL or INPUT UNAVAILABLE**, not a guessed zero or a forced order. A reconnect invalidates the working incomplete episode; historical completed bars may be reloaded, but the trade decision must respect their actual availability time.

### 3.2 Time and shock computation

Normal entry decision window: **09:50–14:45 IST**, respecting the **actual** exchange calendar and any earlier verified cutoff. New entries are intraday only in V1: do **not** carry them overnight. Exit before the relevant exchange deadline using the calendar. Current working cap for a normal full trading session: initiate flattening no later than **15:15 IST**, leaving an operational buffer; do not assume every session ends at 15:40 or 15:45. V1 does not rely on the closing auction or final settlement price.

At a freshly *completed* bar with availability timestamp `t`:

- `S_now = close_spot(t)` and `S_5 = close_spot(t−5min)`.
- `r5 = S_now / S_5 − 1`.
- `direction d = +1 if r5 > 0 else −1`.
- Absolute shock requires `abs(r5) >= 0.0030` (0.30%).
- Build a **prior-only** baseline from five-minute absolute returns ending at t−6 through t−30 where the five-minute intervals are fully complete. Require at least 20 valid comparisons and `abs(r5) >= 2.0 × median(prior_abs_r5)`. If baseline is zero/insufficient, abstain rather than divide by zero.
- Compute `pre_break_high` and `pre_break_low` from the **30 completed bars ending at t−2** (exclude the two confirmation bars at t−1 and t).
- For `d=+1`, require `close_spot(t−1)` and `close_spot(t)` both exceed `pre_break_high × 1.0002`; for `d=−1`, require both closes below `pre_break_low × 0.9998`.
- Reject a chase when spot already lies more than **0.55%** beyond the pre-break boundary, measured from that boundary to `S_now` in the trade direction. This is an explicit overextension rule, not a proven optimum.
- Require front future's completed five-minute return to have the **same sign** and absolute return >= **0.10%**. Reject if the latest futures book is stale or crossed.
- Require the **last three completed futures minutes** to show total volume >= **1.3×** the median total of nonoverlapping three-minute windows earlier in the same session, with at least five available baseline windows. If the data's volume semantics cannot be verified or a source supplies duplicate cumulative values rather than per-minute volume, mark volume unavailable and abstain.

Only after all conditions pass emit a `SIGNAL`, with `side = CE for d=+1, PE for d=−1`, exact timestamp, feature values, source IDs, and rule version. Avoid treating ratio tests as probabilities; they are yes/no qualifying conditions.

### 3.3 Unique episodes and anti-churn

A new episode begins only when the first completed bar satisfies the full rule after a period when the condition was false; identify it by `(trading_date, direction, first_qualifying_bar_availability_timestamp, rule_version)`. Subsequent qualifying bars belonging to the same breakout are **one** episode, not new independent signals. Persist episode state, consumption, filled/open/cancelled order identities and its cooldown across process restarts.

A signal is actionable for **at most 30 seconds after the exchange-confirmed completed bar becomes available to the strategy**. If it becomes stale before the pre-dispatch check, record `ENTRY_DEADLINE_MISSED`, do not chase the same breakout in a later bar. After a closed trade, no re-entry into the same episode. Allow a genuinely new opposite or independently rearmed episode only after **15 minutes** since the prior position closed; do not impose a compulsory daily trade target. One position at a time.

---

## 4. Option selection — choose return potential, not just the nearest strike

This is the main implementation change versus the existing `directional.py` selector. Today's generic directional selector examines the nearest expiry and only four outward strikes, can abort on missing candle history for a nearby strike, fixes the entry limit from the previous option-candle close plus 5%, and reserves capital using the old default 2× target assumptions. None of that should be inherited blindly.

### 4.1 Universe

For each qualified signal, consider the **nearest two actual future NIFTY expiries** with valid market data and legal eligibility. Enumerate for the chosen call/put side: up to **two ITM, ATM and twelve OTM listed strikes** per expiry. Extend outward only if no affordable liquid contract is found and market-data capacity permits; do not scan every illiquid token or block the option feed by subscribed breadth. All candidates come from the dated instrument master, not generated strike integers or guessed weekday expiries. Hold/pending contracts remain subscribed independently of new-candidate membership.

Exclude candidates whose expiry is not tradable under the exchange calendar and effective regulations; candidates with less than **60 minutes of permitted trading remaining**; empty/crossed books; stale option bids/asks; bid/ask spread greater than **1.5% of midpoint** (an explicit initial threshold); or insufficient actual displayed exit-side depth for one whole lot. Do not treat a large day-volume number as same-moment exit liquidity.

### 4.2 Decide affordability before subscribing everything

Using current actual best ask `A`, available strategy cash `C`, the resolved lot size `L`, and conservative entry+exit charges, a contract is eligible if `L × A + total fee reserves <= C`. Apply the existing ledger/mandate allocation ceiling and observed funds, not a hard-coded ₹7,000. **Size the position as the maximum whole-lot quantity** affordable at the proposed price after fees and required exit reserve, bounded by contemporaneous ask-side liquidity, freeze quantity and OMS policy. The maximum *actual premium plus costs* must be strictly <= spendable broker funds and permitted allocation.

For larger positions the OMS must handle freeze slicing, genuine partial fills and child order charges. Never assume the entire book is available at top-of-book. If no candidate can be bought, report `NO_AFFORDABLE_LIQUID_CONTRACT`; no trade is better than an unaffordable order.

### 4.3 Rank candidates by a declared favorable-continuation scenario

A **scenario** is not an expected return or success probability. Use it only to compare the payoff geometry of currently feasible options.

For all candidates set a single underlying continuation scenario at the time of the signal:

- `m = min(0.018, max(0.006, 1.75 × abs(r5)))` (0.60% minimum; 1.80% maximum)
- `S_scenario = S_now × (1 + d × m)`
- Horizon: the earlier of **45 minutes** and **30 minutes before the chosen option's trading cutoff**.

Compute an indicative future option value for each specific strike/expiry using a conventional option-pricing model fitted to **current** observable bid/ask and time-to-expiry (use a validated implementation or robust implied-volatility inversion; reject impossible quotes). Revalue at `S_scenario` after the horizon with implied volatility stressed **10% lower** than the current fitted volatility. Also calculate expiry intrinsic value to show why out-of-the-money calls/puts can still reach zero. Do not label the scenario value as a target guaranteed to trade. Record the actual IV/model input assumptions, quote timestamp and the chosen time basis.

For candidate with one-lot or multi-lot executable entry cash `D` and net proceeds in the scenario `P`, compute `scenario_multiple = P / D`; rank by **highest scenario ending-bankroll contribution** (cash not committed + modeled net proceeds), not merely cheapest premium or largest percentage return on an untradeable one-tick token. Resolve ties toward narrower spread, deeper exit-side depth, lower order fragmentation and more recent exact quote.

Require `scenario_multiple >= 1.8` and gross scenario profit >= **3× the estimated complete round-trip charges** before permitting entry. These are *research hypothesis filters*. They do not establish positive expected value: the unfavorable move can be more likely than the scenario. If no candidate clears, abstain. Never impute missing option IV/quote/depth with zero or favorable values.

**No look-ahead:** scenario only uses contemporaneous spot, futures and option book; never choose the strike because it later had the largest actual high.

### 4.4 Live entry execution

- Evaluate all qualified contracts at one decision timestamp and select **one**. Do not enter multiple positions on the same episode.
- Read the newest live option book and broker cash again immediately before committing the intent; ensure the index/future direction remains valid and the signal is not past its 30-second expiry.
- Submit a **LIMIT IOC buy** through the existing durable `orders.submit` path; do not add a separate direct REST writer.
- First limit price: current best ask rounded to tick plus **at most two ticks**; never exceed a maximum price equivalent to **0.4% above the latest ask**. If affordability, spread, depth, limit band or scenario floor fails at that price, skip. No unbounded market order or blind chasing.
- An IOC canceled with zero fill is **not a losing trade**. One reprice attempt for the *same* contract/episode may be allowed only after unequivocal broker confirmation of zero fill, cash/account recheck, valid current quote and still-current 30-second signal; all attempts/fees reconciled. A timeout/unknown result is **not** a license to resubmit.
- Record actual sent/acknowledged timestamps, exchange order IDs, requested quantity, filled quantity, executed prices and why the unfilled remainder expired. An accepted order is not a fill.

---

## 5. Exit policy — capture a trend while limiting uncontrolled giveback

V1 **does not inherit** the generic `exit_target = 2`, `exit_stop = 0.5`, or existing `profit_exit_retain = 0.50` unless the strategy explicitly uses a compatible versioned policy. Implement `SHOCK_EXIT_V1` as a named owner-specific module that operates from actual fills and executable current quotes.

### 5.1 Price and position tracking

Persist, per lifecycle: actual average entry premium, actual entry turnover and fees, cumulative executed quantity, current valid bid-side liquidation proceeds for *all held lots*, estimated paid and future charges, maximum observed **after-cost executable profit**, spot breakout boundary, entry-time underlying price, entry trading session, confirmed bar timestamp, signal side, expiration and rule version.

**Never reset the high-water mark on a management loop or process restart.** Do not estimate profit from last-traded option price when the bid-side book cannot liquidate the position. An empty/stale book is not a tradable exit. The last known reference is telemetry only, not evidence of current execution value.

### 5.2 Exit triggers (first eligible trigger wins)

1. **Underlying invalidation:** after entry, two newly completed spot minutes close back inside the original broken range; or the five-minute spot return turns against the position by >= **0.20%**. Latch an immediate exit reason `SHOCK_UNDERLYING_INVALIDATED`.
2. **Premium loss:** when executable liquidation net value implies a loss >= **40% of paid entry cash**, latch `SHOCK_PREMIUM_STOP`. This is a best-effort order trigger, not a guaranteed 40% maximum loss; gaps/slippage can take the position to zero.
3. **Profit protection:** after *executable net profit* reaches **+80% of entry cash**, begin a versioned trailing floor. Let `peak_net_profit` be the largest broker-fee-adjusted cash profit seen on a fresh fully executable bid ladder. Trigger exit if current net profit drops below `max(0.40 × peak_net_profit, peak_net_profit − 0.45 × total_entry_cash)`. This is a hypothesis chosen to allow >2× upside without giving back all gains. Ratchet the peak and floor monotonically; do not recompute past observations after a restart.
4. **No-momentum timeout:** if **45 minutes** have passed since first actual fill and the option has not shown a fresh executable net profit >= **+20% of entry cash**, close instead of paying indefinite theta decay.
5. **Maximum exposure:** close after **120 minutes** from first actual fill or at the verified session flattening deadline, whichever comes first. Begin attempts early enough to resolve the position before normal trading ceases. Never deliberately carry overnight in V1.
6. **Expired or unavailable exchange:** preserve a latched exit and all broker obligations; no fabricated settlement or out-of-session sale. Resume only under permitted actual exchange procedures.

Use the existing idempotent `ExitManager.reduce`/OMS handling. For an exit, determine executable prices from the live **bid ladder**, respect freeze slices, and bound adverse price allowance. Do not prevent emergency reduction merely because the entry-side spread threshold no longer holds; do not assume a missing bid can be sold at LTP. No separate position owner, no concurrent sell writers and no automatic reversal into an opposite position before actual flat-account reconciliation.

### 5.3 All-in is intentional but broker-account constraints are non-negotiable

The strategy should use the maximum permissible whole-lot bankroll, with fees reserved. The 40% **position exit trigger is not a 40% account allocation cap**. A gap can lose more; full-premium loss is possible. Do not silently install a 2% daily loss cap, 25% position limit, scaling ladder or diversification rule contrary to the operator's objective. On unreconciled state, conflicting positions, stale feeds, missing contract identity, or rejected route: **do not open a new position**. This prevents programming mistakes, not market losses.

---

## 6. Precisely how to integrate it into the current repository

The main architecture already exists. Keep one process, one authenticated broker, one ledger, one OMS, one position owner and current durable recovery behavior. Modify signal and candidate/exit selection **without copying the entire project or creating a new account writer**. Refer to the named code files below; use the exact current code rather than blindly applying line numbers from an older commit.

### 6.1 New `dhan_cas_bot/volatility_shock.py`

Create a pure deterministic module with typed models:

- `ShockConfig` named revision (`shock_v1`) holding all published thresholds.
- `ShockFeatureSnapshot` with spot/future bars, volumes, timestamps, breakout boundary and data provenance.
- `ShockEvaluation` or the existing `Evaluation` format with states `SIGNAL`, `NO_SIGNAL`, `INPUT_UNAVAILABLE`, `WAITING`, and explicit reasons.
- `evaluate_completed_shock(...)` enforcing the exact section-3 causal rules.
- `episode_id(...)` stable across restarts/replayed identical bars and unique for independently rearmed breakouts.
- `ShockCandidate` with exact security ID, expiry, strike, side, lot, current bid/ask, fees, observed depth, scenario assumptions and ranking score.
- `select_shock_candidate(...)` using current books, actual spendable funds, scenario pricing and the constraints in section 4.

Never import runtime/network clients into the pure signal evaluator. It must not submit orders. Keep Decimal for money and instrument tick alignment; clearly isolate any necessary floating-point option-pricing calculations with finite-input checks and conservative re-rounding.

### 6.2 `dhan_cas_bot/session_strategies.py`

Register `VOLATILITY_SHOCK_V1` in `STRATEGIES` without moving it into the 137 legacy expanded rule variants. Keep it a distinct named strategy. Ensure config validation accepts exactly this name when specified. Do not enable it merely by adding the constant.

### 6.3 `dhan_cas_bot/strategy_inputs.py` and `stream_minutes.py`

- Route `VOLATILITY_SHOCK_V1` through the new evaluator; **do not** pass it to `expanded_strategies.evaluate`, because `SPECS` does not include it.
- Use Dhan one-minute spot/future history and optionally the existing completed-index stream; reconcile exact bar availability semantics. The current `StreamMinutes` class retains only approximately two minutes, so **it alone cannot supply the required 35+ minute shock baseline**. Build a bounded per-session completed-bar cache from verified observations plus read-only historical refresh, keyed by actual availability timestamp. Do not upgrade an incomplete bar to complete just because wall time advanced.
- Allow a decision promptly after a bar completes. The existing minute worker performs REST reads and then sleeps; emitting a shock while the signal has only 30 seconds validity requires measured processing timestamps. If the required books and signal cannot arrive promptly, abstain instead of stretching their age.
- Expand option-data warming to affordable nearby candidates and both relevant actual expiries. The current `wanted_options` function caps warm minute-contract IDs at 18 and may starve the new selection. Reuse the existing bounded subscription manager, prioritize open/held securities, batch changes and avoid a full-chain subscription flood.
- Do not require three completed option minute bars for every contract in V1 when a valid current market book, security metadata and scenario calibration exist; the old candidate's option-bar history policy is specific to old research rules.

### 6.4 `dhan_cas_bot/directional.py`

- Add V1 to `DirectionalEngine.enabled`, but preserve all legacy owner management methods for positions that existed before the change.
- For V1, use the **episode-keyed** signal ID, not `directional-signal:<day>:<strategy>`; otherwise only the first shock each day would be representable. Extend `family_key`/consumed metadata equivalently.
- Dispatch V1 signals at their actual availability/receipt time. Do not inherit the legacy `due = signal.evaluated_at + 1 minute` or the generic 30-second window from an incorrectly delayed due time. Use the V1-specific 30-second expiry after the *new bar's real publication/observation*, with post-fetch and pre-dispatch rechecks.
- Route V1 candidates through `select_shock_candidate`; do not use `candidate()`'s old first-four-OTM, prior-close-plus-5% path.
- Because V1 is the only funded entry engine, bypass historical cross-strategy `cash_profit_per_minute` ranking **for V1**: after all V1 checks pass, use its deterministic option-selection score. Do not rewrite ranking for disabled legacy strategies or pretend one prior live trade is a reliable outcome distribution.
- Store strategy/version/episode/candidate/scenario/exit-policy details in the lifecycle payload **before** order submission, like the current durable intent path. Retain idempotent correlation IDs and submit via `runtime.orders.submit(...)`. Every broker response must reconcile through existing persisted order/fill identities.
- Branch `manage_locked()` for V1 to the owner-specific `SHOCK_EXIT_V1`; do not let generic target/stop logic simultaneously fire. When the entry fills, initialize the risk state from the actual broker average fill, not the signal's earlier candle premium. Use a persisted high-water record and the current actual bid ladder.
- Keep order reconciliation and exit management working if `VOLATILITY_SHOCK_V1` is later disabled from new funding while a position remains open.

### 6.5 `dhan_cas_bot/engine.py`, `service.py`, `market_subscriptions.py`

Keep the existing session engine and core `SessionEngine.cycle()` ownership rules. Confirm that `has_directional` is true for V1; ensure the feature worker loads the correct spot/future inputs; route/order socket connection and data subscriptions become available early enough for a 09:50 signal. `market_ids` should subscribe to current affordable neighborhood candidates for the chosen side plus kept open/held contracts. Do not conflate a future's stale last-trade time with a fresh book frame. Do not relax feed freshness or disable account refresh to increase apparent signal count.

The 20 October CAS-only recording optimization scopes capture to its special afternoon window **only while CAS-only and flat**. Once V1 becomes authorized, restore full-day capture/replay for V1 through the existing directional-recording path. Do not delete prior CAS records; manage journal quotas and disk reserves.

### 6.6 `dhan_cas_bot/risk.py`, `runtime.py`, `orders.py`, `ledger.py`

Prefer **no changes** to generic `lifecycle_ceiling()`: below ₹40,000 it already allows the entire bankroll subject to its ₹10,000 ceiling; once funded capital exceeds ₹10,000, that ceiling would cap this strategy, and above ₹40,000 it becomes 25%. **For the operator's specified full-bankroll policy, introduce a scoped, explicitly versioned V1 allocation rule** that permits up to **100% of the reconciled strategy capital** at any bankroll level, after conservative paid and future exit charges. Do *not* weaken the generic budget policy for old engines. Record the new policy version and allocated bankroll in the mandate/release receipt. Note that changing the effective mandate capital or account spending cap requires the operator's existing explicitly configured authority; never infer consent for higher deposits or borrowing from the ability to reinvest profits.

No change may defeat:

- the matching exact Dhan account ID and IP whitelist;
- the current exchange account permission and funded strategy allowlist;
- cash/fees/freeze/lot validation and reconciled available funds;
- durable BUY intent before network send, and deduplication on ambiguous outcomes;
- partial fills, order slicing, broker-reported charges, unmatched sell prevention, and idempotent flat-account closure;
- stop/restart recovery and source verification.

### 6.7 Dashboard (`dhan_cas_bot/dashboard/*`)

The authenticated dashboard should show V1 as the **only funded entry strategy**, with CAS **paused**. Add a V1 view or reuse the existing strategy board fields for: current evaluated bar and source receipt timestamp; observed five-minute return, historic median, breakout high/low, future return and volume multiple; why the rule passed or failed; affordable candidates and rejected reasons; selected strike/expiry, actual ask and bid, planned lots, charged cash, scenario multiple marked **scenario only**; current real position, actual holding time, last real executable net liquidation, persistent profit high-water mark, reason for any exit, order attempts and real broker-reconciled P&L. Maintain read-only browser auth. Never label projected values as cash balance.

---

## 7. Required changes in exact code behavior (old vs V1)

| Existing behavior | New V1 behavior | Why |
|---|---|---|
| CAS-only funded roster after 20 Oct | `strategies=["VOLATILITY_SHOCK_V1"]`, `funded_strategies=["VOLATILITY_SHOCK_V1"]` after verified activation | One funded engine; no capital splitting |
| Generic directional first near expiry + 4 OTM strikes | Two actual expiries, 2 ITM + ATM + 12 OTM each, affordability and live-book scoring | Do not miss cheaper feasible convexity |
| Candidate limit from prior candle close × 1.05 | Live fresh best ask plus strictly bounded ticks | Entry price follows executable market, not stale bar |
| Legacy minute due at signal + 1 minute | V1 within 30 sec of confirmed *available* signal | Capture early continuation without pretending future bars existed |
| Generic one signal per strategy/day | Persist distinct episodes and cooldown | Enable later genuinely independent shocks |
| Historical profit per minute strategy ranking | Sole V1 funded; candidate-based after-cost scenario ranking | Optimize single-position premium payoff rather than scalp frequency |
| Target at 2× plus generic 50% stop | Owner-specific invalidation, cash-based stop and profit-ratchet | Avoid automatic sale of strong trends at precisely 2× |
| `peak = entry` each management loop | Persist peak executable net profit per lifecycle | Prevent losing trailing state on restart |
| Existing sub-₹40k/₹40k+ cap discontinuity | Scope V1 to 100% authorized reconciled cash at all bankroll levels | Preserve deliberate all-in mandate as winnings compound |
| CAS settlement window | Normal regular-session V1 with calendar-derived flat deadline | Broader eligibility and December 2026 rule resilience |

---

## 8. Live-order admission and outcome accounting

The user wishes to learn from **actual money**, so production evidence must be maximally complete. Each rejected setup, broker intent, partial fill, exit attempt and final settlement creates durable immutable records. There must be a clear causal chain: source observation → derived feature → signal → candidate ranking → pre-dispatch book/funds → intent → broker acknowledgment → executed fill → open position → exit trigger → sell fill → charged net P&L → reconciled flat cash.

The minimum realized reporting is: signal episodes, valid opportunities, submitted buys, zero-fill IOC attempts, partial/full entry fills, worst/average slippage versus contemporaneous best ask, gross profits and losses, all reported charges, true net per trade, before/after spendable cash, maximum favorable/adverse excursion recorded while open, reason for every exit, and exact blackout/blocker times from the VM. Do not conflate a modeled return with a completed trade. Do not silently replace a missing broker charge with zero.

Do not optimize thresholds automatically after each winning or losing fill; that would manufacture in-sample success. Store all results and source versions for a deliberate future revision. On the first live day, absence of a trade is permitted if criteria are absent. Never force a calibration order merely to make the dashboard look active.

---

## 9. Release, VM cutover and real-money activation

**Existing installation paths discovered in source:** immutable installed releases under `/opt/sablestone-dhan-dashboard/releases/<40-character-SHA>`; VM configuration `/etc/sablestone-dhan/production.toml`; account state and ledger under configured `state_dir`; trading service `dhan-cas.service`; existing guarded roster/cutover helper `ops/activate-profit-exit.py`. These are source-level facts, **not proof that the current VM has those paths today**. Check the actual VM, active service override, existing release SHA and configuration *before* calling any upgrade helper. Do not guess the working directory.

Required rollout order:

1. **Read current production truth:** `git rev-parse HEAD`, active `systemctl cat dhan-cas.service`, current software digest, sanitized strategy roster, broker flat/position/pending-order status, ledger/recovery state, trading calendar and current mandate. Do not print credentials, TOTP/PIN or access tokens to logs. Preserve and archive the previous exact release and roster for rollback.
2. **Edit the code** in the repository, keep history and CAS source untouched, implement new V1 entry/exit version, update dashboard and required packaging/manifest. Build/ship an immutable source release using the project's existing mechanism, retaining the same dependency and credential handling. If newer source changed the architecture, adapt without dropping newer safety fixes.
3. **Operational correctness gate:** keep the repository's required source-integrity, acceptance and mutation checks needed by `run_verification()` and the activation tool. This is **not** a historical-strategy profitability study and must not be reinterpreted as one. Fix actual code failures; never create forged verification markers, patch away the mutation check or run with an unverified artifact.
4. **Reconcile the incumbent:** before switching source, verify existing live account exposure and unresolved/unknown orders are managed and flat if the upgrade path demands flat. Do not close an unrelated real position merely to make a deployment pass; if flatness is impossible, preserve recovery and report a blocked cutover.
5. **Stop new CAS entries through the guarded roster cutover** while keeping its code and past lifecycles. On final activation use scanned/funded allowlists containing **only `VOLATILITY_SHOCK_V1`**; confirm the actual effective config includes the funded subset explicitly. Avoid the `funded_strategies` default that funds every scanned strategy if omitted. Preserve the operator's existing account mandate and live authority, subject to its valid explicit limits.
6. **Install verified release and restart** through the current project's guarded VM workflow, not `git pull` on a running process. No direct `systemctl restart` with live unknown positions. Check the service process runs the *new* verified source and the associated config, data-socket feed and route qualification match.
7. **Permit real live entries only when naturally generated V1 signals qualify.** The operator has requested actual live executions and all-in sizing within the existing mandate. Do not submit a synthetic initial trade, spoof a signal or use fixed-entry test orders. Do not block the launch on paper returns. A broker order still requires real-time account authority, no unresolved obligations and a qualifying real observation.
8. **Verify after switch** using read-only dashboard/ledger/current broker API: V1 is the only funded entry owner; CAS and old strategies cannot initiate; no source-digest mismatch; no order-account conflict; no invalid or duplicated broker orders. Show the first genuine live decision and any authentic fill/exit/charges only when they occur.
9. **Rollback plan:** if input-integrity/OMS/reconciliation/source errors occur, immediately disable **new** V1 entries, preserve active-position management, maintain the prior immutable release and existing ledger for recovery. Do not revert while the previous release cannot manage a V1-owned open position; new version must remain able to close it or include a compatibility migration. Never delete ledgers/positions to restore the previous state. Trading loss by itself is not proof of software corruption; log it honestly instead of inventing a system fault.

`ops/activate-profit-exit.py --scan-only ... --funded-only ...` currently validates release and account obligations and performs an atomic source/config switch. Extend/reuse that guarded workflow *only if* its existing assumptions and installed paths remain valid. Its `--retain` policy can conflict with V1's new owner-specific exit rules; do not unintentionally apply two competing profit ratchets. Do not grant an `--extra-route-attempt-on` unless expressly authorized. Avoid shell commands that reset the old mandate, database or session counters.

---

## 10. Exchange rules that must be versioned by effective date

NSE's current published regular derivatives session is 09:15–15:40 IST. The SEBI change published on **15 October 2026** is effective **7 December 2026** (except later provisions) and provides: expiring index derivatives stop at **15:30** on their expiry day, non-expiring index derivatives may trade until **15:45**, and expiring derivative settlement becomes a **15:00–15:30 underlying VWAP** rather than an auction-linked closing price. Cash CAS becomes a separate 15:30–15:40 session. These timing and settlement changes make **effective-date- and contract-specific** logic essential. Actual day's exchange market-calendar response and formal current notices outrank generic times written here.

V1's ordinary intraday flatten-by-15:15 design avoids intentional dependence on expiry settlement, but all clocks must still be verified and no hard-coded weekday may be used for expiry selection. The existing CAS code is retained but **not funded**; do not assume it will retain an edge under the changed settlement system.

Dhan currently publishes **₹20 per executed F&O order**, plus taxes and exchange charges; use the exact rate schedule already implemented in `FeeSchedule` and reconcile to genuine broker contract notes. Broker pricing or statutory charge changes must be effective-date/version-aware. Expired/exercised contracts can have additional charges. The ledger's last observed broker fees outrank a zero-cost assumption.

**Authoritative / supporting sources for implementation:**

- GitHub repository: https://github.com/zaynvirkk/Dhan-Bot
- Dhan Orders API: https://dhanhq.co/docs/v2/orders/
- Dhan Live FULL feed: https://dhanhq.co/docs/v2/live-market-feed/
- Dhan minute history: https://dhanhq.co/docs/v2/historical-data/
- Dhan current charges: https://dhan.co/pricing/
- NSE market timings: https://www.nseindia.com/static/market-data/market-timings
- Exchange-rule summary (dated 16 Oct 2026, links formal SEBI circular): https://zerodha.com/marketintel/bulletin/461085/changes-to-closing-auction-session-cas-from-december-7-2026
- Main SEBI circular reference: `HO/47/11/11(3)2025-MRD-POD2/I/23843/2026`, issued 15 Oct 2026. Codex should fetch the official circular before hard-coding effective-date behavior.

---

## 11. What Codex must not do

- Do **not** falsely tell the operator the new strategy is proven better in realized returns than CAS. It is a payoff-aligned experiment.
- Do **not** change capital to 10%/25% per trade, split funds between CAS and V1, or allocate real funds to a shadow strategy; the operator intentionally accepts full-debit risk.
- Do **not** remove the old CAS source, prior actual trade receipts, or historical research; pause it for *new* entry only.
- Do **not** silently reactivate seconds scalps, PCR trend, rebound or old expanded strategies.
- Do **not** disable charge reserves, bid/ask validation, quantity/price bands, static-IP checks, exact-account confirmation, authorization, failed-order reconciliation, pending-position recovery, release verification or the one-position constraint.
- Do **not** fabricate source timestamps, future option bars, executable depth, backtest profits, order fills, P&L or missing broker fee receipts.
- Do **not** treat absence of a good setup as failure and lower thresholds mid-session simply to produce a live trade.
- Do **not** re-use a previous close or top-of-book bid as a guaranteed fill; IOC can expire or partially execute.
- Do **not** rebuild a second order writer, move money outside the operator-authorized account, borrow, use naked option shorts or widen mandate beyond observed spendable funds.
- Do **not** use a full repository redeploy command on the live VM until the previous source is preserved and the current position can still be managed.

---

## 12. First live session: the evidence to return to the operator

After actual release cutover, return a factual record with:

**Deployment identity:** source/release commit SHA, effective V1 config revision and strategy roster, daemon PID/status, data-feed status, account/route admission, calendar, current position, remaining funded bankroll and whether the service is armed for naturally occurring trades.

**Signal timeline:** each completed eligible minute that passed shock-size screening; exact reasons for abstention or failure of futures/breakout/volume/liquidity conditions; actual available timestamps and feed freshness.

**Real-money evidence:** for each authentic intent and fill, original/filled lots, entry limit versus executed average, gross premium committed, actual reported fees, exit trigger, successful/failed sell attempts, final reconciled net P&L and next bankroll. Do not credit a trade until actual broker fills and settled records support it.

**Status vocabulary:** `DEPLOYED_IDLE`, `SIGNAL_OBSERVED`, `ENTRY_BLOCKED`, `BUY_PENDING`, `POSITION_OPEN`, `EXIT_PENDING`, `BROKER_RECONCILING`, `CLOSED_RECONCILED`, `DEPLOYMENT_BLOCKED`. Do not print `DEPLOYED_LIVE_PROFITABLE` in the absence of realized profit. Do not promise a time until the first signal or a target cash amount.

**Final directive:** Implement the above bounded, versioned single-strategy replacement and perform the existing guarded production deployment to the operator's already authorized live account when the actual VM/account checks permit. It should be a real-money strategy, not a paper engine. If a genuine operational blocker exists, do not bypass it: deliver the precise blocking fact, with code ready and history intact. All economic claims must follow actual broker results, not simulated expectation.
