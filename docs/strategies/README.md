# Trading Strategies Documentation

This folder contains strategy documentation, backtesting results, and research files organized by strategy type.

> [!TIP]
> For backtest standards and data sources, see [BACKTEST_STANDARDS.md](BACKTEST_STANDARDS.md).

---

## Strategies Overview

| Strategy | Description | Status |
|:---|:---|:---|
| [9:30 Opening Range Breakout](9_30_breakout/) | NQ breakout based on first candle | ✅ Backtested |
| [Initial Balance Break](initial_balance_break/) | IB range breakout (10-year stats) | ✅ Validated |
| [Expected Moves](expected_moves/) | EM-based trading strategies | 📊 Research |

---

## 9:30 Opening Range Breakout (`9_30_breakout/`)

Trades the breakout of the 9:30 AM opening candle on NQ.

| Document | Description |
|:---|:---|
| [9_30_NQ_STRATEGY.md](9_30_breakout/9_30_NQ_STRATEGY.md) | Original strategy rules and logic |
| [9_30_NQ_V2_STRATEGY.md](9_30_breakout/9_30_NQ_V2_STRATEGY.md) | Enhanced version with filters |
| [nq_930_breakout.md](9_30_breakout/nq_930_breakout.md) | Backtest results and analysis |

**Scripts:** (`scripts/backtest/9_30_breakout/`)
- `verify_930_strategy.py` - Quick verification script
- `run_930_v2_strategy.py` - V2 strategy runner
- `compare_930_variants.py` - Variant comparison
- `generate_930_charts.py` - Chart generation
- `web/lib/backtest/strategies/nq-1min-strategy.ts` - TypeScript strategy class

---

## Initial Balance Break (`initial_balance_break/`)

Trades breakouts of the Initial Balance (first hour) range with 96% historical break probability.

| Document | Description |
|:---|:---|
| [README.md](initial_balance_break/README.md) | Strategy overview and rules |
| [STRATEGY_COMPLETE_GUIDE.md](initial_balance_break/STRATEGY_COMPLETE_GUIDE.md) | Comprehensive strategy guide |
| [STRATEGY_ENCYCLOPEDIA.md](initial_balance_break/STRATEGY_ENCYCLOPEDIA.md) | All strategy variants |
| [TRADE_EXAMPLES.md](initial_balance_break/TRADE_EXAMPLES.md) | Example trades with charts |
| [MAE_MFE_FINDINGS.md](initial_balance_break/MAE_MFE_FINDINGS.md) | MAE/MFE optimization |
| [VALIDATION_RESULTS.md](initial_balance_break/VALIDATION_RESULTS.md) | Backtest validation results |

**Subfolders:**
- `charts/` - Visual trade examples
- `historical_validation/` - Historical validation data
- `mechanism_evaluation/` - Entry mechanism comparisons
- `multi_asset_validation/` - Cross-asset testing
- `stop_loss_comparison/` - Stop loss optimization

**Backtest Results:**
- `backtest_results_all.csv` - Full 10-year backtest (94 KB)
- `backtest_results_*min.csv` - By timeframe (15m, 30m, 45m, 60m)

---

## Expected Moves (`expected_moves/`)

Research on expected move calculations and trading applications.

| Document | Description |
|:---|:---|
| [README.md](expected_moves/README.md) | EM methodology overview |
| [DATA_DICTIONARY.md](expected_moves/DATA_DICTIONARY.md) | EM data fields and calculations |
| [METHODOLOGY_COMPARISON.md](expected_moves/METHODOLOGY_COMPARISON.md) | Straddle vs IV approaches |
| [ES_COMPREHENSIVE_ANALYSIS.md](expected_moves/ES_COMPREHENSIVE_ANALYSIS.md) | ES-specific findings |
| [INTRADAY_TRADING_PLAYBOOK.md](expected_moves/INTRADAY_TRADING_PLAYBOOK.md) | EM-based trading strategies |
| [OVERNIGHT_ANALYSIS.md](expected_moves/OVERNIGHT_ANALYSIS.md) | Overnight session statistics |
| [INTRADAY_SR_ANALYSIS.md](expected_moves/INTRADAY_SR_ANALYSIS.md) | Support/Resistance analysis |

---

## Backtest Standards

See [BACKTEST_STANDARDS.md](BACKTEST_STANDARDS.md) for:
- Required CSV fields (Context, Execution, Outcome)
- Metric standardization (percentages)
- Visualization requirements
- Market regime validation periods
