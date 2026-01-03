# Net Change SDEVs Logic

**Source**: NQStats "Net Change SDEVs" Video Transcript
**Concept**: Mean reversion probabilities based on the Standard Deviation (SD) of Daily Net Changes.

## 1. The Metric
*   **Formula**: `Net Change % = (Close - Open) / Open`
*   **Sample Size**: Recommended 10-20 Years of Daily Data.
*   **Calculation**: Calculate the Standard Deviation (SD) of this population of Net Changes.

## 2. The Levels & Reversion Probabilities (One-Sided)
The probability that the session will **CLOSE** *inside* (below a positive SD or above a negative SD) if that level is touched.

| Level (SD) | Reversion Probability | Concept |
| :--- | :--- | :--- |
| **0.5 SD** | **~69%** | "The First Test" - often consolidation. |
| **1.0 SD** | **~84%** | "Standard Deviation" - Strong reversion edge. |
| **1.5 SD** | **~93%** | Extreme extension. |
| **2.0 SD** | **~97%** | Rare Event (Black Swan/Crash/Melt-up). |

## 3. Operational Strategy
*   **Avoid the Open**: No "tension" on the rubber band near the mean (Open).
*   **Fade the Edges**: Look for mean reversion trades at 1.0 SD (84% win rate) or 1.5 SD (93%).
*   **Trend Day Filter**: If price reaches a level (e.g., 0.5 SD) and **does not consolidate** (blows through with strong candles), do NOT fade. It is likely a Trend Day moving to the next level.
*   **Execution**: Wait for consolidation/rejection at the SD level before entering. Target a return to the Mean (Open) or the previous SD level.
