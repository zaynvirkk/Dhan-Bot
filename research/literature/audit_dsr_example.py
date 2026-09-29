"""Replicate L18's published numerical example, not a market backtest.

The normal approximation and effective independent trial count are assumptions.
Do not interpret this arithmetic check as a live deployment test.
"""
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist


def example(trials, skew, kurtosis):
    normal = NormalDist()
    gamma = 0.5772156649015329
    # Paper example: 250 days/year, annual SR=2.5, annual SR variance=0.5.
    sr = 2.5 / math.sqrt(250)
    threshold = math.sqrt(0.5 / 250) * (
        (1 - gamma) * normal.inv_cdf(1 - 1 / trials)
        + gamma * normal.inv_cdf(1 - 1 / (trials * math.e))
    )
    # Pearson kurtosis (normal=3), NOT excess kurtosis (normal=0).
    z = ((sr - threshold) * math.sqrt(1250 - 1)
         / math.sqrt(1 - skew * sr + (kurtosis - 1) * sr * sr / 4))
    return {"trials": trials, "skew": skew, "pearson_kurtosis": kurtosis,
            "daily_sr_threshold": threshold, "dsr": normal.cdf(z)}


def main():
    root = Path(__file__).resolve().parents[2]
    pdf = root / "artifacts/private/gauntlet/literature/deflated_sharpe.pdf"
    cases = [example(100, -3, 10), example(46, -3, 10), example(88, 0, 3)]
    published = [0.9004, 0.9505, 0.9505]
    for case, expected in zip(cases, published):
        case["published_rounded_dsr"] = expected
        case["matches_published_rounding"] = abs(case["dsr"] - expected) < 0.0001
        assert case["matches_published_rounding"], case
    report = {
        "kind": "PUBLISHED_EXAMPLE_ARITHMETIC_NOT_MARKET_BACKTEST",
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "annualization_days": 250, "observations": 1250, "cases": cases,
        "historical_strategy_profitability": "NOT_TESTED_BY_THIS_SCRIPT",
    }
    Path(__file__).with_name("dsr_example_audit.json").write_text(
        json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
