# Execution and capital frontier

Research-only extension registered before new results. No order placement,
activation or cloud deployment code. Previous experiments remain unchanged.

```bash
.venv/bin/python -m pytest -q tests/test_execution_frontier.py
.venv/bin/python -m research.execution_frontier.replay
.venv/bin/python -m research.execution_frontier.capital
.venv/bin/python -m research.execution_frontier.cash_capital
.venv/bin/python -m research.execution_frontier.report
```

The capital command authenticates through existing local configuration and
uses only quotes, funds, positions and margin-calculator requests. It saves
redacted request receipts privately. Do not publish credentials or treat a
closed-market quote as fill evidence.

The replay uses three already-observed 90-day periods, eight CE/PE signal
rules, three allocations and seven scenarios. Fixed limits/deadlines precede
all future prices. Entry-bar high is not used as an exclusion rule for a
resting limit. A modeled intrabar fill is assigned to the bar end; missing
or partial exposure is UNKNOWN. Complete outputs are in
`research/results/execution_frontier`; current source and raw inputs are
verified before reporting. These data cannot supply a tick-level simulator.

See [protocol](PROTOCOL.md), [mechanism inventory](RESEARCH.md) and
[results](../results/execution_frontier/REPORT.md).
