# Full-text reading and replication notes

Updated 2026-09-29. This continues the earlier methods screening. Reading a
complete body does not reproduce its historical results. Page numbers below
refer to downloaded PDFs unless stated otherwise. Source files stay in the
private artifact directory; the coverage register records their hashes.

## S01 — MACD

All 7 pages read; equations on PDF pages 4–5 inspected visually. The above-zero
variant buys a bullish signal crossover with MACD positive and sells a bearish
crossover with MACD negative. The histogram variant uses three observed days,
not a future-confirmed turning point. Costs are explicitly omitted. Prose and
table trade counts disagree (including 153/1,536, 528/523 and 1,536/836).
Reported gross Sharpe ratios are modest. Retain a fixed baseline only.

## S02 — Technical strategies

All 16 PDF pages read, including tables A2–A4; plotted strategy examples on PDF
page 9 inspected visually. The 39.54% result is mean profitable-trade percentage,
not return. The same stock has different buy-and-hold results across strategy
tables: Maruti 11.85%, 17.26%, 14.34%; UPL 2.69%, -6.33%, -9.74%.
Different effective windows or benchmark construction need resolving before a
fair comparison; the reason is not established. Sun Pharma's SMA row also
reports winning trades alongside zero gross profit. Exact RSI/exit settings,
cost configuration and executable code remain unavailable. Use common dated
windows in any new replay; do not inherit the paper's ranking uncritically.

## S03 — Investment and trading strategies

All 15 pages read. The trading analysis explicitly measures recovery from the
full-period minimum. That minimum is not knowable at entry. Complete-history
selection and the historical availability of beta/debt-equity classifications
are additional concerns. Factor associations can motivate new hypotheses;
the reported bottom-to-recovery returns are not executable evidence.

## S04 — Option structures

All 15 pages read. Five authors, including Jishu Das. This is a descriptive
payoff survey, not a backtest. Table 2's short put at strike 350, premium 24 and
expiry spot 320 should lose 6, not gain 6. The bear-put prose describes a credit
and short call although its numerical spread example is a debit put spread.
The section labelled short butterfly describes buying the wings and selling
the middle, a long butterfly. A straddle needs movement beyond combined
premium to profit at expiry. Do not copy these examples into production maths.

## S05 — Calendar effects

All 12 pages read, including the otherwise unextracted appendix on PDF page 10,
which was rendered and inspected. The last-two/first-two trading-day rule is
observable. The sample is 1981–1995; costs and changed market structure matter.
The appendix has inconsistent standard-error typography: one two-sample
formula uses a difference of reciprocal sample sizes, whereas another uses
their sum. Its one-sample table aligns with the conventional standard error,
not a literal reading of the printed formula. Use validated statistical
functions rather than transcribing it. Calendar windows remain controls.

## L06 — Indian hedging demand and intraday momentum

All 18 pages read, including individual-stock appendix tables. The gamma
equation was inspected visually. Costs are explicitly excluded. The reported
portfolios use 44 selected liquid futures and substantial capital. Entry times,
lookbacks and gamma percentile filters are selected within the study. Dropping
whole days with very low volume is not a live filter unless eligibility is
formed from prior information. The displayed sum of positive option gammas and
OI does not explain negative net gamma; the position-sign convention remains
unresolved. Percentage changes of a negative baseline also need care. Plain
late-session direction merits replication; total OI cannot establish dealer
inventory or affordable option profitability.

## A25 — Betting against beta in India

All 22 pages read, including shrinkage derivation and six tables. Five-year
correlation and one-year volatility estimates feed monthly beta sorting; the
1993 data start precedes the 1998 factor-return start. The Bayesian own-beta
weight N/(40+N) is derived for shorter histories. The strategy levers low-beta
longs and shorts high-beta stocks. Reported factor returns are not returns on
a small whole-lot account: borrowing, short availability, margin and financing
must be reconstructed. Table 4's large-company subgroup has much weaker
statistical evidence than the full universe. Keep as a slower factor/control,
not evidence for expiry option multiplication. Figure captions/axes were read;
the plotted points have not been independently digitised.

