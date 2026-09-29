# Mechanism review for the INR 9,411.18 account

Reviewed 26–27 September 2026. Rank a strategy on realizable **net** bankroll
growth, calendar time to doubling, loss of trading capacity and evidence beyond
the discovery sample. Maximizing the best observed multiple alone selects
hindsight and exposure to rare outcomes; it is not a tradable decision rule.

| Economic strategy family | Source of possible returns | Result for this account and this search |
|---|---|---|
| Directional long calls/puts: trend, breakout, reversal, OI, skew, basis, flow | Predict a move large enough to overcome premium decay and costs | Earlier 80 NIFTY variants lack a repeatable qualifier across two 90-day windows. Options remain affordable selectively; that alone supplies no signal. |
| Overnight/intraday company-event continuation | Incomplete public-information repricing | Existing two 90-day event replays do not qualify; one loses and the other stops with unresolved exposure. Original handpicked winners do not overturn this. |
| Expiry long gamma: straddles/strangles | Large realized movement relative to paid premium | Eight new late-session/volatility variants, 112 scenarios, two 90-day windows. No same scenario grows cash in both. Exact results are in REPORT.md. |
| Scheduled-event long volatility | Implied move understates conditional event distribution | Distinct from the unconditional pair test. Full timestamped calendar, prior-only event sample and IV-crush outcomes have not been replayed across all events. Unproven, not eliminated by an empty narrow test. |
| Short straddles/strangles, credit spreads, condors/iron flies | Sell insurance and bear volatility/jump risk | Current sampled short-call margin about INR 170k; narrow credit spreads INR 36.9k–39.7k; iron fly INR 73.6k. Not affordable at this balance. Credit is not a free return and a hedge's payoff limit is not its broker margin. |
| Debit spreads and long butterflies | Cap payout in exchange for cheaper economic exposure | Sample debit spread requires INR 37.9k; butterfly INR 72.5k. A low net debit does not establish a fundable short leg. These examples do not prove all possible spreads unaffordable. |
| Calendar/diagonal spreads, term structure, skew relative value | Relative option pricing and volatility changes | Sample calendar INR 58.0k margin. Needs simultaneous prices, short-leg margin paths and roll/legging costs; no validated INR 9k deployment. |
| Covered calls/collars and cash-secured puts | Equity exposure with option overlay/insurance premium | Capital in the underlying or cash collateral plus derivative lots; incompatible with the intended rapid small-bankroll multiplication. No new account backtest claimed. |
| Futures momentum/carry | Persistent trends or a risk premium | NIFTY/Bank NIFTY current one-lot margin INR 170.5k/189.1k. Published diversified futures momentum research is materially different from minute-level all-in expiry buying. |
| Cash-futures arbitrage, conversions/reversals and boxes | Basis/financing discrepancy after all legs | Need funding, shorts, synchronized executable quotes and fees. NSE's arbitrage benchmark illustrates a low-volatility financing/carry exposure, not repeated short-horizon doubles. |
| Pairs, sector lag, cross-market lead/lag, dispersion | Relative mispricing, economic exposure or correlation pricing | Requires prior-estimated relations, both-leg execution and sufficient portfolio margin. Earlier bounded lag cases do not validate the broad family; full 90-day universe tests remain incomplete. |
| Index rebalance, OFS/block supply, auction residual | Pre-announced flows or temporary auction dislocation | Direction need not follow the advertised flow. Time-stamped event terms and historical auction observations/books remain necessary; end-of-auction summaries cannot supply the signal trajectory. No winner credited. |
| Commodity futures and options | Trends, inventory/macro shocks, volatility pricing | Current Gold Petal one-lot margin INR 1,415 is affordable. Gold Ten, crude mini, gas mini and silver micro examples exceed INR 9k. Gold Petal is an affordability exception, **not a tested edge**; commodity activation, historical margin/rolls and a full strategy replay are not established here. |
| Currency futures/options and FX carry | Currency trend/carry or relative pricing | Dhan currently states that currency trading was discontinued from July 2024. It is not an execution route under the chosen funded-broker architecture. |
| Market making, very fast book/auction arbitrage | Spread capture and queue/information advantage | Live depth access is useful, but existing minute history cannot prove queue position, cancelled liquidity or subsecond fills. No latency or execution edge established. |

The scope distinguishes **tested and losing**, **no qualifying trades**,
**current capital infeasibility**, and **not fully tested**. None of the latter
three is silently scored as a profitable INR 9,411 no-trade bot.

## Primary evidence checked

- [Dhan funds/margin documentation](https://dhanhq.co/docs/v2/funds/) explicitly
  describes indicative current-session margins. The separate capital.json and
  private request receipts contain the actual authenticated account checks.
- [Dhan official SDK margin request](https://raw.githubusercontent.com/dhan-oss/DhanHQ-py/main/src/dhanhq/_funds.py)
  supplies the multi-leg schema where the web documentation is inconsistent.
- [NSE circular FAOP74467](https://nsearchives.nseindia.com/content/circulars/FAOP74467.zip)
  was downloaded and its PDF inspected: derivatives close at 15:40 from
  3 August 2026. This is why the new post-change liquidation starts at 15:35.
- [Dhan RMS policy](https://dhan.co/risk-management-policy/) distinguishes
  broker restrictions, delivery/tender margins and commodity devolvement.
  A pure premium-paid stock-option simulation cannot replace these checks.
- [Dhan currency support](https://dhan.co/support/account-related/activate-my-f-and-o/how-can-i-activate-currency-trading-on-my-account/)
  states currency trading is discontinued. This is a broker eligibility fact,
  not an assertion about profitability of currencies elsewhere.
- [NSE Nifty 50 Arbitrage factsheet, dated 29 May 2026](https://niftyindices.com/Factsheet/Factsheet_Nifty_50_Arbitrage_Index.pdf)
  reports 6.63% over one year and 6.31% five-year CAGR for its price-return
  benchmark. These are benchmark figures, not this account's attainable net
  returns. [Its methodology](https://www.niftyindices.com/methodology/method_nifty_50_arbitrage.pdf)
  combines equity, offsetting futures, debt and cash.
- [Moskowitz, Ooi and Pedersen, Time Series Momentum](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum)
  studies 58 futures/forward markets over more than 25 years; its medium-term,
  diversified evidence cannot be transplanted into this small expiry bot.
- [Cboe strategy index descriptions](https://www.cboe.com/us/index_income/)
  document covered-call and cash-secured-put exposures. They provide useful
  definitions and benchmarks, not an executable NIFTY strategy recommendation.
- [NIFTY VRP supplementary research](https://zenodo.org/records/22167522)
  documents expiry alignment and past-only volatility forecasts, but does not
  distribute the licensed underlying data. The existence of a research pipeline
  is not a replicated profit receipt; no numerical result is adopted here.

The relevant alternative to speculative long options is often compensated
risk-taking (volatility selling, carry, diversified trend), not a guaranteed
mispricing. Those approaches have different capital and time requirements.
There is no supported basis here to present any as a fast all-in replacement.

## Decision

Do not arm the funded bot on this evidence. Stop this bounded search without
crowning a narrative winner or spending on deployment. This is a concrete
decision about the **INR 9,411 rapid-multiplication mandate**, not a claim that
all F&O strategies are worthless. Additional capital would expand feasibility;
it would not turn these failed or unvalidated signals into profitable ones.
