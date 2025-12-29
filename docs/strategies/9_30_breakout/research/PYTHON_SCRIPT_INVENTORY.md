# Python Backtest Script Inventory

This document catalogs the existing Python scripts used to research and validate the 9:30 Breakout Strategy variants.
Scripts are located in: `scripts/backtest/9_30_breakout/`

## Core Backtesters

| Script | Logic Implemented | Key Features |
|--------|-------------------|--------------|
| `run_930_v2_strategy.py` | **V2 Optimized** | Breakout Close, 0.2% Hybrid SL, Dynamic TP. Supports Tuesday/Extreme Filters. |
| `compare_930_variants.py` | **Variant Comparison** | Compares `Base`, `NoEarlyExit`, and `Enhanced (CTQ)` (Cover the Queen). Implements Multi-Attempt logic and Break-Even stops. |
| `verify_930_strategy.py` | **Validation** | Basic verification script to check data integrity and basic trade logic execution. |

## Analysis Tools

| Script | Purpose | Output |
|--------|---------|--------|
| `analyze_mfe_mae.py` | **Sensitivity Analysis** | Analyzes `MFE` (Maximum Favorable Excursion) to find optimal TP targets and `MAE` (Heat) to set Stop Loss. |
| `analyze_pullback_conditions.py` | **Pullback Research** | Tests efficiency of Limit Entries vs Market Entries (Slippage Analysis). |
| `final_composite_analysis.py` | **Composite Scoring** | Combines multiple metrics (Win Rate, Profit Factor, Drawdown) to rank strategy variants. |
| `generate_930_charts.py` | **Visualization** | Generates matplotlib charts of specific trade days for visual debugging. |

## Specialized Scripts

- **`analyze_mickey_mechanics_v2.py`**: Investigation into specific "Mickey" patterns (Deep Pullback reversals).
- **`analyze_vvix_correlation.py`**: Statistical correlation between 9:30 AM VVIX Open and Intraday Range probabilities.
- **`check_entry_sync.py`**: Debug tool to compare Python Entry Prices vs NinjaTrader CSV exports (Parity Check).

## Legacy Note
Most of these scripts target the **V2** or **V5** logic. 
For **V6** (Current Production Release), specific features like **Regime Filter** and **VVIX Filter** are hard-coded in the new `run_930_v6_strategy.py` (Implementation Pending).
