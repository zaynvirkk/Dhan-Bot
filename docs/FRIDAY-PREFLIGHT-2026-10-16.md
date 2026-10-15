# Friday preflight, checked Thursday 15 October

**Not a complete live-readiness pass.** The selected seven strategies already
have funded permission, but the running funded process is still `bc3b50a`.
Publishing monitoring software does not put the route, signal-history or token
repairs into that process. A fresh route acceptance and current executable
quotes must still be observed in Friday's session. No trade or profit is promised.

## Current external checks

Read-only VM and broker checks at18:32–18:35IST confirmed:

- Cash INR7,805.94; zero positions and pending orders. Today's three orders
  were zero-fill connection checks, not strategy executions.
- Dhan account/profile, derivatives/data subscription, static-IP whitelist and
  actual egress passed. Data validity is reported through8November.
- All seven selected strategy names are both configured and funded. No extra
  strategy or capital allocation was introduced by this preflight.
- The live Upstox calendar returns Friday16October09:15–15:40IST for NSE F&O
  and cash close15:30. Its next session is Monday19October. The official
  [NSE F&O holiday circular](https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf)
  lists20October as the next scheduled holiday, not16October.
- Friday has zero used route attempts, normal limit two, no dated extra grant.
  Thursday's exhausted three-attempt allowance is not refunded or reused.
- The funded service is enabled, running without a systemd restart, and its
  own older-source verification is current. There are no failed systemd units.
  The VM has approximately18.2GiB free disk and870MiB available memory; chrony
  is running. These are snapshots, not guarantees against future outages.
- PIN/TOTP authentication is configured without a fixed Dhan token. The cache
  was issued14October23:48IST, with normal20-hour renewal due15October19:48.
  Actual renewal has not yet occurred in this inspection. The currently
  accepted Upstox credential reports an expiry in September2027.
- The signed-in dashboard receives current account updates, shows all seven
  names and explicitly says **Funded · update pending**. It correctly retains
  today's rejected order check and closed-market status.

## Additional defect found and repaired

The read-only connection checker can renew the shared Dhan token cache before
the trader's own renewal check. Previously the trader inspected only the cache's
issue time. A newly written issue time could conceal the older credential still
held by its HTTP client and market/order sockets.

The production loop now also checks that the cached credential/account still
matches its active session. A mismatch ends that session without fabricating
an exit or clearing obligations, then the existing outer loop starts with
broker-first recovery and the replacement credential. A new production-session
test first timed out on the old code while holding a managed position and
experiencing account-read failures. After repair it exits the obsolete session,
retains the position and sends no additional synthetic order. Existing day/age
rotation and recovery tests remain required. Runtime repair revision3 makes
an older publisher visibly require an update; this does not change authority.

The installed50351fc upgrade preview independently passed636 software tests,
60 acceptance cases and its read-only account reconciliation, returning
`applied:false, checks_passed:true`. This was a preview, not an activation or
verification of the subsequently added token fix.

## Remaining operator switch and opening checks

The existing operator command switches the repaired release while preserving
the selected names, capital and probe-money caps:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python /opt/sablestone-dhan-dashboard/current/ops/activate-seconds.py --apply
```

No extra-attempt flag is needed. The assistant did not execute this financial
activation, submit an order, grant attempts or restart the funded process.

After the operator switch, confirm the funded source matches the installed
release and runtime revision3; an active systemd process alone is insufficient.
At the next verified open, require current reconciled funds, usable futures and
option depth, a current accepted order-socket route, and an actual rule signal.
Missing books must say unavailable; cash, depth, spread and insufficient net
margin must have their own rejection reason. The new durable health history
preserves these observations beyond the short UI ring.

The six non-CAS selected engines can inspect ordinary sessions; CAS remains
expiry/auction dependent. A rule with no qualifying setup must not submit a
trade to make the dashboard appear active. Software checks, a token-expiry claim,
and an after-close socket handshake cannot establish tomorrow's fills or profits.
