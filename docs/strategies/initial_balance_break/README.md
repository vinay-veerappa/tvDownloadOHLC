# Initial Balance (IB) Break Strategy

## Overview

**Objective**: Trade breakouts of the Initial Balance range with high statistical probability based on 10 years of NQ historical data (2014-2024).

**Market**: NQ Futures (can be adapted to ES, other indices)  
**Timeframe**: 5-minute bars  
**Session**: NY Regular Trading Hours (9:30 AM - 4:00 PM ET)

## Strategy Definition

### Initial Balance (IB)
The **Initial Balance** is the high and low range established during the first hour of the NY session:
- **IB Period**: 9:30 AM - 10:30 AM ET
- **IB High**: Highest price during this 1-hour window
- **IB Low**: Lowest price during this 1-hour window
- **IB Midpoint**: `(IB_High + IB_Low) / 2`

### Core Statistics (10-Year Historical Data)

| Metric | Probability | Notes |
|--------|-------------|-------|
| IB breaks before 4:00 PM ET | **96%** | Either high or low breaks |
| IB breaks before 12:00 PM ET | **83%** | Morning session only |
| High breaks when IB closes upper half | **81%** | Directional bias |
| Low breaks when IB closes lower half | **74%** | Directional bias |

## Entry Rules

### Variant 1: Pure IB Breakout (Aggressive)
1. Wait for 10:30 AM ET (IB formation complete)
2. Calculate IB close position: `(Close_10:30 - IB_Low) / (IB_High - IB_Low)`
3. Determine expected break direction:
   - If close > 50% → Expect high break (go LONG on break)
   - If close < 50% → Expect low break (go SHORT on break)
4. Enter immediately on breakout of expected level
5. Entry window: 10:30 AM - 12:00 PM ET

### Variant 2: IB Pullback Entry (Conservative)
1. Wait for 10:30 AM ET
2. Determine expected break direction (same as Variant 1)
3. Wait for breakout to occur
4. Enter on first pullback toward IB range
5. Entry window: 10:30 AM - 2:00 PM ET

### Variant 3: Confirmation Break
1. Wait for 10:30 AM ET
2. Only enter if IB close is in extreme quartile (0-25% or 75-100%)
3. Wait for 2-3 bars to confirm direction after 10:30
4. Enter on breakout with confirmation

## Exit Rules

### Stop Loss
- **Fixed**: 50% of IB range
- **Dynamic**: Place stop on opposite side of IB range
- Example: Long on IB high break → Stop at IB low

### Take Profit
- **Target 1**: 100% of IB range (1:1 R/R)
- **Target 2**: 150% of IB range (1.5:1 R/R)
- **Target 3**: 200% of IB range (2:1 R/R)

### Time-Based Exits
- **12:00 PM ET**: Exit if no profit and break hasn't occurred
- **3:30 PM ET**: Exit all positions (avoid close volatility)
- **4:00 PM ET**: Hard stop (end of session)

## Filters & Conditions

### Required Conditions
- IB range must be > 0.3% of open price (avoid tiny ranges)
- IB range must be < 2.0% of open price (avoid gap days)
- No major news events during IB formation

### Optional Filters
- **Gap Filter**: Only trade if overnight gap < 1%
- **Trend Filter**: Align with higher timeframe trend (daily/4H)
- **Volatility Filter**: Only trade if ATR(14) within normal range

## Risk Management

### Position Sizing
- Risk 1% of account per trade
- Calculate position size based on stop loss distance
- Example: $100k account, 1% risk = $1000 max loss

### Daily Limits
- Max 1 trade per day (one IB per session)
- Stop trading after 2 consecutive losses
- Max daily loss: 2% of account

## Statistics to Capture

### IB Characteristics
- `IB_Range_Pct`: IB range as % of open price
- `IB_Close_Position`: Where 10:30 close is within IB (0-100%)
- `IB_High_Time`: Time when IB high was set
- `IB_Low_Time`: Time when IB low was set

### Break Analysis
- `Break_Time`: When IB was first broken
- `Break_Side`: HIGH or LOW
- `Break_Matched_Expectation`: Boolean (based on IB close position)
- `Break_Before_Noon`: Boolean
- `Minutes_To_Break`: Time from 10:30 to first break

### Trade Metrics
- `Entry_Time`: Exact entry timestamp
- `Entry_Price`: Entry price
- `Entry_Delay_Minutes`: Minutes after 10:30
- `Direction`: LONG or SHORT
- `Stop_Loss`: Stop price
- `Take_Profit`: Target price
- `MAE_Pct`: Maximum Adverse Excursion (% of entry)
- `MFE_Pct`: Maximum Favorable Excursion (% of entry)
- `MAE_In_IB_Range`: MAE as % of IB range
- `MFE_In_IB_Range`: MFE as % of IB range
- `Exit_Price`: Exit price
- `Exit_Time`: Exit timestamp
- `Exit_Reason`: TP / SL / TIME / EOD
- `PnL_Pct`: Final P&L as % of entry
- `Hold_Duration_Minutes`: Time in trade

### Context
- `Date`: YYYY-MM-DD
- `DayOfWeek`: Mon-Fri
- `Gap_Pct`: Overnight gap size
- `Market_Regime`: BULL / BEAR / CONSOLIDATION
- `Result`: WIN / LOSS / BREAKEVEN

## Expected Performance (To Validate)

Based on historical statistics, we expect:
- **Win Rate**: 60-70% (high probability setup)
- **Profit Factor**: > 1.5
- **Average Win**: 1.0-1.5 R
- **Average Loss**: 0.5-1.0 R
- **Break Accuracy**: ~80% (matching expected direction)

## References

- **NQ Stats Website**: https://nqstats.com/ib-breaks
- **YouTube Video**: https://www.youtube.com/watch?v=SjGOXiAFKgc
- **Insights Document**: [insights.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/initial_balance_break/insights.md)
