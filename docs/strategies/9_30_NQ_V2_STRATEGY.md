# 9:30 NQ Breakout Strategy (V2 - Optimized)

## Goal
To capture the initial 30-minute volatility impulse of the NQ session while using data-driven filters to avoid low-probability setups and protect capital.

## Core Setup
- **Ticker**: NQ (Nasdaq 100 Futures)
- **Timeframe**: 1-Minute
- **Anchor Candle**: 09:30 EST (Opening Minute)
- **Level Identification**: High and Low of the 09:30 candle.

## Entry Rules
1. **Breakout Entry**: Enter Long if price crosses 09:30 High; enter Short if price crosses 09:30 Low.
2. **Entry Window**: Only take entries between 09:31 and 09:35 EST.
3. **FVG Efficient Entry (Optional)**: If an "Inside FVG" (Fair Value Gap formed entirely within the 09:30 range) appears before the breakout, users may enter on the FVG confirmation to secure a better price, provided the direction aligns with the eventual breakout.

## Strategy Filters (The Alpha Add-ons)
- **Tuesday Avoidance**: DO NOT trade on Tuesdays. Historical data shows negative expectations and inconsistent follow-through on this day for the 9:30 impulse.
- **Extreme Range Filter**: Do not trade if the 09:30 candle range is "Extreme" (defined as Top 25% of the 20-day rolling distribution, typically > 0.20% of price). Large opening candles often lead to mean reversion rather than expansion.
- **Expansion Bias**: Preference is given to "Tight" or "Normal" opening ranges.

## Risk Management (Protection)
- **Stop Loss (Initial)**: 0.20% (MAE) from entry price.
- **Structural Stop**: Opposite side of the 09:30 range.
- **Tighter Rule**: Always use the **tighter** of the 0.20% Stop or the Structural Stop.
- **No Breakeven Move**: Data proves that moving to BE after hitting small targets (15bps) suffocates the trade. Keep the stop at 0.20% until TP or Hard Exit.

## Profit Target (Dynamic)
- **Take Profit (TP)**: 0.80x (80%) of the 09:30 candle's range.
- *Reasoning*: The median follow-through expansion is ~83% of the opening volatility. Dynamic TP ensures we scale our profit expectations to the daily volatility.

## Exit Rule
- **Hard Time Exit (Baseline)**: 10:00 AM EST.
- **Flexibility**: Strategy V2 testing includes sensitivity analysis for exits at 9:45 AM, 10:00 AM, 10:30 AM, 12:00 PM (Noon), and 4:00 PM (EOD). All open positions are closed flat at the specified time.
