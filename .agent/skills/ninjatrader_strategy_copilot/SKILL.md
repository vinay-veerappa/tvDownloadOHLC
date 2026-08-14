---
name: NinjaTrader Strategy Copilot
description: Automates the end-to-end lifecycle of NinjaTrader 8 strategies including source deployment, MCP compilation, automated backtesting, and high-speed token-efficient trade log analytics.
applyTo: "**/*.cs, **/*Grid*.csv"
---

# 🏛️ NinjaTrader Strategy Copilot Skill

Use this skill whenever the user asks to:
1. **Analyze or debug NinjaTrader backtest exports** (CSV logs, summary sheets, performance grids).
2. **Deploy and sync C# strategies or base classes** to the NinjaTrader 8 custom directory.
3. **Compile and verify NinjaScript code** via the MCP bridge.
4. **Run and optimize Strategy Analyzer backtests** across instruments and timeframes.

---

## ⚡ 1. Token-Efficient Trade Log & Summary Analytics

Instead of dumping massive CSV files into context or writing scratch analysis scripts, execute a single command using `nt_log_analyzer.py`:

```powershell
# Analyze the newest Grid or Summary CSV automatically:
python -m scripts.ninjatrader.tools.nt_log_analyzer

# Analyze a specific CSV log file:
python -m scripts.ninjatrader.tools.nt_log_analyzer "NinjaTrader Grid 2026-08-14 12-02 AM.csv"

# Simulate filtering to Morning Initial Balance (09:30 - 10:30 ET):
python -m scripts.ninjatrader.tools.nt_log_analyzer --ib-only

# Simulate One-and-Done (First Pristine Setup of Each Day):
python -m scripts.ninjatrader.tools.nt_log_analyzer --first-trade-only
```

### Key Analytics Automatically Provided:
- **Macro Performance**: Net Profit, Gross Profit/Loss, Win Rate, Profit Factor, Payoff Ratio, Max Trailing Drawdown.
- **Bracket Health Check**: Automatically identifies rogue detached stops (losses $>25\text{ pts}$) and calculates artificial drag.
- **Directional Split**: Separates Long vs. Short expectancy and win rate.
- **Execution Window Diagnostics**: Compares Initial Balance ($09:30\text{--}10:30\text{ ET}$) vs. Late Morning Chop ($>10:30\text{ ET}$).
- **Holding Period**: Intraday exits vs. overnight/weekend holdovers.
- **Multi-Year Progression**: Year-by-year P&L and win rate breakdown.

---

## 🚀 2. Strategy Deployment & Sync

To deploy strategy C# source files and base classes from `scripts/ninjatrader/strategies/` to `C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\Strategies\`:

```powershell
# Deploy specific strategy (and its base classes):
python -m scripts.ninjatrader.tools.nt_deploy Bandits8020Bot

# Deploy all strategies:
python -m scripts.ninjatrader.tools.nt_deploy --all
```

---

## ⚙️ 3. Compilation via MCP

After deploying, trigger compilation via the native NinjaTrader MCP tool:

```json
{
  "ServerName": "ninjatrader",
  "ToolName": "nt_compile",
  "Arguments": { "debug": false }
}
```
* Verify `success: true` and `errorCount: 0`.

---

## 🧪 4. Automated Strategy Analyzer Backtesting

Run native backtests directly via the MCP bridge:

```json
{
  "ServerName": "ninjatrader",
  "ToolName": "nt_backtest",
  "Arguments": {
    "strategy": "Bandits8020Bot",
    "symbol": "MNQ 09-24",
    "period": "Second",
    "periodValue": 200,
    "from": "2024-06-15",
    "to": "2024-09-10",
    "params": {
      "AutoCalibrateInstrument": true,
      "SizingMode": "TargetRiskDollars",
      "TargetRiskDollars": 200,
      "UseRthOpenBias": true,
      "EarliestEntry": 930,
      "LatestEntry": 1030
    }
  }
}
```

---

## 📋 Best Practices & Failure Checks

1. **Stale Compilation Lock**: If identical compiler errors persist twice in a row, assume the NT8 UI editor or cache is locked and notify the user.
2. **Bracket Attachment Rule**: Always ensure strategies use tick-based OCO brackets (`SetStopLoss(CalculationMode.Ticks, ticks)`) and hard EOD flattening (`FlattenBy = 1555`) to prevent unmanaged overnight drift.
3. **Session Template Awareness**: Make sure backtests use appropriate trading hours (e.g. `CME US Index Futures RTH`) or explicit time-of-day filters in code.
