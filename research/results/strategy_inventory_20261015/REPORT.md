# Complete production-strategy inventory — 15 October 2026

Live snapshot: 2026-10-15T04:14:54.570267+00:00. All **137** configured names checked, including **136** minute-rule evaluations and CAS.

**This is a fresh inventory/evidence audit and cached execution recheck, not 137 new end-to-end live-policy backtests.** Existing candle-model results do not certify the exact deployed policy, current profit-ratchet overlay, real historical spreads, queues or fills.

The main research windows are 23 March–20 June and 21 June–18 September 2026, each 90 calendar days. Additional rebound/frontier validation is 23 December 2025–22 March 2026. These are reused historical windows, not the latest rolling 90 days or untouched future observations.

The names represent **125 dispatch specifications** across **42 family labels**. Twelve names are exact aliases. Exit variations and families share signals and capital; they are not independent discoveries.

Funded: CAS_LAG_V1. Cash INR 7805.94; orders today 0; open positions 0. Next NIFTY expiry 2026-10-19.

## Coverage and qualification

Every non-CAS name is bound to a retained research scoreboard. Every other scoreboard record under the same name or exact alias is also attached in audit.json; the headline categories use the selected primary batch and do not erase older positive results. Unknown data and zero-fill paths are not profits. The later rebound failure and all three frontier periods are included. All model paths start at INR 9,411.18 independently.

No additional funded qualifier is established. CAS has real positive net receipts from one expiry, not a validated repeatable edge. All remaining configurations stay observation-only.

Re-executed **5,416** cached candle-execution scenarios against current kernels; **0** changed paths. These reuse saved signals and tapes and include unresolved scenarios; they are not independent new observations. Underlying input hashes were checked. Original source-bound reports were not patched to bypass their stale-source guards. NIFTY scenario noise controls were not rerun; the separate event-engine refresh below reran its own controls.

Every one of the 136 minute-rule dispatches rejects missing inputs and future-only bars: **272 synthetic negative cases**. This proves software boundaries, not profits.

| Evidence category | Configurations |
| --- | ---: |
| Lost in at least one primary period | 106 |
| One profitable live session; unvalidated | 1 |
| Positive primary periods; too few trades | 1 |
| Only one profitable primary period | 5 |
| No primary-window profit | 6 |
| Unresolved historical inputs | 18 |

## All configurations

Cash columns below are retained reported-candle scenario outputs, not money earned live. UNKNOWN means an unresolved path. Blank validation means that batch did not have a third period.