## A27 — NIFTY variance risk premium strategy backtest

All 23 pages and all seven figures inspected. Public strategy, panel-builder,
figure code and reproduction notes recovered from author repository commit
`8b8589009806b0bdfb876c7005c9ee95a5f26924`. Static code inspection is not a rerun
of the missing historical panel. Several issues prevent accepting the paper's
strategy ranking or cost explanation without reconstruction:

- The reported average monthly cost is labelled percent of margin, but
  `compute_performance` averages raw cost in rupees per index unit. Figure code
  also treats this quantity as rupees. The units do not match the table label.
- The same function computes cumulative-path drawdown; the paper describes
  that field as a worst single-month result. Its running peak omits initial
  wealth, potentially missing a loss in the first observation.
- `get_expiry_settle` prefers positive settlement/close fields before computing
  intrinsic. Heuristics are not sufficient to distinguish an underlying-level
  settlement from an option payoff, or a stale option close from expiry value.
  The historical frequency of this problem has not been measured.
- Nearest-strike selection lacks the OI tie-break described in the paper and
  selects calls/puts separately. Fixed full-sample volatility and backward
  filling initial rates need point-in-time replacements.
- Delta hedge code uses the correct long combined delta against a short
  straddle; ambiguous prose alone is not evidence of a sign bug. However,
  fractional spot-proxy hedges do not reproduce executable futures lots.
- The author's reproduction notes report cumulative-return overflow. Those
  outputs cannot serve as a funded chronological bankroll ledger.
- Some payoff explanations mix expiry intrinsic and changing IV. With a put
  wing at 94% of initial spot and expiry spot at 90%, that long put pays 4%,
  not the stated 6% of initial spot.

No opposite profitable strategy follows from these errors. Rebuild dated
contract selection, settlement, capital and costs before interpreting results.
Never run the downloaded main program against local services: it contains
database writes. Isolated pure-function fixtures are the appropriate audit.

The isolated audit (`python3 -m research.literature.audit_vrp_functions`) ran:
30 synthetic 1% losses give a reported drawdown of 25.28% versus 26.03% when
initial wealth is included. A raw cost of 3 on margin of 3,000 returns a cost
field of 3, although the percentage is 0.1%. This proves the calculation/unit
issues, not their frequency or profit impact in the unavailable market panel.

## A28 — Anatomy of NIFTY volatility premium

All 53 pages read, including both appendices; all nine chart pages inspected
visually. The author explicitly presents descriptive research, not a strategy
backtest. The ex-post IV minus forward-RV series is an outcome label unavailable
at entry. Overlapping future windows can themselves create persistence; a
forecast needs lagged, fully matured labels and purged validation.

Several interpretation and consistency problems require reconstruction:

- Close-to-close returns **include** overnight moves; they do not isolate
  intraday ranges or overnight components. The repeated claim that they omit
  overnight gaps is incorrect: log(C/Cprev) = log(O/Cprev) + log(C/O).
- Marginal density overlap does not measure the probability that contemporaneous
  IV exceeds future RV, nor the fraction of exploitable trades. Correlation is
  not a percentage of shared movement or a measure of independence.
- The quantity called VRP here is a volatility spread, not a variance spread.
  Adding overlapping annualised volatility spreads is not compounded profit.
- The claimed tenor alternates between 7-day forward RV and a 21-day window.
  Charts A1/A4/A9 display close-to-close figures while nearby prose presents
  revised Yang–Zhang figures. Chart A7, its table and appendix cost numbers
  disagree; Q3's median net edge even changes sign between tables.
- The cost conversion lacks a complete executable straddle/hedging ledger and
  consistent lot-count/vega scaling. A positive ex-post spread does not guarantee
  an option trade profits after costs.
- Failing to reject a structural break does not prove stable parameters or
  localise a change to the mean. AR(1) intercept and long-run mean are conflated.
  The worked 21-day decay is about 99.4% of the excess, not 75%.

