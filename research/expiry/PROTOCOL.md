# NIFTY expiry search — registered 20 September 2026

This is a new, bounded research batch following the unsuccessful gauntlet.
It does not inherit a profitable-strategy claim. No broker orders are permitted.
Initial capital is INR 9,411.18; the current account balance is a separate fact.

## Periods and selection

- Development: 20 July–18 September 2026, already contaminated by prior research.
- Recent retrospective validation: 1 April–30 June 2026.
- Older retrospective validation: 1 October 2025–31 March 2026.
- July 1–19 is excluded. All actual NIFTY expiries in these periods are included,
  including holiday-adjusted dates. Nothing is selected by a profitable outcome.
- Freeze six signals and two exits below (12 trials) before reading new returns.
  Validation periods are opened only after implementation tests pass. They are
  retrospective checks, not a substitute for future shadow execution in the new
  CAS regime. No tuning against their results is allowed in this batch.
- One independent bankroll per variant/period. Also replay all dates
  chronologically without resets. Only the first signal per strategy/day is
  eligible; a missed/unaffordable order does not earn a later replacement.

## Signals, using completed one-minute bars

1. ORB30: 09:15–09:45 opening range. First two consecutive closes beyond the
   range by at least 5 points, decision 09:47–12:00. Buy breakout direction.
2. LATE_BREAK: same two-close rule against the fixed 14:15–14:30 range,
   decisions 14:32–15:14 (15:24 before CAS).
3. LATE_FADE: after a close at least 5 points outside that afternoon range,
   first two consecutive closes back inside it; buy against the initial break.
4. TREND1445: at 14:45, absolute 15-minute return >=0.1%, same-signed
   60-minute return, and absolute net / sum of absolute one-minute changes
   >=0.60 over those 15 minutes. Buy that direction.
5. OPTION_ACCEL: fix the ATM strike using the spot close observable at 14:45.
   From 14:45 to ten minutes before derivative close, first CE or PE at that
   fixed strike with premium +25% over three minutes and three-minute volume
   >=2x median of ten preceding nonoverlapping three-minute volumes. At a tie
   choose larger three-minute premium return, then CE. No future ATM rolling.
6. OPTION_ACCEL_OI: same but OI must fall >=8% over three minutes. This is
   an ablation of the old forced-flow idea, not proof that shorts caused buying.

Regular spot is used only through 15:15 after CAS begins. The option signals
use their fixed 14:45 strike thereafter, not a fabricated indicative index.
Missing any required feature is UNKNOWN, never a no-signal success.

## Contracts, orders, exits

NIFTY expiry-day long options only. Prior-session official contracts define
availability; exact expired-contract metadata must agree on lot/strike/expiry.
Select ATM then up to three outward strikes on the signal side, using prices,
OI and volume already available. ATM ties choose lower strike. Option signals
retain their fixed 14:45 anchor. Never use a future premium to choose/resize.
95% of cash including entry fees; whole lots; limit = prior completed close
plus 5%, rounded up; minimum 10 lots OI; capacity <=5% of EACH previous three
minute volumes. Quantity stays fixed. Missing closer-strike data stops the
selection as UNKNOWN rather than picking a conveniently available farther one.

Primary modeled entry: next full minute after a one-minute processing delay,
at that minute's high, only if <= frozen limit and quantity <=5% volume.
Alternative entry scenario: that minute's open plus 1%, same gates.
Latency sensitivity: two and three full minutes. Minute bars cannot identify
1/3/5-second execution quality or actual bid/ask fills.

Both exits start with a 50% premium stop. Exit A has a resting 2x target;
exit B has no target and raises the stop to 50% of the highest COMPLETED bar
close since entry. Stops have adverse precedence if both stop and target could
occur in one minute. Entry-minute targets are never credited; entry-minute
stop ambiguity is resolved adversely. Stop/timed liquidations use bar LOW
minus 1%, rounded down; target requires trade-through by 2%. All exits require
5% volume capacity; insufficient volume leaves a pending exit, not a fill.
Begin forced liquidation six minutes before session close; no settlement
profit credited. Any unresolved position makes terminal bankroll UNKNOWN.
Historical close: 15:30 before 3 August 2026, 15:40 thereafter. MARGIN product
is assumed, not INTRADAY auto-square-off. Broker RMS/depth remain unverified.

Use the existing conservative current Dhan/NSE fee envelope on every period,
including earlier periods with lower taxes. This is a disclosed cost stress,
not a claim of historically exact invoices. Charge each freeze-size child;
all cash uses Decimal. Data-volume reconciliation is an archive audit only,
never a signal. No unverified zero-volume filling of missing candles.

## Noise and qualification

Report all 12 trials, counts, missed orders, unknowns, cash, drawdown, costs,
2x exits, latency and alternate-fill sensitivity. Add fixed CE/PE at 14:45
controls. For each signal, randomized CE/PE controls keep decision times,
contract selection, fees and compounding identical. Best-trade deletion means
rerunning with that entry removed, not subtracting terminal P&L.
Use day-level paired/randomization inference, show sample size and adjust
the 12 comparisons with Holm; never treat Monte Carlo paths as independent
market observations. Positive development alone cannot qualify a strategy.
No live eligibility without positive independent validation, resolved data,
robust execution stress and prospective quote/order-lifecycle evidence.

## Archive diagnostic, added before opening any strategy returns

Collection found full 375-minute contracts whose summed volume differs from
official NSE volume (including a one-lot difference out of billions of units).
The strict replay remains unchanged and stops at relevant unverified data.
Also run a **reported-candles diagnostic**, retaining every available bar and
every losing trade, allowing volume mismatches but NOT missing minutes,
identity errors or missing metadata. Record each mismatch in the dataset and
each result's quality policy. This is conditional model performance, not an
exactly reconciled or live-eligible result. No tolerance threshold is optimized
and no unfavorable trade is removed to make this diagnostic pass. Apply the
same policy to all baselines, execution sensitivities and random-side controls.