| Configuration | Funding | Today | Earlier model | Recent model | Additional validation | Evidence verdict |
| --- | --- | --- | ---: | ---: | ---: | --- |
| GAP_FADE_DOUBLE | Observe | WAITING | 7544.54 | 12566.43 | — | Lost in at least one primary period |
| NIFTY_SELLOFF_REBOUND_1510 | Observe | WAITING | 14663.22 | 16762.25 | 8561.91 | Lost in at least one primary period |
| CAS_LAG_V1 | Funded | NO_TRADE_DAY | — | — | — | One profitable live session; unvalidated |
| OPEN_DRIVE_FAST | Observe | WAITING | 5616.25 | 7846.33 | — | Lost in at least one primary period |
| OPEN_DRIVE_SWING | Observe | WAITING | 4051.14 | 9831.50 | — | Lost in at least one primary period |
| OPEN_DRIVE_DOUBLE | Observe | WAITING | 4048.91 | 1590.92 | — | Lost in at least one primary period |
| GAP_FADE_FAST | Observe | WAITING | 8199.73 | 6903.44 | — | Lost in at least one primary period |
| GAP_FADE_SWING | Observe | WAITING | 10262.90 | 6040.30 | — | Lost in at least one primary period |
| FIRST_LAST_FAST | Observe | WAITING | 7310.29 | 8380.25 | — | Lost in at least one primary period |
| FIRST_LAST_SWING | Observe | WAITING | 6969.20 | 9460.05 | — | Lost in at least one primary period |
| FIRST_LAST_DOUBLE | Observe | WAITING | 6375.69 | 9460.05 | — | Lost in at least one primary period |
| TREND_PULLBACK_FAST | Observe | WAITING | 9623.88 | 9500.24 | — | Positive primary periods; too few trades |
| TREND_PULLBACK_SWING | Observe | WAITING | 8481.37 | 8825.52 | — | Lost in at least one primary period |
| TREND_PULLBACK_DOUBLE | Observe | WAITING | 9175.57 | 9123.39 | — | Lost in at least one primary period |
| VOLUME_REVERSAL_FAST | Observe | WAITING | 7334.80 | 9411.18 | — | Lost in at least one primary period |
| VOLUME_REVERSAL_SWING | Observe | WAITING | 5514.31 | 9411.18 | — | Lost in at least one primary period |
| VOLUME_REVERSAL_DOUBLE | Observe | WAITING | 7250.33 | 9411.18 | — | Lost in at least one primary period |
| SECTOR_CATCHUP_FAST | Observe | WAITING | 9411.18 | 7793.61 | — | Lost in at least one primary period |
| SECTOR_CATCHUP_SWING | Observe | WAITING | 9411.18 | 8024.26 | — | Lost in at least one primary period |
| SECTOR_CATCHUP_DOUBLE | Observe | WAITING | 9411.18 | 7699.39 | — | Lost in at least one primary period |
| RANGE_FAILURE_FAST | Observe | WAITING | 3768.89 | 4662.08 | — | Lost in at least one primary period |
| RANGE_FAILURE_SWING | Observe | WAITING | 4230.43 | 3593.19 | — | Lost in at least one primary period |
| RANGE_FAILURE_DOUBLE | Observe | WAITING | 3557.01 | 3526.17 | — | Lost in at least one primary period |
| AFTERNOON_COMPRESSION_FAST | Observe | WAITING | 7028.64 | 3363.04 | — | Lost in at least one primary period |
| AFTERNOON_COMPRESSION_SWING | Observe | WAITING | 5438.11 | 2390.02 | — | Lost in at least one primary period |
| AFTERNOON_COMPRESSION_DOUBLE | Observe | WAITING | 4228.83 | 1819.83 | — | Lost in at least one primary period |
| CHAIN_UNWIND_FAST | Observe | WAITING | 3949.65 | 6090.34 | — | Lost in at least one primary period |
| CHAIN_UNWIND_SWING | Observe | WAITING | 3787.57 | 5036.09 | — | Lost in at least one primary period |
| CHAIN_UNWIND_DOUBLE | Observe | WAITING | 2708.99 | 10603.30 | — | Lost in at least one primary period |
| SKEW_UNWIND_FAST | Observe | WAITING | 9411.18 | 9669.55 | — | Only one profitable primary period |
| SKEW_UNWIND_SWING | Observe | WAITING | 9411.18 | 8394.84 | — | Lost in at least one primary period |
| SKEW_UNWIND_DOUBLE | Observe | WAITING | 9411.18 | 11908.11 | — | Only one profitable primary period |
| EXPIRY_FUTURE_TREND_TARGET | Observe | NOT_APPLICABLE | 1068.77 | 2781.16 | — | Lost in at least one primary period |
| EXPIRY_FUTURE_TREND_TRAIL | Observe | NOT_APPLICABLE | 701.17 | 2826.88 | — | Lost in at least one primary period |
| ORDINARY_FUTURE_TREND_TARGET | Observe | WAITING | 2350.65 | 1274.23 | — | Lost in at least one primary period |
| ORDINARY_FUTURE_TREND_TRAIL | Observe | WAITING | 1928.19 | 1559.16 | — | Lost in at least one primary period |
| EXPIRY_FUTURE_OI_TARGET | Observe | NOT_APPLICABLE | 9411.18 | 9411.18 | — | No primary-window profit |
| EXPIRY_FUTURE_OI_TRAIL | Observe | NOT_APPLICABLE | 9411.18 | 9411.18 | — | No primary-window profit |
| ORDINARY_FUTURE_OI_TARGET | Observe | WAITING | 9411.18 | 7859.77 | — | Lost in at least one primary period |
| ORDINARY_FUTURE_OI_TRAIL | Observe | WAITING | 9411.18 | 7859.77 | — | Lost in at least one primary period |
| EXPIRY_BASIS_LEAD_TARGET | Observe | NOT_APPLICABLE | 16177.78 | 8873.55 | — | Lost in at least one primary period |
| EXPIRY_BASIS_LEAD_TRAIL | Observe | NOT_APPLICABLE | 8217.63 | 6156.02 | — | Lost in at least one primary period |
| ORDINARY_BASIS_LEAD_TARGET | Observe | WAITING | 3925.37 | 5231.18 | — | Lost in at least one primary period |
| ORDINARY_BASIS_LEAD_TRAIL | Observe | WAITING | 4536.11 | 4760.13 | — | Lost in at least one primary period |
| EXPIRY_IV_CHEAP_TREND_TARGET | Observe | NOT_APPLICABLE | UNKNOWN | 6762.33 | — | Unresolved historical inputs |
| EXPIRY_IV_CHEAP_TREND_TRAIL | Observe | NOT_APPLICABLE | UNKNOWN | 6762.33 | — | Unresolved historical inputs |
| ORDINARY_IV_CHEAP_TREND_TARGET | Observe | WAITING | 8381.88 | 7471.01 | — | Lost in at least one primary period |
| ORDINARY_IV_CHEAP_TREND_TRAIL | Observe | WAITING | 8381.88 | 7471.01 | — | Lost in at least one primary period |
| EXPIRY_SKEW_UNWIND_TARGET | Observe | NOT_APPLICABLE | 2407.29 | 2101.32 | — | Lost in at least one primary period |
| EXPIRY_SKEW_UNWIND_TRAIL | Observe | NOT_APPLICABLE | 4277.72 | 1728.04 | — | Lost in at least one primary period |
| ORDINARY_SKEW_UNWIND_TARGET | Observe | WAITING | 9411.18 | 11908.11 | — | Only one profitable primary period |
| ORDINARY_SKEW_UNWIND_TRAIL | Observe | WAITING | 9411.18 | 11908.11 | — | Only one profitable primary period |
| EXPIRY_SECTOR_CONFIRM_TARGET | Observe | NOT_APPLICABLE | 1508.52 | 6444.35 | — | Lost in at least one primary period |
| EXPIRY_SECTOR_CONFIRM_TRAIL | Observe | NOT_APPLICABLE | 1392.01 | 3928.96 | — | Lost in at least one primary period |
| ORDINARY_SECTOR_CONFIRM_TARGET | Observe | WAITING | 1966.21 | 1775.50 | — | Lost in at least one primary period |
| ORDINARY_SECTOR_CONFIRM_TRAIL | Observe | WAITING | 2354.35 | 996.61 | — | Lost in at least one primary period |
| EXPIRY_GIFT_CATCHUP_TARGET | Observe | NOT_APPLICABLE | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| EXPIRY_GIFT_CATCHUP_TRAIL | Observe | NOT_APPLICABLE | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| ORDINARY_GIFT_CATCHUP_TARGET | Observe | WAITING | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| ORDINARY_GIFT_CATCHUP_TRAIL | Observe | WAITING | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| EXPIRY_CHAIN_UNWIND_TARGET | Observe | NOT_APPLICABLE | 1279.99 | 4673.53 | — | Lost in at least one primary period |
| EXPIRY_CHAIN_UNWIND_TRAIL | Observe | NOT_APPLICABLE | 744.14 | 2970.93 | — | Lost in at least one primary period |
| ORDINARY_CHAIN_UNWIND_TARGET | Observe | WAITING | 2616.71 | 10843.71 | — | Lost in at least one primary period |
| ORDINARY_CHAIN_UNWIND_TRAIL | Observe | WAITING | 3936.91 | 8468.26 | — | Lost in at least one primary period |
| EXPIRY_PCR_CONFIRM_TARGET | Observe | NOT_APPLICABLE | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| EXPIRY_PCR_CONFIRM_TRAIL | Observe | NOT_APPLICABLE | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| ORDINARY_PCR_CONFIRM_TARGET | Observe | WAITING | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| ORDINARY_PCR_CONFIRM_TRAIL | Observe | WAITING | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| EXPIRY_PAIN_ESCAPE_TARGET | Observe | NOT_APPLICABLE | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| EXPIRY_PAIN_ESCAPE_TRAIL | Observe | NOT_APPLICABLE | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| ORDINARY_PAIN_ESCAPE_TARGET | Observe | WAITING | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| ORDINARY_PAIN_ESCAPE_TRAIL | Observe | WAITING | UNKNOWN | UNKNOWN | — | Unresolved historical inputs |
| EXPIRY_INSTITUTIONAL_ALIGN_TARGET | Observe | NOT_APPLICABLE | UNKNOWN | 3212.32 | — | Unresolved historical inputs |
| EXPIRY_INSTITUTIONAL_ALIGN_TRAIL | Observe | NOT_APPLICABLE | UNKNOWN | 5050.31 | — | Unresolved historical inputs |
| ORDINARY_INSTITUTIONAL_ALIGN_TARGET | Observe | WAITING | UNKNOWN | 4068.74 | — | Unresolved historical inputs |
| ORDINARY_INSTITUTIONAL_ALIGN_TRAIL | Observe | WAITING | UNKNOWN | 3548.74 | — | Unresolved historical inputs |
| EXPIRY_PUBLISHED_PCR_TARGET | Observe | NOT_APPLICABLE | 4091.37 | 2320.38 | — | Lost in at least one primary period |
| EXPIRY_PUBLISHED_PCR_TRAIL | Observe | NOT_APPLICABLE | 4306.86 | 3212.35 | — | Lost in at least one primary period |
| ORDINARY_PUBLISHED_PCR_TARGET | Observe | WAITING | 2940.95 | 3637.10 | — | Lost in at least one primary period |
| ORDINARY_PUBLISHED_PCR_TRAIL | Observe | WAITING | 2485.34 | 1408.99 | — | Lost in at least one primary period |
| EXPIRY_PUBLISHED_PAIN_TARGET | Observe | NOT_APPLICABLE | 9411.18 | 16579.28 | — | Only one profitable primary period |
| EXPIRY_PUBLISHED_PAIN_TRAIL | Observe | NOT_APPLICABLE | 9411.18 | 8930.01 | — | Lost in at least one primary period |
| ORDINARY_PUBLISHED_PAIN_TARGET | Observe | WAITING | 9993.05 | 6212.76 | — | Lost in at least one primary period |
| ORDINARY_PUBLISHED_PAIN_TRAIL | Observe | WAITING | 9993.05 | 6212.76 | — | Lost in at least one primary period |
| EXPIRY_FAILED_ORB_TARGET | Observe | NOT_APPLICABLE | 1250.37 | 9411.18 | — | Lost in at least one primary period |
| EXPIRY_FAILED_ORB_TRAIL | Observe | NOT_APPLICABLE | 1990.66 | 9411.18 | — | Lost in at least one primary period |
| ORDINARY_FAILED_ORB_TARGET | Observe | WAITING | 7600.78 | 6801.53 | — | Lost in at least one primary period |
| ORDINARY_FAILED_ORB_TRAIL | Observe | WAITING | 11763.15 | 3373.77 | — | Lost in at least one primary period |
| EXPIRY_VWAP_RECLAIM_TARGET | Observe | NOT_APPLICABLE | 6159.28 | 2313.18 | — | Lost in at least one primary period |
| EXPIRY_VWAP_RECLAIM_TRAIL | Observe | NOT_APPLICABLE | 6373.68 | 3367.24 | — | Lost in at least one primary period |
| ORDINARY_VWAP_RECLAIM_TARGET | Observe | WAITING | 3444.56 | 3531.19 | — | Lost in at least one primary period |
| ORDINARY_VWAP_RECLAIM_TRAIL | Observe | WAITING | 3444.56 | 3531.19 | — | Lost in at least one primary period |
| EXPIRY_COMPRESSION_BREAK_TARGET | Observe | NOT_APPLICABLE | 9411.18 | 4133.26 | — | Lost in at least one primary period |
| EXPIRY_COMPRESSION_BREAK_TRAIL | Observe | NOT_APPLICABLE | 9411.18 | 4471.11 | — | Lost in at least one primary period |
| ORDINARY_COMPRESSION_BREAK_TARGET | Observe | WAITING | 2638.54 | 3751.91 | — | Lost in at least one primary period |
| ORDINARY_COMPRESSION_BREAK_TRAIL | Observe | WAITING | 2638.54 | 3751.91 | — | Lost in at least one primary period |
| EXPIRY_PRIOR_OI_WALL_TARGET | Observe | NOT_APPLICABLE | 3019.03 | 9411.18 | — | Lost in at least one primary period |
| EXPIRY_PRIOR_OI_WALL_TRAIL | Observe | NOT_APPLICABLE | 4045.61 | 9411.18 | — | Lost in at least one primary period |
| ORDINARY_PRIOR_OI_WALL_TARGET | Observe | WAITING | 9411.18 | 6901.89 | — | Lost in at least one primary period |
| ORDINARY_PRIOR_OI_WALL_TRAIL | Observe | WAITING | 9411.18 | 6901.89 | — | Lost in at least one primary period |
| EXPIRY_ORB30_TARGET | Observe | NOT_APPLICABLE | 1783.70 | 590.13 | — | Lost in at least one primary period |
| EXPIRY_ORB30_TRAIL | Observe | NOT_APPLICABLE | 541.49 | 1107.36 | — | Lost in at least one primary period |
| EXPIRY_LATE_BREAK_TARGET | Observe | NOT_APPLICABLE | 1198.95 | 232.88 | — | Lost in at least one primary period |
| EXPIRY_LATE_BREAK_TRAIL | Observe | NOT_APPLICABLE | 2293.49 | 220.83 | — | Lost in at least one primary period |
| EXPIRY_LATE_FADE_TARGET | Observe | NOT_APPLICABLE | 2934.32 | 9411.18 | — | Lost in at least one primary period |
| EXPIRY_LATE_FADE_TRAIL | Observe | NOT_APPLICABLE | 3168.22 | 9411.18 | — | Lost in at least one primary period |
| EXPIRY_TREND1445_TARGET | Observe | NOT_APPLICABLE | 9411.18 | 9411.18 | — | No primary-window profit |
| EXPIRY_TREND1445_TRAIL | Observe | NOT_APPLICABLE | 9411.18 | 9411.18 | — | No primary-window profit |
| EXPIRY_OPTION_ACCEL_TARGET | Observe | NOT_APPLICABLE | 1490.78 | 2169.57 | — | Lost in at least one primary period |
| EXPIRY_OPTION_ACCEL_TRAIL | Observe | NOT_APPLICABLE | 1490.78 | 2169.57 | — | Lost in at least one primary period |
| EXPIRY_OPTION_ACCEL_OI_TARGET | Observe | NOT_APPLICABLE | 1427.48 | 2169.57 | — | Lost in at least one primary period |
| EXPIRY_OPTION_ACCEL_OI_TRAIL | Observe | NOT_APPLICABLE | 1427.48 | 2169.57 | — | Lost in at least one primary period |
| ORB30_TARGET | Observe | NOT_APPLICABLE | 1783.70 | 590.13 | — | Lost in at least one primary period |
| ORB30_TRAIL | Observe | NOT_APPLICABLE | 541.49 | 1107.36 | — | Lost in at least one primary period |
| LATE_BREAK_TARGET | Observe | NOT_APPLICABLE | 1198.95 | 232.88 | — | Lost in at least one primary period |
| LATE_BREAK_TRAIL | Observe | NOT_APPLICABLE | 2293.49 | 220.83 | — | Lost in at least one primary period |
| LATE_FADE_TARGET | Observe | NOT_APPLICABLE | 2934.32 | 9411.18 | — | Lost in at least one primary period |
| LATE_FADE_TRAIL | Observe | NOT_APPLICABLE | 3168.22 | 9411.18 | — | Lost in at least one primary period |
| TREND1445_TARGET | Observe | NOT_APPLICABLE | 9411.18 | 9411.18 | — | No primary-window profit |
| TREND1445_TRAIL | Observe | NOT_APPLICABLE | 9411.18 | 9411.18 | — | No primary-window profit |
| OPTION_ACCEL_TARGET | Observe | NOT_APPLICABLE | 1490.78 | 2169.57 | — | Lost in at least one primary period |
| OPTION_ACCEL_TRAIL | Observe | NOT_APPLICABLE | 1490.78 | 2169.57 | — | Lost in at least one primary period |
| OPTION_ACCEL_OI_TARGET | Observe | NOT_APPLICABLE | 1427.48 | 2169.57 | — | Lost in at least one primary period |
| OPTION_ACCEL_OI_TRAIL | Observe | NOT_APPLICABLE | 1427.48 | 2169.57 | — | Lost in at least one primary period |
| NIFTY_SELLOFF_REBOUND_0930 | Observe | WAITING | 9256.78 | 12732.73 | — | Lost in at least one primary period |
| NIFTY_DAY_CONTINUATION_0930 | Observe | WAITING | 3943.12 | 3527.84 | — | Lost in at least one primary period |
| NIFTY_DAY_CONTINUATION_1510 | Observe | WAITING | 16818.43 | 2413.99 | — | Lost in at least one primary period |
| NIFTY_TREND_ALIGNMENT_0930 | Observe | WAITING | 1975.65 | 1920.23 | — | Lost in at least one primary period |
| NIFTY_TREND_ALIGNMENT_1510 | Observe | WAITING | 5359.25 | 2036.96 | — | Lost in at least one primary period |
| SELLOFF_CALL | Observe | WAITING | 7743.70 | 14615.88 | 8453.62 | Lost in at least one primary period |
| SELLOFF_PUT | Observe | WAITING | 7586.71 | 5060.64 | 3744.00 | Lost in at least one primary period |
| RALLY_CALL | Observe | WAITING | 15966.13 | 4005.25 | 8014.13 | Lost in at least one primary period |
| RALLY_PUT | Observe | WAITING | 1396.64 | 5058.63 | 6795.08 | Lost in at least one primary period |
| TWO_SIDED_REVERSAL | Observe | WAITING | 3650.92 | 12511.87 | 8453.62 | Lost in at least one primary period |
| TWO_SIDED_CONTINUATION | Observe | WAITING | 15923.89 | 2404.93 | 3744.00 | Lost in at least one primary period |
| TREND_PULLBACK | Observe | WAITING | 6990.11 | 12961.61 | 8453.62 | Lost in at least one primary period |
| TREND_CONTINUATION | Observe | WAITING | 10002.19 | 6728.72 | 5015.11 | Lost in at least one primary period |

