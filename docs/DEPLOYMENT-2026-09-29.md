# GitHub and Google Cloud deployment — 29 September 2026

Repository: `https://github.com/zaynvirkk/Dhan-Bot`, branch `main`.
Project: `project-cead8bae-10ea-4ea9-875`.
Existing VM: `sablestone-dhan-cas`, `asia-south1-a`, IP `34.100.255.111`.

## Delivered

During the unrestricted part of this session, GitHub authentication and
publication succeeded. Kimi WebBridge reached the signed-in Google Cloud
console in the `Dhan deployment` tab group.

Runtime release `884178a01bd4c0a5ab211273fc921fa2c52d5c3a` was pushed to
GitHub and installed on the existing VM through IAP. The clean remote checkout
advanced from `d5efcfd` by fast-forward using a hash-checked Git bundle.
Production configuration, credentials and the existing ledger were preserved.
No additional VM, billing upgrade or public application port was created.

Both local and installed-source verification passed **276 tests**, including
all **60 acceptance cases**, and rejected all **15 injected production faults**.
The source digest is
`84d28084692f4d4feda97e44dad391c4d2838a4d2c96dcbba75055e8d5683d58`.
The VM generated its own current-source verification marker before restart.

The updated service was active/running, with zero automatic restarts at the
post-deployment observation. Its status reported `software_verified=true`,
`writes=false` and `auto_live_armed=false`. Configuration and mandate authority
remain false; systemd retains `DHAN_BROKER_READ_ONLY=1`.

## Read-only provider checks

Observed on 29 September around 07:42 IST:

| Check | Observed result |
|---|---|
| Dhan identity and permissions | Account matches; derivatives enabled; data plan active |
| Funds and account state | INR 9,411.18; zero positions, orders and trades |
| VM egress and broker whitelist | Expected static IP matches |
| Current NIFTY contract metadata | 29 September expiry; 538 instruments; lot 65; freeze quantity 1,800 |
| Upstox index feed | WebSocket and binary index frames received |
| Dhan order-update socket | Connected and ping responded; actual order route unverified |
| Dhan options feed | Socket opened; check failed with ContractError while awaiting depth; exact cause unresolved |

The aggregate connection check is **not passing** while the options-feed
failure remains. CAS/IEP and a real order route are not verified by these
pre-market observations. No order probe or funded activation was performed.

## Latest access restriction — 19:37 IST

The subsequent session permission change restored restricted network access
and made the home credential/log directories read-only. Fresh attempts failed:
GitHub could not resolve `github.com`; gcloud could not write
`~/.config/gcloud/credentials.db`; the local Kimi endpoint was unreachable.
No credentials were moved and no alternate route was used to bypass those
restrictions. The latest documentation changes are saved locally; their
publication and another VM inspection are blocked in this session.

Two follow-up feed diagnostics timed out without usable packet evidence.
A bounded read-only diagnostic script was copied to the VM, but its final
invocation was blocked by the new permissions. These attempts do not establish
a particular protocol defect or provider rejection code. The last verified
remote runtime remains `884178a`; its present health after the access change
is unverified. Real-money order activation was not performed.

## Scope and evidence

The runtime remains NIFTY CAS. Catalogue discovery does not implement trading
across every index or the separate rebound research candidate. Software tests
and connected APIs do not establish profitability; that status remains UNKNOWN.

Broker tokens, PIN/TOTP material, production configuration, SQLite state,
licensed raw datasets/PDFs and raw account/authentication/cloud/margin receipts
remain private and ignored. Fresh deployment receipts are stored locally under
`artifacts/private/deployment-20260929/`. Missing private evidence in the public
repository must not be interpreted as an empty successful result.

See [cloud runbook](CLOUD-DEPLOYMENT.md) and [index API audit](INDEX-OPTIONS-API-AUDIT.md).
