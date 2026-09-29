# Publication/deployment attempt — 29 September 2026

Requested destination: `https://github.com/zaynvirkk/Dhan-Bot` (`main`).
Requested Google Cloud project: `project-cead8bae-10ea-4ea9-875`.
Existing target from the runbook: `sablestone-dhan-cas`, `asia-south1-a`.

## Release contents

The local release includes the accumulated runtime/recovery fixes, research
code and derived results, tests, literature notes and the index-option API
audit. It corrects Dhan FULL packet decoding and preserves market statistics.
The runtime still implements NIFTY CAS; catalogue discovery is not multi-index
live execution or an implementation of the selloff/rebound research candidate.

Broker tokens, PIN/TOTP material, production configuration, SQLite state,
licensed raw datasets/PDFs and raw account/authentication/cloud/margin receipts
stay local and ignored. Research documents may link to those private receipts;
their absence from GitHub must not be treated as an empty successful result.

## Verification and access results

The preceding source check ran `python3 -m pytest`: 270 passed; six integration
cases failed while creating local socket listeners in this restricted runtime.
The focused new protocol/catalogue/boundary suite passed 33 tests. No code
changes were made after those checks during publication preparation. This is
not a complete current-source integration verification or market-hours test.

`git ls-remote --heads origin main` failed to resolve github.com. The browser
bridge could not connect; startup failed because its home-directory log is on
a read-only filesystem. The provisioned gcloud binary exists, but instance
inspection failed because its credentials database/log directory is read-only.
No VM connection, source install, service restart or live activation occurred.
A GitHub integration was found but is not connected. No alternative cloud
provider was substituted for the requested project.

The systemd service template retains `DHAN_BROKER_READ_ONLY=1`. Software
deployment can proceed with orders disabled after connectivity is restored.
Real-money order activation remains a separate direct operator action; it was
not performed by this publication attempt.

## Remaining operations

1. Push the prepared `main` commit to the requested origin and verify the remote
   commit ID. Do not force-push if remote history has advanced.
2. Inspect the existing VM, effective unit settings and current account/position
   state. The 27 September read-only status is historical, not current evidence.
3. Install the exact published revision while retaining broker-write disablement,
   production secrets and the existing ledger. Run the full offline verification
   in a socket-capable environment before restarting the service.
4. Verify the installed commit, effective read-only setting, service health,
   authentication renewal and real data connections. Do not report a deployment
   as trading, or a connected feed as a profitable strategy.

See [cloud runbook](CLOUD-DEPLOYMENT.md) for existing VM paths and
[API audit](INDEX-OPTIONS-API-AUDIT.md) for the dated instrument inventory.
