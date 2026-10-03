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