## Important source and execution distinctions

- Twelve unprefixed expiry names are exact aliases of their EXPIRY-prefixed names. Both labels retain the same model result rather than earning two pieces of evidence.
- TREND_PULLBACK_FAST has positive baseline cash in both reused windows but only one modeled filled trade per window. This is a thin research lead, not a robust qualifier.
- TREND1445_TRAIL has an older positive expiry result: 9,411.18 → 31,436.13 over October–March, from only two modeled trades (one win, one loss). Removing its best trade leaves 5,143.23. The newer primary windows had no fills. Its earlier positive result is included in all_retained_evidence; NO_MODELED_PROFIT_IN_PRIMARY_WINDOWS does not mean it never made a modeled profit.
- NIFTY_SELLOFF_REBOUND_1510 failed its later 90-day validation and alternative entry execution scenario. Its earlier attractive results are not the final qualification result.
- Current live exits overlay NET_PROFIT_RATCHET_V1 where recorded. Related NET50 research results are in audit.json; they are not certified exact replicas of every live variant.
- The intraday, multifeature and readiness report guards detect old source receipts after the optional liquidation-hook change. Fresh path-by-path rechecks preserve the old files and reproduce the cached scenarios; stale Monte Carlo source receipts are not promoted to current significance evidence.
- The production NIFTY_DAY_CONTINUATION branch currently asks for prior_trend even though this rule does not use trend to choose direction. This is an unnecessary input dependency, not evidence of alpha.
- _0930 overnight suffixes describe the next-session exit, not a morning entry. Fixed observation windows remain part of the tested hypotheses.
- Original company-event, passive-flow, block/OFS, scheduled-volatility and full cross-market/stock strategies are not implemented by this NIFTY-only registry. Similar labels are not substitutes for their missing catalyst and execution paths.
- No broker order, activation, restart or production-policy change is performed by this auditor.

