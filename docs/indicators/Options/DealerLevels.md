# 📖 DEALER LEVELS TRADING PLAYBOOK
### A Day Trader’s Guide to Options-Based Market Structure & Institutional Order Flow

Your quantitative data pipeline computes market mechanics every session, blending **Structural Dealer Positioning** (Resting Liquidity) with **Institutional Order Flow** (The Urgent Tape). 

This playbook teaches you how to translate that raw data into a mechanical trading edge.

---

## CHAPTER 1: How to Read Your Dashboard
Every time the pipeline runs, it delivers three things: visual levels on your chart, a narrative Coach's Briefing on Discord, and a unified quantitative dashboard. Before looking at candlesticks, you must understand the mathematical environment.

### 🚦 The Traffic Light
The traffic light tells you *if* you should be trading.
* 🟢 **GREEN:** Clear structure. The regime is well-defined and levels are actionable. Trade with normal size and confidence.
* 🟡 **YELLOW:** Caution. The regime is transitional (COILED) or data is thin. Reduce your size by half and wait for confirmation before entry.
* 🔴 **RED:** Stand down. Multiple levels are missing or the structure is too compressed to trade safely. Paper trade or sit on your hands.



### 🏛️ The Regime Label
The regime tells you **HOW** to trade—not the direction, but the style of trading the market makers are forced to reward today.

| Regime | What It Means | How To Trade | Watch Out For |
| :--- | :--- | :--- | :--- |
| **PINNED** | Positive GEX + tight walls. Dealers dampen moves. | Fade moves to the walls. Short near call wall, long near put wall. Mean reversion works. | A sudden GEX flip to negative. The pin can break. |
| **TRENDING** | Negative GEX + wide walls. Dealers amplify moves. | Follow the trend. Join after confirmation, trail stops. Don’t fade. | Reversal at the call or put wall. Take profit at walls. |
| **COILED** | Negative GEX + tight walls. Compressed spring. | Wait. Watch for a break of the gamma flip zone. Then join the breakout direction. | False breakouts. Require a candle close outside the zone before entry. |
| **BATTLE ZONE** | Positive GEX + wide walls. Big swings that reverse. | Trade wall-to-wall. Short at call wall, long at put wall. Use wider stops. | Getting stopped out on the swing. Position size for the range. |

### 🧭 The Structural Bias & Volatility Context
The dashboard provides a unified view of both directional bias and volatility regime.

1.  **Directional Bias (↑ / ↓ / ↔)**:
    *   **Price vs Gamma Magnet**: Gravity pulls toward the magnet.
    *   **Put/Call Gamma Ratio**: Hedging dominance (>60% put/call ratio).
    *   **Net Vanna**: Sensitivity to IV drops (Negative Vanna = Selling pressure on IV contraction).
2.  **Volatility Context (Fear Premium / Skew)**:
    *   **Fear Premium (Skew Premium)**: The extra cost of OTM Puts relative to Calls. High premium (>4.0) = extreme anxiety / hedging.
    *   **IV Shift (VOL Change)**: The **cumulative** change in ATM Implied Volatility since the market open.
        *   🟢 **Negative Shift**: Volatility is contracting (crushing). Markets stabilizing.
        *   🔴 **Positive Shift**: Volatility is expanding (spiking). Markets in discovery or panic.

---

## CHAPTER 2: The Map & The Tape (Your Levels Explained)
Your chart displays two distinct layers of data. **The Map** shows where resting capital has built structural walls. **The Tape** shows where institutions are urgently attacking *today*.

### 🗺️ Layer 1: The Structural Map (Dealer Positioning)
These are your primary anchors. They change slowly and dictate the overarching trend.



* **Zero Gamma:** The absolute pivot. The price where cumulative GEX crosses zero. Above it, dealer hedging dampens moves (Positive GEX). Below it, hedging amplifies moves (Negative GEX). 
* **Macro Call Wall / Put Wall:** The absolute structural ceiling and floor of the market. Treat these as extreme resistance and support. 
* **Major Nodes:** Thick, brightly colored lines representing massive, slow-accumulated Open Interest fortresses (e.g., `MAJ P (8.0%)`). Price will struggle heavily to break these on the first test.
* **Gamma Magnet:** The intraday center of gravity where hedging flows pull price. Use this as your mid-range profit target.
* **Expected Move (EM Upper/Lower):** The options-implied "normal" range for the day. Inside the band = two-way chop; outside the band = violent expansion.

### 🚨 Layer 2: The Urgent Tape (Institutional Whales)
These are dynamic labels injected directly from the live options flow, representing aggressive institutional conviction.
* **GOLDEN SWEEPS (Gold Lines):** The ultimate urgency signal. An institution just dropped massive capital (Volume > OI) into a short-term expiration. *Action:* Trade with the sweep if it aligns with the macro trend.
* **Confluent Whales (e.g., `W-PUT x5`):** Multiple expirations are piling massive volume onto the exact same strike. *Action:* Treat this as a heavily defended institutional fortress.
* **Local Whales (e.g., `LW-CALL`):** An isolated, massive intraday sniper bet. *Action:* Use as an immediate Draw on Liquidity (DOL) for day trades. (These vanish if price moves too far away).

