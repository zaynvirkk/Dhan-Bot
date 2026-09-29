# Dhan strategy research — current results

**29 September: operator ended literature work; index-options API/build audit.**
The saved 27 September Dhan master contains ten equity-index option families
plus MCXBULLDEX. Added dynamic inventory parsing and fixed the production FULL
packet size/depth offset against the official SDK; retained OI, volume and trade
statistics with each book. Current tests: 270 pass, six socket tests blocked by
this runtime. Fresh broker reads are UNKNOWN because DNS fails here. No orders
or deployment. Live routing remains NIFTY CAS; this is not the rebound strategy.
[API audit and catalogue](../docs/INDEX-OPTIONS-API-AUDIT.md).

The literature counts below are a historical 28 September checkpoint; further
full-text notes were saved before the operator ended that work.

**28 September: academic review reopened at the operator's request; incomplete.**
Resolved the eight supplied links into five distinct seed papers and a Scholar
search. All five seed bodies obtained and reviewed. The deduplicated register
now has 30 studies: 15 methods/results reviews, three partial bodies and 12
abstract-only entries; 18 included PDFs preserved privately. Reviewed timing,
costs, selection bias and capital requirements, including the future-selected
bottoms in the Ashraf/Baig trading analysis and an unresolved signed-gamma
formula in the Indian intraday study. Identified fixed intraday cash direction,
hourly BB/RSI, longer momentum and earnings-drift comparisons, with explicit
specification/data gaps. No new return claims or deployment approval.

Current documentation review also corrects the old source map: Upstox now
documents news and fundamentals, but news has a seven-day lookback; Dhan's
detailed rolling-strike scope is narrower for non-near-expiry-index contracts.
These are schema checks, not fresh authenticated broker calls. Verified hashes
for 19 retained source files, including 18 PDFs; no orders, spending, cloud or
production changes. The broader review and citation tracing remain active.
[Review](literature/REVIEW.md), [paper register](literature/papers.json),
[remaining work](literature/QUEUE.md), [data mapping](literature/API_INPUTS.md).

**28 September: order-policy, put/call and capital expansion completed within
its stated scope.** Eight signal rules × three allocations × seven execution
scenarios × three reused 90-day windows = 504 attempted paths. Resting-limit
fills no longer reject an entire minute because its high exceeded the cap.
SELLOFF_CALL at 95% ends INR 8,453.62 / 7,743.70 / 14,615.88 from INR 9,411.18;
SELLOFF_PUT ends 3,744.00 / 7,586.71 / 5,060.64. No rule/allocation profits
in all three base windows. Sixty-nine strict paths remain UNKNOWN. These are
exploratory scenarios, not actual fills or 504 independent strategies.

Forty-six current broker margin probes cover six index futures, ten lowest
quoted-notional stock futures (from 210 quoted), six commodity futures and
24 narrow index verticals. Only sampled Gold Petal fits (INR 1,415.1875);
sampled spreads start INR 33,594. This does not eliminate all spreads. Ten
subsequent cash 4x probes succeed: long/short RELIANCE, HDFCBANK, SBIN, INFY
and TCS require INR 7,356–7,503.12 each, fitting current cash. Earlier lookup
and authentication failures remain recorded. This establishes current broker
affordability, not historical margin or a profitable cash strategy.
Software tests: 260 pass. No orders, account spending or cloud changes.
[Full results](results/execution_frontier/REPORT.md),
[coverage and remaining mechanisms](execution_frontier/RESEARCH.md).

**27 September: rebound candidate fails deployment qualification.** The
registered additional period, 23 December 2025–22 March 2026 (90 days, 61
sessions), ends INR 8,561.91 from INR 9,411.18; dated fees give INR 8,570.94.
It has twelve signals and three modeled fills, one winner/two losers.
Dhan's independent option reconstruction also loses: INR 8,639.15 with
dated fees. Signal dates still come from the frozen underlying tape; this
is an independent option-path check, not an independent market experiment.
Full-session monitoring does not change the original earlier/recent primary
balances, but an open-plus-1% entry model loses in the earlier period,
ending INR 8,255.83. That model fills a May 29 trade with INR 6,959.89 loss
which the adverse-high entry model skips. Adverse prices are not a guaranteed
lower bound on strategy returns when they alter which orders fill.

Matched-date controls (999 per period) beat or match observed results in
62 additional / 328 earlier / 95 recent cases, with no unresolved controls.
They match clock, exact expiry distance and past-only volatility terciles;
adjustment over prior search is inconclusive. The new period is retrospective
strategy validation, not prospective evidence. Strict source checks remain
unresolved. Production integration is conditional on a passing research gate,
so the old CAS engine is not being armed as a substitute.

