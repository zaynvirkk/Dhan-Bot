# Rebound deployment qualification — 27 September 2026

**Decision: NO LIVE QUALIFIER. Do not deploy the rebound strategy with funded authority.**

The unchanged selloff signal fails its registered additional 90-day validation and an alternative
entry-price scenario. The original favorable results remain reproducible but do not establish
a repeatable execution edge. No live orders, deployment, cloud changes or spending occurred.

Each period starts independently at INR 9,411.18. Additional validation is 23 December 2025–
22 March 2026 (61 sessions); discovery periods are 23 March–20 June (59) and 21 June–
18 September (63). The additional period is previously unscored strategy history; some
underlying bars existed as prior warm-up. It is not prospective evidence.

| Execution scenario | Additional validation | Earlier discovery | Recent discovery |
|---|---:|---:|---:|
| primary | 8561.91 | 14663.22 | 16762.25 |
| delay3 | 8636.68 | 10048.67 | 16638.71 |
| slippage2 | 8363.76 | 14159.69 | 16088.54 |
| open_plus_1pct | 8496.89 | 8255.83 | 17389.75 |
| dated_fees | 8570.94 | 14663.22 | 16762.25 |
| delete_best | 5502.49 | 10029.17 | 9592.86 |
| strict | UNKNOWN | UNKNOWN | UNKNOWN |

## What changed and what failed

V2 monitors every completed option minute through the effective derivatives close (15:30
before 3 August, 15:40 thereafter), including late triggers and pending orders carried
across the closed session. This correction leaves both original base balances unchanged.
The signal threshold, contract order and sizing were not optimized.

The earlier open-plus-1% scenario fills the 29 May call that the adverse-high model rejects.
That trade loses INR 6,959.89; final cash is INR 8,255.83. A pessimistic price on each
accepted trade is therefore not a conservative bound on strategy returns: it can also
remove losing trades. This execution sensitivity is a material failure of qualification.

The added validation has twelve selloff dates, three modeled fills, one win and two losses.
Nine dates cannot afford a qualifying lot under the known price/volume rules. Dated fees
raise the validation balance only slightly; they do not rescue the result.

## Noise controls

999 seeded CE-entry date assignments per period match 15:10, exact calendar days to expiry
and a prior-only 20-session volatility tercile. All dates are selected without option
outcomes; signals face the same whole-lot cash and occupied-position rules. These are
conditional randomization diagnostics, not independent market samples or causal proof.

| Period | Controls at least as good | Unresolved | Smoothed tail | Adjusted upper (144 tried variants) |
|---|---:|---:|---:|---:|
| validation | 62/999 | 0 | 0.063 | 1.000 |
| earlier | 328/999 | 0 | 0.329 | 1.000 |
| recent | 95/999 | 0 | 0.096 | 1.000 |

Random assignment assumes comparison within the stated matching groups is meaningful;
it does not eliminate all regime dependence. Failed profit gates stand independently of
these control scores. No significance or live-profit claim is made.

## Independent Dhan reconstruction

| Period | Dhan base | Dhan dated fees | First unresolved boundary |
|---|---:|---:|---|
| validation | 8630.12 | 8639.15 | none |
| earlier | UNKNOWN | UNKNOWN | ['2026-06-01', 'ValueError:UNKNOWN_HOLDING_BAR:2026-06-01T15:21:00+05:30'] |
| recent | 16837.00 | 16837.00 | none |

Signal dates remain based on the frozen Upstox underlying tape. This is an independent
option-path reconstruction, not an independent market sample.

Dhan rolling observations are matched to actual timestamp, strike and prior-published
expiry mapping. Different strike streams are never treated as one contract. Returned
observations outside the requested calendar day are retained in raw receipts and excluded
from that day’s reconstruction. Non-near expiries have only ATM ±3 coverage; remaining
holes are UNKNOWN. Duplicate disagreements stop reconstruction. Daily official volume,
tick and high/low audits remain separate from the conditional scenario.

Neither broker supplies historical executable order-book receipts here. The result is
not repaired merely because a second vendor produces a similar profit number.

## Operational evidence and remaining work

The read-only cloud check confirms the VM is running the old CAS revision with live
authority disabled in configuration and mandate, and the broker read-only interlock enabled.
It reports RECOVERING; cached-token
profile/funds/positions/orders/trades/IP reads return HTTP 400 DH-906. No daemon restart
or credential persistence was performed. These operational gaps remain unresolved.

Because the research gate failed, the conditional production integration and funded
deployment steps were not executed. Full-session handling is tested in the research
replay; it is not an installed overnight trading strategy. No prospective shadow fills
are claimed from Sunday checks. A future candidate needs new predeclared validation,
actual market-hours observations and a separately approved concrete deployment.

## Verification and sources

123 resolved scenario trade rows pass cash, whole-lot, fee, limit, chronology and expiry checks.
All raw inputs are hashed; original broader-experiment files remain unchanged.
[Registration](registration.json), [scoreboard](scoreboard.csv), [ledger](ledger.json),
[controls](controls.json), [cloud check](cloud_check.json), [fresh API check](api_check.json),
[software checks](software_tests.json), [protocol](../../rebound_validation/PROTOCOL.md).

Fee revisions: [NSE FA73061](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf)
and [NSE FATAX73524](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf).
The dated scenario uses their effective dates with conservative component rounding;
it remains a fee model, not an actual broker invoice. Production and parent fee policy
were not modified. [Dhan rolling-data limits](https://dhanhq.co/docs/v2/expired-options-data/).

Source SHA-256: `455b17342bc542b901616c0b0e4f0f71acb0b3556ea7bd107de67364c8e51563`
