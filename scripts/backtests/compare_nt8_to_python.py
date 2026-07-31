"""
Compare an exported NinjaTrader 8 Strategy Analyzer CSV to the Python
EMAPullbackBot backtest target metrics.

Usage:
    python scripts/backtests/compare_nt8_to_python.py path/to/nt8_export.csv

The script expects the CSV to contain at least these columns:
    'Trade #', 'Entry price', 'Exit price', 'Profit', 'Cum profit'
or common alternatives like 'Profit Pips', 'PnL', 'NetProfit'.

Python target (from context):
    ~273 trades, ~$11,539 PnL, profit factor ~1.44,
    avg trade ~$42.27, max drawdown ~$2,813
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

PYTHON_TARGET = {
    'trades': 273,
    'total_pnl': 11539.0,
    'profit_factor': 1.44,
    'avg_trade': 42.27,
    'max_drawdown': 2813.0,
}


def find_column(df: pd.DataFrame, candidates):
    for c in candidates:
        matches = [col for col in df.columns if c.lower() in col.lower()]
        if matches:
            return matches[0]
    return None


def compute_metrics(df: pd.DataFrame) -> dict:
    profit_col = find_column(df, ['Profit', 'NetProfit', 'PnL', 'Profit Pips'])
    cum_col = find_column(df, ['Cum profit', 'CumProfit', 'Cumulative Profit', 'Equity'])
    if profit_col is None:
        raise ValueError(f"Could not find profit column in: {list(df.columns)}")

    pnls = pd.to_numeric(df[profit_col], errors='coerce').dropna().values
    total = float(pnls.sum())
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    pf = abs(wins.sum() / losses.sum()) if losses.sum() != 0 else np.inf
    equity = np.cumsum(pnls)
    running_max = np.maximum.accumulate(equity)
    mdd = float((running_max - equity).max())

    return {
        'trades': len(pnls),
        'total_pnl': total,
        'win_rate': float(len(wins) / len(pnls)) if len(pnls) else 0,
        'profit_factor': pf if pf != np.inf else None,
        'avg_trade': float(pnls.mean()) if len(pnls) else 0,
        'max_drawdown': mdd,
    }


def pct_diff(actual, target):
    if target is None or target == 0:
        return 0.0
    return round((actual - target) / target * 100, 2)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {Path(__file__).name} <nt8_export.csv>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    metrics = compute_metrics(df)

    print(f"\nNT8 Strategy Analyzer: {path}")
    print("-" * 50)
    for key in PYTHON_TARGET:
        target = PYTHON_TARGET[key]
        actual = metrics[key]
        diff = pct_diff(actual, target)
        print(f"{key:20s}: {actual:>12,.2f}  target {target:>10,.2f}  ({diff:+.1f}%)")

    print("-" * 50)
    print(f"Win rate: {metrics['win_rate']*100:.1f}%")


if __name__ == '__main__':
    main()
