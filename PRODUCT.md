# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The owner of the funded Dhan account needs to see what the existing bot is
observing and doing, from a browser, without reading SSH logs.

## Product Purpose

A private operational dashboard for the existing NIFTY CAS service on Google
Cloud. Success means the owner can identify trading authority, service/data
freshness, connection failures, account observations and actual ledger activity.

## Stack

Existing Python service and SQLite ledger. Implementation assumption: a small
WSGI adapter with plain HTML/CSS/JavaScript, avoiding a separate frontend build.
Gunicorn serves the adapter behind Caddy HTTPS on the existing VM.

## Capabilities and Constraints

The current strategy is CAS_LAG_V1. This task does not change signal or sizing
rules. The dashboard reads allowlisted status and ledger fields; it does not
receive broker credentials, send orders, or modify trading authority.
Unknown and stale inputs remain visibly different from zero and healthy.
The user requested deployment to zaynvirkk/Dhan-Bot and the existing GCP VM,
and instructions for operator-run real-money activation.

## Operating Context

Private single-owner monitoring during and outside Indian market hours.
Desktop and phone support are implementation assumptions. A hostname based on
the existing VM IP and a separate dashboard password were confirmed by the user.
The chosen hostname is dhan.34.100.255.111.sslip.io.
The current session cannot access GitHub/GCP or bind local sockets; delivery
must distinguish implemented code from a verified public URL.

## Evidence on Hand

Runtime status.json, connections.json, and SQLite intents/orders/fills/incidents.
Historical provider observations exist privately. They cannot be presented as
current live data. No frontend or confirmed profitable strategy existed at task
start. Raw credentials, payloads and account identifiers are not public UI data.

## Product Principles

- Show provenance and observation age next to financial and connection data.
- Diagnose failures without implying a failed request returned an empty account.
- Keep monitoring separate from operator-run funded activation.
- Use actual persisted observations; never synthesize performance or fills.
