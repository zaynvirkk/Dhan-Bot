# 15 October 2026: complete-session execution review

The account made **zero filled trades and INR 0 gross trading P&L today**.
Fresh post-close Dhan orders, trades, positions and funds reads agree with the
durable ledger: three zero-fill route-check orders, no strategy order, no open
position, no pending order, spendable cash **INR 7,805.94**. That is the same cash
observed at09:44; it is not an independently recorded09:15 balance. Subscription
and VM expenses are not included in trading P&L and were not recovered today.

This was not a full-day trial of seven execution-ready strategies. The opening
roster funded only CAS; the pullback engine was funded after10:14, and the five
seconds engines joined the funded process after14:24. The afternoon route check
failed. Recorded funded rules also produced no qualifying setup. Both the
execution failure and the actual unmet rules matter.

## Scope and independent checks

Session: provider-confirmed NSE derivatives09:15–15:40 IST. Account/order audit
was taken after17:30; the independent market-history read was at17:35:39. All
calls were read-only. No service was restarted, no allowance granted, no order
placed/cancelled and no strategy or execution rule changed during this audit.

Sources: current Dhan orders/trades/positions/funds, read-only dated SQLite
queries, systemd lifecycle events, actual retained evaluation receipts, the
separate simulator state, retained dashboard history and Dhan minute index
history. Account/order IDs, credentials, private broker errors and raw financial
ledger payloads are excluded from the published artifacts.

## Open-to-close timeline

| IST | What actually happened | Consequence |
| --- | --- | --- |
|09:15–09:55|Only CAS had funded permission;137 configurations were scanned. Today was not the loaded NIFTY expiry; next expiry19Oct.|CAS could not trade. Other scanner signals could not use money.|
|09:55–10:10|13 configurations in six correlated families recorded29 SIGNAL receipts, all bullish. Saved assessments say FUNDED_STRATEGY_DISABLED.|These were observed setups, not13 independent executable wins. No option affordability/depth assessment was recorded.|
|10:14:39–10:14:52|Roster change restarted the funded service; CAS and TREND_PULLBACK_FAST became the selected funded pair.|The five seconds engines did not exist in the funded runtime yet.|
|10:15:36|First route check:65 units, minimum-price buy limit, rejected for low OI.|No fill; first normal attempt used.|
|10:15:38|Second route check:65 units, cancelled by exchange system, zero fill. Matching route evidence subsequently qualified this socket.|The pair had a qualified route during the following daytime period. Fresh account/feed snapshots through13:08 independently confirm it.|
|10:00–14:45|Every one of58 scheduled five-minute pullback boundaries has a completed NO_SIGNAL receipt, including observations before funding.|No qualifying pullback was ignored by a fill selector. Nine additional missing-bar warnings remain warnings.|
|13:46–14:09|The separate read-only seconds observer was introduced. Permission errors, then catalogue-memory failures, were repaired. A futures receipt-time/midquote correction was deployed; current futures observations began after14:09.|This development/observer startup period was not a funded seconds-strategy trial. It did not create a position.|
|14:08 onward|Corrected observer ran its five independent simulations.|Model results are separate from actual money.|
|14:23:50–14:24:54|Operator activation restarted the funded trader onbc3b50a; seven names were selected and seconds evaluations began.|Restart required a new route qualification. Previous socket proof did not carry over.|
|14:24:57|The authorized third route attempt selected the same November20050PE strike rejected in the morning; Dhan again rejected it for low OI.|All3of3 permitted attempts were used. New real entries remained blocked for the rest of the session.|
|14:24:54–15:40|All five seconds engines recorded evaluations; none recorded a funded SIGNAL. Four quote rules also experienced stale/missing futures and repeated warmup periods.|No strategy buy order was created. Feed availability was imperfect even apart from the route blocker.|
|15:00:09–15:00:11|The independent futures-catch-up simulator saw one signal and then a delayed limit/signal miss.|Zero simulated entry; no paper profit. At15:00:09.776 the funded runtime separately recorded NO_SIGNAL / SECONDS_EDGE_BELOW_COSTS.|
|15:40 close|Zero actual trades/fills, positions and pending orders.|INR0 gross trading P&L.|

## Why the pullback strategy never bought

All58 scheduled boundaries from10:00 through14:45 have an actual NO_SIGNAL:

- **49:** absolute30-minute trend below0.25%.
- **9:** trend large enough, but the10-minute move went in the same direction;
  the required opposing pullback was absent.
- **0:** qualifying setup.

For example,10:20 had a+0.4509%30-minute move and+0.0498%10-minute move, both
up. At14:35 the trend was−0.1585%, below threshold. At14:45 it was−0.1880%,
also below threshold. Nine additional UNKNOWN receipts occurred at10:15,
10:40,10:50,11:30,11:45,11:55,13:20,13:55 and14:05. Each of those boundaries
also has a completed NO_SIGNAL receipt; missing inputs were never counted as
successful evaluation. Full values and receipt times are in
[pullback_decisions.csv](pullback_decisions.csv).

This frozen rule seeks a trend, an opposing pullback and resumption. It does
not buy a sustained rally merely because the market is rising.

## What the seconds engines actually saw