Retain estimator comparison as a research diagnostic. Recompute matched
maturities, past-only regimes and dated rupee costs before any trading use.

## A29 — Market intraday momentum

All 48 pages of the June 2017 author manuscript read, including 13 tables and
visual inspection of the three figures. This is the SSRN revision, not a
byte-identical copy of the final journal article. The separate 14-page internet
appendix at https://guofuzhou.github.io/Appendix_IntraDay.pdf was also read in
full through the web reader. Its binary was not downloaded: shell networking
became restricted during this session. No local hash is claimed for it.

The plain rule is unusually reproducible: previous close to first-half-hour
return predicts the final half-hour; a second version requires agreement with
the preceding half-hour. Recursive forecasts use prior observations. However,
the joint rule's 77.05% success rate includes zero-return no-trade days, so it is
not a 77% winning-trade rate. Cost tests use entry bid/ask and a closing auction
price, omit commissions, and concern US ETFs. Annualised returns computed on
event-only days are not the calendar-year bankroll return of trading only those
events. Full-year volume ranks, end-of-day institutional imbalance and eventual
recession classifications belong to explanatory analysis, not available live
filters. ETF selection also uses full-sample volume. Replicate the simple price
signals with locally executable exits and all costs; do not port US cost or
auction assumptions to Dhan options.

The appendix's late-informed-investor model generates positive intraday
covariance under parameter restrictions, including sufficiently small liquidity
noise. It is a possible mechanism, not a universal direction guarantee. Its
bid-to-bid, ask-to-ask and midpoint regressions help test microstructure
explanations, but do not demonstrate executable ask-to-bid profits. Alternative
window and conditioning tables add trial choices that a new comparison must
count. Mean-variance portfolio utility improvements are not whole-lot option
bankroll returns. Appendix formula text was read; the web screenshot service
could not render it for separate visual verification.

## A30 — Momentum anomaly in India

All 18 pages read, including nine tables and references. The stated rule uses
past 3/6/9/12-month rankings and equally weighted winner-minus-loser portfolios.
The exceptionally large reported monthly spreads need raw-data reproduction:
3/3 is 25.23%, while 6/6 is 17.77%; a subsequent prose comparison mistakenly
attributes 25.23% to 6/6. Table VII spread entries do not equal the displayed
winner-minus-loser entries (e.g. 11.90 minus -12.10 is 24.00, not 23.34).
The magnitude alone does not prove look-ahead or an error in the underlying
returns, but the exact overlapping-portfolio calculation, point-in-time
constituents, inference and costs are not sufficiently recoverable from prose.
Authors explicitly acknowledge short-sale constraints. Retain a fixed causal
momentum comparator; do not budget from these extraordinary reported spreads.

## L18 — Deflated Sharpe ratio

All 22 pages of the July 31, 2014 author manuscript read, including proofs,
appendices and exhibits. Formula pages 7–10, 12 and 14 and all exhibit pages
16–20 were inspected visually. The published numerical example was independently
recomputed with the standard-library normal distribution: DSR 0.900397 for
100 independent trials, 0.950502 for 46, and 0.950491 for 88 with Gaussian
moments. All match the paper's rounding. See `dsr_example_audit.json` and run
`python3 -m research.literature.audit_dsr_example`.

Use unannualised Sharpe and matching variance units, Pearson kurtosis (normal
equals 3), and all disclosed trials. Correlated variants are not independent
strategies; the average-correlation effective-trial formula is a heuristic with
explicit caveats for negative correlation, short samples and nonlinear
redundancy. Estimated moments, serial dependence and tail stability need separate
attention. This calculation cannot repair an invalid fill or look-ahead and is
not a posterior probability of live profitability. Repeatedly inspected holdouts
are no longer untouched. The paper's secretary-problem stopping analogy is not
a universal deployment rule. Our arithmetic reproduction uses synthetic stated
inputs, not a new historical trading result.

