# 15 October: morning decisions and the no-trade explanation

Cutoff: 12:02 IST. This is an audit of actual recorded observations, configuration
and current broker reads, not a strategy backtest or an oracle profit estimate.

At 12:01 IST, Dhan reported INR 7,805.94 spendable cash, no open position and no
pending order. The two orders today were route qualification attempts with zero
fills. The funded trader was still PID387657, zero restarts, source ab11f4a,
verified against its own immutable release. Authority enabled; route qualified;
all three sockets connected, fresh reconciled account and completed spot/futures
inputs. No incident or unmanaged lifecycle was recorded. Read-only dashboard
57023b4 was deployed independently.

Only CAS_LAG_V1 and TREND_PULLBACK_FAST have funded permission. CAS is ineligible
on this session; the loaded next NIFTY expiry is 19 October. The pullback engine
uses its existing completed five-minute decisions from 10:00 to 14:45. We did
not change that researched rule into a continuous momentum entry.

## Actual pullback decisions, 10:00–12:00

There are 25 distinct completed NO_SIGNAL decisions, no SIGNAL decision, and six
additional UNKNOWN receipts for a missing completed bar. Eight NO_SIGNAL checks
had a sufficiently large 30-minute move but no opposing ten-minute pullback.
Seventeen had a 30-minute move below the 0.25% threshold. All scheduled boundaries
in that period have a recorded NO_SIGNAL; the extra warnings remain visible and
are not represented as successful checks.

For example, 10:20 recorded a +0.4509% trend and +0.0498% ten-minute movement:
both pointed up, so the required opposing pullback was absent. At 11:10 the
ten-minute move was negative, but the 30-minute trend was only +0.0572%, below
threshold. At 12:00 trend was +0.0821%, also below threshold. There is no recorded
qualifying funded pullback setup for an affordability or fill gate to reject.

Before 10:00 this engine's entry window had not opened. Zero signals within its
window does not imply that buying calls earlier could not have made money.

## Other observed setups

Thirteen previously scanned configurations across six families recorded bullish
setups around 09:55–10:10: OPEN_DRIVE (three exit variants), FUTURE_TREND,
IV_CHEAP_TREND, SECTOR_CONFIRM, PCR_CONFIRM and INSTITUTIONAL_ALIGN (two exit
variants each). Their saved execution assessments all say FUNDED_STRATEGY_DISABLED.
The configuration records are correlated variants, not thirteen independent bets.
They had no chosen-contract affordability/depth checks recorded. They cannot
establish a missed executable profit; enabling them retrospectively would select
today's winners after the move. The other 135 configurations were subsequently
removed from the scanning roster under the operator's instruction to keep only
the strongest candidates. Their historical observations remain intact.

## Coverage and limits

The audit queried observation primary-key ranges for each registered strategy on
this date, and the allowlisted signal/assessment metadata. It did not scan or
export the full private ledger, place a test trade, reset a cap, or restart the
funded service. API/account/feed facts are timestamped live reads, not inferred
from the dashboard banner. The dashboard now reads the same dated checks so
the last completed explanation survives reloads.

The evidence supports no ignored qualifying signal in the current two-engine
roster through this cutoff. It does not support “no good trade existed anywhere”
or a guarantee of profitability. A full opportunity comparison needs the exact
option selected using information available at each signal, receipt latency,
then available depth, real costs and all failures. Candle highs or the later
index rally cannot supply those missing execution facts.
