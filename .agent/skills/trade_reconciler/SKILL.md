---
name: Trade Reconciler
description: Automated cross-platform trade reconciliation tool comparing NinjaTrader 8, TradingView, and Python backtests trade-by-trade to flag fill discrepancies, slippage, and execution bugs.
---

# Trade Reconciler Skill

The **Trade Reconciler** automates cross-platform verification between NinjaTrader 8 Strategy Analyzer exports, TradingView Strategy reports, and Python institutional engines.

## 🎯 Primary Use Cases
1. **Reconcile NinjaTrader vs. Python**: Verify that live/simulated NinjaTrader trades match Python ground truth.
2. **Reconcile TradingView vs. Python**: Eliminate Pine Script repainting discrepancies.
3. **Audit Execution Divergence**: Identify slippage, missed entries, ghost signals, and bracket desynchronization.

---

## 🛠️ CLI Tool Usage

The core reconciler script is located at [`scripts/tools/reconcile_trades.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/tools/reconcile_trades.py).

### 1. Reconcile NinjaTrader 8 CSV Export
```bash
python scripts/tools/reconcile_trades.py --nt "<path_to_nt8_grid_csv>" --start-date 2026-01-01 --end-date 2026-08-15
```

### 2. Reconcile TradingView Strategy Report CSV
```bash
python scripts/tools/reconcile_trades.py --tv "<path_to_tv_strategy_csv>" --start-date 2026-01-01 --end-date 2026-08-15
```

### 3. Reconcile with Custom Tolerance & Output Report
```bash
python scripts/tools/reconcile_trades.py --nt "NinjaTrader Grid 2026-08-15 06-57 PM.csv" --tolerance-mins 15 --out "reports/custom_reconciliation.md"
```

---

## 📊 Standard Reconciliation Output
The tool produces a detailed Markdown report containing:
- **Summary Matrix**: Total trades, match rate, net P&L delta across platforms.
- **Matched Trades Audit**: Exact entry/exit timestamps, fill price differences, P&L delta per trade.
- **Platform A Only (Unmatched)**: Ghost signals or over-triggering trades.
- **Platform B Only (Unmatched)**: Missing setups or execution blocks.
