# Independent expansion of the search

The old best INR 12,566.43 is an observed score on repeatedly reused data.
It is not a target that warrants increasingly flexible fitting. The new pass
changes economic exposure, universe and holding period; parameters are frozen
in PROTOCOL.md before outcomes. Rankings across many attempted rules are
subject to selection bias even when individual trades are timestamp-correct.

## Distinct mechanisms investigated

| Family | Why examine it | Concrete treatment in this pass |
|---|---|---|
| Overnight inventory reversal | Selling pressure and risk-bearing constraints may reverse across sessions | NIFTY overnight selloff-rebound with next-morning and next-afternoon exits; include unconditional long-call control |
| Directional overnight continuation | Information may propagate beyond the cash session | Day continuation and alignment with a prior 20-session trend; same fixed, exact option contract across the gap |
| Cross-sectional stock momentum | A strong stock can continue while the index is quiet | Rank all prior-session F&O stocks on 20-session return and return/volatility; shares and long calls tested separately |
| Pullback within trend | Temporary selling in an established trend | Prior-day drop >=3% with positive 20-session return; one/five-session shares and five-session calls |
| Participation and futures positioning | Volume expansion/position change may distinguish a persistent repricing | Published volume breakout, price rise with OI contraction, and price rise with OI expansion; OI is not proof of dealer positioning |
| Commodity micro futures | Small contract multipliers may avoid option decay and equity-index margin constraints | Actual Dhan Gold Petal history probe succeeds; Upstox expired-contract request rejects the underlying key; historical margins/contract-liquidity audit remain incomplete, no invented bankroll |
| Short volatility / spreads / carry | Premium or financing compensation differs from directional prediction | Previous actual Dhan margin requests exceed the balance for sampled NIFTY structures; margin paths and synchronized leg fills remain necessary, cannot substitute net debit or maximum loss |
| Corporate information and scheduled-event vol | Public information or a known event may be underpriced | Earlier event tests retained, not discarded; no new materiality threshold chosen to recover handpicked winners |
| Cross-market/auction/microstructure | Information or compulsory order flow can lead local prices | Delayed global indicators, missing historical quotes/auction trajectories prevent a subsecond edge claim; minute bars are not order books |
| Cash-equity delivery | Tests whether derivatives packaging destroys a stock signal | Unleveraged whole shares, explicit fees and settlement timing; does not assume intraday leverage or free turnover |

The selected stock universe is historical F&O membership, not the current
list and not only companies appearing in a prior news shortlist. Every day's
top rank is chosen from prior information; a later inability to afford the
option does not permit choosing a stock that eventually did better.

## Primary sources and what they establish

* [New York Fed, The Overnight Drift](https://www.newyorkfed.org/research/staff_reports/sr917):
  investigates overnight equity returns and inventory-related asymmetry in
  US markets. Supports asking an overnight question, not a NIFTY profit claim.
* [AQR authors, Time Series Momentum](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum):
  diversified futures/forwards evidence at much slower horizons. It does not
  validate minute option buying or a concentrated small account.
* [Nifty200 Momentum 30 methodology overview](https://www.niftyindices.com/indices/equity/strategy-indices/nifty200-momentum-30):
  an Indian momentum index exists, with different construction and horizon.
  The 20-session hypotheses here are not replicas of that index.
* [Dhan historical-data specification](https://dhanhq.co/docs/v2/historical-data/):
  minute OHLCV/OI history for active instruments, with bounded date requests.
  A history endpoint supplies neither historical margin nor bid/ask execution.
* [Upstox expired-futures endpoint](https://upstox.com/developer/api-documentation/get-expired-future-contracts/):
  exact contract discovery is documented, including commodity fields; actual
  request for MCX_COM|525 / 2026-06-30 returned HTTP 400 UDAPI100011. A documented
  schema alone is not evidence that this particular historical route works.
* [MCX Gold Petal product page](https://classic.mcxindia.com/products/bullion/gold-petal):
  dated contract specifications are versioned; use those rather than backcast
  today's trading or margin terms. The current broker metadata says one gram.
* [Dhan pricing](https://dhan.co/pricing/): current delivery brokerage, taxes,
  exchange charges and DP charges inform the explicitly conservative cash fee
  assumptions; historical broker contract notes would be stronger evidence.
* [Dhan RMS policy](https://dhan.co/risk-management-policy/) and
  [physical settlement policy](https://dhan.co/download-centre-pdf/physical-settlement-in-equity-derivatives.pdf):
  stock-option delivery margins and commodity tender/devolvement obligations
  mean premium or initial margin is not always the full capital requirement.

Sources checked 27 September 2026. No secondary site's return table is adopted
as this bot's backtest. No research source establishes guaranteed returns.

## Actual fallback probes

Four authenticated Dhan stock rolling requests for PREMIERENE, 27 March,
second monthly expiry, ATM through ATM+3, returned HTTP 200 with 324, 355,
281 and 363 minute records. At 09:27–09:29 the ATM strike is 920; ATM+3 is
950. The first unresolved Upstox candidate in that selection is 960, beyond
this documented range. No rolling series is spliced across strike changes
or silently treated as an exact held contract. The 920 call at 09:29 was
49.90 per unit, beyond the starting account's capacity for a 575-unit lot.

[Dhan's expired-option specification](https://dhanhq.co/docs/v2/expired-options-data/)
distinguishes up to ATM +/-10 for near-expiry index options from ATM +/-3
for other contracts. Both stock and index history are documented, but that
does not imply a full historical book for every affordable strike.

The MCX historical daily-margin page is indexed with the appropriate margin
fields, but the direct read of its English route returned HTTP 403 in this
runtime. No dated margin rows were obtained. Together with the rejected
Upstox commodity discovery request, that leaves the commodity replay
unscored despite Dhan returning real Gold Petal price history.
