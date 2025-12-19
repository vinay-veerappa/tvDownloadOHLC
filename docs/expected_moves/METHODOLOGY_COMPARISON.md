# Expected Move Methodology Comparison

This document summarizes which Expected Move (EM) calculation method is "best" for specific trading and analysis use cases, based on backtested performance (SPY, 2023-2025).

## Summary Table

| Methodology | Best For | Containment (Safety) | S/R Performance | Note |
| :--- | :--- | :--- | :--- | :--- |
| **ATM Straddle (x0.85)** | **Defensive Boundaries** | **Elite (95%+)** | Moderate (51% Rev) | Gold standard for live data. |
| **VIX Scaled (2.0x)** | **Futures/Proxy EM** | **Elite (96%+)** | Lower (43% Rev) | Best "Synthetic" Straddle. |
| **IV-252 (Trading)** | **Tactical S/R & Pivots** | Statistical (79%) | **Best (61% Rev)** | Most "Rebound" friction. |
| **IV-365 (Calendar)** | **Trend Targets** | Aggressive (68%) | Moderate (50% Rev) | Tighter, aggressive limits. |

---

## Detailed Comparison by Experiment

### 1. Containment (Probability of Profit)
*How often does the move stay inside the range?*

| Method | Prediction Type | In(Close) % | In(Excur) % |
| :--- | :--- | :--- | :--- |
| **Straddle / Scaled VIX** | **Extreme (High Prob)** | **98%** | **95%** |
| **IV-252 (Standard)** | Statistical 1-SD | 79% | 56% |
| **IV-365 (Tight)** | Aggressive | 69% | 45% |

**Verdict**: If you are setting **entry alerts** or **stop losses**, use the **Straddle** or **Scaled VIX**. They represent the "Safe Zone."

### 2. Intraday Support & Resistance (S/R)
*Where does the price actually bounce or reverse?*

| Method | Touches (502d) | Reversal Rate % | Quality (HOD/LOD) |
| :--- | :--- | :--- | :--- |
| **IV-252** | 150 | **60.7%** | **4.0%** |
| **Straddle** | 51 | 51.0% | 2.0% |
| **IV-365** | 173 | 50.3% | 2.9% |
| **Scaled VIX** | 121 | 43.0% | 0.8% |

**Verdict**: If you are looking for **intraday bounce trades**, the **IV-252 (Trading Day)** level is the "Better" Choice. It has a significantly higher immediate reversal rate (61%) and captures the actual session extremes twice as often as the Straddle.

---

## Conclusion: "The Right Tool for the Job"

### Use **ATM Straddle (or 2x VIX)** when...
- You want to stay safe.
- You are selling iron condors or credit spreads (High Probability).
- You want to know the "absolute" boundary of market risk.

### Use **IV-252** when...
- You are day trading for a mean-reversion move.
- You want to find high-probability "reversal" pivots.
- You want a level that the market actually "feels" and reacts to frequently.

### Use **IV-365** when...
- You are looking for breakout targets or extensions.
- You want a conservative target that trend days frequently touch and hold.
