# Mickey & Austin Master Tool Inventory & Infrastructure Blueprint

> **Source**: NotebookLM Query on *Pack Oct Bootcamp*, *Pack Live Wargaming YouTube*, & *Pack Trading Reengineering Q2 2026*
> **Purpose**: Master baseline inventory documenting all trading tools, TradingView indicators, statistical models, key levels, and execution checklists used by Matt Mickey and Austin.

---

## 1. Core Tool & Indicator Inventory

| Component | Mickey & Austin Tool | Description / Logic | Current Status in Repo | Action Plan / Priority |
| :--- | :--- | :--- | :--- | :--- |
| **Position Sizing** | **Dump Pouch Indicator** (`OuURs2Gl-Dump-Pouch`) | Dynamic contract sizing based on SL distance to honor fixed dollar risk ($100-$1000 per trade). | ⚠️ Manual math | Build Python module & Pine v6 indicator |
| **Daily Profiler** | **Daily Profiler v2.2** | Projects session O/U midlines, P12 boundaries (18:00-06:00), 10-day median range, 3-hour price cloud. | ✅ `daily_profiler_wargaming.md` | Build Python feature extractor `profiler_feature_extractor.py` |
| **Candle Probabilities**| **Candle Science Platform** (`candle.kopping.se`) | Calculates C1 $\rightarrow$ C2 $\rightarrow$ C3 OHLC continuation/reversal probabilities, C2 Open line in the sand, MFE/MAE percentiles. | ✅ `scripts/trader/signals/candle_science.py` | Wire into `morning_wargamer.py` and `eod_reengineer.py` |
| **HTF EMA Analysis** | **Weekly EMA(5) Excursion** (`random HF` / `Mickey1984`) | Percentage distance excursions from prior completed Weekly EMA(5), 52-week Mean/Median/Mode, 2%-3% magnet zones. | ✅ Spec in `docs/features/htf-ema-analysis/` | Build `scripts/wargaming/htf_ema_analysis.py` |
| **Range & Session Targets**| **T&P Ranges V2 Pro** (JerryG) | High-timeframe session projections, target zones, and percentiles. | ⚠️ Partial in `session_ranges.py` | Enhance session range engine |
| **Swing Structure** | **Cody's Valid Highs/Lows** | Objectively tracks wicks and bodies to mark valid swing pivots and project MFE 50 and MFE 80 target zones. | ❌ Not built | Flagged for Phase 3 expansion |
| **0-5 Box Momentum** | **0-5 Box Strategy Tester** | Tracks first 5m range of hourly candles with 10 bps threshold for RTH momentum confirmation. | ✅ `daily_profiler_wargaming.md` | Implement 10 bps threshold filter in profiler extractor |
| **Monte Carlo Cloud** | **Monte Carlo Price Cloud** | 25,000 historical intraday 5m price patterns condensed into mean & std-dev price cloud boundaries. | ❌ Not built | Flagged for future enhancement |
| **Backtest Testers** | **Captain Backtest (CPT BTS)** & **Reverse Breakout** | Pre-coded strategy testers for reverse breakout, 0-5 box breakout, and CPT BTS models. | ✅ `scripts/trading_framework/core/backtest_engine.py` | Connect to Wargaming backtest loop |

---

## 2. Key Reference Levels & Anchors

1. **P12 Levels (18:00 – 06:00 ET)**: P12 High, Low, and **P12 Midline**. Midline holding indicates bullish expansion to P12 High; accepting below targets P12 Low. Rejection between 06:00–07:00 locks in daily extreme.
2. **Session Over/Under (O/U) Lines**: 50% midpoints of fixed session constants (Asia O/U, London O/U, NY1 O/U, NY2 O/U).
3. **Time-Based Anchors**: Globex Open (18:00 ET), Midnight Open (00:00 ET), Settlement Price, Previous Day High/Low/Mid (PDH/PDL/PDM).
4. **The 0-5 Box**: High-to-low range of the first 5 minutes of an hourly candle. 10 basis points breach confirms RTH momentum; failure to reach threshold flags instant high/low reversal.
5. **C2 Open Price**: The ultimate "line in the sand" for Candle Science. Holding above supports bullish continuation; breaching shifts probabilities to taking out C2 Low.
6. **Weekly & Monthly Anchors**: Sunday 18:00–19:30 box, Tuesday 09:30–10:30 box, Previous Month 50%, and NFP Friday Close.

---

## 3. Execution & Wargaming Checklists

### A. Morning Wargaming SOP (08:30 – 09:30 AM EST)
1. **Input session variables**: Classify Asia and London profiles ($P_{session}$ = LT, ST, LF, SF).
2. **Plot session O/U midlines**: Asia O/U and London O/U.
3. **Identify HOD/LOD projections**: Mode-to-Median price zones and time windows.
4. **Overlay 3-hour price cloud**: Visualize expected hourly flow (09:00, 10:00, 11:00).
5. **Check DROs & 10-day range**: Evaluate whether volatility is cheap or expensive.
6. **Evaluate P12 level interactions**: Monitor 06:00–08:30 price action relative to P12 Mid.
7. **Formulate "If-Then" Scenarios**: Build Scenario A (Primary), Scenario B (Alternative/Goalpost), and Scenario C (Invalidation/R1 chop).

### B. The 4-Step Reversal Counter (Trend vs. Reversal Filter)
- **Step 1**: Does price breach & accept past 09:30 RTH open range?
- **Step 2**: Does price accept past 09:00 hour 50% midpoint line?
- **Step 3**: Does the 10:00 AM candle take out the 09:00 AM high or low?
- **Step 4**: Does the 10:00 AM candle establish an Instant High/Low in Q1 (first 15m)?
- *Rule*: All 4 steps met = Major Reversal confirmed. 0 steps met = Trend Continuation locked in.

### C. 9:45 AM Reversal Rules Checklist
1. Is LOD/HOD as per Daily Profiler in (after 9:30)?
2. Is daily profile verified as *Long False* or *Short False*?
3. Is price trading opposite to 09:00 50% midpoint and 09:30 box?
4. Is price netting off a key level (P12, O/U, PDH/PDL)?
5. Enter on 09:30 breakout/rejection with TP targets at 10 bps ("Cover the Queen") and 50% DRO.

### D. End-of-Session Re-Engineering SOP (16:00 PM EST)
1. **Classify the day**: Range 1 (R1), Directional No Pullback (DNP), Directional With Pullback (DWP), Range 2 (R2).
2. **Review session & P12 metrics**: Audit P12 High/Mid/Low and session O/U level hits.
3. **Deconstruct hourlies & quarters**: Check 0-5 box 10 bps breakouts and 3-hour line vs. apex reversals.
4. **Verify reversal & daily extremes**: Confirm exact HOD/LOD lock-in time and 4-step counter completion.
5. **Check performance & edge metrics**: Audit trade execution against model SOPs (EV, Profit Factor, Max DD).
6. **Identify invalidation points & adjust levers**: MFE/MAE evaluation.
7. **Acknowledge mistakes & reset the edge**: Document emotional friction and prepare for next session.

---
*Document Location: `docs/profiler/mickey_austin_tool_inventory.md`*
