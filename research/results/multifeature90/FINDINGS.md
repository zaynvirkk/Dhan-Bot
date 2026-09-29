# NIFTY: two 90-day windows, no demonstrated repeatable edge

Each rule/exit variant starts separately with **INR 9,411.18** in each window.
The earlier period is 23 March–20 June 2026 (59 sessions); the recent period is
21 June–18 September (63 sessions). Each contains 13 NIFTY expiries. These are
retrospective comparisons; the historical dates have already been examined.

Registered 64 variants: six earlier expiry signals with two exits, plus thirteen
additional mechanisms, each split into expiry/ordinary sessions and two exits.
They are not 64 independent mechanisms. Futures price/OI/VWAP and basis, option
OI/IV/skew, three-strike chain flows, bank/IT/VIX, aged GIFT, dated PCR/max pain,
previously published NSE chain data and lagged FII/DII were included where the
actual archive supplied them. Historical availability is not inferred from a
current quote or an advertised API feature.

## Conditional bankroll comparison

These are received-candle model outputs, not verified exchange fills. Use the
[full scoreboard](scoreboard.csv) for every variant and its strict audit status.

| Target-exit variant | Earlier INR | Recent INR | Recent trades | Recent without best |
|---|---:|---:|---:|---:|
| Expiry futures/spot basis lead | 16,177.78 | 8,873.55 | 2 | 6,299.34 |
| Expiry prior-day max-pain escape | 9,411.18 | 16,579.28 | 1 | 9,411.18 |
| Ordinary option-OI unwind | 9,411.18 | 11,908.11 | 1 | 9,411.18 |
| Ordinary three-strike chain unwind | 2,616.71 | 10,843.71 | 9 | 4,961.24 |
| Expiry futures trend | 1,068.77 | 2,781.16 | 7 | 2,141.00 |
| Expiry premium acceleration plus OI | 1,427.48 | 2,169.57 | 2 | 4,816.85 |

No variant has positive net growth in both primary windows. The apparent
recent expiry leader depends on one 4 August trade, on a day with unresolved
source-quality discrepancies. It cannot be credited as an executable winner.
The ordinary chain rule also falls to INR 3,115.61 with five minutes of extra
feature delay, and to INR 5,729.89 with the two-minute order-delay scenario.
These results do not establish that every possible expiry strategy is noise.
They reject selecting these tested definitions for live trading on this evidence.

## Evidence and limits

All 1,536 execution scenarios completed, including strict/reported data modes,
1/2/3-minute order delays, an alternative open-plus-1% fill model, best-trade
deletion with full resimulation, and five-minute additional feature delay.
The report verified cash chronology, whole lots, fees and source/input hashes
across 1,176 primary reported-ledger rows. The 45,908 conditional random-side
paths reuse the original observations; they are not independent new trades.
Minimum unadjusted comparison value is 0.108; minimum Holm-adjusted value is
1.0 across the 64 registered variants per window. None establishes directional
advantage. Prior conversation-wide searching makes 64 a lower bound on the
actual number of strategies considered.

Reported-mode terminal balances can be computed for 46/64 earlier and 52/64
recent variants. The other paths remain UNKNOWN. Strict data checks leave
10/64 earlier and 6/64 recent terminal balances computable, including no-trade
balances; those counts are not counts of profitable strategies.

Retrieved 513,870 exact-option minute rows across 1,362 contract-days, with
complete expected minute counts. NSE daily volume agrees on 1,015 and differs
on 347. Forty contain off-tick OHLC. Cross-broker differences are generally
small (median relative close difference 0.17%), but they are not silently
averaged or repaired. See the [broker inventory](../../multifeature/CAPABILITIES.md)
and [alignment audit](alignment_audit.json).

Only nine sessions returned nonempty historical intraday PCR/max-pain insights.
GIFT has missing observations and an API launch boundary; early institutional
history and one IV-dependent session also leave affected paths unresolved.
Current news, smartlists, fundamentals, Greeks or depth do not establish a
90-day as-of archive. Dhan rolling option expiry identity remains inferred from
the nearest-week request and historical contract schedule.

Whole-lot affordability, fixed pre-fill limits, fees, volume participation,
missed orders, adverse within-minute ambiguity and partial exits are modeled.
Historical bid/ask/queue, actual feed receipt timing and account-specific dated
RMS are not proved. Minute candles cannot distinguish a 1-second entry from a
3-second entry or establish a sub-minute CAS/forced-flow edge. Current fees are
a conservative envelope, not reconstructed historical invoices.

The original nine broad full-universe event/flow families remain separately
scoped and incompletely validated; this NIFTY batch does not claim to finish
90-day full-universe tests of those families. No strategy is certified live.

Fresh read-only Dhan checks returned **INR 9,411.18 available and withdrawable,
zero open positions**. No orders, live activation, account changes, subscription
purchases or deployment were performed.

[All variants](REPORT.md) · [Ledgers](ledger.csv) · [Reproduction](../../multifeature/README.md)
