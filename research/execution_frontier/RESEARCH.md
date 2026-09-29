# Mechanism inventory: avoid confusing an instrument with an edge

Calls, puts, futures and leverage specify exposure. The research question is
which observable information forecasts a net payoff after financing, option
pricing, taxes and execution. A bearish forecast may work in a put yet fail
in a short future because of funding, or vice versa because of time value.
No such equivalence is assumed here.

| Distinct source of return | Coverage actually completed | Remaining executable test |
|---|---|---|
| Directional continuation/reversal, long CE or PE | Prior expiry/intraday work plus this symmetric overnight, trend-filter and allocation replay | A newly frozen candidate needs genuinely separate history or prospective outcomes and executable quote calibration |
| Public event repricing | Earlier event-family replays and failures remain recorded | Complete timestamped event denominator, exact options and independent validation; do not select news by later winners |
| Scheduled-event volatility | Previously reviewed, not a complete event-conditioned option replay | Price CE+PE before an already-known event; train its conditional move distribution only on prior events; include IV crush and both legs' costs |
| Stock cross-sectional momentum/reversal | Earlier historical-universe share/call experiments cover six selectors | Intraday long/short cash implementation with prior dated VAR/ELM, broker eligibility and forced square-off; a current 4x quote cannot be backcast |
| Commodity trend/carry | Gold Petal history and current small-lot feasibility checked | Dated contract rolls, margin/MTM, tender restrictions and two-sided liquidity; exact-contract returns, not leveraged continuous spot |
| Volatility insurance selling | Current sampled short/hedged capital requirements checked | Real premium-to-realized-risk edge, dated SPAN/ELM and worst funding path, legging and overnight jumps |
| Debit/credit/calendar relative value | Expanded cross-index vertical margin survey | Synchronized executable leg quotes, margin throughout entry/exit and holding, no naked first-short assumption |
| Auction/passive flow and cross-market lag | Earlier source/clock feasibility work remains incomplete | Timestamped auction trajectory, ex ante exposure relations, actual feed delivery delay and depth; final auction summaries cannot become pre-auction signals |

## Independent primary-source checks in this pass

* [Dhan orders](https://dhanhq.co/docs/v2/orders/) documents limit orders,
  validity and cancellation. These controls constrain orders; they do not
  provide historical queue positions or guarantee execution. This experiment
  does not assert that a particular API-validity combination is accepted live.
* [Dhan margin documentation](https://dhanhq.co/docs/v2/funds/) explicitly calls
  returned margins indicative and valid for the current session. Broker
  snapshots here are feasibility probes, not a historical financing model.
* [Dhan RMS](https://dhan.co/risk-management-policy/) describes stock-specific
  cash intraday VAR+ELM subject to a minimum 20% margin; F&O follows exchange
  margin. Its current cash auto-square-off starts 15:10 and derivatives 15:25,
  with a warning about orders near the cutoff. Current rules must not be
  silently imposed on older sessions or on a carry-forward strategy.
* [NSE clearing margins](https://www.nseindia.com/static/products-services/equity-derivatives-margins)
  explains upfront margin collection. [Dhan options](https://dhan.co/options/)
  describes premium plus charges as the buyer's required outlay. Buying a
  cheap option embeds leverage; it does not grant arbitrary borrowing against
  a INR 9,411 premium budget.
* The [New York Fed's July 2026 follow-up](https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/)
  reports that the previously documented U.S. overnight drift faded in the
  later sample. It is not Indian evidence, but it weakens treating the earlier
  inventory explanation as a timeless trade. Mechanistic plausibility still
  needs current local out-of-sample evidence.
* [Time Series Momentum, authors' research](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum)
  studies diverse futures/forwards and slower horizons. This motivates a
  commodity/trend lane, not a claim that one gold contract or rapid option
  bets inherit its returns.

The broader agenda is not exhausted. The highest-information missing lanes
are a funded, dated-margin cash intraday implementation and event-conditioned
volatility, followed by exact-contract commodity trend. This prioritization
reflects different economics and identified data gaps, not a promise they win.
No additional capital, paid data, trading or deployment is authorized by a
research ranking.

The completed cash probe now confirms ten current broker margin quotes: both
intraday sides in RELIANCE, HDFCBANK, SBIN, INFY and TCS, at approximately 4x
account notional. All fit current cash, requiring INR 7,356–7,503.12. This
closes today's affordability question, not the historical margin/eligibility
or directional-edge questions. Earlier bounded authentication failures remain
recorded; a later identity-checked session completed these read-only probes.
