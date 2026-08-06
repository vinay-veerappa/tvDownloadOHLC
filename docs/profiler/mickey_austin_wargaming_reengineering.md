# Mickey & Austin's Complete Wargaming & Re-Engineering SOP

> **Source**: NotebookLM - *Pack Oct Bootcamp* (`1689f881-6486-4b05-9fd4-f3a3d7f4af31`) & TCM System
> **Authors**: Matt Mickey & Austin
> **Purpose**: Systematic framework detailing pre-market morning wargaming (08:30–09:30 AM EST) and post-market re-engineering (16:00 PM EST).

---

## Part 1: Morning Wargaming (08:30 – 09:30 AM EST)

Morning wargaming is a proactive planning phase where traders build **"if-then" scenarios** so that all trading decisions, model selections, and risk parameters are predetermined before the 09:30 AM RTH opening bell.

### 1. The 4-Step Daily Profiler Workflow
Traders execute this repeatable 4-step workflow every morning:
1. **Input Session Variables & Plot O/U Lines**: Ingest data from Asia (Tokyo) and London (Frankfurt) sessions to classify their states ($P_{session}$). Plot Over/Under (O/U) session midlines.
2. **Plot HOD & LOD Projections**: Overlay statistical price zones (mode-to-median) and time windows (modes) to project where daily extremes are expected to form (based on 4,300+ days).
3. **Overlay 3-Hour Price Cloud**: Visualize expected hourly directional flow (9:00, 10:00, 11:00 stacking vs. apex reversal).
4. **Set Range Expectations using DROs**: Plot the 10-day median range and session-specific Distribution Ranges (DROs) to determine whether the market is "cheap" (contracting volatility) or "expensive" (expanding volatility).

### 2. Overnight Context & Directional Indicators
- **Profile States ($P_{session}$)**: Long True (LT), Long False (LF), Short True (ST), Short False (SF).
- **Trending Overnights (Sessions Agree)**: Asia & London directionally agree (e.g., ST + ST or LT + SF). Signals a **"Firecracker Day"** — expect strong trend expansion where bounded overnight extremes are respected.
- **Contradicting Overnights (Sessions Conflict)**: Asia & London directionally oppose (e.g., LT + ST). Signals **"Broken-Broken"** status — both overnight extremes are expected to be swept during RTH (Goalpost effect).
- **NY Opening Handshake Vector**:
  - *Agreement (A)*: RTH (09:30) opens above P12 Mid on a bullish profile (or below on bearish).
  - *Disagreement (D)*: RTH opens inside consolidation or contradictory to overnight expansion.

### 3. Key Levels & Order Flow Signals
- **P12 Levels (18:00 – 06:00)**: P12 High, Mid, Low. **P12 Mid** is the ultimate directional switch (holding above targets P12 High; accepting below targets P12 Low).
- **Session O/Us & Anchors**: Over/Under lines, Globex Open (18:00), Midnight Open (00:00), and Settlement serve as high-probability netting/bounce levels.
- **Intraday Execution Rules**:
  - **4-Step Reversal Counter**: Tracks (1) breach of 09:30 open, (2) acceptance past 09:00 hour 50% line, (3) 10:00 candle taking out 09:00 extreme, (4) 10:00 candle establishing Q1 instant extreme.
  - **3-Hour Line vs. Apex**: Line = hours stack cleanly in one direction. Apex = Hour 2 reverses Hour 1 via footprint rejection in Q3/Q4.
  - **0-5 Box & Momentum Thresholds**: Hourly 0-5 min range box requires **10 basis points (0.10%)** breach in Q1 during RTH (**5 bps** overnight) to confirm true momentum.

---

## Part 2: End-of-Session Re-Engineering (16:00 PM EST)

Re-engineering is a systematic daily review conducted at **16:00 PM EST** every single day. Mickey and Austin guide traders to map live price tape against statistical models, review execution mechanics, and refine their edge.

### The 7-Step Re-Engineering Process

1. **Classify the Day**:
   - Evaluate RTH price action (09:30 to 16:00) relative to the 09:30 open print.
   - Classify the session environment: **Range 1 (R1)**, **Directional No Pullback (DNP)**, **Directional With Pullback (DWP)**, or **Range 2 / Reversion (R2)**.
2. **Review Session & P12 Metrics**:
   - Review pre-market P12 High, Mid, Low boundaries.
   - Verify if price accepted, rejected, or netted off P12 levels and session O/U midlines.
   - Assess whether Asia/London session ranges overspent or underspent their historical checkbooks.
3. **Deconstruct Hourlies, 3-Hour Blocks & Quarters**:
   - Walk bar-by-bar through the 5m and 15m charts:
     - Check if **0-5 boxes** triggered valid 10 bps momentum breakouts or false Q1 extremes.
     - Verify if previous hour 50% midpoints and footprint wicks were respected.
     - Trace **3-Hour Blocks** (09:00–12:00 / 12:00–15:00) to confirm if order flow formed a 3-Hour Line or an Apex Reversal.
4. **Verify Reversal & Daily Extremes**:
   - Compare morning wargamed HOD/LOD expectations with actual live pivots.
   - Verify the exact time HOD/LOD locked in and count how many steps of the **4-Step Reversal Counter** were completed.
5. **Check Performance & Edge Metrics**:
   - Audit trade execution in the Trading Command Center against the active model's SOP (Mickey's 09:30 structure model, Austin's 9:30 breakout, Captain Backtest).
   - Log key performance metrics: Win Rate, Profit Factor (PF), Expected Value (EV), Max Drawdown, and Consecutive Losses.
6. **Identify Invalidation Points & Adjust Levers**:
   - Review stop-loss (SL) and take-profit (TP) targets against Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE) stats.
   - Determine if strategy levers (e.g., "Cover the Queen" levels, median MFE) need optimization.
7. **Acknowledge Mistakes & Reset the Edge**:
   - Document whether execution followed the business plan or if emotional friction (FOMO, overleveraging, front-running rules) occurred.
   - Systematically **"reset the edge"** for the next trading day, releasing emotional attachment to the session's outcome.

---
*Last Updated: 2026-08-05. Source: Pack Oct Bootcamp / TCM Systems.*
