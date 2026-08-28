---
name: pack-wargaming
description: Generates the authentic Mickey & Austin Pre-Market Wargaming Playbook and If-Then Scenario Cards. Enforces P12 directional vectors, InStat mode timing, Candle Science target boxes, statistical cutoff rules (09:45 / 10:15), and Pack Trading Cover The Queen brackets. NEVER predicts R1/R2/DNP/DWP as pre-market outcomes (day types are EOD diagnostic classifications only).
license: MIT
applyTo: "**"
---

# Pack Wargaming & Morning Game Plan Skill

Use this skill whenever the user asks for **wargaming**, **pre-market game plan**, **Mickey wargaming**, **morning scenario briefing**, or **Pack Trading wargame**.

## Core Wargaming Philosophy (Mickey & Austin SOP)

1. **Never Predict Day Types (R1/R2/DNP/DWP)**:
   - R1, R2, DNP, and DWP are **End-of-Day (16:00 EST) classifications**. They are diagnostic labels evaluated during post-market reengineering.
   - Pre-market wargaming is exclusively about building **actionable If-Then Scenario Branches (True Continuation vs. False Reversion)** with mechanical execution cutoffs.

2. **The 6 Canonical Briefing Sections**:
   Whenever generating a wargaming briefing, ALWAYS output the complete 6-section structure:
   - **Section 1: Overnight Context & Session Structure**: Asia ($P_{Asia}$), London ($P_{London}$), Broken status, Alignment (Broken-Broken / Goalpost vs Aligned Expansion), P12 Range (18:00–06:00 EST), and P12 Directional Switch vs Midline.
   - **Section 2: Key Anchor Levels & Liquidity Map**: Ascii map of P12 High/Low/Mid, PDH, PDL, PDM, PDC, Midnight Open (00:00), and Globex Open (18:00).
   - **Section 3: Actionable If-Then Scenario Cards**:
     - *Scenario 1 (False Branch / Reversion)*: Conditioned on failure at key level / 0-5 box, targeting P12 Midline (88.1%) and Midnight Open (85.6%). Cutoffs: 09:45 AM P12M retest, 10:15 AM reversal expiration.
     - *Scenario 2 (True Branch / Trend Expansion)*: Conditioned on 10 bps breakout and acceptance, targeting Candle Science MFE levels and extended extremes. Cutoff: 10:15 AM trend lock.
   - **Section 4: Candle Science Excursion Target Boxes**: Upside ($C_1$ Bullish MFE) and Downside ($C_1$ Bearish MAE) P30 / P50 / P70 percentile levels.
   - **Section 5: Pack Trading Execution & Universal Basis Points (bps) Brackets**:
     - Stop Ceiling: Max 12.0 bps.
     - Target 1 ("Cover The Queen"): **+10.0 bps** (50% scale-out + breakeven stop lock $\rightarrow$ zero-risk trade).
     - Target 2 ("Runner"): **+25.0 to +30.0 bps** trailing for HTF targets.
   - **Section 6: Mickey & Austin 4-Step Reversal Counter (Intraday Checklist)**: Step 1 (09:30 Open), Step 2 (09:00 Mid), Step 3 (10:00 Candle Sweep), Step 4 (10:00 Q1 InStat).

## Execution Engine

Run the canonical wargaming generator:
```powershell
python scripts/wargaming/generate_daily_wargame.py --ticker NQ1 --time 06:00
```
Or for a specific date / time:
```powershell
python scripts/wargaming/generate_daily_wargame.py --ticker NQ1 --date YYYY-MM-DD --time 08:30
```

## LLM Transcript Wisdom Infusion

As an LLM trained on the Pack transcripts, always synthesize the quantitative output with Mickey & Austin's verbatim trading philosophy:
- *"Process over outcome, probability over prediction."*
- *"We do not rise to the level of our goals; we fall to the level of our systems."*
- *"Cover the Queen (+10 bps) gets you paid to be wrong."*
- *"Respect the 09:45 and 10:15 statistical cutoff fences — if a high-probability level isn't hit by 09:45, you are in anomaly territory."*
