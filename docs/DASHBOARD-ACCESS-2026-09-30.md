# Dashboard browser access repair — 30 September 2026

URL: https://dhan.34.100.255.111.sslip.io/

Brave reproduced ERR_TOO_MANY_RETRIES while unauthenticated HTTPS returned a valid
401 and authenticated requests returned 200. The installed VPN extension answered
all HTTP authentication challenges with proxy credentials, including website
challenges. Replaced native Basic prompts with a regular login form and an 8-hour
signed Secure/HttpOnly/SameSite=Strict host-only cookie. Retained explicit Basic
headers for monitoring scripts without sending WWW-Authenticate challenges.
Existing credentials are preserved. Account data and dashboard assets remain
private; only the login page and its stylesheet are public.

The first live form test also found that no-referrer suppresses POST Origin in
Chromium. Changed to same-origin referrer policy and retained strict origin checks
for login/logout. Cross-origin referrers remain suppressed. API session expiry
returns the browser to login; dashboard sign-out does not alter trader authority.

Final deployed dashboard: 05f23169e254f9e99cecec793ca501410238548b.
Trader source: 884178a01bd4c0a5ab211273fc921fa2c52d5c3a, unchanged.
The trader was not restarted or reconfigured. Operator-enabled authority remained
enabled; no trading order or activation command was submitted by this repair.

Verification: 326 tests passed during the access repair; final dashboard suite
50 passed locally and on the VM. Shell/JavaScript syntax passed. Public TLS and
unauthenticated API rejection passed. Real browser form tests passed wrong-password
recovery, secure cookie, refresh persistence, logout, mobile keyboard submission,
mobile overflow and expired-session redirection. No JavaScript errors. Login
screenshots and the actual signed-in Brave dashboard were inspected. The final
Brave tab displayed account observations and New entries enabled.

Private logs/screenshots are under artifacts/private/dashboard-20260930. A transient
broker-read failure was displayed as historical account information rather than
healthy data; a later read recovered with fresh account/runtime observations and
NO_TRADE_DAY. These are observations, not a guarantee of future feed availability.
