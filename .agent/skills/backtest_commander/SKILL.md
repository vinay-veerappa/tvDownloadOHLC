---
name: Backtest Commander
description: Automates the execution, validation, and reporting of trading strategy backtests.
---

# Backtest Commander

## Purpose
Streamlines the process of running backtests, ensuring consistent configuration and easy-to-read reports.

## Workflow

### 1. Strategy Identification
- Locate strategy scripts in `scripts/backtest/` or `scripts/strategies/`.
- Identify the target runner (e.g., `run_930_v2_strategy.py`).

### 2. Configuration Check
- Ensure `DATA_INVENTORY.md` confirms data availability for the requested ticker/timeframe.
- Check hardcoded dates in the script before running.

### 3. Execution
- Run the python script.
- **Important**: Use `--help` if available to check for arguments.

### 4. Result Analysis
- Locate the output CSV (usually in `results/`).
- **Summarize**:
    - **Total PnL**
    - **Win Rate**
    - **Max Drawdown**
    - **Trade Count**
- Compare against previous baselines if available.

### 5. Report Generation
- If significant, generate a markdown report `docs/strategies/[STRATEGY_NAME]_REPORT.md` summarizing the findings.
