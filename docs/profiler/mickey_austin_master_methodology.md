# 🏛️ Matt Mickey & Austin's Master Trading Methodology
> **Source**: NotebookLM Notebook `ef6358af-5096-4427-87fd-93ed015416c6` (*Pack Trading Reengineering Q2 2026* — 52 Processed YouTube Sessions)
> **Authors**: Matt Mickey & Austin (Pack Trading / TCM / Candle Science)
> **Core Philosophy**: "Objective logic over fluff, probability over prediction, and process over outcome. We do not rise to the level of our goals; we fall to the level of our systems."

---

## 📊 SECTION 1: THE 4 DAILY CLASSIFICATIONS & LIVE PRICE SIGNATURES

Mickey & Austin categorize every intraday market into one of four distinct statistical regimes. The daily classification determines profit targets, execution styles, and invalidation rules.

### 1. Range 1 (R1) — Low-Volatility Mean Reversion (38.98% Mode)
* **Volatility State**: Contracting Volatility (VVIX dropping, 10-day median range compressed).
* **Live Price Signature**: **The 10:00 AM candle sweeps BOTH sides of the 09:00 AM hour's range (both high & low).**
* **Magnet Level**: **09:30 AM Open** is the primary mean-reversion magnet ("making out with the 9:30 price").
* **Execution Rule**: Breakout trades constantly fail. Fading momentum back toward the 09:30 open is favored. Quick cash-flow scalps.

### 2. Range 2 (R2) — High-Volatility Mean Reversion (12.52% Mode)
* **Volatility State**: Expanding Volatility (VVIX popping, wide gaps between hourly bounds).
* **Live Price Signature**: Wide swings **2 to 3 standard deviations** away from the 09:30 open, followed by aggressive mean reversion back to the 09:30 open.
* **Confirmation**: Confirmed when the **NY2 (afternoon 12:30–16:00) session breaks in the opposite direction** of the morning breakout.
* **Execution Rule**: Fading extreme extensions into the 11:00 AM or 12:30 PM reversal windows.

### 3. Directional No Pullback (DNP) — One-Way Trend Day (15.63% Mode)
* **Volatility State**: Massive Expansion / Strong Weekly Alignment.
* **Live Price Signature**: **NO hourly low (or high on a bear day) is taken between 09:00 AM and 15:00 PM.**
* **Chop Trap**: The 09:30 to 10:30 AM window is often messy ("bag of dicks"), luring retail into fading before relentless one-way expansion begins.
* **Execution Rule**: Never fade. Buy dips / sell rips only. Targets are extended 75th+ percentile MFE levels.

### 4. Directional With Pullback (DWP) — Trend Day with Daily Wick Creation (32.87% Mode)
* **Volatility State**: Moderate to High Volatility Expansion.
* **Live Price Signature**: Fast and furious initial breakout from 09:30 (e.g., 200 points in 5 mins without returning to 09:30 open), followed by a **single defined pullback hour** (typically **11:00 AM** or **13:00–14:00 PM**).
* **Daily Candle Wick**: The pullback hour creates the **wick of the daily candle** (often running liquidity on a single hourly low/high) before resuming the primary trend into the close.
* **Execution Rule**: Ride initial breakout, execute on the 11:00 AM/13:00 PM pullback hour, and hold runners for new daily extremes.

---

## 🔮 SECTION 2: P12 LEVELS, OVERNIGHT PROFILES & MEASURED HANDSHAKES

### 1. P12 Levels (18:00 to 06:00 EST)
* **Definition**: First 12 hours of the daily candle (Globex Asia + London).
* **Levels**: P12 High, P12 Mid, P12 Low.
* **P12 Mid Baseline**: Midpoint of the first half of the daily candle.
  * *Rejecting P12 Mid* in pre-market ("Magic Hour" 07:30–08:30) targets **P12 Low**.
  * *Accepting above P12 Mid* targets **P12 High**.
  * P12 Mid carries a **91.4% historical hit probability**.

