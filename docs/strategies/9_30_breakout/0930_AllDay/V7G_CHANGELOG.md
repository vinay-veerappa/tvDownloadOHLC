# Modification Log: ORB V7G Hybrid Strategy
## Date: 2026-01-07

### 1. Runner Mode Added
Added a new `Runner Mode After TP1` input with three options:
- **Dump Pouch** (Default): Progressive V7F-style trailing stop (DP1/DP2/DP3).
- **Breakeven + EOD** (V2 Style): Moves SL to Breakeven (+2 ticks) immediately after TP1, then holds until EOD. Use this to capture maximum runner potential without trails cutting you out.
- **Hold to EOD**: Keeps original SL after TP1 (risky but max potential).

### 2. Exit Logic Fix (Profit Locking)
Changed the internal valid logic for Stop Loss management from `loss=` (relative ticks) to `stop=` (absolute price).
- **Why**: The previous `loss=` logic prevented "locking profit" because `loss` parameters in PineScript always place stops *below* entry for longs.
- **Fix**: Using `stop=currentSLPrice` allows the strategy to place stops *above* entry (protecting profit) correctly.

### 3. Dump Pouch Logic Update
Updated the Dump Pouch block to ensure `currentSLPrice` is correctly tracked and updated for all modes, not just when "Dump Pouch" is enabled.

### 4. Code Cleanup
Removed redundant MAE checks in the runner management section as the main MAE block handles it globally.

### 5. Critical Fix: "Size 1" Runner Protection
**Implemented Date**: 2026-01-07 (Run 5 Prep)
- **Problem**: When account size is small ($3,000), position size is often 1 contract. The strategy was programmed to exit `qty=1` at TP1, effectively closing the entire trade and eliminating the runner.
- **Fix**: Added logic to check `strategy.position_size`. If size is 1, the strategy **skips** the partial TP1 exit and instead holds the entire position as a runner (moving SL to Breakeven upon hitting TP1 price).
- **Impact**: Ensures every winning trade captures runner potential, even with small accounts.

---

## How to Test (Run 5)
1. Update Strategy in TradingView.
2. Inputs: Runner Mode = **"Breakeven + EOD"**.
3. Run Backtest.
4. **Expect**: Higher Net Profit and significantly more "EOD Exit" or "BE" trades compared to Run 4.
