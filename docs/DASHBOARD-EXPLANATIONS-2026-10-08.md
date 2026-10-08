# Dashboard decision explanations, 8 October 2026

Pushed and deployed on 8 October. The final dashboard, collector and read-only
daily monitor release is `3792d8512bc45bf184eb96825d556225df5b8cba`, installed at
16:43 IST and inspected in the authenticated browser at 16:44 IST. The funded
trader remains `5596c5d`, CAS only, with PID 288398 and its 7 October start time
unchanged. The dashboard deployment does not activate daily-strategy orders.

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

Live inspection found that earlier monitor versions had saved numeric details
without the new condition rows. The final compatibility fix displays those
original details in the expandable retained-decision panel; it does not invent
historical condition evidence. A failing browser test reproduced that omission
before the fix.

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

The earlier restricted-environment attempt could not bind localhost or reach
the VM. After access was restored, full verification completed twice, including
after the compatibility fix:

```bash
.venv/bin/dhan-cas verify --state-dir /tmp/dhan-dashboard-deploy-final-20261008
# 432 tests, all 60 acceptance cases, all 15 production mutations killed
```

Covered-source digest:
`b0b88f44aa23f4ba6b201ff85ed923bff507146a8335f9261baec43371674bcf`.
The browser regression is included through the Node lifecycle test invocation.

## Deployment and actual observations

`ops/deploy_dashboard.sh` ran from a clean temporary checkout to preserve the
operator's untracked instructions. It pushed all three pending application
commits (`f7793e8`, `ea5100c`, `3792d85`) and installed the final immutable
release. Its 59 local deployment checks and 78 VM checks pass; public HTTPS
serves the sign-in form and returns 401 for unauthenticated account requests.
Authenticated local status is current. All dashboard/collector/monitor units
are active, and the existing funded trader was not restarted.

The operator signed in privately after the browser session expired. Actual
desktop and 390-pixel mobile inspection verifies the condition rows, thresholds,
next scheduled checks, saved inputs and ongoing time updates, with no horizontal
overflow. Mobile/focus overrides were cleared afterward. Screenshots:
`/tmp/dhan-explanations-desktop-view-20261008.png` and
`/tmp/dhan-explanations-mobile-20261008.png`.

Observed cash was INR 8,822.36 with zero open positions. The session open was
22,599.05 against a prior close of 22,603.05: a -0.0177% opening gap, below the
0.5% minimum. The retained 11:30 gap-fade decision was NO_SIGNAL. The retained
15:10 rebound observation was SIGNAL (CE), with -1.82596% from the open. That
record came from the read-only monitor and is not a broker order or fill. The
closed session displays tomorrow's 09:45 and 15:10 checks, retaining today's
decisions separately. The funded CAS process remains enabled/armed, with its
route unverified; no new execution authority was applied.