Fresh read-only cloud inspection confirms disabled configuration/mandate
authority, an enabled broker read-only interlock, and RECOVERING with
HTTP 400/DH-906 cached-token account reads.
No cloud mutation, order, deployment or spending. See the
[qualification report](results/rebound_validation/REPORT.md) and
[registered protocol](rebound_validation/PROTOCOL.md).

Fresh local PIN/TOTP authentication passes the account-identity check. All
eight read-only Dhan account/chain requests succeed: INR 9,411.18 available,
zero positions/orders/trades, active derivatives/data access and VM IP in the
whitelist. Upstox market status also responds. The October 6 chain has 231
strikes, but this is a closed-market snapshot, not fill or latency evidence.
The cloud daemon's older invalid cache is a separate unresolved operational
issue. [Account receipt](results/rebound_validation/api_check.json).

**27 September: broader overnight/stock search complete.** Tested 26 frozen
variants in two 90-day windows (23 March–20 June and 21 June–18 September),
260 scenario paths and 3,996 matched-time random-side controls. The new
conditional leader is NIFTY overnight selloff-rebound with next-afternoon
exit: INR 9,411.18 → **14,663.22 earlier / 16,762.25 recent**, four/five trades.
It exceeds the prior recent record of INR 12,566.43. Three-minute delay:
INR 10,048.67 / 16,638.71; doubled slippage: INR 14,159.69 / 16,088.54;
delete-best: INR 10,029.17 / 9,592.86. These are model balances, not live profits.

Noise remains unresolved: 156/999 earlier and 20/999 recent random-direction
paths match or beat it; adjustment across at least 144 variants is inconclusive.
Ten of 52 base paths are UNKNOWN; all 52 strict paths stop at data-audit gaps.
Dhan matched 27 selected timestamps/strikes, but no sampled OHLC tuple was
identical to Upstox; all nine entry limits and 18 entry/exit volume snapshots
pass the model checks. This does not establish order-book fills or full-path
agreement. A five-session cash OI rule is also positive in both base windows,
but fails earlier slippage stress and recent best-trade deletion.

Validated 1,789 resolved trade rows and exact parity on 210 unaffected paths.
All 227 tests pass. No funded orders, deployment or spending. Gold Petal history
is available, but historical margin/liquidity/eligibility remain unverified;
that family is unscored. [Full comparison](results/broader/REPORT.md),
[frozen rules](broader/PROTOCOL.md), [reproduce](broader/README.md).

**27 September, subsequent operator-requested intraday challengers complete.**
Eight new signal rules and the two original benchmarks, each with three exit
profiles: 30 variants, 360 scenario paths over the same earlier/recent 90-day
windows (46/50 non-expiry sessions), independently starting INR 9,411.18.
GAP_FADE_DOUBLE beats both previous recent benchmarks at INR 12,566.43
(+33.53%, four trades/three wins). Earlier primary: INR 7,544.54; recent
delete-best: INR 9,275.76; two-/three-minute delays: INR 10,197.70 / 3,780.44.
120/999 matched-time random-side controls match or beat it. No live qualifier.

TREND_PULLBACK_FAST is mildly positive in both primary windows, INR 9,623.88
and INR 9,500.24, but only one fill each and earlier delay tests lose. Faster
exit profiles do not make the original unwind benchmarks robust. Collected
34 additional API batches; 838 contract-days, 231 volume mismatches and 18
off-tick cases (overlap). All 60 reported primary paths resolve; 54 strict
paths remain UNKNOWN. The six strict resolved paths either lose or have no
fills. No missing data is counted as a flat result.

[New comparison, controls and ledger](results/intraday_challengers/REPORT.md) ·
[Frozen rules](intraday_challengers/PROTOCOL.md) ·
[Reproduce](intraday_challengers/README.md). No funded orders or cloud changes.

**27 September: final bounded search complete; no strategy to arm.** Reviewed
the major F&O mechanisms and ran eight additional late-expiry/long-volatility
variants across the same two 90-calendar-day windows. All 112 declared
execution scenarios finished; no same strategy/scenario grows the INR 9,411.18
bankroll in both windows. Recent primary 15:15 straddle: INR 6,203.96; 15:15
strangle: INR 1,328.02. The two no-fill variants provide no profit evidence.
All 16 strict primary paths are UNKNOWN at source-audit gaps; conditional
results are not exchange execution receipts or independent validation.

