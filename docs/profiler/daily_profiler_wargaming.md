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

### 3. The 1-Minute RTH Opening Range (09:30 OR) & 14:00 0-5 Box
- **1-Minute RTH Opening Range (09:30:00 – 09:30:59 AM EST)**:
  - The foundational reference frame for RTH open is the **first 1-minute candle**.
  - **Range Filter (Sweet Spot vs. Toxic Cutoff)**:
    - **Sweet Spot (0.10% – 0.18% / 10–18 bps)**: Optimal liquidity and momentum balance; highest probability of clean expansion.
    - **Toxic / Skip (> 0.25% / > 25 bps)**: Excessive opening chop/volatility; mandates DO NOT TRADE (SKIP).
  - **Strict 0% Fakeout Invalidation**: If price breaks out but any subsequent 1m candle closes **back inside the 1m Opening Range**, exit immediately.
  - **Selective MAE Stop**: Ultra-tight stop of **0.05% of price (~10–12 pts on NQ)**.
  - **Golden Timing Window**: 09:30–09:40 AM ET (peak edge at 09:32 AM; hard time-based exit at 09:44 AM ET).
- **14:00 (2:00 PM) Afternoon 0-5 Box Strategy**:
  - The **0-5 Box** (minutes 14:00:00 to 14:05:00) is a specialized setup specifically for the **14:00 afternoon session**. Entries occur between 14:06 and 14:45.

---

## 7. Economic News Catalysts & Manipulation Windows (09:45 & 10:00 AM EST)

Economic news releases act as major algorithmic liquidity magnets and volatility catalysts. Market makers routinely exploit the pre-news window to accumulate positions and sweep retail stops.

### Key Macro Timing Windows
1. **08:30 AM EST (Pre-Market Macro)**: CPI, PPI, NFP, Unemployment Claims, Retail Sales, GDP. Sets the overnight expansion baseline before RTH opens.
2. **09:45 AM EST (Open Drive Catalyst)**: S&P Global Flash Manufacturing / Services PMI.
3. **10:00 AM EST (Morning Institutional Anchor)**: ISM Manufacturing / Services PMI, JOLTS Job Openings, CB Consumer Confidence, New Home Sales, Michigan Sentiment.
4. **14:00 PM EST (Afternoon Macro)**: FOMC Rate Decision, FOMC Minutes, Fed Chair Press Conference (14:30).

### Core Tactical Rules for Trading with 09:45 / 10:00 AM News
* ⚠️ **The 09:30–09:44 Liquidity Trap**: When 09:45 or 10:00 AM high-impact news is scheduled, the initial 09:30 RTH open is frequently a manipulation/chop zone. Institutional algos engineer false breakouts to both sides of the 0-5 box.
* 🎯 **09:45 AM News Rule**: Do NOT assume an early 09:30–09:35 breakout is authentic. Wait for the 09:45 news candle to establish whether price confirms displacement or produces an instant mean-reversion V-spike.
* 🚀 **10:00 AM News Rule (Institutional Ignition)**: When high-impact news (e.g., ISM PMI, JOLTS) prints at 10:00 AM, the true session expansion trend almost always begins **at or after 10:00 AM**.
  - **Reversal Counter Step 3 & 4 Synergy**: The 10:00 AM news candle provides the exact catalyst for **Step 3 (10:00 AM Candle sweeping 09:00 AM extreme)** and **Step 4 (establishing the 10:00 Q1 InStat direction)**.
  - *Golden Rule*: Do not front-run 10:00 AM news. Let the news candle clear the liquidity pool and commit only after the displacement candle closes.

---
*Last Updated: 2026-09-01. Enhanced with 09:45 & 10:00 AM Economic News Manipulation Protocols.*
