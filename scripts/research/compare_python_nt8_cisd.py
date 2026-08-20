"""Compare Python and NT8 IFVG/CISD Variant2 backtest results."""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import pandas as pd

# Load Python trades
py_trades = pd.read_csv("reports/research/python_cisd_variant2_trades.csv")
print("=" * 90)
print("PYTHON (Variant2, 5min, NQ1, Jan 2025 - Mar 2026)")
print("=" * 90)
print(f"Total signals: {len(py_trades)}")
print(f"  LONG:  {len(py_trades[py_trades.direction == 'LONG'])}")
print(f"  SHORT: {len(py_trades[py_trades.direction == 'SHORT'])}")
print(f"Date range: {py_trades.signal_time.min()} to {py_trades.signal_time.max()}")
print(f"Avg risk pts: {py_trades.risk_pts.mean():.2f}")
print()

# NT8 metrics from the backtest API result
nt8 = {
    "entries": 422,
    "totalTrades": 844,
    "winners": 328,
    "losers": 501,
    "tradeWinRatePct": 38.9,
    "profitFactor": 1.035,
    "netProfit": 6840,
    "maxDrawdown": -34730,
    "firstEntry": "2025-01-02T10:05:00",
    "lastExit": "2026-03-31T11:05:00",
    "exitReasons": {"Profit target": 298, "Stop loss": 544, "EOD Flatten": 2},
}
print("=" * 90)
print("NT8 (Variant2, 5min, NQ 09-26, Jan 2025 - Mar 2026)")
print("=" * 90)
print(f"Entries: {nt8['entries']}")
print(f"Total trades (2-contract pack): {nt8['totalTrades']}")
print(f"  Winners: {nt8['winners']}")
print(f"  Losers:  {nt8['losers']}")
print(f"Win rate: {nt8['tradeWinRatePct']}%")
print(f"Profit factor: {nt8['profitFactor']}")
print(f"Net profit: ${nt8['netProfit']:,}")
print(f"Max DD: ${nt8['maxDrawdown']:,}")
print(f"Exit reasons: {nt8['exitReasons']}")
print()

# Side-by-side comparison
print("=" * 90)
print("COMPARISON")
print("=" * 90)
py_entries = len(py_trades)
nt8_entries = nt8["entries"]
print(f"{'Metric':<30} {'Python':>15} {'NT8':>15} {'Diff':>15}")
print("-" * 75)
print(f"{'Entries':<30} {py_entries:>15} {nt8_entries:>15} {nt8_entries - py_entries:>+15} ({(nt8_entries - py_entries)/max(py_entries,1)*100:>+.1f}%)")
print()

# Compare first few signals
print("First 5 Python signals:")
for _, row in py_trades.head(5).iterrows():
    print(f"  {row.signal_time}  {row.direction:<5} entry={row.entry_price} stop={row.stop_price} risk={row.risk_pts}")
print()
print("First 5 NT8 entries (from API):")
nt8_first = [
    ("2025-01-02T10:05:00", "Long", 22795.50, 22817.25, "TP"),
    ("2025-01-02T10:05:00", "Long", 22795.50, 22794.25, "SL"),
    ("2025-01-03T09:50:00", "Long", 22827.25, 22796.50, "SL"),
    ("2025-01-03T09:50:00", "Long", 22827.25, 22796.50, "SL"),
    ("2025-01-03T10:30:00", "Short", 22725.50, 22715.75, "TP"),
]
for t in nt8_first:
    print(f"  {t[0]}  {t[1]:<5} entry={t[2]} exit={t[3]} {t[4]}")
print()

# Key observations
print("=" * 90)
print("KEY OBSERVATIONS")
print("=" * 90)
print("""
1. SIGNAL COUNT: Python generates 408 signals vs NT8's 422 entries (+14, +3.4%).
   Close but not identical -- the difference is likely from:
   - Contract rollover: NT8 uses NQ 09-26 (single contract), Python uses NQ1 (continuous)
   - Data differences: NT8 may have slightly different OHLC bars at contract rollover

2. FIRST SIGNAL ALIGNMENT:
   - Python first signal: 2025-01-02 09:55 LONG @ 22303.25
   - NT8 first entry:     2025-01-02 10:05 Long @ 22795.50
   Different entry times AND prices -- this is the contract difference:
   - Python NQ1 = continuous (back-adjusted) -> 22303.25
   - NT8 NQ SEP26 = raw front-month -> 22795.50
   The 492-point gap is the roll adjustment between continuous and raw contract.

3. DIRECTION PARITY:
   - Python first: LONG at 09:55
   - NT8 first:    Long at 10:05
   Same direction, 10 min apart -- likely a bar-timing difference (NT8 OnBarClose
   vs Python merge_asof alignment).

4. TRADE SIMULATION:
   - Python: signals only (no trade simulation in this run)
   - NT8: full simulation with 2-contract pack, TP1/TP2, stop loss
   To compare trade-level PnL, need to run Python's simulate_trade_policy().

NEXT STEPS:
   - Run Python trade simulation with CoverTheQueen policy for direct PnL comparison
   - Update NT8 diag CSV date filter to cover the full backtest range
   - Run bar-by-bar diagnostic comparison once both CSVs exist
""")