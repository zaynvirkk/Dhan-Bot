# Indian trading literature: first evidence review

28 September 2026. **Active and incomplete. No strategy approved for funded trading.**

The eight supplied links resolve to five distinct papers plus a Scholar search.
All five papers were obtained and their methods/results reviewed. The register
currently contains 30 studies: 15 with methods/results reviewed, three with
partial body review, and 12 screened from abstracts only. Eighteen full texts are
stored privately with retrieval hashes. An unrelated PDF found during discovery
is explicitly excluded. This is not an exhaustive literature review, a claim
that every appendix was audited, or a new backtest result.

[Paper register](papers.json) · [Next work](QUEUE.md) ·
[Candidate specifications](CANDIDATES.md) · [Data mapping](API_INPUTS.md) ·
[Search log](SEARCH_LOG.json) · [Scope and protocol](PROTOCOL.md)

## What the supplied papers establish

| Paper | Useful finding | Consequence for our research |
|---|---|---|
| S01: MACD optimization | Reports gross results; explicitly excludes transaction costs. | A baseline to reproduce, not proof of a net option edge. |
| S02: Technical strategies | Hourly BB/RSI outperforms the comparison in several stocks during its short sample. | Recover exact settings, then test cash execution across other regimes. |
| S03: Investment/trading strategies | Measures recovery from minima identified over the study period. | Those return figures use future-dependent entry selection. They cannot be credited to a live rule. |
| S04: Option strategies | Describes spreads and option payoffs. | A payoff diagram does not estimate how often a trade wins after its premium and costs. |
| S05: Calendar strategy | Documents historical turn-of-month effects. | Keep a fixed calendar benchmark; do not infer a present-day expiry-options edge. |

Source identities, primary URLs and precise reading locations are in S01–S05
of the register. ResearchGate and Academia copies of S02 are one paper, as are
the two IJNRD links. The Ashraf paper's actual coauthor is Baig; search URL slugs
are not authoritative metadata.

## Findings that change the next experiment

**Late-day continuation deserves a clean, inexpensive test.** The international
hedging paper supplies a simple direction rule and a plausible mechanism, while
the Indian adaptation supplies local minute-data evidence. Neither establishes
net retail profitability. The international paper excludes costs from its main
results; the Indian authors also report gross results and describe difficulty
monetizing the close. Start with fixed price-only rules, actual session hours and
observable fills. [Baltussen et al.](https://academicweb.nd.edu/~zda/intramom.pdf),
[Motwani et al.](https://www.researchgate.net/publication/383567351_Hedging_Demand_and_Intraday_Momentum_within_the_Indian_Stock_Market)

**Do not copy the Indian gamma filter as written.** PDF page 7 was visually
checked: both call and put exposure equations are added without an explicit
negative position term, yet the selection rule requires negative exposure.
With ordinary unsigned vanilla gamma, positive OI/lot size/spot cannot produce
that result. This could be an omitted convention or formula error; it remains
unresolved. The international source explicitly signs put exposure negatively
under its market-maker inventory assumption. Public aggregate OI does not
identify the actual inventory side. We may test an explicitly assumed proxy,
but must label it as such and include a price-only comparator. [Indian formula](https://www.researchgate.net/publication/383567351_Hedging_Demand_and_Intraday_Momentum_within_the_Indian_Stock_Market),
[original equations 14–15](https://academicweb.nd.edu/~zda/intramom.pdf)

**Do not count correlated papers as independent Indian replications.** The
16-market developed-market study excludes India; the APAC replication studies
five other markets and finds heterogeneous results. Their evidence motivates a
test here but cannot qualify it. [Li et al.](https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf),
[Limkriangkrai et al.](https://researchmgt.monash.edu/ws/portalfiles/portal/519509174/494419119_oa.pdf)

**Slower effects belong in the comparison.** Indian cross-sectional momentum
and earnings drift have more relevant historical evidence than guessing which
cheap option will multiply. Their horizons and capital structures differ from
expiry buying. A cash implementation should be tested independently; monthly
winner-minus-loser returns cannot be multiplied by the account balance without
shorting, financing and portfolio accounting. [IIMA factor construction](https://faculty.iima.ac.in/iffm/legacy/four-factors-India-90s-onwards-IIM-WP-Version-original-Sep13.pdf),
[earnings drift](https://file.scirp.org/pdf/TEL_2018102515432009.pdf)

**Positive and negative technical studies need equal scrutiny.** The long Sensex
study is contrary evidence, but its displayed RSI calculation and MACD
conditions differ from common implementations. It does not invalidate every
RSI or momentum strategy. Likewise, the short BB/RSI study does not establish
robust profitability. [Muruganandan](https://reference-global.com/article/10.4038/cbj.v11i1.56),
[Tadas et al.](https://www.businessperspectives.org/images/pdf/applications/publishing/templates/article/assets/17910/IMFI_2023_02_Tadas.pdf)

**Newer options papers are leads, not winners.** The current FPI-position paper
is unavailable for download; its abstract itself says the conditional fit does
not improve its point-in-time forecasting loss. The short-volatility paper
needs a full audit of dated costs, collateral and tail losses before its return
claims are usable. [Vatsa](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6781558),
[Pillai](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6876580)

## Execution and inference requirements

These are our implementation decisions, not claims that the reviewed authors
used them:

- Freeze signal, universe, tie-breaking, order policy and costs before seeing
  new outcomes. A known-close signal cannot fill at that same close by default.
- Use all qualifying cases. Future highs, future volume, later delisting,
  quarterly announcement ranks and retrospective regime labels cannot choose
  which orders are submitted.
- Separate `NO_SIGNAL`, `UNAFFORDABLE`, `KNOWN_UNFILLED` and `UNKNOWN_EXECUTION`.
  Missing observations never become successful avoidance of a losing trade.
- Compare cash long/short, long calls/puts, spreads and futures only when each
  has a feasible dated funding model. A signal's direction and its instrument
  choice are separate hypotheses.
- A bar backtest supports a declared scenario, not an exact fill. Minute data
  cannot prove 1-, 3- or 5-second execution, queue priority or signed participant
  flow. Tick/book observations still require latency and cancellation modeling.
- Keep the whole search history. A paper chosen after screening many papers is
  also a selection decision. Reused December 2025–September 2026 data remain
  exploratory; calling the next rerun a holdout would be false.
- Evaluate terminal bankroll, drawdown, unaffordable signals, ruin and costs;
  report uncertainty and dependence, not only the largest multiplier. Ninety
  days is a minimum requested duration, not enough independent expiries to
  establish every rare-event hypothesis.

The overfitting papers motivate search-aware assessment, but a statistical
correction cannot repair bad timestamps or nonexistent fills.
[PBO framework](https://www.carmamaths.org/resources/jon/backtest2.pdf),
[Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)

## Current decision

The review adds testable mechanisms and removes misleading evidence. It does
not produce a new bankroll figure or a final live strategy. The immediate
research priority is a fixed-rule cash-versus-option comparison for intraday
continuation, followed by momentum/earnings implementations over longer
histories. Access-limited pairs, volatility and order-flow studies remain open.
The existing unsuccessful tests remain recorded; none is erased or reclassified
as an untouched holdout.
