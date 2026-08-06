# Daily Profiler & Daily Wargaming Knowledge Base

> **Source**: NotebookLM - *Pack Oct Bootcamp* (`1689f881-6486-4b05-9fd4-f3a3d7f4af31`)
> **Purpose**: Systematic morning wargaming SOP (8:30 – 9:30 AM EST) to classify market environments, set expected volatility, align overnight context, and define mechanical trade execution rules.

---

## 1. Core Philosophy of Daily Wargaming
- **Execution Window**: Conducted daily between **8:30 AM and 9:30 AM EST** before the Regular Trading Hours (RTH) open.
- **Objective**: Eliminate real-time discretionary decisions by defining SOPs beforehand:
  1. Determine which trading models to turn **ON** or **OFF**.
  2. Set position contract sizing based on volatility parameters.
  3. Define realistic Take-Profit (TP) expectations (scalps vs. trend extension runners).

---

## 2. The 4-Step Daily Profiler Workflow

```
[Step 1: Session Variables & O/U Lines] 
       ↓
[Step 2: Plot HOD / LOD Statistical Projections] 
       ↓
[Step 3: Overlay 3-Hour Price Cloud] 
       ↓
[Step 4: Set Range Expectations via DROs]
```

1. **Input Session Variables & O/U Lines**:
   - Classify outcomes for **Asia** (Tokyo) and **London** (Frankfurt) sessions (e.g., *Long True*, *Short False*).
   - Plot the **Over/Under (O/U) midlines** (50% midpoints of the session fixed constants).
2. **Plot HOD & LOD Projections**:
   - Plot the highest-probability price zones (**mode-to-median**) and time windows (**mode times**) for expected daily extremes (based on 4,300+ historical days).
3. **Overlay the 3-Hour Price Cloud**:
   - Generate the statistical 3-hour price cloud to visualize expected hourly directional flow (9:00, 10:00, 11:00 stacking vs. apex reversal).
4. **Set Range Expectations using DROs**:
   - Plot the **10-day median range** and session **Distribution Ranges (DROs)** to evaluate whether volatility is contracting (cheap) or expanding (expensive).

---

## 3. Session Windows & Overnight Context

### Session Breakdown (Eastern Time)
- **Asia**: Fixed Constant (**18:00 – 19:30**) | Variable Trade Phase (**19:30 – 02:30**)
- **London**: Fixed Constant (**02:30 – 03:30**) | Variable Trade Phase (**03:30 – 07:30**)
- **New York 1 (NY1)**: Fixed Constant (**07:30 – 08:30**) | Variable Trade Phase (**08:30 – 11:30**)
- **New York 2 (NY2)**: Fixed Constant (**11:30 – 12:30**) | Variable Trade Phase (**12:30 – 16:15**)

### The 4 Overnight Structural Profile States ($P_{session}$)
1. **Long True (LT)**: Continuous bullish expansion with sequential hourly closes above 50% midpoints, leaving an un-swept session low.
2. **Short True (ST)**: Continuous bearish expansion with sequential hourly closes below 50% midpoints, leaving an un-swept session high.
3. **Long False (LF)**: Upward manipulation sweep breaching distribution boundaries, followed by a structural break closing below key prints (high pivot established).
4. **Short False (SF)**: Downward manipulation sweep breaching distribution boundaries, followed by a structural break closing above key prints (low pivot established).

### Session Alignment Types
- 🚀 **Trending Overnights (Aligned Sessions)** (e.g., *LT + SF* or *ST + LF*):
  - Asia & London directionally agree.
  - Signals a **"Firecracker Day"** — high probability of continuous RTH trend without pullbacks. Session extremes act as strong support/resistance.
- 🌀 **Contradicting Overnights (Conflicting Sessions)** (e.g., *LT + ST*):
  - Asia & London directionally disagree.
  - Signals range-bound chop. High probability of **"Broken Broken"** status (both overnight session extremes get swept during RTH). Prepare for the **"Goalpost" effect** (sweeping both sides before consolidating).

