# NQ 9:30 Breakout Strategy

## 1. Strategy Overview
**Objective**: Capture early session volatility by trading breaks of the opening minute range.

| Parameter | Value |
| :--- | :--- |
| **Ticker** | NQ1! (Continuous Contract) |
| **Timeframe** | 1 Minute |
| **Session** | New York (09:30 EST Open) |
| **Direction** | Long & Short (Reversal/Trend) |

## 2. Trading Logic

### Opening Range
- **Definition**: The High and Low of the **09:30 - 09:31 EST** candle.

### Entry Trigger
- **Window**: 09:31 EST to 09:44 EST.
- **Condition**:
    - **Long**: Candle Close > 09:30 High.
    - **Short**: Candle Close < 09:30 Low.
- **Limit**: Max 1 trade per day (First valid signal).

### Risk Management
- **Stop Loss (SL)**: Set at the opposite end of the 09:30 range.
    - Long SL = 09:30 Low.
    - Short SL = 09:30 High.
- **Take Profit (TP)**: 2.0x Risk (Reward-to-Risk Ratio).

### Exits
1.  **Stop Loss**: Initial SL hit.
2.  **Take Profit**: Limit order hit.
3.  **Time Exit (Hard Close)**: **09:44 EST** (15 minutes after Open). Position is closed at Market.

## 3. Implementation Maps

| Component | File Path | Description |
| :--- | :--- | :--- |
| **TS Logic** | `web/lib/backtest/strategies/nq-1min-strategy.ts` | Core Strategy Class implementation |
| **TS Runner** | `scripts/backtest/full-scale-backtest.ts` | 10-Year Backtest Runner |
| **Verification** | `scripts/backtest/verify_930_strategy.py` | Python script for quick logic verification |

## 4. Verification Results (Dec 2025)
**Date**: 2025-12-17
**Dataset**: Last 30 Days (Nov 17 - Dec 15, 2025)
**Script**: `verify_930_strategy.py`

### Performance
- **Trades**: 19
- **Win Rate**: 36.8% (7 Wins / 12 Losses)
- **Net PnL**: -38.50 pts
- **Observations**:
    - Logic successfully captures breakouts.
    - Time Exit (09:44) frequently triggers, cutting potential runners or saving from full stops.
    - Win rate is currently below breakeven threshold for 2R (33% required, but slippage/fees not included).

### Example Trades
| Date | Direction | Entry | Exit | Result | Reason |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-11-17 | LONG | 25011.75 | 25125.25 | WIN | TP (2R) |
| 2025-11-18 | SHORT | 24670.25 | 24758.75 | LOSS | SL |
| 2025-12-15 | SHORT | 25600.00 | 25543.50 | WIN | Time Exit |