Audited 341 exact contract-days (243 match NSE volume, 98 differ; 12 off-tick,
overlapping categories). Acquired 11 additional API batches, validated 590
resolved scenario trades and passed all 209 tests. Fresh read-only Dhan calls
confirm INR 9,411.18 and zero positions. Fifteen current one-lot margin checks
exclude the sampled NIFTY futures/spreads/shorts at this balance; Gold Petal
is affordable at INR 1,415.19 but has no validated strategy or confirmed MCX
eligibility here. Current quotes were closed-market observations.

The decision is to stop this bounded rapid all-in multiplication search
without funded activation. This is not proof that every F&O strategy loses,
nor completion of every broad family's 90-day universe replay. No orders,
deployment, paid service or cloud change occurred.

[Final results and ledgers](results/finalsearch/REPORT.md) ·
[Mechanism review and sources](finalsearch/RESEARCH.md) ·
[Reproduce](finalsearch/README.md).

**21 September event-family extension complete; no funded candidate.**
Two frozen attachment-based event variants now cover 21 June–18 September:
90 calendar days and 63 sessions, with 25 earlier warm-up sessions. Each starts
independently at INR 9,411.18. The intraday primary conditional path ends at
INR 3,453.01 (four trades, one winner); 665/999 matched-time random-side paths
do at least as well. The overnight path closes five trades, reaches INR
3,913.33 and stops at an unresolved L&T option exit. That is cash before the
unresolved position, not final wealth. All its delay/open-model paths also
stop unresolved; the intraday alternatives lose money.

Collected 4,925,250 test-window underlying minutes across 13,134 company-
sessions, 4,059 attachment references and 2,881 additional option contract-
day requests in 2,690 batches. Verified 4,050 attachment raw/text hashes.
Recovered 16 missing, date-validated ban records through NSE's report API;
three dates and seven affected signals remain UNKNOWN. Completed 1,998
random-side paths, both strict paths and best-profitable-trade deletion.
Nine reference/compiled paths agree per engine. Full software verification
passes 201 tests with no skips and rejects all 15 deliberate defects.

Fresh evening checks: Upstox market status succeeds. Two Dhan session-renewal
attempts fail the identity gate; bounded direct authentication diagnostics
match the configured account. The final check through the production auth
function succeeds and verifies INR 9,411.18 available and zero positions.
Unattended renewal consistency remains unresolved. No orders or deployment
were performed. All attempts are retained in the dated API receipts.

[Individual results and ledgers](results/event90/FINDINGS.md) ·
[Coverage](results/event90/coverage.json) · [Reproduce](event90/README.md).
The other seven broad families still need complete 90-day inputs/coverage;
these two variants also lack full execution coverage and independent
validation. This is not a completed full-family gauntlet or a live approval.

**21 September readiness follow-up: no qualified funded strategy.** Added 16
NIFTY failed-breakout, VWAP-reversal, compression-break and prior-OI-wall
variants, separately for expiry/ordinary sessions and target/trailing exits.
Each starts at INR 9,411.18 in each of the same two 90-calendar-day windows.
Finished 320 execution scenarios and 13,972 random-direction paths, bringing
these two NIFTY batches to 80 variants, 1,856 scenarios and 59,880 controls.
None is profitable in both reported primary windows; the new minimum adjusted
p-value is 1.0. Strict data checks resolve 6/16 variants per window, including
no-fill cases. Missing evidence remains UNKNOWN, not a saved bankroll.

Fresh real account reads verify F&O, INR 9,411.18 and no orders/trades/positions.
Cloud egress and whitelist are correct. The read-only daemon is RECOVERING
with an invalid cached credential; active-credential reads succeed from that
same VM. Local recovery rotation is fixed and verified with exposed-position
outage fixtures. Full suite: 196 tests, no skips, 15 rejected production defects.
No deployment, credential persistence on the VM, live probe or broker order.

[New individual bankrolls and ledgers](results/readiness/REPORT.md) ·
[API/cloud evidence and remaining work](../docs/RELEASE-READINESS.md) ·
[Reproduce](readiness/README.md).
Full nine-family 90-day universe coverage, historical execution/CAS inputs,
and independent prospective strategy evidence remain outstanding.

## Earlier multi-source NIFTY experiment

**Expanded NIFTY 90-day batch complete; no demonstrated repeatable edge.**
64 rule/exit variants ran independently over 23 March–20 June and
21 June–18 September 2026: 90 calendar days each, 59/63 trading sessions,
13 expiries per window. Completed 1,536 execution scenarios and 45,908
conditional random-side paths. No variant grows cash in both primary windows;
minimum Holm-adjusted value is 1.0. Reported-model balances exist for 46/64
earlier and 52/64 recent variants; strict checks leave only 10/64 and 6/64
computable, including no-trade cases. All remaining balances stay UNKNOWN.

