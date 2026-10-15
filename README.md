# SableStone Dhan CAS bot

**15 October seconds experiments:** five quote-driven engines now have shared-OMS
entry/exit implementations and a separate live-data simulator. Financial activation
remains an operator-run step. [Rules, limits and activation](docs/SECONDS-STRATEGIES-2026-10-15.md).

**15 October compact dashboard:** Live, History and System are separate views.
The default view shows money, the current decision and compact strategy checks;
actual completed trades, holding times and net results have their own history.
[Scope and validation](docs/DASHBOARD-LIVE-VIEWS-2026-10-15.md).

**15 October narrowed roster:** the selected production scan is CAS_LAG_V1 plus
TREND_PULLBACK_FAST; the other 135 configurations are disabled, with their history
retained. The operator explicitly authorized real-money testing of the non-expiry
candidate today; both selected names are funded. See the
[roster and evidence limits](docs/STRATEGY-ROSTER-2026-10-15.md).

**13 October strategy expansion:** the production registry now covers 137 NIFTY
configurations across 41 rule families plus CAS. Shared-capital selection uses
already closed executions, with unknown profitability explicitly unranked;
unfillable signals no longer starve other engines. The dashboard groups families
and exposes their actual inputs. Stock/event and multi-leg research still have
no NIFTY order path. Deployment evidence is recorded in the
[expansion record](docs/STRATEGY-EXPANSION-2026-10-13.md).

**13 October complete strategy audit:** three implemented NIFTY engines are enabled;
CAS has 16 filled closed lifecycles / 32 executed orders / 69 partial fills.
The original nine gauntlet families and 175 research identifiers have no production
order path. Final net profit remains unknown until charges are published.
Read-side release `bde7887` refreshes diagnostics every ten minutes, distinguishes
closed position records from open exposure, and labels closed-session history.
The funded trader remains unchanged.
[Full audit and strategy inventory](docs/STRATEGY-LIVE-AUDIT-2026-10-13.md).

**13 October afternoon: real strategy executions confirmed.** The funded auction
engine begins filling real Dhan orders after the provider opens CAS. At 15:28
IST cash is INR 10,697.52, positions zero, recorded fill count 69, Dhan realised
P&L INR 2,791.75 and unrealised P&L zero. These are live snapshots, not final net
profit after all charges or proof of repeatability. Dashboard release `702fbea`
separates current live frames from auction-entry eligibility and shows the
provider's closed auction explicitly, removing false market-data outage warnings
while preserving actual stale-feed warnings. At 15:43 IST the signed-in page
shows a current idle session, the closed auction and enabled authority. The
funded process remains unchanged and enabled.
[Live execution and browser evidence](docs/LIVE-TRADING-2026-10-13.md).

**13 October: missed-entry audit and selector repair deployed.** Funded release
`197c4f8` runs all three strategies with enabled real-money authority and fresh
broker-route proof. At 11:36 IST cash is INR 8,822.36, with zero positions and
strategy fills. Yesterday's 15:10 CALL signal was real; all four permitted
next-expiry contracts exceeded its INR 8,381.24 entry budget. The selector now
skips known unaffordable contracts before requiring their live quote. The
dashboard retains qualifying signals and recorded rejection reasons, with older
missing reasons explicitly unknown. Local/VM funded verification passes 452
tests; no profitability is established. Dashboard transport releases `ea03527`
and `eeb1b5` are deployed without restarting the qualified trader; browser-verified
history loads in 1.75 seconds with roughly 28 KB transferred instead of 723 KB.
Read-only diagnostic release `e381a83` also removes parser-induced socket
timeouts; all seven actual connection checks pass at 12:16 IST. The funded
trader remained on its qualified release with zero restarts through these midday
checks; the subsequent auction executions are recorded above.
[Market, affordability and deployment evidence](docs/LIVE-ENTRY-AUDIT-2026-10-13.md).

**12 October: funded order route recovered and browser-verified.** Release
`687d733` is running all three configured strategies with enabled real-money
authority and current broker-route proof. Qualification can recover during the
verified open session before the 15:10 rebound decision. The operator authorized
one additional route attempt; existing INR 100 session / INR 500 lifetime probe
cash caps and capital allocation are unchanged. At 13:40 IST cash is INR
8,822.36, both today's qualification orders are cancelled with zero fills, and
there are no positions or strategy fills. This establishes execution readiness,
not profitability. [Repair and live evidence](docs/ROUTE-RECOVERY-2026-10-12.md).

**12 October: money-first dashboard deployed.** Available cash, recorded fills,
positions and reported P&L lead the overview. The unverified order route is shown
as the entry blocker; routine unmet signals say Not met, with expandable inputs.
Release `810add3` is browser-verified on desktop/mobile. The funded trader remains
armed on `c57221f`, with zero fills and route qualification still pending.
This does not establish a profitable edge. [Live state and changes](docs/MONEY-DASHBOARD-2026-10-12.md).

