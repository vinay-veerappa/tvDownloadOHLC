# ICT Knowledge Base

This document outlines the Inner Circle Trader (ICT) concepts that this agent is aware of, specifically focusing on elements that have been implemented in code or analysis scripts within this codebase.

## 1. Core Framework (Time & Price)

### 🗓️ Time (The Algo Clock)
The market is algorithmic and operates on specific time windows.
-   **Midnight Open (00:00 EST)**: The true "Open" of the dealing day. Used as the primary pivot for Bullish/Bearish bias.
    -   *Rule*: If Price > Midnight Open, seek Longs. If Price < Midnight Open, seek Shorts.
-   **08:30 Open**: Major news injection time (Bond Market Open). Often marks the start of the "Judas Swing".
-   **Kill Zones**:
    -   **London (02:00 - 05:00 EST)**: Often creates the High or Low of the day (HOD/LOD).
    -   **NY AM (09:30 - 11:00 EST)**: Initial volatility and "Silver Bullet" window (10am-11am).
    -   **NY PM (13:30 - 16:00 EST)**: The "PM Session" often seeks liquidity resting from the AM session.

### 💰 Liquidity (Draw on Price)
Price moves to seek liquidity.
-   **BSL (Buy Side Liquidity)**: Resting stops above old highs (PDH, PWH, Swing Highs).
-   **SSL (Sell Side Liquidity)**: Resting stops below old lows (PDL, PWL, Swing Lows).
-   **Sweeps**: When price pierces a level to trigger stops and then reverses. This is a primary reversal signal.

## 2. Implemented Concepts (Codebase)

I have specific scripts (`scripts/backtest/ICT/`) designed to test and validate these concepts:

| Concept | File | Description |
| :--- | :--- | :--- |
| **Displacement** | `bias_displacement.py` | Identifying energetic moves that leave "Glossy" candles vs "Lethargic" chopping. |
| **Fair Value Gaps (FVG)** | `bias_fvg_mtf.py` | Detecting inefficiencies (Gap between Candle 1 High and Candle 3 Low). |
| **Liquidity Sweeps** | `bias_liquidity_sweep.py` | Logic to detect a fakeout: Break Level -> Reclaim Level. |
| **Magnet Trend** | `bias_magnet_trend.py` | Assessing if price is drawn to specific "Magnets" (Round Numbers, Open prices, NWOG/NDOG). |
| **P12 Levels** | `bias_p12_levels.py` | Proprietary level logic likely related to projection/extension (Power of 12). |
| **Asia Volatility** | `bias_asia_volatility.py` | Using Asia Range expansion to predict NY direction. |

## 3. Daily Analysis Tools (Active Skills)

### 🛠️ The ICT Trader Skill
*Located in* `.agent/skills/ict_trader/`

I have a built-in skill `ICT Trader` that automates the daily markup:
1.  **PDH / PDL**: Automatically fetches the Previous Day High/Low.
2.  **Midnight Open**: Identifies the 00:00 EST opening price.
3.  **Bias Check**: Compares current price to Midnight Open to determine algorithmic state.

### 📊 The Reversal Magnet Hub
*Located in* `docs/DailyClassification/`

My comprehensive analysis (`REVERSAL_MAGNETS_MASTER_HUB.md`) validates ICT theories with data:
-   **07:30 / 08:30 Open**: Statistically proven as a major reversal driver (13% of all NQ reversals).
-   **London High/Low**: Confirmed as a key level held in 8.4% of strong trend days.
-   **Midnight Open**: Acts as a "Line in the Sand" for 8% of major turns.

## 5. Advanced Concepts & PD Arrays

I possess deep theoretical understanding of the following concepts, though they are currently on the **Roadmap** for implementation:

### 🧩 Market Structure & Divergence
-   **SMT (Smart Money Technique)**: Divergence between correlated assets (e.g., NQ makes a higher high, ES makes a lower high). This cracks the correlation and signals a reversal.
-   **CISD (Change in State of Delivery)**: The moment price shifts from a Buy Program to a Sell Program (or vice versa), often marked by the first candle that closes below/above a key swing after a liquidity sweep.
-   **Profiles**:
    -   **Weekly Profiles**: The roadmap for the week (e.g., "Classic Tuesday Low of Week").
    -   **Daily Profiles**: The template for the day (e.g., "London Swing -> NY Expansion").

### 🧱 PD Arrays (Premium/Discount)
The hierarchy of institutional reference points:
1.  **Mitigation Block**: A failed swing low/high that is revisited. Unlike a Breaker, it did *not* take liquidity before breaking.
2.  **Breaker Block**: A swing low/high that *took liquidity* and was then broken impulsively. It flips from Support to Resistance.
3.  **Liquidity Void / Imbalance**:
    -   **IFVG (Inversion Fair Value Gap)**: An FVG that served as support, was broken, and now acts as resistance (or vice versa).
    -   **first presented FVG**: The initial FVG that forms *after* the 09:30 AM Opening Bell. This frequently sets the tone for the session and offers the first high-probability entry.
    -   **Volume Imbalance**: A gap where candle bodies do not overlap, but wicks might.
    -   **NWOG / NDOG (Implemented)**: New Week/Day Opening Gaps. *These are currently tracked in my Magnet Analysis.*

## 6. Glossary of Terms

-   **AMD**: Accumulation, Manipulation, Distribution. The structure of a standard candle.
-   **FVG**: Fair Value Gap.
-   **OB**: Order Block.
-   **MSS**: Market Structure Shift.
-   **PD Array**: Premium/Discount Array (Matrix of levels).
-   **Judas Swing**: The fake move at the open (Manipulation) to induce traders into the wrong direction before the true trend (Distribution).

---
*This document is auto-generated based on current agent capabilities and codebase analysis.*
