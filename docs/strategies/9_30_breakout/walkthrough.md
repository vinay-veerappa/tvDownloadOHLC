# Backtest Analysis Report

## 1. Strategy Overview
**Strategy:** 9:30 AM Breakout, 1-minute chart.
**Exit Rules:**
1.  **Strict Close Inside Range (0%):** If a candle ENTRY closes back inside the Opening Range, CLOSE IMMEDIATELY.
2.  **Range Filter:** If Opening Range > 0.25% of price, SKIP TRADE.
3.  **Target:** 2.0R (Based on MFE analysis).

## 2. Multi-Year Robustness Test (2016 - 2025)

We tested the first 100 trades of each year (starting Jan) to verify consistency.

| Year | Trades | PnL (Points) | Win Rate | Date Range |
| :--- | :--- | :--- | :--- | :--- |
| **2025** | 100 | **+1085.25 pts** | 36.0% | Jan 02 - May 30 |
| **2024** | 100 | **+157.28 pts** | 28.0% | Jan 02 - May 13 |
| **2023** | 100 | **+389.54 pts** | 38.0% | Jan 05 - May 31 |
| **2022** | 85 | **+639.04 pts** | 37.6% | Jan 03 - Jul 26 |
| **2021** | 100 | **+873.97 pts** | 43.0% | Jan 04 - May 24 |
| **2020** | 100 | **+749.85 pts** | 44.0% | Jan 02 - Jul 21 |
| **2019** | 100 | **+90.45 pts** | 33.0% | Jan 03 - May 16 |
| **2018** | 100 | **-22.31 pts** | 30.0% | Jan 02 - May 23 |
| **2017** | 100 | **+91.33 pts** | 37.0% | Jan 03 - May 22 |
| **2016** | 100 | **+363.88 pts** | 37.0% | Jan 05 - May 13 |

**Total PnL (1000 Trades): +4,418.28 Points**

## 3. Full Scale Data (2016 - 2025)

We generated detailed datasets for every single trade in the 10-year period (approx 2800 trades per strategy).

**Available CSVs:**
*   **Base Strategy (No Early Exit)**: [Base_Strategy_2016_2025.csv](Base_Strategy_2016_2025.csv)
*   **Strict Exit (0% Threshold)**: [Threshold_0Pct_2016_2025.csv](Threshold_0Pct_2016_2025.csv) *(Recommended)*
*   **Loose Exit (25% Threshold)**: [Threshold_25Pct_2016_2025.csv](Threshold_25Pct_2016_2025.csv)
*   **Loose Exit (50% Threshold)**: [Threshold_50Pct_2016_2025.csv](Threshold_50Pct_2016_2025.csv)
*   **Loose Exit (75% Threshold)**: [Threshold_75Pct_2016_2025.csv](Threshold_75Pct_2016_2025.csv)

## 4. Trader's Insights (Deep Dive)
*Based on analysis of 2,761 unfiltered trades using the **Strict Exit (0%) Strategy**.*

### A. The "Sweet Spot" (Range Size)
While the strategy is generally profitable, the **highest quality trades** occur when the Opening Range is **Tight (0.10% - 0.18%)**.
*   **Micro (<0.10%)**: Solid, but lower volatility (Avg 3 pts/trade).
*   **Tight (0.10-0.18%)**: **THE BEST**. Highest PnL density (Avg 5.2 pts/trade).
*   **Normal (0.18-0.25%)**: Decent (Avg 3 pts/trade).
*   **Wide (>0.25%)**: In the last 10 years (Bull Run), these were actually profitable (Avg 7.4 pts/trade), unlike 2008. *However, they come with much higher risk.*

### B. Day of Week Bias
Avoid Fridays.
*   **Mon/Tue/Thu**: **Excellent**. (>2700 pts PnL each).
*   **Wed**: Mediocre (~990 pts).
*   **Fri**: **Weakest** (~640 pts). Consider taking Fridays off.

### C. Psychology Check
*   **Max Losing Streak**: **16 Trades**.
    *   *Reality Check*: Can you handle 3 weeks of straight losses without changing the system? If not, you will miss the recovery.
*   **Win Rate**: ~37%. This is a specialized breakout system. You lose often, but small.

### D. Volatility Context
In the 2008 crash, "Large Ranges" were toxic. In the 2016-2025 Bull Run, "Large Ranges" (Volatility) were profitable.
*   **Recommendation**: Keep the 0.25% filter for SAFETY (protection against crash regimes), but know that in a strong bull market, you might be "filtering out profit."

For the **Live Chart Indicator**, we will include inputs to toggle these filters (Day of Week, Max Range %).