**12 October: native Dhan order-status parser repaired and deployed.**
The actual lower-camel WebSocket `status` field was omitted, preventing route
qualification despite a cancelled zero-fill probe. Release `c57221f` is running
with all three funded strategies; 438 tests, 60 acceptance cases and 15 mutations
pass locally and on the VM. No strategy trade has filled. Route proof remains
pending after restart because today's one-probe allowance is already used.
[Live findings and repair](docs/ORDER-STATUS-REPAIR-2026-10-12.md).

**8 October: decision explanations deployed and browser-verified.**
Strategy rows show each condition's actual value, threshold and passed/failed/
unavailable result, the next calendar-confirmed check and the last completed
decision with its inputs. Missing data cannot appear as a passed condition.
All 432 tests, 60 included acceptance cases and 15 mutation checks pass.
Dashboard/collector/daily monitor release `3792d85` passes 78 VM checks and
authenticated desktop/mobile inspection. Older retained decisions expose their
recorded numeric inputs too. Funded strategy authority is shown separately.
[Change and verification record](docs/DASHBOARD-EXPLANATIONS-2026-10-08.md).

**7 October: daily live-data monitoring and a funded-service upgrade are prepared.**
The data subscription is Active again. Real API checks exposed and fixed decimal
candle-number parsing and the separate cash/derivatives closing boundaries.
The read-only daily monitor evaluates morning gap-fade and afternoon rebound,
with distinct dashboard rows and history. The older funded CAS service requires
the operator upgrade command; publishing the dashboard does not activate daily
orders. [Deployment details and operator command](docs/DAILY-MONITOR-2026-10-07.md).

**6 October: explicit session engines added.** Gap-fade and overnight rebound
now have separate runtime rules and persistent position ownership beside CAS,
with a shared bankroll and order manager. Date-specific exchange calendars and
contract metadata govern eligibility. That change was published as `a40af75`; the
read-only dashboard and history collector were deployed on 6 October. The funded
trader remains on `5596c5d`, running CAS only; gap-fade and rebound are not active.
These remain experimental strategies. See the [deployment receipt](docs/DASHBOARD-DEPLOYMENT-2026-10-07.md) and
[integration and verification notes](docs/SESSION-STRATEGIES-2026-10-06.md).

**28 September: execution and capital search expanded.** Tested resting-limit
policies, calls/puts in both directions, trend filters and three allocations:
24 combinations / 504 scenario paths across three reused 90-day windows.
No combination profits in every base window. Broader margin checks include
24 index verticals and small commodity contracts; Gold Petal fits the current
cash snapshot, which does not establish profitability. Ten cash intraday
4x long/short probes also fit current cash. [Results](research/results/execution_frontier/REPORT.md)
and [coverage inventory](research/execution_frontier/RESEARCH.md).

**27 September: rebound deployment qualification fails.** The added 90-day
period (23 December–22 March) ends INR 8,561.91, or INR 8,570.94 with dated
fees, from INR 9,411.18. Full-session monitoring preserves the two favorable
discovery results, but the earlier alternative entry model ends INR 8,255.83
after admitting a large losing trade skipped by the adverse-high model.
Matched-date controls do not establish an edge. Funded authority stays
disabled; the existing CAS cloud daemon is not a rebound implementation.
[Qualification evidence](research/results/rebound_validation/REPORT.md).

**27 September: broader search produces a stronger conditional candidate.**
NIFTY overnight selloff-rebound with next-afternoon exit ends INR 14,663.22 /
16,762.25 in two separate 90-day windows, independently starting INR 9,411.18.
This beats the previous recent record, but only nine modeled trades, reused
samples, inconclusive adjusted noise tests and unresolved strict data audits
prevent funded qualification. Completed 26 variants / 260 scenarios / 3,996
controls; 227 software tests pass. [Results and ledger](research/results/broader/REPORT.md).

**27 September: intraday challenger search completed.** Thirty registered
variants across two 90-day windows produce a new conditional recent-period
leader: gap-fade, INR 9,411.18 → INR 12,566.43 (four trades, three wins).
Earlier window: INR 7,544.54; recent delete-best: INR 9,275.76; three-minute
delay: INR 3,780.44. Of 999 matched-time random-side paths, 120 do at least as
well. This improves the historical leaderboard without qualifying a funded
strategy. [Comparison and ledger](research/results/intraday_challengers/REPORT.md).