The apparent recent expiry winner returns conditional INR 16,579.28 from one
trade and INR 9,411.18 without it; its source tape is unresolved. Ordinary
chain unwind returns INR 10,843.71 recently but INR 2,616.71 earlier and
INR 4,961.24 recently after removing its best trade. None qualifies for live use.
New data includes futures, Dhan option IV/OI, VIX/sector/GIFT and historical
market analytics where actually available. The exact-option sample contains
513,870 minute rows; 347/1,362 contract-days have volume discrepancies and
40 contain off-tick OHLC. Historical quotes/IEP and complete broad-family
90-day coverage remain outstanding.

[Findings](results/multifeature90/FINDINGS.md) ·
[All variants](results/multifeature90/REPORT.md) ·
[Broker inventory](multifeature/CAPABILITIES.md) ·
[Reproduction](multifeature/README.md).
54 focused tests pass. Fresh read-only funds/positions: INR 9,411.18 and zero
open positions. No live trading or deployment was performed.

## Preserved earlier research

**NIFTY expiry follow-up: no live-qualified strategy.** Twelve frozen variants
were replayed over 48 expiries, with an additional 53-expiry check of the
selective trend candidate. The recent active rules lose money. The full
101-expiry trend/trailing diagnostic ends at INR 15,938.86, but only makes
three trades; deleting the best leaves INR 2,817.04. Its additional-year
diagnostic ends at INR 5,099.55. These are conditional reported-candle results;
strict paths remain UNKNOWN where volume discrepancies affect a trade.

See the [decision and evidence](results/expiry/FINDINGS.md),
[all twelve variants](results/expiry/REPORT.md),
[execution scenarios](results/expiry/scoreboard.csv), and
[additional-year validation](results/expiry/extension/REPORT.md).
The funded account was checked read-only: INR 9,411.18 available, no open
positions. No live order or engine activation was performed.

The earlier nine-family work is preserved below.

**Nine bounded discovery variants tested; no validated winner.**

The follow-up [noise audit](results/NOISE-AUDIT.md) completed 5,994 random-side bankroll controls and processed 3,413 original attachment references. None of the four original active families has a convincing primary directional result after the nine-family adjustment. The two expanded event variants are reported separately; neither is an independently validated winner.

The full-universe, executable and statistically validated gauntlet remains incomplete. All full-family bankrolls are UNKNOWN. Each independent model started with INR 9,411.18 on July 20 and used data through September 18, 2026.

See the [full report](results/GAUNTLET.md), [scoreboard CSV](results/scoreboard.csv), [execution scenarios](results/execution_scenarios.csv) and [per-bot ledgers](results/ledgers/).

| Bot | Closed trades | Cash after resolved trades (INR) | Path |
|---|---:|---:|---|
| EVENT_CONTINUATION | 3 | 2574.15 | Stopped at unresolved trade |
| INTRADAY_EVENT | 2 | 3368.37 | Conditional observed-data scenario |
| NONEXPIRY_FORCED_FLOW | 2 | 9394.55 | Conditional observed-data scenario |
| EXPIRY_FORCED_FLOW | 0 | 9411.18 | No observed signal in narrow scope |
| PASSIVE_FLOW | 0 | 9411.18 | No observed signal in narrow scope |
| SCHEDULED_EVENT_VOL | 0 | 9411.18 | No observed signal in narrow scope |
| BLOCK_OFS_DISLOCATION | 0 | 9411.18 | No observed signal in narrow scope |
| SECTOR_SHOCK_LAG | 16 | 5612.37 | Conditional observed-data scenario |
| CROSS_MARKET_LEAD_LAG | 0 | 9411.18 | No observed signal in narrow scope |

These balances are conditional diagnostics. A stopped path reports cash before its unresolved trade, not final equity. Data gaps can change earlier trades and subsequent bankrolls. Zero signals in one subvariant do not validate the broader family.

Data acquisition completed for 21,415 planned option contract-days: 19,227 reconcile with NSE traded totals; 2,188 remain uncertain. All 45 scheduled model replays finished. Historical depth, complete event and family inputs, broker-specific RMS and untouched holdout validation remain outstanding.

The prior EVENT_CONTINUATION leadership claim is not supported by this replay. No live orders were submitted. See [protocol](gauntlet/PROTOCOL.md) for the frozen rules and disclosed discovery revisions.

Refresh derived results with `.venv/bin/python -m research.report` and `.venv/bin/python -m research.status`.
