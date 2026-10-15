# 15 October pre-open production check

Operator requested a live audit and repair before the market opens. The saved
funded selection remains CAS_LAG_V1 only; 137 implemented NIFTY configurations
remain scanned. Other rules are observation-only. This check does not expand
funded authority or submit a broker order.

The actual Dhan reads before deployment succeeded: cash INR 7,816.11, no open
positions, pending orders or orders today; profile and funded-account identity
matched. Data plan Active, data validity 8 November, token validity 15 October
23:48 as reported by Dhan. Actual public egress matched the whitelisted static
IP. Fresh instrument and NSE freeze downloads identified next NIFTY expiry
19 October, lot size 65, price tick 0.05 and freeze quantity 3510. The provider
calendar schedules 15 October 09:15 to 15:40 IST. Today is not NIFTY expiry.

The trader restarted once overnight after token generation returned a response
that failed account-identity validation. It failed closed and systemd recovered;
current authenticated broker reads succeeded. No invalid token was accepted.
Before deployment all four services ran, all three feed sockets were connected,
account reconciliation was current, disk free was 20.81 GiB and no unresolved
lifecycle or recorded incident existed. Connected quiet sockets before opening
do not certify current executable quotes or an order route.

Production repair: scanned but unfunded strategies no longer admit money writes,
choose probe contracts or bring route qualification into their ordinary-session
windows. CAS-only non-expiry sessions report NO_TRADE_DAY; an eligible expiry
before opening reports WAITING_EXCHANGE_SESSION. Observation scans keep ACTIVE
feed-freshness monitoring during verified open sessions even when CAS funding is
ineligible. Existing position recovery and exits remain outside entry admission.

Regression evidence: real production-session fixtures initially submitted a
probe on both a non-expiry day and before CAS qualification on an expiry day.
Both exact negative cases now reject that probe. Positive funded ordinary-session
qualification remains possible. Additional failing-before cases exposed hidden
observation-feed monitoring and an incorrect pre-open expiry label.

Local full verification passed 580 tests, all 60 acceptance cases and all 15
production mutations, with source digest
`c31f3a33acd8cd8b791251e4fb6f5e14f52e37ce29c9ee17d5f1f83b9f8a8365`.
The installed VM must independently run this same complete verification before
switching the funded service. The release preserves the mandate,
capital, normal two-attempt probe limit and daily/lifetime probe cash caps. New
route proof cannot be claimed before its eligible window. Today CAS-only funding
has no strategy entry opportunity; it will not manufacture an order merely to
appear active. Yesterday PCR final charges remain unavailable, so its net loss
is still unknown (gross loss INR 2,665); earlier CAS final net is INR 1,709.36.