## Live operational check

Snapshot health: account reconciliation fresh=True; broker API errors=[]; connected sockets=['signal', 'market', 'order']; current completed spot/futures={'spot': True, 'future': True}; option-history readiness={'requested': 10, 'ready': 10, 'loaded': 10, 'failed': 0}. Exact receipt timestamps and errors are retained in audit.json. Socket connectivity is not funded route qualification.

## Research identifiers outside the live registry

Also inventoried **137** research identifiers without their own scanned production entry path: {"ALTERNATIVE_EXIT_OVERLAY": 96, "CONTROL_OR_OTHER_UNIMPLEMENTED_RESEARCH": 7, "MULTILEG_RESEARCH_NO_PRODUCTION_PATH": 7, "ORIGINAL_GAUNTLET_NO_FULL_PRODUCTION_PATH": 9, "STOCK_RESEARCH_NO_PRODUCTION_PATH": 18}. These include exit overlays and controls, not that many independent additional bots.

The original nine gauntlet families are all retained in this external inventory. NIFTY option-acceleration, sector-co-movement and GIFT rules are limited proxies, not complete implementations of full-universe forced-flow, event, passive-flow or cross-market strategies.

OI_SQUEEZE_CASH5 is another historical research lead outside the NIFTY registry: 9,411.18 → 10,342.25 / 10,949.47 across the two reported windows, with 8/9 modeled fills. Its recent best-trade-deletion result falls to 8,552.35 and strict source reconciliation remains UNKNOWN. It is not a funded qualifier.

The original EVENT_CONTINUATION and INTRADAY_EVENT engines were freshly replayed over 21 June–18 September (90 calendar days), including 18 reference/compiled parity cases and 1,998 matched random-side paths. Economic paths match the retained research. EVENT_CONTINUATION has five modeled round trips and UNKNOWN terminal wealth; INTRADAY_EVENT has four modeled round trips and conditional cash 3,453.01. Both full-family bankrolls and strict paths remain UNKNOWN due to coverage gaps. Neither qualifies or has a production entry path. Fresh timestamped receipts are archived under event90_refresh; original historical receipt files were preserved.

[Fresh event replay verification](event90_refresh/verification.json)

[All additional research identifiers](research_not_deployed.csv) · [Their retained scoreboard records](research_not_deployed.json)

[Machine-readable full inputs, costs/evidence and scenario details](audit.json) · [All 137 rows as CSV](strategies.csv)
