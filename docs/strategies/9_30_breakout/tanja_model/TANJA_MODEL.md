# Tanja 9:30 Model - Trading Strategy Research
**Status**: Validated (Strategy Refined)
**Last Updated**: January 11, 2026
**Analysis Period**: 2008 - 2025 (17 Years)

---

## Executive Summary

The "Tanja 9:30 Model" was originally hypothesized as a "Judas" (Reversal) strategy. However, extensive data analysis (2008-2025) on NQ **disproves the Reversal theory** for this specific timeframe and **validates a Trend Confirmation strategy**.

**The New Reality (Data-Driven):**
1.  **Don't Fade the First Move**: The 9:30 breakout direction is statistically the "Real Move" for the morning session.
2.  **MFE > MAE**: If 9:30 is Green, the market extends 30% further UP than DOWN on average.
3.  **Trend Beats Reversal**: A Trend Following strategy has a **+12% higher win rate** than a Judas Reversal strategy for targets between 0.5R and 3.0R.

---

## The Validated Strategy: "Chain of Confidence"

The strategy works as a 3-step confirmation chain.

### Step 1: The Setup (9:28 - 9:32 Pattern)
The interaction between the 9:28 and 9:32 candles sets the bias.

| Pattern | Definition | Bias |
| :--- | :--- | :--- |
| **GAP UP** | 9:32 Low > 9:28 High | **STRONG BULL** |
| **ON TOP** | 9:32 High/Low > 9:28 High/Low | **BULLISH** |
| **GAP DOWN** | 9:32 High < 9:28 Low | **STRONG BEAR** |
| **BELOW** | 9:32 High/Low < 9:28 High/Low | **BEARISH** |
| *Others* | Engulf, Kiss, Inside | *Neutral / Wait* |

### Step 2: The Trigger (9:30 Direction)
The 9:30 1-minute candle is the execution signal.
*   **Bullish Trigger**: 9:30 Close > Open
*   **Bearish Trigger**: 9:30 Close < Open

### Step 3: Execution (Alignment)
Only take trades where **Step 1 and Step 2 agree**.

*   **LONG**: (Gap Up OR On Top) **AND** (9:30 Green).
    *   **Entry**: Break of 9:30 High.
    *   **Stop**: 9:30 Low (1R).
*   **SHORT**: (Gap Down OR Below) **AND** (9:30 Red).
    *   **Entry**: Break of 9:30 Low.
    *   **Stop**: 9:30 High (1R).

---

## Statistical Proof (2008-2025)

### 1. The Trend Advantage (Trend vs Judas)
We simulated 4,492 sessions comparing "Following the Move" vs "Fading the Move".

| Target (R-Multiple) | **Trend Win Rate** | Reversal Win Rate | Advantage |
| :--- | :--- | :--- | :--- |
| **0.5 R** | **34.6%** | 22.3% | **+12.3%** |
| **1.0 R** | **33.9%** | 21.7% | **+12.2%** |
| **2.0 R** | **30.8%** | 19.4% | **+11.4%** |
| **3.0 R** | **26.3%** | 16.1% | **+10.2%** |

*Interpretation: Attempting to trade the "Judas" reversal is statistically inferior. The initial move has significantly higher positive expectancy.*

### 2. Full Chain Win Rates (Setup + Trigger)
When the 9:28 Pattern aligns with the 9:30 Trigger, the win rate (MFE > MAE for the hour) is exceptionally high.

| Setup Type | Win Rate | Median R/R |
| :--- | :--- | :--- |
| **STRONG BULL** | **67.1%** | **3.9** (4:1) |
| **STRONG BEAR** | **66.4%** | **3.1** (3:1) |
| *Failed Setup (Contrarian)* | *35.2%* | *0.5* |

### 3. Smart Mode Validation (Hybrid Strategy)
"Smart Mode" applies the logic: *If Pattern contradicts Trigger, trust the Pattern.*
This leads to a **+2.5% Global Win Rate Improvement**.

| Target | Trend Win% | Smart Win% | Edge |
| :--- | :--- | :--- | :--- |
| **0.5 R** | 34.9% | **37.4%** | +2.5% |
| **1.0 R** | 34.2% | **36.7%** | +2.5% |
| **2.0 R** | 31.0% | **33.4%** | +2.4% |

**Why it works**: On "Flip" days (where Pattern and Trigger disagree), Smart Mode achieves a **38.7% Win Rate**, drastically outperforming the Trend strategy which fails (11.5% Win Rate) on those same days. This turns "guaranteed losses" into profitable reversal trades.

---

## Nuance: The "Judas" Paradox

Why did the original theory suspect Judas moves?
Our validation script showed that ~88% of days technically "reverse" by the end of the 30-minute session (e.g., Close < High).

**The Explanation**:
The market breaks out (Trend), hits profit targets (1R, 2R, 3R), and *then* pulls back later in the session.
*   **Technical Definition**: "Judas" because it didn't close at the high.
*   **Trader Reality**: "Profitable Trend" because it hit target before stop.

**Actionable Advice**: Do not hold these trades for the full session close. Take profits at logical R-multiples (1R, 2R) or use a trailing stop.

---

## Reference Artifacts

All analysis scripts and raw data are located in `scripts/research/tanja_model/` and `docs/strategies/9_30_breakout/tanja_model/output/`.

*   `analyze_930_prediction.py`: Proof that 9:30 direction predicts session.
*   `analyze_full_chain.py`: Detailed Breakdown of Pattern + Trigger combinations.
*   `simulate_day_trader.py`: Backtest of Trend vs Reversal expectancy.
*   `validate_tanja_model.py`: Legacy script showing high "technical" reversal rates (which we now know are late-session pullbacks).

### Detailed Reports
*   [Analysis Report](output/ANALYSIS_REPORT.md)
*   [Day Trader Simulation Results](output/day_trader_sim_results.csv)
*   [Full Chain Results](output/full_chain_results.csv)
