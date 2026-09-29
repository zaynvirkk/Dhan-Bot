"""Audit two pure published calculations; never execute the author's main.

These synthetic fixtures test arithmetic, not historical profitability.
Run with system python3 (NumPy), after downloading the pinned public source.
"""
import ast
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'artifacts/private/gauntlet/literature/vrp_strategy_code.html'
PINNED_COMMIT = '8b8589009806b0bdfb876c7005c9ee95a5f26924'


def main():
    source = SOURCE.read_bytes()
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'compute_performance')
    namespace = {'np': np, 'math': math, 'MIN_OBS_SHARPE': 30}
    exec(compile(ast.Module(body=[function], type_ignores=[]),
                 '<isolated published compute_performance>', 'exec'), namespace)
    # Thirty identical losses avoid an unrelated small-sample warning.
    rows = [{'net_return': -0.01, 'net_pnl': -30.0, 'cost': 3.0}
            for _ in range(30)]
    result = namespace['compute_performance'](rows, 'SYNTHETIC', 'ATM')
    initial_margin = 3000.0
    true_cost_pct = 100 * rows[0]['cost'] / initial_margin
    wealth = np.concatenate(([1.0], np.cumprod([0.99] * 30)))
    correct_dd = float(np.min(wealth / np.maximum.accumulate(wealth) - 1))
    checks = {
        'published_average_cost': result['mean_monthly_cost'],
        'fixture_cost_rupees_per_unit': 3.0,
        'fixture_cost_percent_of_margin': true_cost_pct,
        'published_drawdown': result['max_drawdown'],
        'drawdown_including_initial_wealth': correct_dd,
        'raw_cost_is_not_percent_of_margin':
            not math.isclose(result['mean_monthly_cost'], true_cost_pct),
        'initial_wealth_omission_understates_drawdown':
            result['max_drawdown'] > correct_dd,
    }
    assert checks['raw_cost_is_not_percent_of_margin']
    assert checks['initial_wealth_omission_understates_drawdown']
    report = {
        'kind': 'SYNTHETIC_ARITHMETIC_AUDIT_NOT_MARKET_BACKTEST',
        'commit': PINNED_COMMIT,
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'isolated_function': 'compute_performance',
        'checks': checks,
        'historical_occurrence_and_profitability': 'NOT_REPRODUCED',
    }
    out = Path(__file__).with_name('vrp_function_audit.json')
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
