# The "Edge System" V3.1: Strategy Reference Manual

**Status**: Production / Optimization  
**Symbol**: MNQ (Micro Nasdaq 100)  
**Timeframe**: 1 Minute  
**Type**: Opening Range Breakout (ORB) with Forensic Timing Optimization

---

## 1. Executive Summary

The **Edge System V3.1** is a high-frequency, precision-based breakout strategy designed specifically for **Proprietary Trading Firm Evaluation** environments. unlike traditional ORB strategies that rely on wide stops and high win rates, the Edge System operates on a **"Sniper" thesis**: usage of ultra-tight stops (0.05% MAE) to systematically cull weak trades immediately, allowing the "Runner" contracts to generate outsized Risk:Reward ratios.

While this results in a lower raw Win Rate (~27-30%), the **Profit Factor (1.85+)** and **SQN (System Quality Number)** remain robust due to the asymmetric payoff structure.

---

## 2. System Philosophy & Logic

### The "Sniper" Paradox

Conventional wisdom suggests widening stop losses to avoid "noise." Our forensic data proves the opposite for NQ Futures:

- **Observation**: Winning trades typically move in our favor _immediately_.
- **Data**: 85% of large winning trades never experience a drawdown > 5 points.
- **Conclusion**: Any trade that moves against us by >11 points (0.05%) is statistically likely to be a "Trap" or "Chop."
- **Action**: We cut these trades instantly. This results in frequent small "stings" (losses of ~$30) which are paid for 10x over by a single successful "Runner" (profit of ~$300-$500).

### Core Components

1.  **Doji Filter (The Chop Guard)**
    - **Rule**: Reject entries if the signal candle's body size is < 50% of its total range.
    - **Why**: "Spinning Tops" and "Dojis" indicate market indecision. Breakouts from these candles have a >60% failure rate ("Fakeouts").

2.  **Selective MAE (Maximum Adverse Excursion)**
    - **Rule**: Hard Stop Loss set at **0.05%** of price (approx. 10-12 points on NQ).
    - **Why**: Mathematically filters out "slow bleeding" trades. If momentuem isn't instant, we exit.

3.  **Golden Window Timing**
    - **Rule**: Aggressive sizing during **09:30 - 09:40 EST**.
    - **Forensic Insight**: The minute **09:32 AM** alone generates +$9,000 in historical profit. This is the "Follow-Through" variance where the initial auction balance breaks.

---

## 3. Algorithmic Rules (The Code)

### Entry Logic

1.  **Time**: Session begins 09:30 EST.
2.  **Trigger**: Price closes above/below the Opening Range (first 1-minute candle).
3.  **Validation**:
    - Candle Body > 50% of Range.
    - NOT in a "Toxic Time Slot" (e.g., 10:11 AM, which has 90% failure rate).

### Exit Logic

1.  **Stop Loss**: Fixed 0.05% MAE (approx. 10 pts).
2.  **Take Profit 1 (Scalp)**: Fixed 10-15 pts. Banks cash flow.
3.  **Take Profit 2 (Runner)**: Trailing Stop based on Market Structure or Fixed Extension (3:1 RR).

### Risk Management (Prop Firm Sizing)

- **Recommended Size**: **2 Micro Contracts (MNQ)** per $50k account.
- **Monte Carlo Simulation**:
  - At 2 contracts, the Risk of Ruin (<$2,000 drawdown) is **0.8%**.
  - Average Time to Pass Evaluation ($3,000 target): **27 Days**.
  - At 3 contracts, Ruin Risk spikes to 4.4% (Too aggressive).

---

## 4. Forensic Performance Analysis

### The "Golden" vs. "Toxic" Matrix

Our analysis engine breaks down performance by specific minutes.

- **Golden Minute**: **09:32 EST** (High Probability, High MFE).
- **Toxic Minute**: **10:11 EST** (Consistently results in reversal/loss).
- **Best Hour**: **09:00** (+$24k Total P&L).
- **Worst Hour**: **12:00** (Lunch Hour Chop - Neutral/Negative Expectancy).

### Weekly Seasonality

