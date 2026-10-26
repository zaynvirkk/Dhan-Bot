# Operational monitoring and bounded repair

The funded mandate and economic filters remain unchanged. A day without an
eligible option can have zero investment orders. Monitoring must explain that
outcome without labelling it a connection failure or a missed profitable trade.

The existing read-only dashboard collector checks operational state every five
seconds. It reads the trader's allowlisted status and SQLite in read-only mode;
it cannot submit orders or change trader authority. It records complete-day
counts from timestamped observations separately from the recent 256-row detail
ring. Unique qualifying minutes and durable strategy episodes are distinct.
Entry orders, fills and nonmarketable route checks are distinct.

`operations.json` retains first-seen/last-seen/recovery records. Resolved incidents
have a bounded retained tail; unresolved incidents remain. Daily counters and
assessment summaries survive in `operations-day-YYYY-MM-DD.json`. Recorder/input
outages remain unknown evidence, never fabricated no-trade or profit outcomes.
Monitor corruption is preserved and reported unavailable; it is not erased.

During a verified open session (or exposure management), checks include fresh
trader status, broker reads/reconciliation, options transport and usable books,
order transport, futures usability, strategy inputs and evaluation progress,
software verification and route qualification. Unknown route liabilities and
recorder failures are urgent even outside market hours. Normal closed-session
silence, normal signal filters and scenario-floor rejection are not incidents.
Transient conditions appear pending, becoming open after 30 seconds; unknown
order outcomes and recorder failures open immediately. Ready assessments with
no recorded terminal dispatch outcome are an observability fault to investigate,
not permission to recreate an old order. Opening incidents also emit enum-only
systemd journal events. No email, support or third-party notification is sent.

The installed local user timer runs `ops/incident-repair.py --run-agent` about
once a minute. It fetches the authenticated VM diagnostic through gcloud/IAP and
publishes a credential-free heartbeat. Healthy polls invoke no AI. New confirmed
critical incidents can invoke the existing signed-in Codex CLI, with at most two
attempts per IST date and 30 minutes per invocation. Duplicate active incidents
are not retried continuously; unresolved known attempts may retry after five
minutes within that same daily cap. A successful process exit does not claim a
fix: the runner rereads production incidents. Computer sleep, CLI/GCP auth loss
or a stopped timer prevent local repair; the VM monitor remains independent,
and the dashboard exposes the missing heartbeat. This is not a cloud-hosted AI
worker. No credentials are copied to the VM.

The standing scope and deployment constraints are in
`ops/INCIDENT-REPAIR-MANDATE.md`: repair confirmed software defects, preserve
financial rules and all money/probe caps, no forced orders or browser automation,
no third-party messages, exact regression/source verification, and flat-account
checks before a trader cutover. Existing positions continue being managed if a
repair cannot safely cut over. Profitability and guaranteed fills do not follow
from operational readiness.

Operator commands:

```
systemctl --user status dhan-incident-repair.timer dhan-incident-repair.service
journalctl --user -u dhan-incident-repair.service -n 30
systemctl --user stop dhan-incident-repair.timer
```

Local bounded-run receipts live under `~/.local/state/dhan-incident-repair/`,
permissions 0700. Run transcripts remain local and are not dashboard data. The
VM's allowlisted report is available through the deployed
`ops/incident-report.py --json`. Read the current incidents and actual source
before diagnosing or modifying production.
