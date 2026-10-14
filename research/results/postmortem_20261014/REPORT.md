# Actual execution postmortem: 13–14 October 2026

The winning and losing days used different engines. Yesterday's CAS engine
traded a provisional settlement-price discrepancy on same-day expiry options.
Today's ordinary published-PCR engine bought a next-expiry call from momentum
and yesterday's positioning, then allowed a large profit giveback.

| Actual executions | 13 October | 14 October |
| --- | ---: | ---: |
| Filled closed trades | 16 | 1 |
| Gross trading P&L | INR 2,791.75 | INR -2,665.00 |
| Reported final charges | INR 1,082.3916 | Pending |
| Final reported net | INR 1,709.3584 | Pending |
| Net winners / losers | 6 / 10 | Pending fees; gross loss |
| Observed buy-to-last-sell receipt interval | 3.45–13.74 seconds | 3h 42m 59s |

These are actual filled prices, not order limits. Holding intervals use receipt
timestamps rather than claiming exchange matching latency. Today's 65 units
filled at 122.65, sold at 81.65 at the recorded 15:34 session deadline. Cash after
sale is INR 7,816.11, exposure zero. Today's complete invoice is not published.
Two-day gross profit is only INR 126.75 before yesterday's INR 1,082.39 charges
and today's remaining charges; gross-only comparisons would hide the loss.

## Why yesterday made money

Six profitable transactions outweighed ten losing transactions after the
reported charges. The biggest winner's attributed net INR 1,961.20 exceeds the
whole day's final net. Closed-trade attributed net peaked at INR 4,570.65 after
trade six, then ended at INR 1,709.36: INR 2,861.29 was given back. Fee allocation
is broker-reported and may concentrate a contract's taxes on an order; it was
not known at the earlier decision timestamps. It must not be used as a causal
signal. Most subsequent entries were another attempt at the same 22,700 CE
discrepancy, not independent discoveries of an edge. CAS fits the operator's
short-duration objective, but one expiry is not enough to estimate future returns.

## Why today lost

The 11:50 signal used spot +0.1543% and futures +0.1510% over 15 minutes,
futures above VWAP, and +67.56% PCR change from the complete prior-session
chain. The PCR was not evidence of current short-covering. Four same-side
unranked configurations competed using execution friction and holding time;
there was no estimated positive profit for the selected engine. The retained
trade also predates the deployed correction for successive-clock tie bias.

Both previously tested 90-day windows for this entry rule lose money under
every tested profit-retention exit. Nevertheless the experimental fallback
admitted it to funded trading. Execution quality cannot qualify its alpha.

Its original 50% completed-close premium stop would allow a 137 peak to fall
to 68.50. The quote archive instead contains a bid peak 138.60 at 12:05:36 IST,
about INR 1,036.75 gross liquidation gain for 65 units. The stop did not preserve
that gain; the calendar close minus six minutes eventually ended the losing
trade. From the actual sale to session end, the sampled bid never exceeded
82.55, well below break-even. Simply holding six minutes longer would not have
recovered this trade in the observed tape.

## Counterfactual checks

Read-only processing examined 5,726,400 recorded observations and decoded
18,705 relevant held-option quotes. Only public time/price/depth economics were
extracted; no account, order, token or raw-frame identities were exported. Last
quotes per second retain their true receipt timestamps. Rejections and up to
77-second quote gaps prevent claims of a complete tick or guaranteed fill replay.

Applying the existing net-profit rule from actual entry would first trigger
before the later peak. At 50% retention it triggers at 11:54:38 IST; the one-second
arrival scenario supports a displayed-depth sale at 127.55 and approximately
INR 250.41 net. Initial orders miss their original limit at 3/5/15-second delays.
The experiment does not invent retries or claim that those misses bank a profit.
25% retention gives INR 146–221 in the tested displayed-depth scenarios;
75% retention misses its first limit in every tested delay. Buying the earlier
entry and selling at the later maximum is an oracle, not an executable rule.

A stop-new-entries rule retaining 75% of positive closed session profit, using
conservative fees available at the time, would stop after trade 13 with modeled
net INR 3,364.05 and skip later original transactions. 50% stops after trade 14
at INR 1,886.48; 90% after trade five at INR 3,454.21. These are prefix-stop
attribution scenarios on the recorded path, not a fresh bankroll/fee-invoice
replay or proof that the chosen percentage is optimal. No session-profit
parameter is activated from this one-day threshold comparison.

## Implemented response

An explicit funded strategy subset is independent of scanning configuration.
CAS_LAG_V1 is the chosen funded engine; PCR and all other currently unqualified
directional configurations are observation-only. The normal broker, depth,
cash, route, release and auction admission gates still apply. Existing positions
remain managed even if their owner loses new-entry permission. No position,
mandate, lifetime cash cap or probe budget is reset.

The dashboard exposes funded versus observation-only permissions, current rule
inputs, completed actual executions, gross results, reported fees and net only
when every relevant executed order has complete charge coverage. No-fill
configurations have no performance evidence. Expanded-owner HOLDING/TIME_EXIT
reasons now retain the actual policy explanation.

Other strategies will require a source-consistent chronological net-positive
replay, execution stress and results beyond the reused design periods before
funded promotion. Prior profits, targets, low spreads and many aliases of the
same entry are not sufficient admission evidence. CAS remains a provisional
funded preference supported by this account's execution receipts, not an
always-winning strategy.

Derived exact execution summaries and all twelve exit-arrival scenarios are
in execution_summary.json and comparison.json. Deterministic counterexamples
cover pre-entry information, thin depth, delayed missing quotes, limit misses,
future-peak invariance, explicit funded subsets and charge coverage.