### 🔬 Secondary Levels & Advanced Alpha
* **Gamma Flip Zone:** The narrow, shaded zone around zero gamma. In COILED regimes, a candle close outside this zone confirms the breakout.
* **Gamma Cliffs:** Where GEX builds or falls off most steeply. Price often stalls or accelerates violently at these cliffs.
* **Fear Premium (Skew):** Visualized in the Skew Chart. High Skew + Negative GEX = "The Crash Trap".
* **Cumulative IV Shift:** Located in the Stats Hero and Daily Shift card. Tracks the total daily volatility expansion/contraction.
* **Pin Strike:** The convergence target into the close. If Pin Odds are >25%, expect price to magnetize here after 2:00 PM ET.

---

## CHAPTER 3: The Session Playbook
Your step-by-step workflow from open to close.

**1. Pre-Market (8:30 AM ET)**
Read the Coach’s Briefing on Discord. Absorb the context. Know your Regime, your Bias, and your Traffic Light. Do not trade yet.

**2. The Open (9:30 – 10:00 AM ET)**
Watch the first 30 minutes. The opening range establishes where price wants to go relative to your triggers.
* Acceptance above long trigger → Bullish lean confirmed.
* Break below short trigger → Bearish lean confirmed.
* Chop between triggers → Wait for a clear break.

**3. Mid-Session Execution (10:00 AM – 1:00 PM ET)**
Execute based on your regime:
* **PINNED:** Fade moves to the walls. Target the gamma magnet. Keep stops tight.
* **TRENDING:** Wait for price to break and hold past a key wall, then enter on the retest. Trail your stop. 
* **COILED:** Watch the Gamma Flip zone. Enter *only* after a candle closes outside the zone, with your stop tucked back inside.
* **BATTLE ZONE:** Trade wall-to-wall with wider stops.

*Note: Check Discord for REGIME CHANGE alerts during scheduled pipeline runs. If the regime changes, the rules change.*

**4. The Afternoon & Close (1:00 – 4:00 PM ET)**
Check the Pin Odds. If odds are >25%, expect convergence to the Pin Strike and tighten your targets. Watch Net Vanna; negative vanna brings late-day selling pressure as IV drops. Flatten 0DTE risk by 3:45 PM.

---

## CHAPTER 4: Surviving Regime Changes
Regime changes mean the character of the market has shifted, and your approach must shift with it.

| Alert Type | Severity | Meaning | Required Action |
| :--- | :--- | :--- | :--- |
| **GEX Flip** | **HIGH** | GEX changed sign (positive ↔ negative). Fundamental regime shifted. | Close open positions based on the old regime. Reassess. |
| **Regime Change** | **HIGH** | The label changed (e.g., PINNED → TRENDING). | Switch to the new regime’s approach immediately. |
| **GEX Swing** | **MEDIUM** | GEX magnitude changed >30% without a flip. | Adjust confidence/stops. |



🚨 **THE #1 RULE OF OPTIONS TRADING:** If you are mean-reverting (fading) in a PINNED regime, and GEX flips negative, **STOP FADING IMMEDIATELY**. The move you are fading is now being violently amplified by dealer hedging. 

---

## CHAPTER 5: The 6 Fatal Mistakes
1.  **Trading Every Level:** Your chart has 16+ levels. Focus *only* on the main triggers from the narrative plan. Everything else is just context.
2.  **Ignoring the Regime:** A Call Wall in a PINNED regime means "Short here". A Call Wall in a TRENDING regime means "If it breaks, buy the breakout". The regime dictates the action.
3.  **Front-Running Confirmation:** Entering on the first touch of a level will get you stopped out by noise. Wait for candle-close acceptance, then enter on the retest.
4.  **Fighting the Bias:** If the bias is BEARISH, trying to go long from support is swimming upstream. Trade *with* the structural bias.
5.  **Holding Through a Change:** If you are in a mean-reversion trade and Discord fires a TRENDING regime alert, close the trade. Do not hope. The math changed.
6.  **Overtrading on COILED Days:** COILED is the hardest regime. It chops traders up before breaking violently. Be patient, or stand down.

---

## 🖨️ CHAPTER 6: Quick Reference Card (Print This)

### ✅ Pre-Trade Checklist
* [ ] What is the traffic light? (GREEN / YELLOW / RED)
* [ ] What is the regime? (PINNED / TRENDING / COILED / BATTLE)
* [ ] What is the directional bias? (↑ BULLISH / ↓ BEARISH / ↔ NEUTRAL)
* [ ] Am I trading WITH or AGAINST the bias?
* [ ] Where is my short trigger? My long trigger?
* [ ] Where is the gamma magnet? (My mid-range target)
* [ ] Are there any GOLDEN SWEEPS lighting up the tape?

### 🎯 Regime Action Matrix
| Regime + Bias | Primary Action | Entry Style | Stop Placement |
| :--- | :--- | :--- | :--- |
| **PINNED ↑** | Long from put wall | Fade at support, target magnet | Below put wall |
| **PINNED ↓** | Short from call wall | Fade at resistance, target magnet | Above call wall |
| **TRENDING ↑** | Long on break of call wall | Break + retest of resistance | Below the broken level |
| **TRENDING ↓** | Short on break of put wall | Break + retest of support | Above the broken level |
| **COILED (Either)**| Wait for GF zone break | Candle close outside flip zone, then retest | Back inside the flip zone |
| **BATTLE ↑** | Long at put wall | Bounce at support, wide stop | Well below put wall |
| **BATTLE ↓** | Short at call wall | Rejection at resistance, wide stop | Well above call wall |



> *The pipeline gives you the structure. The Coach’s Briefing gives you the plan. The chart gives you the timing. You provide the discipline.*