# Dashboard design

Private, functional monitoring for the owner of the funded account. The product
contract lives in PRODUCT.md. Implementation uses semantic HTML, plain JavaScript
and a small authenticated Python adapter; no external fonts, images or trackers.

Chosen direction: incident journal, grounded candidate 7, seed `c44a03ea`.
Alternatives considered were market watch, flight board, bank statement, network
operations, railway departures and assay sheet. A journal puts observed facts,
timestamps and exceptions ahead of unsupported performance graphics.

Cool white surfaces, navy text, cobalt selection, amber uncertainty and red
failure. System typography supports frequent operational reading. Financial and
time columns use tabular figures. Rupees are formatted from decimal strings;
missing observations display a dash rather than a fabricated zero.

The first viewport establishes observation status, account facts and trading
entry authority. Connection details lead into positions, order/fill tabs and
persisted activity. The activation guide provides manual copy commands only.
On narrow screens execution status moves above connection rows, account fields
use two columns and wide tables scroll within labelled regions. Keyboard tabs,
focus states, skip navigation, reduced motion and native disclosure controls are
included. Provider text enters the DOM through textContent, never innerHTML.

Single-agent finish review: no subagent/reviewer gate, per portfolio instructions.
Authentication, data isolation and stale-state behaviors passed deterministic
checks. The design detector ran once: dash-density was an intentional unknown-data
placeholder false positive; its two accent-border warnings were resolved by using
a regular notice outline and neutral rule. No charts or illustrative trading data
were added. Authority copy was corrected to distinguish disabled new entries from
ongoing exit handling.

Verdict: verified on the live authenticated HTTPS endpoint on 30 September 2026.
Chromium screenshots at 1440px desktop and 390px mobile were inspected. No document
overflow or JavaScript errors; tab filtering, keyboard selection and disclosure
controls work. A browser-only disconnected-fetch test removed health badges and
changed authority to unknown. Real account observations were separately verified.
The initial 15-second heartbeat threshold was corrected to 45 seconds to cover the
collector's normal 20-second timeout and 15-second scheduling gap. The displayed
observation timestamps make the monitoring delay explicit.

Browser access repair, 30 September: added an ordinary password form in the same
visual system, replacing native HTTP-authentication challenges that conflicted
with the owner’s VPN extension. Login has visible labels, password-manager
autocomplete, keyboard submission and recoverable errors. Added dashboard sign
out; session expiry returns to login. Tested real form login/logout on the public
HTTPS site, mobile at 390px, and the owner’s actual Brave browser. No browser
JavaScript errors or mobile overflow. Password and trading authority are unchanged.


1 October implementation: retained the existing visual system and read-only
interaction model. Added a collapsible Timing and entry checks view using the
existing facts layout. Authenticated SSE carries status snapshots; hidden tabs
pause, failures fall back to polling, and stale/unknown states remain explicit.
DOM and stream lifecycle tests pass. The mechanical detector reports only the
existing em-dash placeholders advisory. This pass has no new browser screenshot
or deployed visual verification because the execution environment blocks sockets.

4 October live-health refinement: preserved the journal design and split current
socket observations from dated diagnostics in a native disclosure. Idle silence,
missing telemetry, disconnected feeds and delayed decoding have distinct copy.
The generic diagnostic-age banner is removed. Push pulses update source ages
without replacing unchanged tables; freshness and unknown states remain explicit.
DOM/lifecycle checks pass; real browser inspection is blocked by EPERM and no
new deployed visual verification is claimed.

4 October decision-first refinement: retained the cool paper/navy/cobalt system,
using a compact operating layout. The first screen now explains the current
state and next prerequisite, then displays accepted auction inputs and six
observed entry checks. Five retained option books expose bid/ask quantities,
whole-lot cash including entry fees, conditional intrinsic and confirmation count.
This is a watchlist, not a selected trade or confidence score. The last persisted
entry decision is separately available alongside actual execution history.

Removed routine healthy banners, decorative section numbers, empty position/order
tables, and duplicate unknown P&L figures. Connections, diagnostics, timings and
VM setup are available under System. Account failures, stale state and unavailable
inputs remain explicit. The dashboard cannot place orders or change authority.

