# Narrow production roster, 15 October

The operator requested keeping the strongest strategies, removing the rest,
and testing alternatives on today's non-expiry session. The selected scanning
roster is `CAS_LAG_V1` and `TREND_PULLBACK_FAST`. The other 135 configurations
are disabled in production configuration. Their source and execution history
remain available for audit; removing a scanner never removes management of an
already open position.

CAS is the only engine with positive recorded funded executions: INR 1,709.36
after reported charges on 13 October. That is one expiry session, not evidence
of a reliably profitable system. The provider currently lists 19 October as
the next NIFTY expiry; CAS cannot open a strategy trade on 15 October.

TREND_PULLBACK_FAST is the strongest ordinary-session candidate in the retained
audit: INR 9,411.18 became INR 9,623.88 and INR 9,500.24 in the two primary
90-calendar-day candle simulations, with only one modeled fill per window.
Those thin results do not establish an edge or historical executable fills.
Its existing rule runs on completed five-minute decisions from 10:00 to 14:45
IST, requiring trend, an opposing pullback, and resumed movement. No thresholds,
entry times, exits, capital allocation or route-probe limits are loosened here.

The operator explicitly selected “Allow real-money testing today” after being
told that the non-expiry candidate had only slightly positive backtests and one
modeled fill per period. Both selected names are therefore funded. This is an
experimental permission, not a claim of established profitability.

The roster-edit command requires both scanning and funded subsets explicitly.
The authorized command is:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python /opt/sablestone-dhan-dashboard/current/ops/activate-profit-exit.py --apply --retain 0.50 --scan-only CAS_LAG_V1 TREND_PULLBACK_FAST --funded-only CAS_LAG_V1 TREND_PULLBACK_FAST
```

The tool verifies the release,
reconciles existing obligations, changes the two lists atomically, and preserves
the existing mandate and cash caps. It does not itself submit broker orders.

The new tests reject implicit funding, duplicate/unsupported/empty scanning
rosters, removed funded names and ambiguous multiline assignments. They also
check idempotence and preservation of unrelated tables and money limits.

The active dashboard board follows the trading service's explicit roster.
Removed names cannot reappear there through the older read-only monitor or
retained evaluation rows. Actual results and dated session-log entries remain
visible, including the disabled PCR engine's loss. The browser regression checks
that distinction; the legacy observer-only dashboard still works without a
configured trading roster. This display change does not restart the qualified
funded trader or change its covered Python source.

For the complete comparisons and limitations, see
[`strategy_inventory_20261015/REPORT.md`](../research/results/strategy_inventory_20261015/REPORT.md).