- **Best Day**: **Wednesday** (Mid-week momentum expansion).
- **Worst Day**: **Monday** (Often "Inside Days" or range-bound).

### Macro Context

- **Bull Markets (2023-2024)**: System thrives on "Trend Days" (AI Rally).
- **Choppy Markets (2022)**: System survives due to tight stops (Breakeven).
- **Regime Change (2025-2026)**: Requires recalibration of volatility thresholds.

---

## 5. Risk & Robustness Scorecard

| Metric              | Value         | Interpretation                                                        |
| ------------------- | ------------- | --------------------------------------------------------------------- |
| **Profit Factor**   | **1.85**      | For every $1 lost, ~$1.85 is made. Excellent.                         |
| **Win Rate**        | **27.8%**     | Low, but expected for a "Sniper" system.                              |
| **SQN**             | **8.93**      | "Holy Grail" territory (>7.0 indicates high statistical signficance). |
| **Max Drawdown**    | **-$1,334**   | Well within Prop Firm limits ($2,000).                                |
| **Avg Loss Streak** | **22 Trades** | Psychological difficulty is high; requires discipline.                |

## 6. Multi-Ticker Logic & Parameters (Feb 2026 Update)

### Asset Class Optimization

We have expanded the "Sniper" logic beyond NQ/MNQ. The core philosophy remains: **Tight Stops (MAE) + Immediate Momentum**.
The following parameters are derived from 1-minute forensic analysis of **15 years of recent data** (2011-2026), prioritizing current market regimes over ancient history.

> **Note**: These values are normalized as **Percentage of Price** to remain valid across contract rolls and price changes.

|    Instrument    | Ticker  |       Feature        | Max Range % | TP1 (Scalp) % | TP2 (Runner) % | Sniper Stop (Median) % | Wide Stop (P90) % |
| :--------------: | :-----: | :------------------: | :---------: | :-----------: | :------------: | :--------------------: | :---------------: |
|   **S&P 500**    | ES/MES  | Mean Reversion/Grind |  **0.14%**  |   **0.28%**   |   **0.65%**    |       **0.13%**        |     **0.48%**     |
| **Russell 2000** | RTY/M2K |   High Volatility    |  **0.32%**  |   **0.54%**   |   **1.14%**    |       **0.24%**        |     **0.77%**     |
|  **Dow Jones**   | YM/MYM  |   Trend/Extension    |  **0.17%**  |   **0.30%**   |   **0.66%**    |       **0.14%**        |     **0.47%**     |
|     **Gold**     | GC/MGC  |    Safe Haven/Pop    |  **0.10%**  |   **0.23%**   |   **0.51%**    |       **0.11%**        |     **0.34%**     |
|  **Crude Oil**   | CL/MCL  |  Extreme Volatility  |  **0.43%**  |   **1.05%**   |   **2.43%**    |       **0.48%**        |     **1.73%**     |

### Key Observations

1.  **Crude Oil (CL)** requires significant room. Even the "Sniper" stop (0.48%) is >1x the Range.
2.  **Gold (GC)** allows for ultra-tight stops (0.11% Median), often staying within 1.1x of its Opening Range.
3.  **Sniper Warning**: Restricting stops to **1.0x Opening Range** (e.g., placing stop at opposite ORB boundary) has a low survival rate (~20-30%). **Median MAE** (the "Sniper Stop" above) is a safer, statistically backed alternative that captures ~50% of winning trades while still being very tight.

### Implementation Checklist

- [ ] **Adjust Stops**: Ensure your ATM strategy converts these % values to ticks based on current price.
- [ ] **Position Sizing**: Volatility varies. A 0.50% stop on ES is very different dollar-risk than 1.63% on CL. Normalize risk to $ amount (e.g., $150 risk per trade).

### Summary for NotebookLM

Use this document to understand the _Edge System V3.1_. It is a counter-intuitive strategy that trades _against_ standard retail wisdom (wide stops) by leveraging _institutional order flow behavior_ (instant momentum). It is optimized not for comfort (win rate), but for **Math** (Profit Factor & Drawdown Control).