## L10 — Indian post-earnings-announcement drift

All 18 pages read, including references and tables; equation 4 on PDF page 6
visually checked. The square root in its standard error is present in the PDF
but lost in text extraction, so it is not an arithmetic error. Earnings surprise
is year-over-year EPS change divided by a pre-announcement price. The outcome
is stock buy-and-hold return minus the market over days +2 through +64.
The reported extreme-decile difference is 4.8 percentage points; the roughly
6-point regression slope is a fitted rank-extreme difference, not a funded
account return or an intraday option result.

Selection uses Nifty 500 membership as of March 2014 for a 2002–2017 study.
Future-window nonzero-return requirements and trimming outcome extremes cannot
be entry filters. Quarterly cross-sectional earnings ranks require careful
asynchronous announcement handling: an early reporter cannot know later
reporters' results. Lagged financial controls are a useful precaution but do not
resolve those other timing issues. Table 1 labels P1 minus P10 while displaying
the opposite sign. No executable spread, tax, short-borrow, option decay or
capital ledger is supplied. Retain a separately specified, delayed earnings
cash-stock candidate with point-in-time ranks; this paper does not establish the
previous intraday EVENT_CONTINUATION rule.

## L12 — APAC intraday momentum replication

All 13 pages read, including the preregistration pitch and six tables; Table 2
was visually checked. This is meaningful contrary evidence to universal intraday
momentum: China and Japan show the first-to-last-half-hour association, Korea
is weaker, and Hong Kong/Singapore do not show it over the full sample. COVID
subsamples differ again and are only about a month long. India is not included.
Recursive forecast comparisons use past estimates, but the whole-day trade-count
exclusion and full-year volume/full-sample volatility terciles must not become
live gates. Calendar changes and sparse prints are material across markets.

This is return-prediction evidence, without a complete net executable strategy
ledger. Higher R-squared is not higher profit or evidence of independent inputs.
The printed Singapore in-sample R-squared row (0.157, -0.032, 0.152) is inconsistent
with ordinary same-sample OLS-with-intercept R-squared: it needs source/code
reconciliation rather than silent correction. Exact numerical replication is
pending. Preserve the negative markets and prespecified sample changes when
comparing with the original US study.

## L17 — Probability of backtest overfitting

All 44 pages of the November 27, 2014 manuscript read, including code snippets,
all 14 figures and the simulation table. Core method: align every candidate's
return series to the same dates, split into equal contiguous blocks, select the
best candidate in each half-block combination, and measure its rank in the
complement. This diagnoses the selection procedure; it is not a chronological
trade simulation, a conventional p-value, or a probability of live ruin.

Important conditions and corrections for implementation:

- A low PBO can coexist with losses; high PBO can coexist with many similarly
  profitable candidates. Report net performance separately.
- Keep genuine alternatives; neither hide losing trials nor pad the comparison
  with deliberately bad ones. Guided-search outputs versus intermediate trials
  need a declared procedure. Do not optimise parameters to minimise PBO.
- Block size must respect dependence. Combinatorial folds overlap: thousands of
  folds are not thousands of independent histories, so a binomial confidence
  interval using the raw fold count is not justified without further analysis.
- Their zero-Sharpe simulation recentres each entire path. The near-100% PBO in
  that experiment is conditional on that constraint, not a universal null
  expectation for independently drawn future returns.
- 16 choose 8 equals 12,870, not the manuscript's 12,780. A uniform variable's
  logit is logistic, not standard normal. Rank-median and tie conventions should
  be explicit; the early N/2 notation differs from the later rank/(N+1) rule.
- A figure prints 0.04 probability (4%) where nearby prose says 0.04%. These are
  transcription issues, not evidence that the whole framework is unusable.

No reshuffling repairs missing costs, future-informed labels, historical broker
restrictions or whole-lot bankroll path dependence. Keep causal chronological
validation alongside this diagnostic. The manuscript's broad criticism of
holdout should not be read as permission to discard an untouched future test.
The simulation table and EVT derivation were inspected, not fully numerically
reproduced; only L18's stated arithmetic example was replicated this session.

