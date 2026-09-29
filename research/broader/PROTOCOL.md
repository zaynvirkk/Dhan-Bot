# Broader search — 27 September 2026

User asks for independent research beyond the previous intraday suggestions.
Benchmark: INR 9,411.18 -> 12,566.43 in the recent 90-day window. Higher
historical return alone does not establish an edge. No orders or deployment.

Economic review: overnight inventory reversal; slower momentum; cross-sectional
stock selection; volume-conditioned breakouts; futures positioning; commodity
micro contracts; option relative value/carry; cash-equity implementation. Use
primary exchange/broker/research sources. Published results motivate hypotheses;
foreign-market effects are not imported as Indian option profits. Margin and
unavailable historical data limit a test, not its economic possibility.

Two reused 90-calendar-day windows: 23 March–20 June and 21 June–18 September
2026. Each variant starts independently with INR 9,411.18, no deposits or
fractional lots. These are discovery periods, not holdouts. Warm-up starts
16 February. All stock ranks use only previous published session data and the
previous session's F&O membership; no current constituent list. Ties alphabetical.
No tuning after new outcomes. Rank the entire eligible historical stock set.

Six stock selectors, each observed at 09:30. Require previous 20 full sessions,
median cash turnover >=INR 100m, valid current identity and 20-session price
history; exclude a symbol when consecutive close/next official previous-close
differs >0.5%, or a daily return exceeds 20%, in this past-only lookback. This
is an explicit action/discontinuity exclusion, not an adjusted-price model.

* MOMENTUM20: highest compounded past 20 daily return, must exceed 10%.
* SMOOTH_MOMENTUM: highest return / daily-return population standard deviation,
  same positive-return gate. This is one past-only score, not fitted weights.
* TREND_DIP: most negative yesterday return <=-3%, with positive 20-day return.
* VOLUME_BREAKOUT: yesterday close above the preceding 20 sessions' highs,
  volume >=2x their median, ranked by volume multiple.
* OI_SQUEEZE: yesterday spot return >=2%, volume >=2x median preceding 20,
  nearest nonexpired same futures contract OI falls >=5% versus previous day;
  rank price return. OI does not identify buyer/seller intentions by itself.
* OI_BUILD: same price/volume filter, futures OI rises >=5%; rank price return.

For every selector test cash shares held to the next session's 15:10 and to
the fifth subsequent session's 15:10 (12 variants), plus long stock calls
held at most five subsequent sessions (6 variants). One position per strategy;
signals while occupied are unavailable, no independent trade multiplication.
Stock CALLs choose closest ATM through ten OTM strikes, within 10% moneyness,
nearest expiry more than seven calendar days beyond planned liquidation.
If no lot fits, record no order; never invent an affordable fractional option.
Cash shares are unleveraged; the purpose is to test signal vs option implementation.

Four NIFTY overnight rules at 15:10, each exited next session at 09:30 or 15:10
(8 variants): unconditional CE control; SELLOFF_REBOUND CE when session return
from 09:15 open <=-0.75%; DAY_CONTINUATION choose day's side if absolute return
>=0.5%; TREND_ALIGNMENT same day-side when >=0.2% and same sign as preceding
20 sessions' close-to-close return. Choose nearest expiry strictly after exit
day, ATM plus at most three OTM strikes. Never hold expiry through settlement.
No new position without a scheduled liquidation inside the test window.

Total 26 variants. All prices at decision use completed minute bars only.
Stocks must have the first 15 completed minutes; entries one full minute after
decision. Cash buy limit 0.5% above known close, high plus 0.1% entry scenario,
0.10 price grid, 1% prior-minimum and entry-bar volume participation. Options
limit +5%, adverse-high entry, 5% participation, known OI >=10 lots, exact
historical lot. Quantity set before future fill: <=95% cash inclusive of fees,
reserve three exit slices. Fixed miss means no trade; no resizing from future.

Monitor completed option closes from entry through 15:15 each day and from
09:16 next session: +100% target / -50% stop, then processing delay and adverse
low minus 1% liquidation; no overnight stop guarantee. Cash shares use +20% /
-10% completed-close triggers, exits low minus 0.1%. At most three one-minute
liquidation slices; insufficient volume or absent holding bars = UNKNOWN.
Daily gaps are actual next-session prices. Skip nontrading hours using the
observed exchange session calendar. Cash settlements wait until next session;
no same-day recycled delivery proceeds. Corporate-action identity/price
discontinuities during holdings make the path UNKNOWN, not a gain/loss.

Fees: options existing conservative FeeSchedule, per executed child/slice;
cash delivery zero brokerage, STT 0.1% each side, NSE transaction 0.0030699%,
SEBI 0.0001%, stamp 0.015% buy, GST 18% on service charges, DP 12.50+GST on
sell; round taxes conservatively up. Use documented assumptions throughout.
Strict audit requires option daily volume/tick reconciliation and verified
dated ban lists for new stock options; reported scenario may relax source
volume/tick audit but never silently assume an unknown ban list is empty.
Report any resulting incomplete paths explicitly. Cash data uses published
ISIN and minute-vs-official OHLC/volume checks; mismatches are disclosed.

Stress all resolved strategies at three-minute processing, doubled price
slippage (cash .2%, options 2%), and best-profitable-trade deletion with full
chronological re-sizing. A benchmark-beating result receives 999 seeded random
direction controls for NIFTY, or seeded random selection from the contemporaneous
qualifying stock set where data permits; unresolved controls are reported.
Correct for at least 144 total variants (118 earlier +26 here). No weak raw
p-value, tiny trade count, or repeatedly reused sample can authorize live trading.

Commodity lane: probe exact historical Gold Petal contracts and history from
both brokers; current one-lot affordability is not historical margin, liquidity
or account eligibility. Do not manufacture a bankroll from continuous spot
gold or backcast today's margin. If necessary inputs are unavailable, document
the specific probe result and leave the family unscored. Same rule applies to
short-volatility, spreads, carry and auction/depth-dependent strategies.
