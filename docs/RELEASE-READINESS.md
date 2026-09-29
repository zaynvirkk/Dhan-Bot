# Release readiness — 27 September 2026

## Subsequent 28 September execution/capital expansion

No funded qualifier after 504 scenario attempts across calls/puts, symmetric
continuation/reversal, prior-trend filters and three allocations. Fixed
resting-limit entry scenarios remove the earlier whole-minute-high exclusion;
the 95% rebound path ends INR 8,453.62 / 7,743.70 / 14,615.88 across the three
reused 90-day windows. All 260 software tests pass; this is not profit proof.

Fifty-six read-only current margin checks now cover index/stock/commodity
futures, 24 narrow verticals and ten cash intraday positions. All ten sampled
cash long/short positions at roughly 4x bankroll notional fit, requiring
INR 7,356–7,503.12 each. Gold Petal also fits; sampled index/stock futures and
verticals do not. Earlier authentication failures remain recorded, followed
by a successful identity-checked cash probe. Historical cash margin and
eligibility, strategy outcomes and actual fills remain unverified. No orders
or cloud changes. [Full results](../research/results/execution_frontier/REPORT.md).

## Current rebound qualification

**NO LIVE QUALIFIER.** The rebound candidate fails the registered additional
90-day test (23 December–22 March): INR 9,411.18 becomes INR 8,570.94 with
dated fees. The earlier alternative entry model ends INR 8,255.83; it admits
a May 29 losing trade that the adverse-high scenario omits. Neither full
session monitoring nor dated costs rescues qualification. Matched-date
controls do not establish a repeatable edge. See the
[new evidence](../research/results/rebound_validation/REPORT.md).

Independent Dhan option reconstruction also loses in the additional period,
ending INR 8,639.15 with dated fees. Software verification passes 245 tests;
that confirms implementation behavior, not an economic edge.

A fresh 27 September read-only cloud check confirms the existing Mumbai VM
is RUNNING at its reserved IP. Installed revision is still d5efcfd; mandate
and config authority are false and DHAN_BROKER_READ_ONLY remains set. State
is RECOVERING, route unverified, and cached-token account reads return
HTTP 400/DH-906. No source, token, service or configuration was changed.
[Cloud receipt](../research/results/rebound_validation/cloud_check.json).

The separate local read-only preflight succeeds with a freshly authenticated,
identity-checked credential: INR 9,411.18 available and zero positions, orders
or trades. Profile, funds, account collections, IP whitelist and option chain
return HTTP 200; the VM IP is whitelisted. Upstox market status also returns
HTTP 200. This Sunday snapshot does not prove market-hours fills, order-route
latency or unattended cloud renewal.
[API receipt](../research/results/rebound_validation/api_check.json).

The proposed rebound runtime was conditional on strategy qualification.
That economic gate failed; no overnight trader was installed, no prospective
shadow execution is claimed and no funded approval is requested. The earlier
CAS implementation and its operating reference below remain separate.

## Preserved 21 September assessment

**No strategy is approved for funded activation.** F&O eligibility is now
confirmed. The remaining obstacles are strategy evidence, historical execution
coverage and operational credential recovery, rather than segment approval.
The operator requested a separate approval question only after a concrete
strategy and deployment pass review. That condition has not been reached.

## Research decision

The [90-day event extension](../research/results/event90/FINDINGS.md) is now
complete for two bounded attachment-category variants. INTRADAY_EVENT's
primary conditional model ends at INR 3,453.01 from INR 9,411.18. Its alternative
execution scenarios also lose money, and 665/999 random-side paths do at least
as well. EVENT_CONTINUATION reaches INR 3,913.33 after five closed trades,
then stops at an unproven exit of one 175-unit L&T option lot. Its final
bankroll remains UNKNOWN. Neither result supports a deployment choice.
The extension includes 1,998 controls and nine independent full/compiled
replay comparisons per engine. Reused dates, three missing ban records,
ambiguous filings and inconsistent option tapes prevent full-family proof.

The [new experiment](../research/results/readiness/REPORT.md) adds 16 NIFTY
expiry/ordinary variants to the earlier 64. Each has a separate INR 9,411.18
bankroll in each of two 90-calendar-day windows, 23 March–20 June and
21 June–18 September 2026. Those windows have 59/63 sessions and 13 expiries
each; they are reused retrospective periods, not independent holdouts.

Across these two batches there are 1,856 execution scenarios and 59,880
conditional random-direction paths. No evaluable candidate is profitable in
both primary windows. The new batch's minimum Holm-adjusted directional
comparison is 1.0. In its strict mode, only 6/16 variants per window have a
complete terminal path, including no-fill cases; others remain UNKNOWN.
Current quotes cannot repair missing historical execution records.

The original nine broad families still lack complete 90-day full-universe
validation. CAS indicative-price/order-book histories and prospective
performance are also missing. The earlier conversational EVENT_CONTINUATION
ranking was a hypothesis and is not a validated deployment choice.

## Fresh real API and cloud observations

An evening recheck at approximately 16:01 UTC on 21 September again receives
Upstox market status successfully, with the market closed. Dhan application
renewal rejects the authentication response at its account-identity gate.
A separate bounded diagnostic returns a matching identity and token field;
the next session-helper renewal still fails. A final instrumented call through
the unchanged production authentication function succeeds with matching
identity, then verifies INR 9,411.18 available and zero positions at 16:05 UTC.
This does not establish reliable unattended renewal or cloud cache coherence.
No rejected token is accepted.
See [initial recheck](../research/results/event90/account_recheck.json),
[sanitized diagnostic](../research/results/event90/auth_response_diagnostic.json)
and [application follow-up](../research/results/event90/account_recheck_followup.json),
plus the [successful final account check](../research/results/event90/auth_async_diagnostic.json).
The account/VM observations below are earlier, separately dated checks;
they do not by themselves establish consistent unattended renewal.

