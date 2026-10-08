# Dashboard decision explanations, 8 October 2026

Implemented locally. These changes have not been pushed or deployed, and the
live browser has not been inspected today. The last verified dashboard and
read-only monitor release is `eb7f442` from 7 October. The last verified funded
trader was still `5596c5d`, CAS only; these observations are not a current
account or service-status check.

## Cause and change

The strategy evaluator condensed multiple failed gates into one no-signal
reason. The dashboard projection discarded persistence, and the frontend did
not display the monitor's retained decisions between scheduled checks.

The evaluator now supplies diagnostic evidence alongside the unchanged signal
rules. Gap-fade shows opening gap (absolute minimum 0.5%), retracement (25–100%),
three-close persistence and the five-minute futures direction. Rebound shows
the actual return from the open against its -0.75% threshold. Each input has a
passed, failed or unavailable state. Missing or nonfinite numbers are not zero
and cannot display as passed.

The frontend names failed or missing conditions, displays actual values and
thresholds, and shows the next check from the verified calendar. Between entry
windows the values are explicitly observations, not trading decisions. The last
completed decision remains visible, with expandable historical inputs. Only
sanitized, same-day, past decisions can be restored after a monitor restart;
failed data reads do not erase them. History retains the new diagnostic fields.
Read-only monitoring and funded execution remain explicitly separate.

No strategy threshold, entry window, execution authority or broker order path
was changed by this dashboard work. A separately pending upgrade-helper fix
prevents a failed preflight from restoring files it never modified; its negative
test is included in the focused run.

## Verification

```bash
.venv/bin/python -m pytest tests/test_strategy_explanations.py \
  tests/test_session_strategies.py tests/test_strategy_inputs.py \
  tests/test_daily_monitor.py tests/test_strategy_dashboard.py \
  tests/test_dashboard_streaming.py tests/test_dashboard_history.py \
  tests/test_directional_engine.py tests/test_session_upgrade.py \
  -o addopts='' -q
# 69 passed
.venv/bin/python -m pytest tests/acceptance -o addopts='' -q
# 60 passed
node tests/dashboard_stream_test.cjs
# passed, including values, stale data, retained decisions and authority isolation
git diff --check
# passed
```

The required full command was attempted:
`.venv/bin/dhan-cas verify --state-dir /tmp/dhan-dashboard-explanations-verify-20261008`.
It did not complete and was interrupted. An isolated real-socket case,
`tests/test_cloud_runtime.py::test_real_socket_reconnect_resubscribes_binary_and_clears_epoch`,
fails because this environment cannot bind `127.0.0.1`. No current full-suite or
mutation-verification pass is claimed; no verification marker was created.

Current access attempts also fail: the local browser bridge is unavailable,
dashboard/GitHub DNS resolution fails, and gcloud cannot open its credential
database on the read-only filesystem. No credentials were copied or exposed.
Deployment requires restored access, a complete verification pass, then the
existing isolated `ops/deploy_dashboard.sh` path. A browser inspection of the
deployed conditions and history remains outstanding.
