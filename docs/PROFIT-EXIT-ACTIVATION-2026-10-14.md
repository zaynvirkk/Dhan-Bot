# Operator-requested profit protection activation

The operator explicitly requested all supported changes pushed and active after
reviewing the unsuccessful profit-exit comparisons. NET_PROFIT_RATCHET_V1 is a
profit-protection experiment, not a demonstrated profitable strategy. The latest
instruction also rejects selling the existing trade merely because it is losing.

Activation uses the exact-version installed source, full current acceptance and
mutation verification, existing funded mandate and capital limits. All 137
supported NIFTY configurations retain their admission conditions. Research-only
stock/event/multi-leg ideas do not become implemented bots through this switch.

The dedicated operator command validates that any open exposure is the one
already managed, matches local confirmed quantity, has no pending/unknown
obligations and is not an active CAS lifecycle. It refuses unmanaged exposure,
foreign product/segment, quantity mismatch, unsupported policy or concurrent
configuration change. The default flat-only strategy upgrader remains unchanged.

After those checks, a bounded service handoff acquires the one writer lock,
rechecks real broker exposure and applies the two explicit profit config fields.
The existing lifecycle freezes the same version and retention from forward fresh
quotes. Its prior profit peak is not retroactively inserted into the new floor;
no order is submitted by the upgrade. Original loss/holding limits remain
backstops. This activation does not authorise an overnight holding extension.
Rollback restores source/config/verification and the original lifecycle policy.

The restarted order socket still requires genuine current evidence. A confirmed
local SELL submitted after that socket connected, echoed in that same epoch,
matched to the funded account/security/quantity and confirmed by actual fills can
qualify the route without an additional artificial BUY probe. Historical/replayed
orders, wrong account/security/quantity, BUYs, missing fills and unresolved
submissions cannot qualify. Existing probe money/attempt caps are unchanged.
Position reduction does not require creating a new entry to prove its route.

The operator command is:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python \
  /opt/sablestone-dhan-dashboard/current/ops/activate-profit-exit.py \
  --apply --retain 0.50
```

This document describes the verified operation; actual deployment and account
outcomes are recorded separately in current portfolio state. Software checks
and active authority do not establish profitability or continuous feed health.
