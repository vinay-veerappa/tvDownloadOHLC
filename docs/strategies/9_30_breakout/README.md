# 9:30 Opening Range Breakout Strategy

## Overview

This folder contains documentation for the NQ 9:30 Opening Range Breakout strategy and its variants.

---

## Strategy Comparison

| Aspect | V1 (Original) | V2 (Optimized) |
|:---|:---|:---|
| **Range Definition** | 9:30 candle H/L | 9:30 candle H/L |
| **Entry Window** | 09:31 - 09:44 | 09:31 - 09:35 |
| **Entry Trigger** | Close above/below range | Cross above/below range |
| **Hard Exit** | 09:44 (14 min) | 10:00 (30 min) |
| **Stop Loss** | Opposite side of range | Tighter of: 0.20% OR opposite side |
| **Take Profit** | 2R fixed | 0.80x of 9:30 range (dynamic) |
| **Filters** | None | Tuesday avoidance, Extreme range filter |

---

## Strategy Variants

### V1: Original Strategy (`9_30_NQ_STRATEGY.md`)

**Concept:** Trade the breakout/reversal from the 9:30 opening candle with tight time management.

**Key Rules:**
- Wait for 9:30 candle to close, define range H/L
- Enter Long on close above High, Short on close below Low
- Stop Loss at opposite side of range
- Exit ALL positions at 09:44 (before 9:45 reversal window)
- Take Profit: 1R (partial), 2R (remaining)

**Key Behaviors:**
- "The Snap" (09:30-09:34): Violent initial move
- "RTFV" (09:35-09:39): Return to Fair Value
- 09:45 Reversal: High probability direction change

---

### V2: Optimized Strategy (`9_30_NQ_V2_STRATEGY.md`)

**Concept:** Data-driven filters to avoid low-probability setups.

**Key Enhancements:**
1. **Tuesday Avoidance**: DO NOT trade Tuesdays (negative historical expectation)
2. **Extreme Range Filter**: Skip if 9:30 range > 0.20% (top 25% of rolling 20-day distribution)
3. **Tighter Entry Window**: 09:31-09:35 only (vs 09:44 in V1)
4. **Dynamic TP**: 80% of 9:30 range (scales with daily volatility)
5. **No Breakeven Move**: Data shows moving to BE chokes the trade
6. **Extended Hold**: Test exits at 9:45, 10:00, 10:30, 12:00, 4:00 PM

**Risk Management:**
- Initial Stop: 0.20% OR structural (whichever is tighter)
- No BE move until TP or hard exit

---

## Backtest Results (Dec 2025)

**Dataset:** 30 days (Nov 17 - Dec 15, 2025)
**Script:** `scripts/backtest/9_30_breakout/verify_930_strategy.py`

| Metric | V1 Result |
|:---|:---|
| Trades | 19 |
| Win Rate | 36.8% (7W / 12L) |
| Net PnL | -38.50 pts |
| Required Win Rate | 33% (for 2R) |

**Observations:**
- Logic correctly captures breakouts
- Time exit (09:44) prevents full stops but also cuts runners
- Win rate marginally above theoretical breakeven but slippage/fees not included
- V2 filters (Tuesday, extreme range) not yet validated in this backtest

### Example Trades
| Date | Direction | Entry | Exit | Result | Reason |
|:---|:---|---:|---:|:---|:---|
| 2025-11-17 | LONG | 25011.75 | 25125.25 | WIN | TP (2R) |
| 2025-11-18 | SHORT | 24670.25 | 24758.75 | LOSS | SL |
| 2025-12-15 | SHORT | 25600.00 | 25543.50 | WIN | Time Exit |

---

## Research & Analysis

We have conducted extensive multi-year research (2016-2025) on the 9:30 breakout strategy. Detailed reports are available in the [research/](research/) folder:

- **[Win Rate Optimization](research/winrate_optimization.md)**: Analysis of trade frequency vs. quality.
- **[Time Exit Analysis](research/time_exit_analysis.md)**: Comparing 9:45, 10:00, and EOD exits.
- **[MFE Profit Targets](research/mfe_profit_targets.md)**: Statistical distribution of maximum favorable excursion.
- **[Risk of Ruin](research/risk_of_ruin.md)**: Position sizing and drawdown analysis.
- **[Session Context](research/session_context.md)**: Impact of overnight gaps and volume regimes.
- [**Position Sizing Calculator**](research/position_sizing_calculator.md): Risk management and contract sizing.
- **[Timing Analysis](research/timing_analysis.md)**: Optimal entry windows (09:31-09:35).

### Key Research Insights
> [!TIP]
> **Best Exit Time**: Data suggests **10:00 AM EST** is the optimal balance between capturing the impulse and avoiding the mid-morning reversal.
> **Target Logic**: Setting TP at **80% of the opening candle range** yields the highest expectancy across 10 years.
> **Day Filter**: Tuesdays show a statistically significant lower win rate for pure breakouts; V2 incorporates this as a "No Trade" day.

---

## TradingView Scripts

Custom PineScript indicators and strategies are located in the [pinescript/](pinescript/) folder:
- **[ORB Indicator](pinescript/ORB_Indicator.pine)**: Visualizes the 9:30 range and expansion levels.
- **[ORB Strategy](pinescript/ORB_Strategy.pine)**: Backtestable strategy component for TradingView.

---


---

## Implementation

| Component | Path |
|:---|:---|
| Strategy Logic (TS) | `web/lib/backtest/strategies/nq-1min-strategy.ts` |
| 10-Year Runner (TS) | `scripts/backtest/full-scale-backtest.ts` |
| Verification (Python) | `scripts/backtest/9_30_breakout/verify_930_strategy.py` |
| V2 Runner (Python) | `scripts/backtest/9_30_breakout/run_930_v2_strategy.py` |
| Chart Generator | `scripts/backtest/9_30_breakout/generate_930_charts.py` |

---

## Derived Data

The strategy uses precomputed opening range data:
- **File:** `data/{ticker}_opening_range.json`
- **Script:** `scripts/derived/precompute_opening_range.py`
- **Fields:** `date`, `open`, `high`, `low`, `close`, `range_pts`, `range_pct`

---

## Next Steps / TODO

- [ ] Backtest V2 with Tuesday filter applied
- [ ] Backtest V2 with extreme range filter applied  
- [ ] Test extended exit times (10:00, 10:30, 12:00, EOD)
- [ ] Apply strategy to ES1, RTY1, YM1
- [ ] Calculate slippage/commission impact on win rate threshold