## L09 — Four-factor model in Indian equities

All 22 pages of the original September 2013 working paper read, including all
tables, the size-distribution figure and the displayed return formula. This is
a comparatively explicit factor construction: at the end of month t, momentum
ranks the eleven-month return ending at t-1, skips month t, and holds during
t+1. Monthly value-weighted winner/loser portfolios are intersected with size;
the largest 10% of eligible companies form the big group. Value portfolios use
September formation with a six-month lag for March financial statements.

The prior-twelve-month 50-trading-day eligibility rule is causal, although it
does not establish executable liquidity. The paper identifies thousands of
companies that stop trading and supplies an explicit distressed-delisting
adjustment. Its one-year confirmation of a delisting is retrospective; revised
factor histories must not masquerade as contemporaneously available signals.
The conditional exclusion of book-value data also changes the factor universe.

Tables 5–6 report annual logarithmic returns. The cumulative momentum figure
of 414.2 is log-return units, not a 414.2% funded account gain. Differences of
portfolio log returns are not directly a self-financing long-short cash ledger
either. The paper itself acknowledges momentum's greater turnover. Borrowing,
dated costs, whole lots and margin remain unmodelled. Retain this transparent
momentum definition as a benchmark and distinguish a long-only cash adaptation
from replication of the published long-short factor.

## L15 — Conditional commodity-futures momentum

All 32 pages read, including four figures, formulas and tables. The study uses
13 selected MCX contracts, June 2006–April 2017, and 24 ranking/holding-period
combinations. Winners and losers are positive- and negative-past-return groups,
not conventional cross-sectional quantiles. Alternative rolls use distant
contracts or a midmonth roll. Only a few selected combinations are significant,
and much of the positive performance occurs in the earliest subperiod.

Replication problems must be settled before accepting the reported magnitudes:

- The overlapping-portfolio description sums six winner returns but averages
  six loser returns. Portfolio weights and the holding-period/monthly return
  denominator need code-level reconciliation.
- Log-return inputs and the displayed one-plus-return wealth recursion need
  consistent conversion. The reported monthly and annual figures cannot be
  equated without the compounding convention and dated return series.
- Continuous-contract splice changes are not trading profits. Reconstruct the
  actual bought/sold contracts, rolls and variation margin.
- Table 3's eighteen-month alternative-roll Sharpe entries repeat its t-statistics
  (7.11 and -1.45); the displayed means/standard deviations imply about 0.715 and
  -0.146. This was checked against the PDF image.
- Table 6's turnover units and cost-adjusted returns need a dated calculation;
  the displayed aggregate numbers do not provide enough information to reconcile
  them. Its borrowed cost assumptions are not dated Indian retail charges.

Concurrent positions in thirteen futures require capital and margin absent from
the small-account claim. Gold Petal alone is not this portfolio. Keep commodity
trend as a distinct hypothesis; do not transfer these published returns into our
bankroll simulation.

## L11 — Technical rules across Indian market cycles

All 23 pages read, including references, seven tables and the nine-panel market
cycle figure. RSI/MACD formulas on PDF pages 9–10 were inspected visually.
Signals use completed-day inputs and next-day open-to-close returns, a useful
timing distinction. However, the displayed RSI averages closing-price levels
on up/down days instead of standard price gains/losses. Its sell condition is
an upward crossing of 70. MACD uses a nine-day simple signal average and
level conditions rather than a crossover; the displayed EMA summation is also
ambiguous. These results cannot reject all conventional RSI/MACD strategies.

The return tables need reconciliation. Table 3's full-sample within-sample sum
of squares is (4545-1) × 0.00576² = 0.150759. Table 6's disjoint buy/sell
subsets alone imply (858-1) × 0.017908² + (1522-1) × 0.010686² = 0.448521.
That exceeds the total before adding between-group variation or other days,
which is impossible under the stated same-series daily-return construction.
The sell sign reversal does not change its within-group variance. The prose
also moves the decimal in the overall sell mean relative to the table.

