# Nine-bot discovery results — 19 September 2026

**The bounded current-data experiments are finished. No bot has earned selection. The requested full-universe, executable and statistically validated gauntlet remains incomplete.**

Each bot starts independently with INR 9,411.18 on July 20 and runs through September 18 (61 calendar days, 44 sessions). Rules were influenced by the supplied historical examples; this period is discovery, not holdout. No live orders were submitted.

**These are conditional model balances, not verified executable bankrolls.** Missing inputs could change earlier trades and every subsequent order. Zero-signal variants retain cash only within their stated scope; they cannot be ranked as winning full strategy families.

| Bot | Signals | Closed trades | Wins | 2x targets | Cash after resolved trades (INR) | Replay gap records |
|---|---:|---:|---:|---:|---:|---:|
| EVENT_CONTINUATION | 137 | 3 | 0 | 0 | 2,574.15 *stopped* | 44 |
| INTRADAY_EVENT | 33 | 2 | 0 | 0 | 3,368.37 | 22 |
| NONEXPIRY_FORCED_FLOW | 34 | 2 | 1 | 0 | 9,394.55 | 6 |
| EXPIRY_FORCED_FLOW | 0 | 0 | 0 | 0 | 9,411.18 | 0 |
| PASSIVE_FLOW | 0 | 0 | 0 | 0 | 9,411.18 | 0 |
| SCHEDULED_EVENT_VOL | 0 | 0 | 0 | 0 | 9,411.18 | 0 |
| BLOCK_OFS_DISLOCATION | 0 | 0 | 0 | 0 | 9,411.18 | 0 |
| SECTOR_SHOCK_LAG | 142 | 16 | 2 | 0 | 5,612.37 | 99 |
| CROSS_MARKET_LEAD_LAG | 0 | 0 | 0 | 0 | 9,411.18 | 0 |

Gap records above concern entry/exit replay. Additional signal-cohort gaps and scope exclusions apply even when that column is zero. Full-family bankroll is **UNKNOWN for all nine**. *Stopped* means an unresolved position or missing input halted the path; its displayed amount is the balance before that unresolved trade, not final equity or current free cash.

| Bot | Precisely tested scope |
|---|---|
| EVENT_CONTINUATION | NSE disclosure-metadata classifier; seven-day stock expiry buffer |
| INTRADAY_EVENT | NSE intraday disclosure metadata; same expiry buffer |
| NONEXPIRY_FORCED_FLOW | 21,415 NSE exact-contract days; persistent spot strike crossings |
| EXPIRY_FORCED_FLOW | NSE index expiry spot crossings; excludes auction indicative-index signals |
| PASSIVE_FLOW | August MSCI Standard additions/deletions only |
| SCHEDULED_EVENT_VOL | August RBI decision; NIFTY/BANKNIFTY straddle filter only |
| BLOCK_OFS_DISLOCATION | Disclosed LICI OFS only |
| SECTOR_SHOCK_LAG | Bank and software index leads; graph fitted before July 20 |
| CROSS_MARKET_LEAD_LAG | GIFT-to-NIFTY only; assumed two-minute feed delay |

**Execution sensitivity and controls**

Every strategy with signals was rerun with 1/2/3-minute entry delay, an alternative next-bar open plus 1% entry, and five matched-time random-side controls. Strategies with closed trades were rerun after deleting the highest-P&L trade. Deletion repeats chronological contract selection and sizing; it does not simply subtract a profit.

If all closed baseline trades lose, "best" means the least-negative trade. In EVENT_CONTINUATION, deleting the losing L&T July 29 trade changes the later path and produces INR 13,865.97 in the conditional scenario, with 136 coverage gap records. This is a retrospective perturbation, not a tradable instruction to skip L&T or evidence that the original bot earned that amount.

| Bot | 1-min high | 2-min high | 3-min high | Open +1% | Delete best | Five random-side balances |
|---|---:|---:|---:|---:|---:|---|
| EVENT_CONTINUATION | 2,574.15 *stopped* | 3,251.93 *stopped* | 4,108.31 *stopped* | 2,607.94 *stopped* | 13,865.97 | 4,099.26 *stopped*; 3,812.35; 16,559.10; 2,574.15 *stopped*; 4,857.73 |
| INTRADAY_EVENT | 3,368.37 | 4,080.63 | 3,570.74 | 2,643.94 | 4,856.54 | 5,527.44; 5,527.44; 5,369.82; 5,527.44; 3,368.37 |
| NONEXPIRY_FORCED_FLOW | 9,394.55 | 9,700.18 | 8,695.40 | 9,479.09 | 9,093.96 | 9,093.96; 9,711.77; 9,711.77; 9,711.77; 9,711.77 |
| SECTOR_SHOCK_LAG | 5,612.37 | 7,060.30 | 8,747.16 | 6,352.80 | 4,542.92 | 5,600.15; 4,425.73; 5,708.82; 9,103.68; 5,959.32 |

All sensitivity balances retain the same conditional-data limitation. If a path stops with an unknown holding/exit, the CSV labels it and cash is only the last resolved cash. Closed-trade drawdown omits intratrade drawdown and is not an executable liquidation bound.

