# Money and execution visibility, 12 October 2026

Dashboard release `810add397357d543e94bc1764a9b89c8f69bba1a` is pushed to
GitHub and deployed at https://dhan.34.100.255.111.sslip.io/.

The overview starts with available cash, open positions, durable recorded fills
and broker-reported P&L. Missing P&L remains unavailable, not zero. Missing ledger
counts remain unknown. A fresh unverified order route is shown as an entry blocker
instead of ordinary signal watching. That blocker cannot obscure open-position
management or stale status. Unmet strategy conditions are labelled Not met, with
actual values and thresholds under native disclosures. Auction input details are
collapsed; actual orders precede the sampled monitoring history.

## Verified live state

At 12:56 IST, the authenticated dashboard and VM agree: INR 8,822.36 cash,
zero open positions, zero recorded fills, enabled trading authority, and
unverified order route. Funded PID 329313 is running with zero service restarts
and valid software verification on release `c57221f`. All three sockets are
connected. Provider/receipt ages remain separate from socket connectivity.
A fresh 12:58 snapshot had accepted index/book observations under two seconds old.

The morning opening gap was +0.323%, below the rule's 0.5% threshold. Its
09:45–11:30 entry window has finished. Rebound next evaluates at 15:10 IST;
CAS is not eligible today, with next loaded NIFTY expiry 13 October.
Today's permitted route attempt is already used. The earlier request to allow
two attempts under unchanged cash caps remains unanswered. No mandate, strategy,
ledger, budget or order-route requirement was changed by this deployment.

## Verification

`node tests/dashboard_stream_test.cjs` and focused dashboard tests pass.
Deployment verifies public HTTPS authentication and private current account reads.
Authenticated 1440px and 390px browser inspection confirms displayed cash/fills
and blocker match the API, no document overflow, and collapsed detailed inputs.
Screenshots: `/tmp/dhan-money-desktop-20261012.png` and
`/tmp/dhan-money-mobile-20261012.png`. Browser emulation was restored afterward.
The design detector's existing dash-placeholder and cadence advisories were
reviewed; no fabricated trading graphics were introduced.

Covered trading source digest remains
`abb9f208fdae9fb84e8a940e1c625d57869e6406079e3d99af49e79e19446459`.
The funded trader was not restarted or reactivated.

## Economic limitation

These deployed strategies remain experimental. The stored gap-fade/rebound
research contains losing earlier periods and inconclusive noise tests. Running
software, enabling authority and fixing execution do not establish profitability.
No profit, completed strategy trade, or permission to exceed the saved probe
allowance is claimed.