Cycle labels are retrospective, not an observable regime switch. Modified
Sharpe is computed on selected signal returns with a zero risk-free rate;
Sharpe below one is not by itself evidence of no economic edge. A comparison
against an unconditional mean containing the selected observations is not an
independent-samples comparison. Bootstrap details and serial dependence need
replication. Gross index prices, without executable contracts, costs or a
chronological capital ledger, do not establish small-account profits.

## L13 — Information in algorithmic versus non-algorithmic option flow

All 34 pages read, including eleven tables, four figures and references.
Figures and the final regression specification/tables were visually checked.
This uses NSE order/trade data from 2009–August 2013 with actual initiator,
algorithmic and investor-category flags. Delta-weighted buyer-initiated minus
seller-initiated contracts is not open interest, total volume or a premium/OI
quadrant. Historical broker candles cannot reproduce the paper's signal.

The direction-learning explanation is supported primarily for non-algorithmic
subgroups. However, equation 3 regresses current buying pressure on past,
contemporaneous and future index returns. It is an explanatory lead/lag test,
not a fitted forecast available at decision time or an out-of-sample trading
ledger. A significant association does not establish absence of all noise or
profits after spreads. Delta classification's stated closing-price inputs must
also be timestamped before any intraday implementation.

Five total-investor rows in Tables 10 and 11 repeat all printed coefficients
despite different AT/non-AT headings (ATM/OTM calls and all three put groups).
The paper acknowledges significant aggregate AT exceptions while broadly
concluding no AT predictability. Resolve the aggregation/table construction
before adopting that strong interpretation. This observation does not prove
misconduct or invalidate every subgroup estimate.

Practical consequence: a public-feed signed-flow proxy would be a new candidate,
with measured trade-classification errors and its own chronological validation.
The historical sample's monthly-expiry structure cannot be assumed to describe
today's weekly-expiry microstructure. No participant flags or live order-book
history have been fabricated to bridge the data gap.

## L14 — NSE student project on CNX 100 momentum

All 31 pages read, including the portfolio membership annexures, methodology
matrices, formulas and seven charts. The four configurations are 3×3, 3×6,
3×12 and 6×12 months. At each formation date the study buys equal-weight top
decile stocks and shorts the bottom decile; it averages overlapping portfolios'
log returns by holding age. These averages are not a chronological bankroll
curve with cash allocated across simultaneous vintages.

The universe is the union of membership over the entire study, and the method
explicitly excludes stocks delisted during the future holding period. Both
need point-in-time reconstruction. The supplied winner/loser lists aid checking
selection, but do not remove that bias. Formation-date and example return
indices contain inconsistent labels and require reconciliation against raw data.

The 6×12 average cumulative spread rises to 3.88 log percentage points at
month six, then falls to about 1.11 at twelve months. Choosing six months after
seeing that peak is an additional tested choice. The claim of positive averages
at each holding age does not establish profits in every market regime or every
individual trade. Equal long/short notionals do not ensure beta neutrality;
zero market beta would not mean risk-free in any case.

The implementation section acknowledges trading costs, price impact, stock
borrowing/recall and futures rolls, but the reported calculations assume zero
costs. The stated similarity of average betas does not eliminate other risk
explanations. Prefer L09's more explicit benchmark construction for a causal
cash-stock comparator; this report supplies neither an intraday option rule
nor a funded small-account result.


## L07 — Global futures hedging and intraday momentum

All 27 pages read, including appendices A–D, references, six figures and
visually checked formulas/tables. The study covers 62 futures (1974–May 2020),
with no Indian market. Its simple baseline uses the return from previous close
until 30 minutes before the underlying market closes to select the final
half-hour direction. Recursive forecasts require 500 earlier observations.
The simple sign rule and estimated forecast are separate strategies.

