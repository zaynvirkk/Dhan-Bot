# Rebound qualification

This experiment tests the previous conditional leader against a predeclared
additional 90-day period, full-session monitoring, execution alternatives,
dated fees, matched-date controls and independent Dhan rolling history.
It has no order submission, deployment or activation code. Broker account
reads and existing-VM inspection are explicitly read-only.

Run sequentially from the repository root:

```bash
.venv/bin/python -m research.rebound_validation.data plan
.venv/bin/python -m research.rebound_validation.data all_contracts
.venv/bin/python -m research.rebound_validation.replay
.venv/bin/python -m research.rebound_validation.replay --provider dhan
.venv/bin/python -m research.rebound_validation.controls
.venv/bin/python -m research.rebound_validation.api_check
.venv/bin/python -m research.rebound_validation.cloud_check
.venv/bin/python -m pytest -q tests/test_rebound_validation.py
.venv/bin/python -m research.rebound_validation.report
```

Broker credentials remain in the existing local configuration. No token or
account identifier is written to public receipts. Raw market history stays
in ignored `artifacts/private/gauntlet/rebound_validation`. Results and
chronological ledgers are under `research/results/rebound_validation`.
Replays reuse raw successful requests. Running the report checks source and
input hashes; changed code requires re-running the relevant experiment.

The registered signal is unchanged: at 15:10 NIFTY must be at least 0.75%
below its session open. The V2 change monitors through the actual session
close, latches late triggers through overnight closure and retains unresolved
execution as UNKNOWN. The original broader experiment remains unchanged.

Collection corrections: a currently expired contract can retain an active
key in an earlier dated snapshot. The collector matches the same token,
expiry, strike, side and dated lot before requesting its expired history.
Dhan sometimes includes the following date despite the documented exclusive
end; the fixed-contract reconstruction explicitly selects the requested
calendar day and retains excluded timestamps/raw receipts. No future bar
is supplied to a signal. Concurrent history reads are bounded to three with
a shared 0.4-second request-start spacing; they do not change replay ordering.

Current-fee comparisons preserve the parent experiment. The separately
reported dated-fee scenario applies NSE FA73061 and FATAX73524 effective
dates. Fee rounding is conservative and broker invoice reconciliation remains
a live requirement. The common production `FeeSchedule` was not changed.

This is a qualification attempt, not a promise of funded deployment. If the
research gate fails, the conditional production integration and activation
steps remain unexecuted. Software tests cannot turn a failed research gate
into profitable evidence.