Verification: two bounded desktop/mobile inspection passes on synthetic preview
inputs; 1440px, 390px and 320px layouts, keyboard order tabs, disclosures, no JS
errors and missing-data demotion passed. Narrow preview header overflow was fixed.
The detector's sole advisory concerned deliberate unknown-value dash placeholders.
Full automatic verification passes 365 tests and 15 source mutation checks.
Deployment and real-observation verification are recorded in the session worklog.

12 October money-first refinement: retained the journal styling and read-only
model. Available cash, recorded fills, positions and broker-reported P&L now
precede the execution decision. A fresh unverified route takes priority over
ordinary signal waiting, while open-position management and unknown observations
remain distinct. Missing execution records never show zero fills. Routine signal
filters say Not met; numeric inputs and auction data use native disclosures.
Actual orders precede the sampled session log. No performance chart or claim of
profitability was added.

Live finish evidence: dashboard release 810add3 verified in the owner's signed-in
browser at 1440px and 390px, with no document overflow and collapsed disclosures.
Cash INR 8,822.36, zero recorded fills and the unverified route match the API.
Trading process and authority were preserved. Detector advisories concern
existing unknown-value placeholders and incidental copy constructions.

13 October entry-history refinement: each funded directional row retains the
last qualifying signal from the durable ledger, labelled historical, with its
recorded outcome and expandable candidate checks. An expired entry window is
distinct from no signal. Unknown older blockers remain unknown; a committed
decision is not labelled a fill. Current waiting states retain their own badge.
The money-first journal layout and read-only authority model are preserved.
Browser inspection also exposed repeated large journal transfers competing with
live status. Compact status/events preserve the cached journal; a separate full
refresh updates it once per minute without overwriting newer live observations.
Unknown historical data and stale authority remain explicit.
Live finish: releases ea03527/eeb1b5 are installed. An uncached signed-in browser
reload keeps the live event connection open and loads the complete journal in
1.75 seconds (28,488 encoded bytes versus 722,549 decoded bytes). History reads
AVAILABLE and current enabled authority matches the fresh backend snapshot.
Finite responses use negotiated gzip; event streams remain uncompressed.

13 October live-status correction: a current Upstox transport receiving and
processing frames remains distinct from an accepted auction input. After a
provider-confirmed CTS_CLOSE reference, missing/currently stale indicative
values are an auction-entry condition, not a generic market-data outage.
Fresh option books remain required for a healthy feed summary; stale index
transport, disconnected sockets and delayed processing keep their warnings.
No execution rule or strategy clock is changed by this read-only presentation.
Provider-confirmed CAS_STOP is a closed auction entry phase, not missing feed
data. Its strategy row says Closed, while exposure/settlement handling remains
separate. Fresh incoming frames cannot conceal genuinely stale option books.

15 October compact operating views: Live, History and System now select separate
panels instead of scrolling through one long page. Live contains three money
observations, one concrete decision, an open position when present and compact
native disclosures for the configured strategies. Recorded closed-trade P&L is
labelled separately from cash and today's completed count. Recorded trend and
pullback measurements explain waiting; unavailable confirmations remain unknown.
Completed trades, holding time, per-strategy outcomes and route attempts live in
History; diagnostics and detailed accounting remain in System. The journal
palette, native disclosure controls and read-only model are retained. No trading
policy, authority or funded process is changed.

15 October seconds experiments: retain the compact journal identity. A native
disclosure beneath the funded roster contains five explicitly simulated engines
with reasons and independent model outcomes. It never changes broker cash,
funding badges or real trade counts; unavailable and stale experiments remain
unknown. Each row expands to its rule, observations and bounded exit policy.

16 October session learning: History gains compact expandable dated reviews,
actual gross/net charge provenance, entry completion, input-loss warnings and a
separate lesson journal. Existing Live and System views remain. No chart or
hypothetical outcome replaces broker records. System exposes dedicated futures
freshness and bounded replay health; hidden initial tabs still fetch one current
snapshot instead of remaining blank. Visual verification is recorded with the
release evidence after deployment.
