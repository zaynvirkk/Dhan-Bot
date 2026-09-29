# Nine-bot noise audit — 20 September 2026

**No demonstrated profitable, repeatable winner.** The active frozen variants lose money in the conditional bar replay and do not show convincing directional performance in the primary noise test. The five zero-signal subvariants have no statistical sample; they are not proven good or bad. Full-family bankrolls remain UNKNOWN.

Every original bot starts independently with INR 9,411.18 on July 20; data ends September 18, 2026. This is the already examined discovery period. The original 45 execution scenarios remain in [GAUNTLET.md](GAUNTLET.md); this audit adds **3,996 original-variant random-side bankroll paths**, **9,999 day-block randomizations and bootstraps per directional test**, and two original-attachment event replays with **1,998 additional random-side controls** (5,994 total). No broker orders were submitted.

## Original frozen variants

| Bot | Closed trades | Conditional cash / unresolved balance | Random controls matching or beating it | Verdict |
|---|---:|---:|---:|---|
| EVENT_CONTINUATION | 3 | 2,574.15 before unresolved trade | Not rankable | NO_DEMONSTRATED_EDGE |
| INTRADAY_EVENT | 2 | 3,368.37 | 100.0% | NO_DEMONSTRATED_EDGE |
| NONEXPIRY_FORCED_FLOW | 2 | 9,394.55 | 73.8% | NO_DEMONSTRATED_EDGE |
| EXPIRY_FORCED_FLOW | 0 | 9,411.18 | No sample | NO_SAMPLE_IN_BOUNDED_VARIANT |
| PASSIVE_FLOW | 0 | 9,411.18 | No sample | NO_SAMPLE_IN_BOUNDED_VARIANT |
| SCHEDULED_EVENT_VOL | 0 | 9,411.18 | No sample | NO_SAMPLE_IN_BOUNDED_VARIANT |
| BLOCK_OFS_DISLOCATION | 0 | 9,411.18 | No sample | NO_SAMPLE_IN_BOUNDED_VARIANT |
| SECTOR_SHOCK_LAG | 16 | 5,612.37 | 90.5% | NO_DEMONSTRATED_EDGE |
| CROSS_MARKET_LEAD_LAG | 0 | 9,411.18 | No sample | NO_SAMPLE_IN_BOUNDED_VARIANT |

These balances are **model diagnostics, not certified ending account equity**. Missing contract history and broker eligibility can change earlier decisions and every subsequent bankroll. Event continuation stops at an unresolved holding/exit; its last resolved balance is not a terminal return. The separate strict replay stops at the first data uncertainty and also leaves the full result unknown. No-signal cash is only cash in that narrow tested variant.

The thousands of controls reuse the same historical observations; they do not create thousands of independent trades. The original four active baselines contain only 23 closed trades and zero 2x target exits. Repeated controls can have identical outcomes, especially where only two trades were affordable.

The random controls use the same underlying and decision times, but choose CE/PE randomly. Each control compounds its own whole-lot bankroll and reruns contract affordability, fixed pre-dispatch limits, liquidity caps, fees and exits. Original forced-flow contract identity is preserved for an unchanged side; a flipped side uses the same ordinary option selector. This tests a specified counterfactual, not an exactly exchangeable pure direction null. Unknown paths stay unresolved. Rank bounds count all unresolved controls as below/above the baseline; they are **not population significance p-values**.

## Direct signal-versus-noise check

Primary horizon was fixed at 15 minutes before these calculations. Entry reference is the underlying open one full minute after signal time. All intervening bars must exist. Returns are signed by CE/PE direction, averaged within each trading day, then equally across dates. These are underlying price returns, not option P&L. Days are the sampling blocks; residual serial dependence across days remains a limitation.

| Bot | Signals / dates | Mean signed underlying return | 95% day-bootstrap interval | Raw p | Holm p (nine families) |
|---|---:|---:|---:|---:|---:|
| EVENT_CONTINUATION | 79 / 28 | 0.110% | -0.115% to 0.361% | 0.1916 | 1.0000 |
| INTRADAY_EVENT | 16 / 12 | -0.112% | -0.701% to 0.489% | 0.6529 | 1.0000 |
| NONEXPIRY_FORCED_FLOW | 33 / 19 | -0.041% | -0.421% to 0.330% | 0.5688 | 1.0000 |
| SECTOR_SHOCK_LAG | 142 / 32 | 0.014% | -0.044% to 0.072% | 0.3317 | 1.0000 |

