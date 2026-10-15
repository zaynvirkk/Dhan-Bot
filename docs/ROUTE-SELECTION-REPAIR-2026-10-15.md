# Route selection and readiness repair

The operator's seven-strategy activation completed on15October. The new socket
could not qualify because Dhan rejected its probe strike for open interest below
broker limits. Three authorized attempts were consumed with zero fills. The
trader was funded but could not enter trades; an unmet strategy rule was a
separate condition. The exchange session subsequently closed.

The old selector sorted contracts by the cash needed for a minimum-price limit,
then security ID. It did not inspect OI. A low-ID illiquid strike could therefore
consume an attempt even when a liquid alternative was already observed.

## Software change

Production probe selection now requires a current-epoch book received within
two seconds, an unexpired index-option contract, at least one lot on both sides,
a noncrossed spread no wider than2%, and observed OI and volume of at least100
lots each. It excludes this session's previously rejected probe contracts and
filters the existing remaining daily/lifetime debit budget before selection.
Candidates rank by observed OI, volume, spread and expiry before security ID.
These are conservative local prefilters, not a published Dhan RMS threshold or
a guarantee that the broker will accept an order.

No qualifying book means no order and no consumed attempt. Existing order,
identity, cash, route-echo, cancellation and reconciliation checks remain.
No attempts are refunded, reset, granted or silently bypassed by this repair.

The dashboard projects only the latest same-day route order, with a safe
LOW_OPEN_INTEREST or generic rejection category; raw broker errors, account
identifiers and tokens are not exposed. It shows funded-but-blocked permission,
rejected/exhausted qualification and concrete seconds-rule explanations. New
seconds diagnostics add observed impulse thresholds and fit/flow/curvature
counts without changing entry thresholds, sizing, targets or exits. Simulation
results remain separate from actual funds.

## Evidence and deployment boundary

The regression first reproduced a real production service sending the probe for
the zero-OI strike. After repair the same test selects the observed liquid
alternative. A second service case supplies only zero-OI books and proves no
order or attempt-counter change. Pure cases cover missing OI, low volume,
stale/future/foreign quotes, expiry, missing depth, known rejections and budgets.
Read-side cases reject yesterday/future observations and private payloads.
DOM cases distinguish funding from readiness and show measured versus required
impulse. Tests use synthetic brokers and establish no real fill or profitability.

The dashboard/read-side deployment does not replace or restart the funded
trader. The repaired funded source requires an operator-run upgrade:

```bash
sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python /opt/sablestone-dhan-dashboard/current/ops/activate-seconds.py --apply
```

That command retains the already selected seven names and existing cash caps.
It does not grant a further route attempt. The15October extra allowance is
exhausted; the normal two-attempt allowance applies on the next session date.
Actual fresh inputs and broker acceptance are still needed before entries.
The assistant does not execute this financial upgrade or submit probe orders.
