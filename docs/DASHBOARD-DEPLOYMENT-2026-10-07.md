# Dashboard deployment and trader status — 7 October 2026

The dashboard and read-only collector were deployed on 6 October at 13:21 UTC
(18:51 IST) to the existing Google Cloud VM. The source commit is
`a40af752832933366ffbd3a075c2e2975fe7ad8d`. GitHub `main` was verified at that
commit after the push; subsequent documentation commits do not change this
installed release.

URL: https://dhan.34.100.255.111.sslip.io/

## What is running

- Dashboard: `/opt/sablestone-dhan-dashboard/releases/a40af752832933366ffbd3a075c2e2975fe7ad8d`.
- Trader: `5596c5da5f54dcc0fbf6ccbf3260687f6fbaef34`, CAS only. The existing
  trader process was not restarted and its funded authority was not changed.
- The web, collector, HTTPS proxy and trader services are active. On the
  7 October recheck, the trader retained its PID and 6 October 10:14:34 UTC
  start time; dashboard services started at 13:21:09 UTC.
- Gap-fade and overnight rebound are implemented and published, but **not
  active in the funded service**. The older trader does not report their new
  strategy/quote fields, so the dashboard leaves those unavailable.

## Verification actually performed

Full local verification:

```bash
.venv/bin/dhan-cas verify --state-dir /tmp/dhan-deploy-verify-20261006
```

Result: 403 tests, all 60 contract acceptance cases and all 15 deliberately
injected defects detected. Software source digest:
`c674d3bc566de6ea01fbe8a268622dbf25e3a25013681b4bfbd8d1bb22933677`.
This is software evidence, not profitability or broker-route evidence.

`ops/deploy_dashboard.sh` ran from a clean clone of the committed source,
preserving the original checkout's untracked operator instruction files. The
first invocation omitted Node from PATH and stopped before publication. The
corrected PATH retained Node; all 59 dashboard deployment tests then passed
locally and again inside the VM's isolated dashboard release.

The installer verified the VM/IP, pushed the exact commit, installed the isolated
release and restarted only the dashboard, collector and HTTPS services. External
TLS validation succeeded; unauthenticated `/api/status` returned 401 and `/login`
returned the expected form. The authenticated local endpoint returned a fresh
snapshot with read-only broker access.

In the user's real browser, the authenticated deployed page returned HTTP 200
and six SSE messages over 5.5 seconds. The history summary loaded real monitoring
samples and the page reported current account/bot observations. No page error
was observed during that sampled interval. At a later 7 October browser recheck,
the eight-hour login had expired: redirect to `/login` and HTTP 401 behaved as
intended. Further authenticated History-control inspection awaits user sign-in.

## Latest read-only status observation

At **7 October 00:34:27 IST** (6 October 19:04:27 UTC), the dashboard's sanitized
VM snapshot reported:

| Observation | Value |
| --- | --- |
| Account read | Successful and fresh |
| Available cash | INR 9,411.18 |
| Open positions | 0 |
| Existing funded authority | ENABLED |
| Existing automatic arming | true |
| Runtime order-write flag | true |
| Order-route verification | false |
| Runtime state | NO_TRADE_DAY |

Enabled/armed means the existing service has operator authority. It does not
override session eligibility, route verification or entry conditions, and it
does not mean the new strategies are running. No activation command, trade,
order-route probe, credential change or funded-service upgrade was performed
by this deployment.

History started at 6 October 18:51:09 IST. The fresh recheck contained dated
summaries for 6 and 7 October with no recorded gaps over 90 seconds or unknown
samples. Retention remains bounded; these samples do not prove uninterrupted
tick coverage or reconstruct missing earlier days.
