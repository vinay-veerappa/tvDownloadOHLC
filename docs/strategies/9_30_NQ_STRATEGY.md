# 9:30 NQ Reversal/Breakout Strategy

## 1. Concept
This strategy is based on the volatility injection at the US Equities Open (9:30 AM ET). It uses the initial 1-minute candle (9:30-9:31) to define a trading range and seeks to capture the subsequent directional move ("The Snap" or "Return to Value") before the 9:45 AM reversal window.

## 2. Setup Parameters
*   **Instrument**: NQ (Nasdaq-100 Futures)
*   **Timeframe**: 1 Minute
*   **Session**: New York Open (09:30 ET)

## 3. Rules

### A. Range Definition (09:30)
1.  Wait for the first candle of the session (9:30 AM ET) to close.
2.  **Range High**: The High of the 9:30 candle.
3.  **Range Low**: The Low of the 9:30 candle.

### B. Timing Window
*   **Formation/Snap**: 09:30 - 09:34
*   **Execution Window**: 09:31 - 09:44
*   **Hard Stop Time**: 09:44 (Exit all positions before 09:45)

### C. Entry Logic
**Standard Entry (Confirmation)**
*   Enter **Long** if a candle *closes* above the **Range High**.
*   Enter **Short** if a candle *closes* below the **Range Low**.

**Advanced Entry (Fade/Snap)**
*   *Note: Not for beginners. requires usage of "Dump Pouch" sizing.*
*   Enter **Short** near **Range High** if price sweeps high but fails to break.
*   Enter **Long** near **Range Low** if price sweeps low but fails to break.
*   *Earliest entry*: 09:31:00.

### D. Invalidations (Stop Loss)
*   **Long SL**: Just below the **Range Low**.
*   **Short SL**: Just above the **Range High**.
*   *Risk Management*: Position size is calculated so that hitting the SL results in a fixed dollar loss (Dump Pouch method).

### E. Take Profit (TP) Levels
1.  **TP1 (Cover the Queen)**: 
    *   Target: 1R (Distance equal to Risk) OR ~10 basis points (0.10%).
    *   Action: Close 50% of position. Move SL to Breakeven (Risk-Free).
2.  **TP2 (range Extension)**:
    *   Target: 50% of the statistical 9:30-10:00 Distribution Range (requires historical stats).
    *   *Alternative*: 1.5R or 2R if stats unavailable.
3.  **TP3 (Time Exit)**:
    *   Target: End of window.
    *   Action: Close **ALL** remaining positions at **09:44 PM**.

## 4. Key Behaviors
*   **The Snap**: Violent move often occurring 9:30-9:34.
*   **RTFV**: Return to Fair Value, often 9:35-9:39.
*   **The Reversal**: High probability interaction at 9:45, hence the hard exit.

## 5. Implementation & Backtesting

| Component | File Path | Description |
| :--- | :--- | :--- |
| **TS Logic** | `web/lib/backtest/strategies/nq-1min-strategy.ts` | Core Strategy Class implementation |
| **TS Runner** | `scripts/backtest/full-scale-backtest.ts` | 10-Year Backtest Runner |
| **Verification Script** | `scripts/backtest/verify_930_strategy.py` | Python script for quick logic verification |

### Verification Results (Dec 2025)
**Date**: 2025-12-17
**Dataset**: Last 30 Days (Nov 17 - Dec 15, 2025)
**Script**: `verify_930_strategy.py`

#### Performance
- **Trades**: 19
- **Win Rate**: 36.8% (7 Wins / 12 Losses)
- **Net PnL**: -38.50 pts
- **Observations**:
    - Logic successfully captures breakouts.
    - Time Exit (09:44) correctly limits risk duration.
    - Consistency of profitability requires higher win rate or larger R-Multiple on winners.

#### Example Trades
| Date | Direction | Entry | Exit | Result | Reason |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2025-11-17 | LONG | 25011.75 | 25125.25 | WIN | TP (2R) |
| 2025-11-18 | SHORT | 24670.25 | 24758.75 | LOSS | SL |
| 2025-12-15 | SHORT | 25600.00 | 25543.50 | WIN | Time Exit |
