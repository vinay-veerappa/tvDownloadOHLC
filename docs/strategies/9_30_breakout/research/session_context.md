# 9:30 AM NQ Breakout Strategy - Session Context
**Date:** December 14, 2025

## Project Overview
Comprehensive 10-year backtest and analysis of the 9:30 AM Opening Range Breakout strategy for NQ (Nasdaq 100 Futures).

---

## Key Files Created

### Analysis Folder
**Location:** `c:\Users\vinay\tvDownloadOHLC\NQ_Strategy_Analysis_2016_2025\`

#### Data Files (CSVs)
- `Base_Strategy_2016_2025.csv` - No early exit (2,807 trades)
- `Threshold_0Pct_2016_2025.csv` - **Recommended** (2,761 trades)
- `Threshold_25Pct_2016_2025.csv` - 25% threshold
- `Threshold_50Pct_2016_2025.csv` - 50% threshold
- `Threshold_75Pct_2016_2025.csv` - 75% threshold

#### PDF Reports
- `analysis_report.pdf` - 10-Year Strategic Overview
- `risk_of_ruin.pdf` - Risk/Position Sizing Analysis
- `time_exit_analysis.pdf` - 9:44 Exit vs No Exit Comparison
- `mfe_profit_targets.pdf` - Optimal Profit Target Levels
- `timing_analysis.pdf` - Entry/Exit Time Patterns
- `winrate_optimization.pdf` - Target & Filter Comparison
- `walkthrough.pdf` - Complete Trader's Analysis
- `position_sizing_calculator.pdf` - Quick Reference Table

#### TradingView PineScript
- `ORB_Indicator.pine` - Visual indicator with signals
- `ORB_Strategy.pine` - Backtestable strategy

### Scripts Created
**Location:** `c:\Users\vinay\tvDownloadOHLC\scripts\`
- `full-scale-backtest.ts` - Generates all strategy CSVs
- `trader-analysis.ts` - Psychological/trader insights
- `timing-scaling-analysis.ts` - Entry/exit timing
- `analyze-mfe-targets.ts` - Optimal profit targets
- `win-rate-optimization.ts` - Target comparison
- `risk-of-ruin.ts` - Monte Carlo risk analysis
- `test-no-time-exit.ts` - No 9:44 exit test
- `multi-year-backtest.ts` - Multi-year runner

---

## Strategy Summary

### Core Rules
1. **Opening Range:** 9:30 AM ET candle (High/Low)
2. **Entry:** Close above range = LONG, Close below = SHORT
3. **Stop Loss:** Opposite side of range
4. **Exit Threshold:** 0% (Strict) - Close immediately if price closes back inside range

### Optimal Configuration
| Parameter | Value |
|-----------|-------|
| Target | 2.0R (or 1.0R for higher WR) |
| Max Range % | 0.25% filter |
| Time Exit | Optional (removing doubles profit) |
| Entry Time | 9:31 (immediate is best) |

### Key Findings
- **10-Year PnL:** +4,418 pts (with 9:44 exit), +9,478 pts (no time exit)
- **Win Rate:** 37% (2R target), 47% (1R target), 51% (0.5R target)
- **Risk of Ruin:** 0% at 2% account risk
- **Max Drawdown:** 44% historical
- **Best Days:** Monday, Tuesday, Thursday
- **Sweet Spot:** 0.10-0.18% range size

### Position Sizing ($3,000 MNQ Account)
- 2% risk = $60/trade = 1 MNQ contract
- Skip if range > 30 points

---

## Strategy Classes

### Nq1MinStrategy
**Path:** `web/lib/backtest/strategies/nq-1min-strategy.ts`
Base strategy without close-inside-range exit.

### Nq1MinCloseInRangeStrategy  
**Path:** `web/lib/backtest/strategies/nq-1min-close-in-range-strategy.ts`
Enhanced strategy with:
- `penetration_threshold` (0%, 25%, 50%, 75%)
- `max_range_pct` filter
- MAE/MFE tracking

---

## Data Source
- **Ticker:** NQ1! (1-minute)
- **Path:** `public/data/NQ1_1m/`
- **Bars:** 5.6M+ (2013-2025)
- **Chunk Format:** `chunk_0.json` to `chunk_N.json`

---

## Resume Checklist
- [ ] Review `ORB_Indicator.pine` in TradingView
- [ ] Test `ORB_Strategy.pine` backtest
- [ ] Integrate strategy into live trading platform
- [ ] Consider automated alerts setup
- [ ] Analyze day-of-week refinements
- [ ] Test hybrid exit approach (1.5R scale out)
