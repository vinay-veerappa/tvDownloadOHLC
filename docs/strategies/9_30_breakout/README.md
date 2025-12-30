# 9:30 Opening Range Breakout (ORB) Strategy - V6

**Current Version:** 6.0 (Production)
**Status:** 🟢 Finalized & Synced (PineScript + NinjaTrader)

## 📌 Overview
The **9:30 ORB V6** is a high-precision volatility breakout strategy designed for **NQ Futures**. It captures the initial impulse of the US Equities Open (9:30 AM EST) using a trend-following approach with strict pre-trade filters.

---

## 📚 Documentation
This repository contains the complete Research, Specification, and Implementation of the strategy.

| Document | Purpose |
|----------|---------|
| **[📄 V7 SPECIFICATION](ORB_V7_SPEC.md)** | **Latest.** Cover the Queen exits, IMMEDIATE entry, optimized filters. |
| **[📄 V6 SPECIFICATION](ORB_STRATEGY_MASTER_SPEC.md)** | Previous production version with Pullback + Fallback. |
| **[📊 ANALYSIS & RESULTS](ANALYSIS_SUMMARY.md)** | 10-Year Backtest results and research insights. |
| **[🔬 OPTIMIZATION RESULTS](research/OPTIMIZATION_RESULTS.md)** | Parameter grid search and MAE/MFE analysis. |
| **[🧪 SCRIPT INVENTORY](research/PYTHON_SCRIPT_INVENTORY.md)** | Catalog of Python scripts for backtesting. |

---

## 📂 Directory Structure

### `ninjatrader/`
Contains the **NinjaScript (C#)** implementation.
- `ORB_V6_Strategy.cs`: Logic execution (Entry/Exit/Filters).
- `ORB_V6_Indicator.cs`: Visual overlays (Box, Signals, HUD).
- *Status: Pixel-Perfect Match with V6 Spec.*

### `pinescript/`
Contains the **TradingView (PineScript)** implementation.
- `ORB_V6_Strategy.pine`: Backtesting and alerts.
- `ORB_V6_Indicator.pine`: Visuals.

### `research/`
Contains detailed PDF reports and Markdown analysis on specific strategy components.
- Topics: Win Rate Optimization, Time Exits, MAE/MFE Risk Analysis, etc.
- See *Analysis & Results* for a summary of these findings.

### `archive/`
Contains obsolete versions (V1-V5) and legacy specifications. Referenced for historical context only.

---

## 🚀 Quick Start
1.  **Read the Spec**: [ORB_STRATEGY_MASTER_SPEC.md](ORB_STRATEGY_MASTER_SPEC.md) to understand the Rules.
2.  **Visual Check**: Install `ORB_V6_Indicator` on NinjaTrader or TradingView to visualize the setup on historical data.
3.  **Backtest**: Run `scripts/backtest/9_30_breakout/run_930_v6_strategy.py` to verify logic against local data.
