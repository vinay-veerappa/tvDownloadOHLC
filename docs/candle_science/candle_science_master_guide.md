# 🕯️ Candle Science Master Methodology & Mathematical Specification

> **Authors**: Matt Mickey & Austin (Pack Trading / Candle Science)
> **Core Concept**: Empirical 3-candle sequence analysis (C1 -> C2 -> C3) over 4,300+ trading sessions to establish quantitative excursion boundaries (MFE & MAE) and statistical reversal limits.

---

## 1. The 3-Candle Triplet Architecture
Every trading day is evaluated as Candle 3 ($C_3$) within the context of the preceding two completed sessions ($C_1$ and $C_2$):
* **$C_1$**: The session two days prior (Open, High, Low, Close, Direction).
* **$C_2$**: The immediate prior session (Open, High, Low, Close, Direction, High/Low vs $C_1$).
* **$C_3$ (Today)**: The active session where statistical distributions project the expected HOD, LOD, and directional excursion.

---

## 2. Quantitative Excursion Percentiles (MFE & MAE)
Instead of arbitrary point targets, Candle Science models excursions in **Price Percentage (%)**:

### 📈 Bullish MFE (Maximum Favorable Excursion)
* **P30 (30th Percentile ~ +0.80% to +0.90%)**: The high-probability baseline. Conservative target for cash-flow scaling ("Cover The Queen" +10 bps).
* **P50 (Median ~ +1.20% to +1.30%)**: The standard session HOD expansion target for typical trading days.
* **P70 (70th Percentile ~ +1.70% to +1.90%)**: The statistical trend ceiling.

### 📉 Bearish MAE (Maximum Adverse Excursion)
* **P30 (30th Percentile ~ -0.40% to -0.50%)**: Normal healthy pullback / sweep depth for false reversions.
* **P50 (Median ~ -0.80% to -0.90%)**: Standard session LOD expansion target.
* **P70 (70th Percentile ~ -1.40% to -1.50%)**: The statistical trend floor.

---

## 3. The Two Core Statistical Laws
1. **The 70% Reversal Law**:
   * **70% of the time**, price reverses before exceeding the P70 target box.
   * *Execution*: When price enters the P70 target box, look for exhaustion and reversal signatures rather than chasing breakouts.
2. **The 30% Trend Expansion Law**:
   * **Only 30% of days** expand cleanly through the P70 box.
   * These days correspond to **Directional No Pullback (DNP)** and **Directional With Pullback (DWP)** regimes where runners should be trailed.
