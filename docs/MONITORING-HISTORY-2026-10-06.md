# Monitoring history and pre-auction visibility

Update, 7 October: the dashboard and history collector were deployed as
`a40af75` on 6 October at 18:51 IST. The funded trader still runs `5596c5d`;
new quote fields requiring its newer projection remain unavailable. History
records observed coverage from installation, including the midnight transition;
it does not reconstruct Monday. See the [deployment receipt](DASHBOARD-DEPLOYMENT-2026-10-07.md).
The original local findings and access failures below are historical.

## Findings

The implemented strategy is expiry-session NIFTY CAS_LAG_V1. `service.py` admits
new entries only when the loaded expiry is today. Route qualification runs
15:05–15:19:30 IST; the engine admits auction entries 15:20–15:30, or the separately
verified final-value path until 15:38:30. Tuesday morning without entries is
consistent with these rules. A non-expiry Monday is ineligible. These are code
findings, not a replay of the VM's 5 October records.

The previous read model omitted accepted pre-auction NIFTY observations. Its
Activity journal contained execution intents, fills and incidents, not daily
monitoring coverage. `status.json` and the dashboard snapshot are overwritten;
empty activity therefore cannot prove that no market data arrived or no trades
occurred. The old idle wording also implied that quiet market data was expected
merely because entries were outside their window.

## Local changes

- Show the latest accepted pre-auction NIFTY price, provider timestamp and local
  receipt timestamp separately from the official auction value. The existing
  reference collector stops accepting LTP at 15:15; the displayed observation
  ages instead of being portrayed as a continuing live price.
- Show index/options message receipt ages, option last price, cumulative volume
  and open interest. Without IEP, the read-only watchlist uses proximity to the
  known pre-auction index. It never creates a trading signal from that value.
- Add History with IST date, Today and Yesterday controls. The sidecar atomically
  maintains a 0640 `history.json` beside its snapshot: 31 recorded-date summaries
  and the latest 240 detailed samples across dates. The page shows at most 30
  details for the selected day. It records each minute or on state changes,
  coalesced to at most one sample per five seconds.
- Record unknown source states and gaps exceeding 90 seconds. First/last samples
  do not prove continuous coverage. Missing dates stay unknown; no Monday
  backfill, zero-trade result, tick tape or complete decision history is invented.
- History read/write failure is exposed without preventing current snapshot
  publication. Invalid existing evidence is preserved. History is independent of
  the trading ledger; it does not change broker writes, strategy or sizing.
- Quote updates omit unchanged history on the authenticated stream. Reconnecting
  streams and ordinary status reads send a complete snapshot.
- An open position remains visible as position management outside entry hours.

## Validation and remaining work

74 focused tests passed with:

```
.venv/bin/python -m pytest tests/test_dashboard.py tests/test_dashboard_streaming.py tests/test_dashboard_history.py tests/test_observation_view.py -o addopts='' -q --junitxml=/tmp/dhan-history-focused.xml
```

This includes actual page-script/DOM assertions, WSGI authentication and SSE
checks, history retention, restart deduplication, stale/unknown data, corrupt
history preservation, and pre-auction/IEP separation. `git diff --check` passed.
The design detector reported placeholder-dash and empty-state-copy heuristics;
the dashes represent unknown data, not measured zero.

The required full `dhan-cas verify` attempt failed. The focused failure replay
showed `OSError: could not bind on any address out of [('127.0.0.1', 0)]` in the
real-socket test. Seven socket/connected-service cases were recorded failed in
the pytest cache. No acceptance marker was generated and no cases were waived.
Chromium could not launch here, so this change has no new visual screenshot proof.

Live checks could not proceed: dashboard DNS failed in this execution environment,
the local browser bridge was unreachable, gcloud could not write its read-only
credential database, and the Dhan read-only order-book connector required an
approval unavailable under this session's policy. These failures do not establish
that the VM or broker is down. Full verification, authenticated VM/status review
and deployment remain necessary in an environment with the required access.
The trader projection and separate dashboard both need the corresponding release;
deploying only the dashboard will leave new quote fields unknown.