Counts below are saved checks within the derivatives session, beginning14:24:54.
They are repeated observations, not independent trading opportunities or exact
elapsed seconds. Each engine has3,776 in-session receipts.

| Funded engine | Rule not met | Combined execution/edge guard failed | SIGNAL |
| --- | ---: | ---: | ---: |
|Futures catch-up|2,860|25|0|
|Failed breakout|2,885|0|0|
|Flow continuation|2,840|45|0|
|Strike catch-up|2,795|90|0|

Each of those four also recorded **589 warmup**, **248 unavailable-futures**
and54 session-closing checks. About22.2% of their saved checks were warmup or
unavailable-futures; this is a sample fraction, not an uptime estimate. The
funded market socket reported14 reconnects since the14:24 startup. A reconnect
resets the quote history and requires fresh warmup; malformed/unusable inputs
can also reset it. Exact causes/times of every reconnect were not retained.
The measured two-second futures move on saved evaluated checks ranged
from−7.7 to+6.9 points.

The guard's saved label SECONDS_EDGE_BELOW_COSTS is broader than its name:
the same check enforces usable quotes, spread/depth, allowed prices, cash and
projected target margin after fees. The old funded release did not retain a
separate failed subcondition. The25/45/90 counts cannot all be attributed to
fees alone, and they are not proven missed winning trades.

Event impulse recorded3,722 NO_FRESH_EVENT checks and54 closing checks. Its
source is a narrow official-filing filter for NIFTY members, not every news,
macro or economic event. NO_FRESH_EVENT does not mean nothing newsworthy
happened anywhere.

The read-only simulator had **one futures-catch-up signal, one miss and zero
entries**, with the other four models also at zero entries. Its nominal delay
is one second; the recorded signal-to-miss interval was about2.04seconds.
Independent feeds/evaluation times differ from the funded process. No model
bankroll gained or lost money, and none of those counters represents a real
order or fill.

## The market did move

Fresh Dhan history returned375 completed index bars, with availability timestamps
09:16–15:30 (completed-minute boundaries). Observed opening NIFTY was22,671.30,
high23,056.40, low22,637.40 and last bar close22,997.35. The previous-close
reference was22,622.70: a374.65-point / roughly1.66% rise. There was a strong
morning rise and an afternoon pullback. This explains why a narrow opposing-
pullback rule could sit out a visibly active day; it does not establish an
executable option profit at an earlier unknown ask.

The six early bullish observation-only families were OPEN_DRIVE, FUTURE_TREND,
IV_CHEAP_TREND, SECTOR_CONFIRM, PCR_CONFIRM and INSTITUTIONAL_ALIGN. Their
selection/funding history must be evaluated with the information available then.
Enabling just today's successful-looking rules afterward would introduce
hindsight. Exact chosen contracts, contemporaneous affordability, depth and
adverse fills are missing for those disabled setups.

## Engineering failures and remaining uncertainty

1. **Probe selection failed twice on the same illiquid strike.** The old chooser
   ranked minimum-price order cost and security ID without OI eligibility or
   excluding today's rejected contract. The afternoon restart lost an otherwise
   qualified route, and the final allowed attempt repeated the known rejection.
   This was avoidable execution engineering, not an unavoidable market outcome.
2. **Funded and dashboard releases differ.** The liquidity-aware selector repair
   is pushed and deployed read-side on377e404; the funded process remainsbc3b50a
   /PID404513. The fix is not yet running in the funded trader. See the
   [existing upgrade record](../../../docs/ROUTE-SELECTION-REPAIR-2026-10-15.md).
3. **Short-horizon data continuity was insufficient.** Four engines repeatedly
   lost usable futures/warmed up. The latest snapshot being connected does not
   erase the earlier gaps. Their lost opportunities cannot be priced from
   missing data.
4. **History is too short for a connection-level postmortem.** The dashboard
   retains only240 recent detailed monitor samples. By this audit those samples
   were all after close. Its daily aggregate retained3,258 samples, two unknown
   samples and zero >90-second sampling gaps, but these are monitor availability
   counters, not proof of uninterrupted market/account data. Durable strategy
   decisions remain available. Market-frame recording when flat is restricted
   to15:05–15:45; the separate quote archive begins in the afternoon, samples
   quotes and omits OI. Neither supplies a full open-to-close execution replay.
5. **No new profitability evidence.** The five new engines were not funded from
   the open, the later route was blocked, and none filled even in the independent
   simulator. Today neither proves they work nor provides a clean full-session
   test of their live execution economics.

The budget counter INR83.67 represents accumulated potential probe debit
allowances, **not an executed cash loss**. All three probes filled zero.
The requested15October broker ledger returned only opening/closing carry-forward
rows dated14October; it supplied no itemized15October VM, subscription or other
expense receipts. Such expenses remain unquantified, not assumed zero.

## Result

Today produced no trading income. There were genuine unmet strategy conditions,
late strategy availability and an avoidable afternoon route failure. It is
incorrect to call the system execution-ready throughout the day, to say the
market offered no movement, or to credit any hypothetical missed profit.
The audit did not alter the funded service or attempt another real order.

Machine-readable, allowlisted evidence: [audit.json](audit.json). This report
extends the separately retained noon audit; it does not overwrite its cutoff.