No primary test rejects the conditional sign-symmetry null at 5%. This is absence of convincing evidence for these signals, not proof that every related strategy is noise. The 5/30-minute sensitivity results are exported without choosing the best horizon. The Holm adjustment covers the nine named primary families; it cannot erase the earlier hypothesis/threshold search or turn this discovery sample into a holdout.

## Original filing-content extension

Processed all **3,413 collected relevant attachment references** (including malformed/missing references) rather than selecting documents by subsequent returns. Results: CATEGORY_MATCH: 1,527, OWNERSHIP_NOTICE: 15, UNKNOWN_DOCUMENT: 9, UNKNOWN_MATERIALITY: 1,845, UNKNOWN_UNREADABLE: 17.

The extractor reads original NSE PDFs and bounded PDF/XML ZIP members, preserving dissemination time and hashes. The predeclared category classifier covers results, business acquisitions, order wins, guidance, regulatory actions and management changes. A text category match is not a validated judgment of economic materiality. The collection includes the 33 additional subject categories frozen after the input inventory; remaining unselected administrative/reposted categories remain outside this variant. Missing, ambiguous, scanned or corrupt content remains UNKNOWN. Original attachment URLs plus dissemination times are the publication-vintage assumption; later archive replacement cannot be ruled out by today’s download alone.

| Content variant | Price candidates | Qualifying category candidates | Closed trades | Last resolved cash | Random rank | Path |
|---|---:|---:|---:|---:|---:|---|
| EVENT_CONTINUATION | 151 | 106 | 3 | 2,574.15 | Not rankable | Unresolved; not terminal equity |
| INTRADAY_EVENT | 33 | 25 | 3 | 3,341.79 | 82.9–82.9% | Conditional only |

These two additional replays use unchanged price/execution thresholds. They are an information-coverage extension, not independent validation. Full chronological [content ledgers](content/ledgers/) retain losses, rejections and uncertainties.

## Tested scope and remaining requirements

| Bot | Actual implemented scope |
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

The remaining work is substantive data/validation work: resolve 2,188 uncertain option contract-days; obtain full family inputs for other index changes, scheduled events, block/OFS cases, external markets and BSE/MCX coverage; establish historical broker RMS and near-expiry delivery-margin eligibility; acquire timestamped indicative-index and bid/ask/depth data where those signals require it; validate unchanged rules on an untouched period. This report does not label that work complete.

Minute OHLCV cannot establish 1/3/5-second latency, displayed liquidity or queue fills. The seven-day stock expiry buffer changes the original near-expiry opportunity set; it is a declared conservative scope restriction, not proof that every nearer contract was prohibited. Dhan publishes pre-expiry delivery-margin requirements and expiry-day fresh stock-option restrictions in its [RMS policy](https://dhan.co/risk-management-policy/). NSE offers [historical order/trade data](https://www.nseindia.com/static/market-data/eod-historical-data-subscription); neither a current quote nor a daily CAS summary reconstructs those historical execution states.

## Reproducibility

The accelerated simulator passed **29 exact original baseline/seeded-reference comparisons**, plus **two content-variant comparisons** with the original full replay. Cash chronology and whole-lot execution were checked again when exporting the content ledgers. Source/input hashes are embedded in the JSON result; raw licensed market history remains in the ignored private cache. Fixtures validate software behavior, never profitability.

- [Machine-readable result](noise_audit.json)
- [All 3,996 control paths](noise_paths.csv)
- [All 1,998 content-variant control paths](content_noise_paths.csv)
- [Directional tests and horizon sensitivities](directional_noise.csv)
- [Every filing reference, classification and failure](filing_coverage.json)
- [Every candidate classification/selection change](content_candidate_changes.json)
- [Frozen audit protocol](../noise/PROTOCOL.md)

Run `.venv/bin/python -m research.noise.report` after completing the commands in [README.md](../README.md).