The equal-weight equity-futures portfolio reports a 6.86% gross annual return
and 1.73 Sharpe ratio, not an option-premium multiple. Main results explicitly
exclude transaction costs. A one-tick E-mini illustration for advanced investors
is not an Indian retail fee/fill model. There are contract and subperiod
exceptions, including negative crude-oil out-of-sample R-squared and weak recent
currency results. Later reversal over one to three days does not establish an
overnight continuation strategy.

Signed gamma assumes market makers hold calls and short puts; actual OTC and
end-user positions are unavailable. Table 7 explicitly uses lagged NGE, so it
would be incorrect to label the whole gamma analysis contemporaneous leakage.
Resolve differing time indices in Table 8's description before replication.
First-difference regressions called difference-in-difference here do not by
themselves establish treatment/control causality. Hedging remains a plausible
mechanism, not a measured counterparty signal from public OI alone.

Roll decisions based on daily volume, whole-day activity exclusions, trading
hours chosen from volume plots and jump-day full-sample percentiles need causal
availability treatment. Negative prices are removed: this matters for commodity
sample coverage. The published appendix D2 commodity block exactly repeats D1's
coefficients, t-statistics and R-squared values despite different subperiods;
visually confirmed on PDF pages 25–26. Seek clarification rather than treating
those repeated rows as independent robustness evidence.

Practical consequence: retain a fixed previous-close-to-entry direction rule
as a separate late-session comparator. Do not transfer diversified futures
Sharpe ratios, dealer-position assumptions or full-sample market filters to a
small-account expiry-option strategy. Raw historical results have not been
independently reproduced.


## L08 — International intraday time-series momentum

All 64 pages of the accepted manuscript read, including appendices A–C,
15 tables and three figures. India is absent from the 16 developed-market
sample (2005–2017). The baseline uses previous-close-to-first-half-hour sign
for a final-half-hour index position. Actual index returns, translated into
USD, are not a broker-executable ETF/futures/options portfolio. No complete
local commission, spread, impact, financing and lot model is supplied.

The recursive forecast starts after five years: only five of 16 unrestricted
out-of-sample R-squared values are positive; ten are positive after constraints
that include clipping negative forecasts. A significant Clark–West adjusted
statistic does not change a negative unadjusted R-squared into lower observed
forecast error. This constrained forecast also differs from the long/short
sign strategy. Canada loses in Table 5 despite the prose's broad positive-return
claim. Always-long beats the sign rule in several markets. Positive annualized
skew and kurtosis near three are rescaled under an IID assumption (appendix A),
not evidence that daily tails are normal or crash risk is low.

The cross-market regression correctly lags the US signal for Asia-Pacific.
Keep that convention in any implementation; Type 3's abbreviated prose alone
is insufficient. Prior-day covariance-based portfolio weights can be causal,
but same-calendar-day global first-half-hour rankings and the TVC net-position
factor cannot all be available before Asia-Pacific's close. These explanatory
sorts require timezone-aware reconstruction. Do not apply this criticism to
all individual-market strategies. The global portfolio has 18 variants and
unequal evaluation periods (full-sample equal/value weights versus post-2010
estimated weights); compare them on common periods before selecting a winner.

Equation 17's printed net position uses counts times two, omitting the /16
normalization used by its worked dollar example. The TVC is an explanatory
component, not automatically a tradeable global factor. Table 10 differs from
its body description: actual panels are spread, volatility, information
discreteness and individualism, without the described TVC panels. The spread
returns 2.67/3.33/3.23 do not show the claimed monotonic near-doubling, and the
spread Sharpe ratios 1.02/1.09/0.91 do not support that claimed trend. Visually
confirmed on PDF page 59. Clarify manuscript/version inconsistency before
copying a liquidity-conditioning rule.

Practical consequence: retain the fixed local opening-sign comparator and an
always-long control. Information-continuity is a separately registered possible
extension, not a validated filter. Do not use global same-day ranks, ex-post
recession labels, annualized tail statistics or synthetic index fills to
justify a funded Indian expiry-option strategy.
