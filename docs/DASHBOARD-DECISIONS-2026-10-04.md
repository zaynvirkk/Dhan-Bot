# Decision dashboard

The owner can now see the bot's current activity, next condition, accepted inputs,
retained contracts and actual execution records without inspecting server logs.

The service emits a bounded read-only projection of its existing in-memory state:
auction phase and timestamps, frozen reference, accepted IEP, direction, verified
final value, loaded expiry, and at most five option books. These are sorted by
qualifying observations and proximity to the accepted IEP; they are not the
optimizer's candidates. Intrinsic is conditional on qualifying IEP observations.
One-lot cash includes entry fees but not exit costs. No allocation, strategy,
permission, order, or exit behavior is changed. The projection is bounded and
re-allowlisted by the dashboard; raw provider payloads and credentials stay private.

The last entry decision is joined to the intent's existing persisted observation.
A decision is not a fill. No artificial confidence or profitability score exists.
The UI describes the deployed CAS_LAG_V1 and separate verified-final-value path,
not a proposed strike-cross or forced-flow strategy from older research.

Routine health information now lives under System. Empty tables and unknown P&L
placeholders are collapsed; failed reads stay unknown rather than implying zero.
Stale collector or runtime observations demote trading status and entry badges.
A connected socket is never represented as a usable signal or executable route.

Validation: full `DHAN_BROKER_READ_ONLY=1 .venv/bin/dhan-cas verify --state-dir
/tmp/dhan-ui-verify-20261004` passed 365 tests, all 60 CP cases and all 15 mutations.
Source digest: dbe4e45d44dc04ca4a0ea36c44ec1440fde048304c1a61526ed4730aadf6f755.
Node lifecycle/DOM tests cover populated, missing, stale and disabled states.
Real Chromium local preview checks cover desktop, 390px and 320px, keyboard tabs,
disclosures, no document overflow and no JS errors. Preview observations were
synthetic and explicitly labelled; they are not trading evidence.
