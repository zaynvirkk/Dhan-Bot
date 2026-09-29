# Additional NIFTY expiry validation

**No live-qualified strategy.** The unchanged 14:45 trend candidate failed its additional-year check. All amounts below are conditional reported-candle model balances, not actual executions.

| Variant | Additional 53 expiries | Full 101-expiry chronology | Full path deleting best trade |
|---|---:|---:|---:|
| TARGET | 5,099.55 | 4,981.99 | 2,817.04 |
| TRAIL | 5,099.55 | 15,938.86 | 2,817.04 |

Initial cash: INR 9,411.18. Extra period: 1 October 2024–30 September 2025; full path appends the original 48 expiries, retaining its predeclared July 1–19 exclusion. There are five signals and three closed trades on the full primary path. No bankroll resets, hindsight replacement of missed orders or borrowing a later winner to repair an earlier loss.

| Conditional random-side comparison | Raw tail probability | Twelve-trial bound |
|---|---:|---:|
| extension TREND1445_TARGET | 1.0 | 1 |
| extension TREND1445_TRAIL | 1.0 | 1 |
| all TREND1445_TARGET | 0.496 | 1 |
| all TREND1445_TRAIL | 0.429 | 1 |

Each row uses 999 simulations, not 999 independent market histories. These preserve signal times and test direction/selection conditionally. The candidate was chosen after the original twelve tests; selection is disclosed and the twelve-trial bound is retained.

The full trailing path remains positive under the modeled delay scenarios, but that does not repair the concentration in one January 20 trade or the negative additional-year result. Only three trades over 101 expiries cannot establish repeatability. Strict reconciled paths remain UNKNOWN because the relevant option archives differ from official daily volume. Minute bars do not establish historical depth, actual fills or second-level latency.

No strategy parameters were changed. The two exit styles are the original registered alternatives. Raw results include every execution scenario, quality policy and control; ledger.csv records the full primary cash paths. No real orders were submitted.

Base source SHA-256: `681d142dbb1819b7aa61b0b52230cc189cbf4c61580e391fb0d1bf5a3e112200`.
Additional data SHA-256: `9a0ddc53799c9748665dd9337e2544b7fb94873e3f55b88794f9b628aead14f9`.