### 2. Overnight Profile States ($P_{session}$)
* **LT (Long True) & ST (Short True)**: Directional continuation holding session extremes.
* **LF (Long False) & SF (Short False)**: Breakout failed and reverted back into the session range.
* **Session Alignment Rules**:
  * **Trending Overnights (LT + SF or ST + LF)**: Sessions agree $\rightarrow$ **FIRECRACKER DAY** 🔥 (high directional expansion, session extremes hold).
  * **Contradicting Overnights (LT + ST or LF + SF)**: Sessions conflict $\rightarrow$ **BROKEN-BROKEN / GOALPOST EFFECT** (both session extremes swept during RTH).

### 3. Measured Handshakes (Sequential Flow)
* Market flow transitions seamlessly across timeframes:
  * **18:00 Asia Break** $\rightarrow$ **03:00 AM London Break** $\rightarrow$ **07:30 Magic Hour** $\rightarrow$ **09:30 RTH Open Break** $\rightarrow$ **11:00 AM PM Transition** $\rightarrow$ **14:00 Afternoon Drive**.

---

## ⏱️ SECTION 3: HOURLY SIGNATURES, COUNTERS & EXPIRATION CUTOFFS

### 1. 0-5 Box ($O_5$) & 10 bps Threshold
* High, low, open, and midpoint of the **first 5 minutes of each hour**.
* **10 Basis Points (0.10%) Threshold**: Breakout of 10 bps off the 0-5 box confirms true hourly momentum ("line signature").
* **False 0-5 Breakout**: A 10 bps breach that immediately sucks back into the range signals a sweeper/reversal.

### 2. The 4-Step Reversal Counter
To confirm a daily reversal (e.g., False Day reverting):
1. **Step 1**: Live price crosses back over the **09:30 AM Open**.
2. **Step 2**: Live price trades back through the **09:00 AM Hour 50% Midpoint**.
3. **Step 3**: The **10:00 AM Candle** takes out the 09:00 AM hour's extreme (high/low).
4. **Step 4**: The 10:00 AM candle locks an **In-Stat High/Low of Day**, mathematically securing the reversal.

### 3. Statistical Expiration Cutoffs
* **09:45 AM Cutoff**: Limit for hitting P12 Mid or Midnight Open. Failing to hit high-probability levels by 09:45 AM signals "anomaly land" (extreme trend strength).
* **10:15 AM Cutoff**: Final cutoff for morning mean-reversion trades. Reversal probabilities expire.
* **10:45 AM Cutoff**: Morning profile distributions expire; market locks in morning trend and shifts focus to afternoon ranges.

---

## 🛡️ SECTION 4: RISK MANAGEMENT & PORTFOLIO CYCLING

### 1. "Cover the Queen" (Cash Flow Security)
* Scale out a major portion of your position (e.g., 7 out of 15 micros) at **10 basis points (+5 to +10 pts)**.
* Instantly converts remaining contracts into a **risk-free trade** ("getting paid to be wrong").

### 2. Dynamic MAE / MFE Percentiles
* **MFE Targets**:
  * **25th–35th Percentile (~10 bps)**: Cash-flow target ("Cover the Queen").
  * **50th Median (~20–30 bps)**: Primary target for standard days.
  * **75th–80th+ Percentile (~50–70 bps)**: Extended runner target for DNP/DWP days.
* **MAE Heatmap Stops**:
  * **Green/White**: Healthy pullback.
  * **Orange**: High-risk warning zone.
  * **Red (70%–85%+ MAE)**: Hard invalidation. Exit trade immediately.

### 3. Portfolio Cycling & Risk of Ruin
* **1.5 / 4-Trade Gap**: Rotate trade execution across multiple funded accounts on different days/weeks.
* Spreads consecutive losing streaks across the portfolio so no single account takes the full drawdown.

### 4. "Failing to the Level of Your System"
* Traders do not rise to their goals; they fall to their systems.
* Completely surrender discretion to objective rules. Variance is expected and managed through statistical edge and portfolio cycling.

---
*Document Version: 1.0 (Master Synthesis). Source: 52 Reengineering YouTube Sessions (NotebookLM `ef6358af-5096-4427-87fd-93ed015416c6`).*
