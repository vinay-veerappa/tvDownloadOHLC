# Initial Balance Break Strategy - YouTube Transcript Analysis

**Source**: https://www.youtube.com/watch?v=SjGOXiAFKgc

## Key Insights from Video

### Additional Strategy Details

1. **IB Close Position Matters**:
   - If IB closes in **upper half** of range → High breaks most of the time
   - If IB closes in **lower half** of range → Low breaks most of the time
   - This provides directional bias for the expected breakout

2. **Trade Management Applications**:

   **A. For Existing Trades**:
   - Use IB break expectation to set targets
   - If already short and IB closes in lower half → expect low break (83% by noon)
   - If already long and IB closes in upper half → expect high break (83% by noon)

   **B. For New Entries**:
   - Wait for IB to close (10:30 ET)
   - Identify which half IB closed in
   - Enter on pullbacks in the expected breakout direction
   - Example: IB closes upper half → wait for pullback → go long expecting high break

   **C. Trade Avoidance**:
   - Don't short when IB closes in upper half (high likely to break)
   - Don't go long when IB closes in lower half (low likely to break)
   - Wait for the expected break to occur first, then look for reversals

3. **Time-Based Probability Shifts**:
   - **Before 12pm ET**: 83% probability of break
   - **After 12pm ET**: 96% probability of break (more time = higher probability)
   - If no break by noon, probability increases for afternoon session

4. **Related Concept - "Noon Curve"**:
   - Mentioned as similar time-based statistical edge
   - Involves pre-noon vs post-noon highs/lows
   - Can be combined with IB break strategy

## Strategy Variations to Test

### Variant 1: Pure IB Breakout
- Wait for 10:30 ET (IB close)
- Determine IB close position (upper/lower half)
- Enter on breakout of expected side
- Target: Opposite side of IB or fixed R-multiple

### Variant 2: IB Pullback Entry
- Wait for 10:30 ET (IB close)
- Wait for expected side to break
- Enter on first pullback after break
- Tighter stop, better risk/reward

### Variant 3: IB Fade (Counter-trend)
- Wait for expected break to occur
- After break and extension, look for reversal
- Trade back into IB range
- Lower probability but potentially higher R/R

### Variant 4: Time-Based Exit
- Enter on IB break
- Exit at specific times (12pm, 2pm, 3:30pm)
- Avoid holding through low-probability periods

## Statistics to Capture in Backtest

1. **IB Characteristics**:
   - IB Range Size (% of open price)
   - IB Close Position (% within range, 0-100)
   - Time of IB high formation
   - Time of IB low formation

2. **Break Timing**:
   - Time until first break (minutes from 10:30)
   - Which side broke first (high/low)
   - Did it match expectation based on IB close position?
   - Break before noon? (Y/N)

3. **Trade Metrics**:
   - Entry time and price
   - Entry delay from IB close (minutes)
   - MAE/MFE as % of IB range
   - Exit reason (TP/SL/TIME/EOD)
   - Hold duration

4. **Validation Metrics**:
   - % of days IB breaks before noon (expect ~83%)
   - % of days IB breaks before 4pm (expect ~96%)
   - Accuracy of directional bias (upper half → high, lower half → low)
   - Win rate by IB close position (0-25%, 25-50%, 50-75%, 75-100%)

## Implementation Notes

- Use 5-minute bars for precise IB calculation
- All times in Eastern Time (ET)
- IB = High and Low between 9:30-10:30 ET
- Calculate IB midpoint: `(IB_High + IB_Low) / 2`
- IB close position: `(Close_10:30 - IB_Low) / (IB_High - IB_Low) * 100`
- Track both "expected" breaks and "unexpected" breaks separately
