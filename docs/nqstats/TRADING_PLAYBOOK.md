# NQStats Day Trading Playbook
*A Statistical Edge Strategy for NY AM & PM Sessions*

This playbook synthesizes over 10 years of verified data (2015-2025) into a chronological workflow. It integrates the "Quarterly Timing" and "Expansion" rules to provide a precise intraday roadmap.

---

## 🌅 Phase 1: Pre-Market Analysis (08:00 AM - 09:25 AM ET)
*Objective: Establish Key Levels and Initial Bias.*

### 1. Check ALN (Asia-London) Structure (08:00 AM)
*   **Metric**: [ALN Sessions](../aln_sessions/REPORT.md)
*   **The Check**: Did London break *only* the Asia High OR Low?
    *   **LPEU (Bullish)**: London High > Asia High. **Bias: Long**.
    *   **LPED (Bearish)**: London Low < Asia Low. **Bias: Short**.

### 2. Check Daily Open Profile (09:25 AM)
*   **Metric**: [RTH Breaks](../rth_breaks/REPORT.md)
*   **Action**: Locate Open relative to Yesterday's RTH Range.
    *   **Inside Open**: **Expansion Mode**. Expect a trend day.
    *   **Gap Open**: **Defense Mode**. Gap fill is NOT guaranteed. Range holds >87% of time.

---

## 🏙️ Phase 2: The Open & "Judas" (09:30 AM - 10:00 AM ET)
*Objective: Survive the Volatility (The Expansion Hour).*

### 🚫 The "No Fade" Zone
*   **Personality**: **Back-Weighted Expansion**. The High/Low of this hour usually forms in the **Last 15 Minutes (Q4)** (40% Prob).
*   **Strategy**: **Do NOT Fade** the "Morning Judas" (09:30-09:40).
    *   If Price drives UP: It usually stays UP (76% Hold). Look for continuations.
    *   **5m ORB Check**: If 9:30-9:35 is GREEN, Expect a **Late High** (Expansion).

---

## 🎯 Phase 3: The Prime Session (10:00 AM - 12:00 PM ET)
*Objective: The "Golden Hour" & Reversion Trades.*

### 1. The 10:00 AM Reversion Setup (The "Money Trade")
*   **Personality**: **Front-Weighted Reversion**. The High/Low of this hour forms in the **First 15 Minutes (Q1)** (37% Prob).
*   **Metric**: [Hour Stats](../hour_stats/REPORT.md)
*   **The Setup**:
    1.  **Wait for 10:00 AM**.
    2.  **Confirm Bias**: Check 9AM Hourly Candle Color (Green = Long Bias).
    3.  **The Trigger**: Price sweeps the 09:00-10:00 High or Low in the **First 15 Minutes**.
    4.  **Action**: **FADE IT**. (Aggressively fade back to 10:00 Open).
    5.  **Win Rate**: **>82%** (if <15m sweep).

### 2. The IB Breakout (10:30 AM)
*   **Metric**: [IB Breaks](../initial_balance/REPORT.md)
*   **Action**: Mark the 09:30-10:30 High/Low ("Initial Balance").
*   **Rule**: If 10:30 candle closes in the Upper Half of IB, **Buy the Breakout**. (>80% Prob).

---

## ☀️ Phase 4: The Midday Pivot (12:00 PM ET)
*Objective: Trend Confirmation.*

### 1. The Noon Curve
*   **Metric**: [Noon Curve](../noon_curve/REPORT.md)
*   **Action**: At 12:00 PM, check if Price is *Inside* the AM Range.
*   **Trigger**: If **Inside**, expect a **Breakout** (Expansion).
    *   **Direction**: Follow the 10:00 AM Bias.

---

## 🌇 Phase 5: The PM Session (12:00 PM - 04:00 PM ET)
*Objective: Execution using "The Expansion Rule".*

### The Hourly Expansion Strategy
*For every new hour (12:00, 1:00, 2:00), apply this filter:*

**Step 1: Check the 5-Minute ORB (First 5 mins of the hour)**.
*   **If Green**: Expect **Expansion** (High in Q2-Q4). **DO NOT FADE**. Look for Trend/Continuation.
*   **If Red**: Expect **Reversion** (High in Q1). **FADE THE EARLY MOVE**.

**Step 2: Time Execution**.
*   **Minute 00-15**: **FADE** (Only if ORB suggests Reversion).
*   **Minute 15-45**: **WAIT**. (Noise).
*   **Minute 45-60**: **FOLLOW**. (Trend Continuation / Close Strength).

### The 15:00 "Power Hour"
*   **Personality**: **Trend Close**. High forms in Q4 (41%).
*   **Action**: **Do NOT Fade**. Expect the 3pm candle to expand into the 4pm close.

---

## 🛠️ Summary Checklist