Read-only checks ran on 21 September IST while NSE was closed:

* Dhan profile matches the configured account; active segments include D and
  data entitlement is active. Available cash is INR 9,411.18; orders, trades
  and positions are empty. Ledger and historical-trade reads also succeed.
* Dhan expiry-list, current option chain and full option quote return HTTP 200.
  The master identifies 22 September expiry, 65-unit lots, INR 0.05 ticks,
  1,800-unit freeze and 472 option instruments. These are current facts, not
  permissions inferred for earlier historical dates.
* Upstox chain, option quote, market status and smartlist return HTTP 200.
  The sampled news query succeeds but returns no records. Upstox WebSocket
  delivers index protobuf frames; no CAS status/IEP was observed.
* REST option books have five levels but their last trade is 18 September.
  Dhan's market socket connects without usable new depth. The order socket
  connects and responds to ping, but no accepted-order echo or fill occurred.
  REST timings are request durations, not order or exchange-fill latency.
* The existing Mumbai VM is running with authority and broker writes disabled.
  Its cached credential returns HTTP 400/DH-906 with an invalid-token message;
  status is RECOVERING. The same VM, using the already active credential in an
  ephemeral read-only check, returns successful profile/funds/orders/trades/
  positions/IP reads. Its actual egress and primary whitelist match
  34.100.255.111. The daemon cache and active credential differ.
* No credential was persisted to the VM, no daemon restarted, no live source
  deployed and no order/probe sent. Existing secret and token files are mode
  0600. The deployed git revision is d5efcfdfc1dd81e60dae21a60be989a8b9ef406c.

[Fresh REST receipts](../research/results/readiness/fresh_api_probe.json),
[socket/account checks](../research/results/readiness/connection_checks.json),
[cloud cached-token probe](../research/results/readiness/cloud_probe.json),
[cloud active-token comparison](../research/results/readiness/cloud_active_credential_probe.json).
Raw licensed/account responses stay in ignored private artifacts.

## Local fixes and verification

Moved session/date/token rotation outside the account-reconciliation success
path. A persistent account-read failure can no longer bypass the scheduled
rotation indefinitely. The next session retains the ledger and starts with
broker recovery, including when an existing position is still exposed.
This does not add immediate renewal of a younger revoked credential or solve
cross-machine credential ownership. The cloud copy has not received this fix.

Corrected the dated connected-test fixture to serve real historical-trade
pagination as its fixed September date moves into the past. Added adversarial
connected cases for both day and token rotation during a reconciliation outage
with exposure, plus a mutation that restores the faulty recovery gate.

The event extension's latest full software verification passes **201 tests,
no skips, and all 15 deliberately introduced defects are rejected**. See the
[current software receipt](../research/results/event90/software_verification.json),
source `105338a0f828e2188eaa5e2afda4d1088a4f1308b20d73e3a1c22e48c4f808a4`.
Five added tests cover dated archives, ban-record completeness, conflicting
candles, unresolved noise controls and replay identity/cash parity.

The earlier readiness verification: **196 tests pass, no skips; 15 deliberately introduced
production defects are rejected.** This includes 60 CP component cases, real
local HTTP/WebSocket lifecycle fixtures, whole-lot/replay checks and five new
causality/coverage tests. The saved receipt is
[software_verification.json](../research/results/readiness/software_verification.json).

Covered software SHA-256: `ea0de91dcb79eab126b02fd41695ff3b507660380d8e1c43e8989911e83ff567`.
Research source and data digests are recorded separately in the research report.
No fixture or passing software receipt proves profitable market outcomes.

## What a future deployment must concretely contain

A qualifying frozen strategy, independent prospective evidence, complete
execution/latency assessment and explicit bankroll policy must come first.
The installed CAS_LAG_V1 daemon is not an implementation of every research
variant; its production sizing also differs from the gauntlet's 95% model.
Activating the existing helper would not deploy a newly discovered winner.

A future review must identify the actual strategy implementation and source
hash, bankroll cap, funded product/rules, live data mappings, credential renewal
arrangement, cloud configuration and rollback/disarm behavior. Software checks
must pass against those exact installed bytes. Only then is the operator's
requested funded-deployment approval question appropriate.

Current deployment decision: **WITHHELD — no qualified strategy**.
The [deployment guide](CLOUD-DEPLOYMENT.md) is an operational reference, not
permission to activate. Earlier engineering receipts are preserved in
[the 14 September report](RELEASE-READINESS-2026-09-14.md).

The current [NSE CAS description](https://www.nseindia.com/static/products-services/closing-auction-session)
still gives a 15:40 equity-derivatives close and disseminated indicative index.
[SEBI's settlement-methodology review](https://www.sebi.gov.in/media-and-notifications/press-releases/sep-2026/sebi-to-review-settlement-price-methodology-for-derivative-contracts-in-the-light-of-cas-rollout_104260.html)
is an additional reason to bind any future CAS experiment to its actual
effective regime. A proposed change is not inserted as an enacted historical
rule, and the existence of an indicative index is not evidence of arbitrage.