**27 September 2026: final bounded research pass complete; keep funded trading
disabled.** Eight additional late-expiry/volatility variants, 112 scenarios
over two 90-day windows and fresh read-only margin checks produce no qualified
winner. All 209 tests pass. The account still has INR 9,411.18 and zero
positions. [Final findings](research/results/finalsearch/REPORT.md) and
[broader mechanism review](research/finalsearch/RESEARCH.md) distinguish
conditional backtests, capital constraints and untested approaches. No live
order, deployment or cloud configuration change was made.

**21 September 2026: no strategy qualifies for funded activation.** F&O is
approved and the Dhan account holds INR 9,411.18. The existing cloud daemon
remains read-only; its cached credential is invalid. Fresh account reads with
the active credential succeed from the VM. See [release readiness](docs/RELEASE-READINESS.md)
and the [latest event-family replays](research/results/event90/FINDINGS.md).
The 90-day intraday event model loses money; the overnight event model stops
at an unresolved exit. Neither qualifies. A later authentication recheck also
finds inconsistent renewal responses. A later direct production-authentication
check verifies the funded account; unattended renewal remains unresolved.

Dhan executes the orders and supplies five-level option depth, positions,
fills and cash. Upstox V3 supplies the official `NSE_INDEX|Nifty 50` CAS status
and IEP. The governing strategy is [CAS_LAG_V1](docs/BUILD-DEPLOY-PLAN.md).

The service runs one `AUTO_LIVE` state machine. It recovers broker state first,
loads current expiry/lot/tick/freeze data, qualifies the order route before CAS,
freezes the pre-auction reference and evaluates individual option lag. It sizes
to finite depth and the standing bankroll rule, manages partial fills, exits,
adds and fresh reversal/re-lag lifecycles. A SQLite FULL/WAL ledger commits
intent and reservation before each POST; ambiguous sends are reconciled, never
blindly retried. New-entry disarming leaves reduction and settlement recovery
available. PIN/TOTP tokens are cached privately and renewed before expiry.

Official dated final-index publications can authorize post-stop residual
entries. Missing timely final publication leaves that capability unavailable.
Unmatched expiry credits remain settlement receivables and cannot finance a
new lifecycle. No fixture establishes that a future opportunity, fill or
profit will occur.

## Installed Google Cloud service

The project, VM, permanent IP, protected configuration and commands are in
[the deployment guide](docs/CLOUD-DEPLOYMENT.md). The environment is already
configured. Deployment alone does not enable real-money orders.

After a qualifying strategy is implemented and the operator separately approves
funded deployment, the activation mechanism on the VM is:

```bash
sudo /opt/sablestone-dhan-cas-bot/.venv/bin/python \
  /opt/sablestone-dhan-cas-bot/ops/activate-live.py --capital available
```

`available` allocates the reusable cash reported by Dhan at activation; an
exact rupee amount can be supplied instead. The helper checks the account,
funds, static whitelist, source verification and credentials before changing
configuration. It refuses to reset an existing trading ledger. Add
`--check-only` to check prerequisites without activating. Activation enables
automatic real orders, including the bounded pre-CAS route probe.

Subsequent decisions use the frozen lifecycle bankroll: below ₹40,000, at
most min(bankroll, ₹10,000); otherwise 25%, including entry fees. Partial exits
do not replenish the lifecycle allowance. Reconciled gains can finance a new
lifecycle according to the mandate.

## Development verification

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps -e .
.venv/bin/python -m pytest -q
.venv/bin/dhan-cas verify --state-dir state
```

`verify` runs the complete suite, including a production service connected to
local HTTP/WebSocket brokers, then injects fifteen execution defects into isolated
copies and requires the tests to reject them. Its source digest covers the
Python implementation, generated protobuf, schema, tests, dependencies and
operation scripts. This is software evidence, not a live broker-route receipt.

Secrets belong only in `.env` locally or `/etc/sablestone-dhan/secrets.env` on
the VM, never in Git. Dhan authentication uses PIN/TOTP to obtain the access
token required by its REST and WebSocket APIs; a manually supplied token is
supported for development but not unattended activation.

## Private monitoring dashboard

The authenticated dashboard shows account observations, entry authority, connection
checks, positions, orders and persisted fills. Deployment and operator activation
instructions are in [the dashboard guide](docs/DASHBOARD.md). Install it separately
with `./ops/deploy_dashboard.sh`; the script leaves the trader's release and
trading authority unchanged. The target URL is
`https://dhan.34.100.255.111.sslip.io`; HTTPS, login and live account observations
were verified on 30 September 2026. See the [deployment receipt](docs/DASHBOARD-DEPLOYMENT-2026-09-30.md).


The 1 October streaming optimization changes are local pending a network-capable
verification run. See [implementation and validation](docs/STREAMING-OPTIMIZATIONS-2026-10-04.md).
The frontend lifecycle tests require Node.js 18+ in addition to the Python test
environment; the VM/dashboard installers include the `nodejs` package.