| Time (ET) | Step | Action |
| :--- | :--- | :--- |
| **08:00** | Pre-Market | Check ALN (LPEU/LPED) Bias. |
| **09:30** | Open | **DON'T FADE**. Follow "Judas" direction. |
| **10:00** | **PRIME SETUP** | **FADE** the 0-15m Sweep of 9am Range. |
| **10:30** | Expansion | Trade **IB Breakout**. |
| **12:00** | Midday | Check **Noon Curve**. (Inside = Breakout). |
| **Hourly** | Execution | Check **5m ORB**. (Green = Expansion, Red = Reversion). |
| **15:00** | Close | **Trend Follow**. High likely at Close. |

### 🚨 Critical Warnings
1.  **Commodities**: Do **NOT** use Noon Curve (12pm) or Morning Judas (9:30) on Gold/Oil. Use optimized times (9am/10am) only.
2.  **SDEV Fades**: Never place blind limit orders at SD levels.

103: 3.  **15m Rule**: If an hour sweep happens *after* minute 15, **KILL THE FADE**. The edge is gone.

## 7. Algorithmic Entry Logic (Step-by-Step Bots)
*Specific "If/Then" logic for each market condition.*

### A. The Bullish Breakout Bot (Trend Mode)
*Use this when: 5m ORB is GREEN.*

1.  **Check Context**:
    *   Is it 09:30, 15:00, or a "Green ORB" Hour?
    *   Is Price > Previous Hour High?
2.  **Wait for Pullback**:
    *   **Trigger**: Price retraces towards Open.
    *   **Filter**: Do **NOT** buy the 50% retracement blindly (Win Rate < 41%).
    *   **Entry**: Buy only if Price holds **Above Previous Close**.
3.  **Execute**:
    *   **Entry**: Limit Buy at Previous Close + 2 pts.
    *   **Stop**: 15 points.
    *   **Target**: 100% Range Expansion (Prev High + Range).

### B. The Reversion "Fade" Bot (Range Mode)
*Use this when: 5m ORB is RED or Noise Hours (10am-2pm).*

1.  **Check Context**:
    *   Is it 10:00, 11:00, or a "Red ORB" Hour?
    *   Is Price within Previous Hour's Range?
2.  **Wait for Sweep**:
    *   **Trigger**: Price sweeps Previous Hour High OR Low.
    *   **Time Filter**: Must be Minute 00-15.
3.  **Execute**:
    *   **Entry**: Market Sell (if High Sweep) / Buy (if Low Sweep) immediately upon confirming the sweep (price ticks 1 pt beyond).
    *   **Stop**: 10 points above the sweep.
    *   **Target**: Return to Current Hour Open. (82% Win Rate).

### C. The Consolidation "Chop" Bot
*Use this when: Price oscillates around Previous 50%.*

1.  **Check Context**:
    *   Price touches Previous Hour 50% (Midpoint).
2.  **Logic**:
    *   **Stat**: Bounces off 50% fail often (40% continuation).
    *   **Action**: **DO NOT TRADE**.
    *   **Wait**: Wait for a new 15m High/Low Sweep to engage the "Fade Bot".

### D. 3H / 4H Macro Filter
*   **3H Rule**: If 09:00-12:00 was Green, bias the 12:00-15:00 session Long.
*   **4H Rule**: If 10:00-14:00 (Prime) is chopping, expect 14:00-18:00 (Close) to Expand.

---


## 8. Risk Management Protocol ($3k Small Account)
*Never risk >10% of your account on a single trade.*

### The Golden Rule: Use Micros (MNQ)
For an account of **$3,000**, trading standard NQ Mini contracts is **SUICIDE**.
*   **NQ (Mini)**: $20 per point. A 20-point stop = **$400 Loss** (13.3% of account). **DO NOT TRADE THIS**.
*   **MNQ (Micro)**: $2 per point. A 20-point stop = **$40 Loss** (1.3% of account). **TRADE THIS**.

### Position Sizing Table ($3,000 Balance)
*Max Risk Target: 10% ($300). Recommended Risk: 2% ($60).*

| Instrument | Stop Loss (Pts) | Contracts | Risk ($) | % of Acc | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NQ (Mini)** | 20 pts | 1 | $400 | 13.3% | ❌ **UNSAFE** |
| **MNQ (Micro)** | 20 pts | **1** | **$40** | **1.3%** | ✅ **SAFE** |
| **MNQ (Micro)** | 20 pts | **7** | **$280** | **9.3%** | ⚠️ **MAX AGGRESSIVE** |

### Trade Management Rules
1.  **Stop Loss (SL)**: Hard Stop at **20 Points** ($40 per Micro contract).
2.  **Trailing Stop (TS)**: Activate at **30 Points** profit. Trail by **10 Points**.
    *   *Goal: Lock in a "Free Trade" asap.*
3.  **Daily Max Loss**: Stop trading immediately if equity drops **$300 (10%)** in one day.
4.  **Pyramiding**: Max **2 Active Trades** at a time. The code allows one per hour, but manage your margin carefully.