Five random paths are diagnostic only: even outranking all five gives a smallest plus-one randomization rank of 1/6, before accounting for nine tested families. The controls also condition on event times selected by the strategy. No significant edge, causal proof, family-adjusted p-value, or out-of-sample validation is claimed.

**What was actually acquired and checked**

- 5,699,958 underlying minute bars across 222 files, with warm-up history; 68 daily exchange contract files and 44 dated F&O ban lists.
- 47,097 exchange announcement records downloaded; original dissemination timestamps gate the metadata variant.
- All 21,415 planned non-expiry option contract-days collected: 19,227 match official traded units exactly; 2,188 remain unknown.
- Expiry: 60 persistent strike-cross prospects, 0 observed signals, 9 unresolved audit records; historical CAS indicative-index paths absent.
- Four NIFTY signal-minute comparisons with Dhan found close-price differences of +0.95, -0.30, -0.20 and +0.15 rupees. OI also differs in three of four. The premium-rise and OI-fall necessary conditions survive all four cross-checks; the complete signal, denominator and fills are not independently certified.
- Dhan read-only account access confirms the derivatives segment is active. Account approval does not validate a trading rule.

**How fills and information were modeled**

Completed minute bars only; historical membership from the prior exchange file; 20 prior sessions for same-time RVOL; event availability from dissemination timestamps. Exact contract identity, historical lot size and metadata are resolved before selection. Each order fixes whole-lot quantity, a last-price-plus-5% limit and cash including fees before looking at arrival bars. At most 95% of cash is deployed. Both prior liquidity and arrival volume limit modeled participation to 5%. No order is resized using future affordability.

Adverse entry uses the next eligible full bar high only within the fixed limit. Targets require a later bar trading 2% beyond twice entry; entry-bar targets are excluded. Invalidations use delayed adverse exits; unresolved holdings stop the path. Scheduled liquidation is 15:10–15:17, with partial fills and fees retained. Stock contracts within seven calendar days of expiry are excluded, changing the original near-expiry stock thesis. This conservative bar scenario still cannot establish historical bid/ask, queue position or 1/3/5-second execution. Costs use the documented conservative Dhan/NSE fee envelope.

**Interpretation and remaining work**

The earlier EVENT_CONTINUATION leadership claim is withdrawn: anecdotes did not establish a winning strategy. Its implemented metadata classifier can mistake takeover/ownership disclosures mentioning acquisition for a material business acquisition. That is a measured specification weakness; fixing it after observing outcomes creates another discovery variant and requires separate validation.

Concrete execution failure: the event baseline reached a WAAREEENER August 25 2200 PE entry on July 30 at 09:20, one 175-unit lot modeled at INR 10.85. The planned exit could not liquidate that lot within the frozen 5% participation limit by 15:17. The path stops there. INR 2,574.15 is the cash before this unresolved trade, not a September ending balance. This is why daily volume and an affordable entry are insufficient evidence of executable compounding.

The famous examples were not credited retrospectively. Solar generates a September 15 09:20 put candidate, but the event bankroll path had already stopped at the unresolved July 30 position. KFin generates a July 27 09:26 call candidate; its board-outcome metadata is ambiguous, so it is outside this narrow metadata variant (not evidence that the actual announcement was immaterial). Coforge on July 28 and Bandhan on July 22 reach the selector with only INR 4,632.84 remaining; none of the reached eligible contracts passes the affordability/past-capacity gate. No qualifying Kaynes July 29 signal appears in this exact exchange-metadata rule.

OI decline with a premium rise is a positioning proxy. It does not identify which side initiated trades or establish that writers were forced out. Likewise, large daily volume does not prove a one-lot fill at the desired timestamp.

Remaining requirements are concrete: complete primary-event content and the missing family-specific datasets; reconcile uncertain option histories and historical RMS; obtain quote/depth and availability-time evidence; then freeze a surviving candidate and test an untouched period with enough independent event/day observations. No amount of additional in-sample threshold tuning substitutes for those checks.

Reproduce with `.venv/bin/python -m research.run_suite --wait-for-reconciliation`, then `.venv/bin/python -m research.report`. The focused suite is `.venv/bin/python -m pytest tests/test_gauntlet.py -q`. Its tests cover information boundaries, whole lots, fees, capacity, ambiguous exits and missing data; they do not prove market profitability.

Derived [scoreboard](scoreboard.csv), [scenario results](execution_scenarios.csv), and per-bot [ledgers](ledgers/) include rejected signals as well as trades. Raw licensed data and provider receipts stay in the ignored private artifact directory.

Source digest: `2e819b19b4391705bd6572539d2acf6f467f16912d497afc28cabd9436bd253a`. Report generated 2026-09-19T23:17:08.735028+00:00.

Primary source references: [Upstox expired candles](https://upstox.com/developer/api-documentation/get-expired-historical-candle-data/), [Dhan expired options](https://dhanhq.co/docs/v2/expired-options-data/), [Dhan RMS](https://dhan.co/risk-management-policy/), [MSCI changes](https://www.msci.com/eqb/gimi/stdindex/MSCI_Aug26_STPublicList.pdf), [RBI calendar](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62422), [LICI OFS](https://nsearchives.nseindia.com/corporate/tchari_03082026210047_LICI_OFSNOTICE.pdf).
