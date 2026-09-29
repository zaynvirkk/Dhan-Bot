# Broader research replay

Research only. No order endpoint or deployment command is used. Licensed
market history and authenticated receipts stay in `artifacts/private/gauntlet`;
the derived comparison and execution ledger are in `research/results/broader`.

The frozen [protocol](PROTOCOL.md) and [source review](RESEARCH.md) distinguish
tested hypotheses from unscored economic families. Both 90-day windows are
reused discovery data. Do not treat their best result as a holdout winner.

From the repository root:

```bash
.venv/bin/python -m research.broader.prepare archives
.venv/bin/python -m research.broader.prepare rank
.venv/bin/python -m research.broader.prepare stock_history
.venv/bin/python -m research.broader.prepare signals
.venv/bin/python -m research.broader.options prepare
.venv/bin/python -m research.broader.bans
.venv/bin/python -m research.broader.replay cash
.venv/bin/python -m research.broader.replay options
.venv/bin/python -m research.broader.controls
.venv/bin/python -m research.broader.crosscheck
.venv/bin/python -m research.broader.report
.venv/bin/pytest
```

Run collection stages sequentially before replay. Read-only broker calls need
the existing local data credentials; never put credentials in the command
line, public report or chat. Request failures are saved as unresolved states.
Cached reads avoid repeating successful external requests.

The report verifies source/input digests, registration and all resolved trade
arithmetic. An UNKNOWN final balance is deliberately null even when earlier
trades resolved. A no-fill result is not a profitable strategy.

Corrections after the initial cash run: a published NSE special-session
circular resolves the VEDL April 30 opening gap as unavailable at 09:30;
the selector does not substitute another stock. Metadata on unused farther
strikes does not invalidate a nearer known selection. Original snapshots are
retained. No signal threshold or exit is retuned to improve outcomes.

When cached active metadata predates expiry, history collection switches to
the expired endpoint using the same exchange token and explicit expiry.
The first option snapshot is retained before this routing correction.
