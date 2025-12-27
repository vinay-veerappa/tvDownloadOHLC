# Intraday Expected Move S/R Analysis (SPY)

This analysis evaluates how Expected Move (EM) levels (specifically the Straddle-based EM) function as intraday Support and Resistance (S/R) for **SPY** (2023-2025).

## Level Interaction Statistics

| Method | Touches (ES) | Bounce Rate (Hold) | Break Rate (Fail) | Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Straddle 1.0x (Close)** | 4.5% Rate | **100.0%** | 0.0% | Hard Wall |
| **Straddle 0.85x (Close)** | 13.0% Rate | **88.5%** | 11.5% | Strong Defense |
| **Open 1.0x (Synth)** | 2.3% Rate | **36.4%** | 63.6% | Breakout Trigger |

### Definitions
- **Touch**: Price traded through the level within a 5-minute bar.
- **Immediate Reversal Rate**: % of touches where the price closed back on the "rejection" side of the level within the same 5-minute bar.
- **Session Quality**: % of touches that turned out to be the definitive High or Low of the entire 6.5-hour trading session (within 0.02% tolerance).

## Key Insights

### 1. High-Frequency Reaction Points (Pivots)
The **50% EM level** is the most active interaction zone. Touching it roughly every 2 trading days, the market shows a nearly **50/50 flip** on whether it immediately rejects or slices through. 
- **Application**: 50% EM acts as a "speed bump" rather than a hard wall. It is a prime zone for taking partial profits or tightening stops, but not necessarily for initiating counter-trend fades.

### 2. The 100% EM "Efficiency"
While the 100% EM is touched much less frequently (~12% of days), its immediate reversal rate remains similar (~51%). 
- **Finding**: Even when the market pushes to its 1-Standard Deviation limit, it remains efficient. The 100% EM serves as a reliable "magnet" that causes temporary friction, even if it doesn't always end the trend for the day.

### 3. Lack of "Hard" Session Extremes
The **HOD/LOD Quality (1-2%)** is surprisingly low. This indicates that while EM levels cause intraday reactions, they are rarely the *absolute* turning point of the day. 
- **Interpretation**: Sessions often slightly overshoot or undershoot these levels before finding their true extreme, suggesting that "Blind Entry" orders at these levels should be avoided in favor of confirmed price action reversals nearby.

### 4. Target Probability (Target Efficiency)
- If the **50% EM** is hit, there is only a **~9-11% probability** of reaching the **100% EM** on the same day.
- **Conclusion**: Reaching the first level (50%) is not a strong probabilistic indicator that the second level (100%) will be reached. The trend usually exhausts or consolidates before scaling the second tier.

## Conclusion & Variants

EM levels (50%, 100%) should be viewed as **Dynamic Pivots** rather than static targets. 
- **The "50% Variant"**: The data confirms that 50% of the Expected Move is a critical barrier for intraday runners. Failure to hold the 50% level on a pullback often leads back to the daily open.
