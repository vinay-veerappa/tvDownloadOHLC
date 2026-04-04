# Unified Research CLI User Guide

## Introduction
The `run_backtest.py` script is the centralized tool for strategy discovery, institutional backtesting, and parameter optimization. It implements the 7-layer research protocol to ensure statistical rigor.

## Location
`scripts/trading_framework/run_backtest.py`

## Usage

```powershell
python scripts/trading_framework/run_backtest.py --ticker <TICKER> --strategy <STRATEGY> [options]
```

### Arguments

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **--ticker** | string | NQ1 | Ticker symbol to test (NQ1, ES1, etc.) |
| **--strategy** | string | box_reversion | Strategy key registered in `registry.py` |
| **--config** | string | sessions.yaml | Path to the YAML configuration file |
| **--optimize** | flag | False | Enable Optuna-based parameter optimization |
| **--trials** | int | 20 | Number of optimization trials (if --optimize is set) |

### Example Commands

**1. Standard Institutional Backtest**
```powershell
python scripts/trading_framework/run_backtest.py --ticker NQ1 --strategy box_reversion
```

**2. 100-Trial Parallel Optimization**
```powershell
# Requires a powerful machine for high internal thread count
python scripts/trading_framework/run_backtest.py --ticker ES1 --strategy box_reversion --optimize --trials 100
```

## Output Artifacts

All outputs are saved to `scripts/trading_framework/reporting/outputs/`.

### 1. Performance Tearsheet (.md)
A detailed markdown report containing:
- **Institutional Scoreboard**: Grades (A-F) for EV, PF, SQN, and DRR.
- **Trade Stats**: Win rate, expectancy, and max drawdown.
- **Risk Analysis**: Risk of Ruin (RoR) and Monte Carlo pass probability.

### 2. MFE/MAE Excursion Plots (.png)
Visual analysis of trade efficiency:
- **Scatter Plots**: MAE vs MFE to identify stop-loss and take-profit "sweet spots".
- **Density Histograms**: Distribution of excursions across different time horizons.

### 3. Institutional Leaderboard (index.html)
A premium dashboard to view and compare all research runs in a single view.
- Open `scripts/trading_framework/reporting/outputs/index.html` in any browser.

## Adding New Strategies
To enable your own strategy logic in the CLI:
1.  Implement your logic class in `scripts/strategies/logic/`.
2.  Register the class in `scripts/trading_framework/strategies/registry.py`.
3.  The CLI will automatically discover it via the `--strategy` flag.
