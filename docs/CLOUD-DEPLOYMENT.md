# Google Cloud deployment

Repository: https://github.com/zaynvirkk/Dhan-Bot

Project `project-cead8bae-10ea-4ea9-875`; VM `sablestone-dhan-cas` in
`asia-south1-a`; Ubuntu 24.04, e2-small, 20 GB balanced disk. Reserved external
IPv4 **34.100.255.111** (`sablestone-dhan-cas-ip`). SSH uses IAP only. No public
application port or attached cloud service account is needed.

Source: `/opt/sablestone-dhan-cas-bot`. Configuration:
`/etc/sablestone-dhan/production.toml` (0640 root:sablestone). Secrets:
`/etc/sablestone-dhan/secrets.env` (0600 root, loaded by systemd). State:
`/var/lib/sablestone-dhan` (0700 sablestone). Broker secrets and account reports
must never be committed.

## Account requirement

Current broker/profile checks show Equity without F&O. Complete **Dhan Profile
→ Equity F&O, Commodities & Currencies** first; an active data subscription
alone does not authorize NIFTY option orders. The VM primary IP has already
been registered as **34.100.255.111**.

## Activation by the operator

Connect to the existing VM:

```bash
gcloud compute ssh sablestone-dhan-cas --zone=asia-south1-a \
  --project=project-cead8bae-10ea-4ea9-875 --tunnel-through-iap
```

The deployed service retains its read-only interlock until the operator runs:

```bash
sudo /opt/sablestone-dhan-cas-bot/.venv/bin/python \
  /opt/sablestone-dhan-cas-bot/ops/activate-live.py --capital available
```

The command validates the current installed-source receipt, Dhan identity,
derivatives/data permissions, reusable cash, empty initial position/order
state, static egress/whitelist and Upstox authorization. It records the chosen
capital once, enables the standing mandate and service, and removes the
read-only environment interlock. It does not reset previous trading history.
An explicit amount can replace `available`. `--check-only` performs the checks
without enabling orders.

The service automatically recovers before signal/calendar logic, refreshes its
session around 15:05 IST, and qualifies its current order socket using a bounded
IOC before 15:19:30. A rejected or unobserved probe never qualifies entries.
Actual CAS state controls entry permission; active-auction entry ends at the
earlier of CAS_STOP and 15:30. Qualified final-value entries end at 15:38:30;
unprotected positions enter time-exit handling at 15:39. Expiry is discovered
from the current master, including holiday-shifted dates. Rule changes affecting
the signal/settlement contract require a validated policy update.

PIN/TOTP authentication is cached under a process-shared file lock and rotates
before its 24-hour lifetime, including when settlement or unknown orders remain
pending. Rotation re-enters broker-first recovery. The older external 14:55
read-only refresh timer is disabled by activation; the production process owns
its token and session refresh. The independent connection timer runs at 14:50.

## Status and recovery

```bash
sudo systemctl status dhan-cas.service --no-pager
sudo cat /var/lib/sablestone-dhan/status.json
sudo journalctl -u dhan-cas.service --no-pager -n 30
sudo -u sablestone /opt/sablestone-dhan-cas-bot/.venv/bin/dhan-cas \
  disarm --config /etc/sablestone-dhan/production.toml --new-entries
```

Disarming persists in SQLite and leaves exits/recovery authorized. Avoid
stopping the process while exposed; its position manager must remain running.
`auto_live_armed` means authority is enabled, not that every market-dependent
entry condition is satisfied. `broker_route_verified`, `official_cas_signal_seen`
and `final_value_source_verified` are separate observed facts. A no-trade day
is not an error. Never erase the ledger to recover from an incident.

Actual checks, test results and remaining empirical limits are recorded in
[RELEASE-READINESS.md](RELEASE-READINESS.md). A successful socket handshake,
synthetic fill or current-source test receipt cannot prove a real order route
or profitability.