### NY Opening Handshake Vector
- **Agreement (A)**: RTH (09:30) opens above P12 midline on a bullish overnight profile (or below on bearish).
- **Disagreement (D)**: RTH opens inside consolidation or opposite to overnight expansion.

---

## 4. Key Reference Levels

- **P12 (Previous 12-Hour: 18:00–06:00)**: P12 High, Low, and **P12 Midline**.
  - *Directional Switch*: Support above P12 Mid between 06:00–08:30 AM targets P12 High; staying below targets P12 Low.
  - *P12 Rejection*: Rejection of P12 Mid between 06:00–07:00 AM confirms one daily extreme is locked in.
  - *99.26% Probability Rule*: If both Asia & London highs/lows are broken before 09:30 AM, there is a 99.26% probability that both HOD and LOD form after 8:30 AM (range-bound chop).
- **Over/Under (O/U) Lines**: Midpoints of fixed constants; key statistical retrace & netting levels.
- **Time Anchors**: Midnight Open (00:00), Globex Open (18:00), and RTH Open (09:30).

---

## 5. Intraday Daily Classifications (RTH Environments)

| Classification | Behavior & Price Action | Frequency | Strategy SOP |
| :--- | :--- | :--- | :--- |
| **Range 1 (R1)** | Price spends **4+ hours** touching/crossing the 09:30 open. | **38.98%** *(Mode)* | Turn **ON** mean-reversion & cash-flow systems. Take quick 10 basis point scalps. |
| **Directional No Pullback (DNP)** | Clean 1-sided trend away from 09:30 open for **5+ hours**. | **15.63%** | Turn **ON** momentum/continuation models. Buy dips / sell rips only. |
| **Directional With Pullback (DWP)** | Early aggressive trend, transitioning to tight afternoon range at 11:00–12:00. | **32.87%** | Ride early momentum; switch to short-range scalp trades in the afternoon. |
| **Range 2 (R2) / Reversion** | Explosive morning trend that collapses completely back to 09:30 open by close. | **12.52%** | Look for midday failure signature to fade trend back to the open ("thigh gap" reversion). |

---

## 6. Execution Rules & Filters

### 1. The 9:45 AM Reversal Checklist
To trade the 9:45 AM morning pivot:
1. Is HOD/LOD verified as post-09:30 by the Daily Profiler?
2. Is daily profile verified as *Long False* or *Short False*?
3. Is price trading opposite to the 09:00 hour's 50% midpoint and 09:30 box?
4. Is price netting off a key level (P12, O/U line, PDH/L)?

### 2. The 4-Step Reversal Counter (Trend vs. Reversal Filter)
To verify if a major trend reversal has locked in a 3-to-7 hour pivot:
- **Step 1**: Price breaches & accepts outside 09:30 open range.
- **Step 2**: Price accepts past 09:00 hour's 50% midpoint.
- **Step 3**: 10:00 AM candle takes out 09:00 AM high or low.
- **Step 4**: 10:00 AM candle creates an "InStat (instantaneous statistical) High/Low" in its first 15 mins (Q1).
- *Rule*: **All 4 steps met** = Major Reversal confirmed. **0 steps met** = Trend Continuation locked in.

### 3. 0-5 Box Breakout Thresholds
- **0-5 Box**: The high-to-low range of the first 5 minutes of an hourly candle.
- **RTH Momentum Threshold**: Price must breach the 0-5 box by **10 basis points (0.10%)** in Quarter 1 (Q1) to confirm true, sustainable momentum.
- **Overnight Threshold**: Requires **5 basis points (0.05%)**.
- *False Breakout Rule*: Failing to reach the basis-point threshold and returning inside the 0-5 box flags a false breakout, establishing a temporary "InStat (instantaneous statistical) High/Low".

---
*Last Updated: 2026-08-05. Additional rules and live case studies will be appended here.*
