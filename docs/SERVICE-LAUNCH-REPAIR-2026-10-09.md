# Session-strategy startup repair, 9 October 2026

The operator applied release `3792d8512bc45bf184eb96825d556225df5b8cba`
at 12:55 IST. A subsequent read-only VM check found all three configured
strategies in the funded service, existing authority enabled and all three
WebSocket connections connected. Cash was INR 8,822.36, with zero orders and
positions. However, `software_verified` and `broker_route_verified` were false.
The successful upgrade message did not establish entry readiness.

The upgrade helper verified the immutable release, then launched its
`.venv/bin/dhan-cas` console script. The dashboard installer uses a non-editable
wheel: that script imports the package under `site-packages`, which lacks the
tests, operation scripts and release metadata included in the source digest.
Read-only checks on the VM reproduced a failed verification for that package
root and a matching verification for the actual release root. No verification
guard or marker was bypassed.

The helper now launches `.venv/bin/python -m dhan_cas_bot` with the pinned
release as its working directory. A subprocess regression test reproduces
both import paths, verifies the corrected launch, and confirms later source
changes still invalidate verification. The helper also prints progress before
the full suite and after it passes. The dashboard explicitly shows a software
verification blocker, and labels funded strategy rows independently from the
presence of the separate read-only observer.

## Operator completion

Once the repaired dashboard release is installed, run the same command on the
VM to reverify and correct the funded service launcher:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python /opt/sablestone-dhan-dashboard/current/ops/upgrade-session-strategies.py --apply
```

This preserves the existing mandate, capital and ledger. It requires a flat
account and no pending orders. The assistant's dashboard deployment does not
restart the funded service. After the operator applies the correction, inspect
fresh runtime status for `software_verified: true`; order-route qualification
and each strategy's signal, funds and execution checks remain required. The
existing operator mandate can permit automatic real orders after those pass.

This fixes software execution and reporting, not strategy profitability.

## Local verification

`tests/test_session_upgrade.py`, dashboard streaming and strategy projection
checks passed 20 tests. Full verification passed 433 tests, including all 60
acceptance cases, and killed all 15 production mutations:

```bash
.venv/bin/dhan-cas verify --state-dir /tmp/dhan-launch-fix-verify-20261009
```

Covered-source digest:
`4e26d0af9a40bd524826538a9b002dcdd869df2529acb08d168b5242ff6f91b7`.
