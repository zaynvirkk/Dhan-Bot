# Dhan market-feed failure and dashboard update — 7 October 2026

The first dashboard update, `bdb13dba5082181948e958971aea0e3471f70203`,
identified the disconnected feed and exposed safe protocol diagnostics. Further
read-only checks found an inactive Dhan Data API subscription. The follow-up
source, `3e11b1c97c400fbf0fb72129ee5b5bcd71621750`, correctly displays Dhan's
`Deactive` subscription value as Inactive and explains it in the disconnect
banner. It is deployed and browser-verified at 11:29 IST. Neither code change
activates a paid subscription.

URL: https://dhan.34.100.255.111.sslip.io/

## Observed failure

The fresh runtime and independent read-only checks agreed: the Dhan options
feed repeatedly disconnected, while Upstox and Dhan order updates were
connected. Authentication, derivatives permission, account reads, contract
metadata and the configured egress IP checks passed. Authentication PASS did
**not** establish an active data subscription; that distinction was important.

At **11:24 IST**, using the same token and matching account, `/v2/profile`
returned HTTP 200 and `dataPlan: Deactive`, while `/v2/marketfeed/quote`
returned HTTP 401. This identifies an inactive data entitlement as a concrete
blocker. The dashboard previously accepted Active/Inactive/Expired but mapped
Dhan's documented Deactive value to UNKNOWN, obscuring the cause. Dhan Web
requires the user's PIN before its subscription/renewal page can be inspected;
the user was asked to unlock it privately. No PIN was requested in chat, no
subscription was purchased and no billing setting was changed.

At 08:17 IST, an enhanced connection check reported `ConnectionClosedError`
without a received or sent WebSocket close code. It did not report a local
keepalive timeout. At 08:23 IST, a control connection completed the handshake
and closed after 0.12 seconds, before sending any subscription. No broker
disconnect-reason packet was received. This rules out the selected option
subscription as a necessary trigger for that observed failure. It does not
identify the rejection reason by itself. The later profile/REST comparison
identified the inactive data subscription. At 11:19 IST, separate asyncio and
legacy WebSocket clients with compression disabled also closed in 0.12 and
0.06 seconds, respectively. The failure persisted during market hours.

The live runtime continued automatic reconnection attempts. At 08:24 IST it
reported 104 reconnects, no message on the current market connection and no
pending processing backlog. No missing data was replaced with zero or marked
healthy. A connected order socket is not proof of an accepted order route.

## Dashboard changes

- The banner names the disconnected feed and points to System → Live connections.
- Each failed connection shows a safe error label and its reconnect count.
- Receipt time is explicitly scoped to the current connection; it is separate
  from cumulative processed-message counters.
- Dated commissioning checks can show close codes and keepalive timeout status.
  Raw provider reasons, URLs and credentials are never published.
- Stale runtime data still becomes unknown. A genuine fresh recovery clears
  the disconnect warning. An idle session does not hide an explicit disconnect.
- Dhan's Deactive subscription value is normalized to Inactive. A market-feed
  disconnection includes that observed subscription condition; older checks
  are explicitly described as historical. An Active plan removes the inactive
  label without falsely marking a still-disconnected feed healthy.

The enhanced diagnostic was run separately with `DHAN_BROKER_READ_ONLY=1`.
The scheduled checker remains part of the older trader checkout; this dashboard
deployment does not upgrade that checker or the funded process.

## Verification and deployment

Negative cases first reproduced the missing close-code sanitizer and generic
banner. After implementation:

```bash
node tests/dashboard_stream_test.cjs
.venv/bin/python -m pytest tests/test_connection_diagnostics.py tests/test_dashboard.py tests/test_dashboard_streaming.py -q -o addopts=''
.venv/bin/dhan-cas verify --state-dir /tmp/dhan-feed-verify-20261007
```

Results: browser lifecycle/DOM checks pass; 62 focused tests pass; full
verification passes 406 tests, all 60 contract acceptance cases and all 15
mutation checks. Covered-source digest:
`4cf3a53fbb5c7d08d92a73c6339dc0608f71c8db7ef912a4b821e183eeb80bb1`.

For the follow-up subscription fix, negative tests first reproduced the
Deactive → UNKNOWN bug and missing subscription explanation. The same focused
commands then passed 63 tests and the browser checks. Full verification with
`--state-dir /tmp/dhan-plan-status-verify-20261007` passed **407 tests**, all 60
acceptance cases and all 15 mutations. Covered-source digest:
`04f499f3f05a2416cc13422749bcc75d6cd0d396a60be9252581585f0a21299b`.

The follow-up deployment also passed 59 checks locally and on the VM,
authenticated local status and public HTTPS/login protection. An initial
invocation stopped before publication because its shortened PATH omitted Node;
the corrected invocation preserved PATH and completed. At 11:29:55 IST the
authenticated browser displayed: "Dhan options feed disconnected. Dhan reports
an inactive data subscription. Check Data APIs in DhanHQ." Live update timestamps
advanced and there was no horizontal overflow. Only dashboard services changed.

`ops/deploy_dashboard.sh` ran from a clean clone, pushed the release to GitHub
and passed 59 dashboard checks locally and on the VM. It switched only the
isolated dashboard release. The dashboard, collector and HTTPS services started
at 02:50:41 UTC (08:20:41 IST). TLS validation, unauthenticated API denial and
authenticated current account data passed.

The user's authenticated browser showed the new named warning and current live
updates at 08:24 IST. System identified Dhan options as disconnected and the
other two sockets as connected. Yesterday and Today history controls displayed
their actual dated summaries. Desktop and 390px mobile views were inspected;
no horizontal overflow or page error was observed during the check. Temporary
viewport and focus emulation were cleared afterward. Screenshots:
`/tmp/dhan-feed-system-desktop-20261007.png` and
`/tmp/dhan-feed-mobile-final-20261007.png`.

## Funded service and remaining work

The funded trader remains `5596c5da5f54dcc0fbf6ccbf3260687f6fbaef34`, CAS only.
PID 276072 and its 6 October 10:14:34 UTC start time were preserved. Its existing
authority was enabled and armed; route verification remained false. The fresh
account observation showed INR 9,411.18 and zero positions. No activation,
order-route probe, order, credential change or trader restart was performed.

The market feed remains unavailable while the data subscription is inactive.
Restoring the subscription requires action in DhanHQ, followed by a fresh feed
check; renewal alone must not be claimed to prove a successful recovery.
A healthy dashboard and passing
software checks do not establish healthy market inputs, an executable route or
profitability. Recovery must be verified with the actual market feed and usable
received data; a successful handshake alone is insufficient.

Protocol references checked against primary documentation:
[Dhan authentication/profile](https://dhanhq.co/docs/v2/authentication/),
[market quotes](https://dhanhq.co/docs/v2/market-quote/) and
[live market feed](https://dhanhq.co/docs/v2/live-market-feed/).
