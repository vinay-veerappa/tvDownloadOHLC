# CRITICAL SYSTEM AUDIT: Wargaming & EOD Reengineering Architecture

**To:** System Architecture Team
**From:** Quantitative Trading System Architect
**Date:** 2026-08-05
**Subject:** Unsparing Critical Review of Master Implementation Plan & Domain Blueprints

I have conducted a rigorous stress test of your Master Implementation Plan, Tool Inventory, and Domain Blueprints. While the **Validation-First (Phase 0)** approach is statistically sound and the **Ticker-Agnostic** ambition is necessary for scale, there are critical structural weaknesses in your statistical assumptions, edge-case handling, and multi-asset scalability that will cause live deployment failure if not addressed immediately.

Below is the unsparing audit.

---

## 1. Gaps & Blind Spots: Statistical Assumptions & Edge Cases

Your blueprints rely heavily on "Mickey's Rules" as absolute truths. In quantitative systems, rules must be probabilistic regimes, not binary switches.

*   **The "Gap Day" Blind Spot (Candle Science):**
    *   **Issue:** The *Candle Science Blueprint* defines the **$C_2$ Open** as the "Line in the Sand." It fails to account for **Overnight Gaps**. If $C_2$ opens > 1 ATR away from $C_1$ Close, the structural integrity of the $C_2$ Open as a pivot diminishes. The market often seeks to fill the gap before respecting the $C_2$ Open.
    *   **Risk:** On high-impact news days, your system will signal "Bullish Continuation" based on $C_2$ Open holding, while price is actually mean-reverting to fill a gap.
    *   **Fix:** Add a **Gap Normalization Factor**. If $|C_2 Open - C_1 Close| > 0.5 \times ATR(14)$, degrade the confidence score of the $C_2$ Open signal by 50% or switch to "Gap Fill" logic.

*   **The Binary Reversal Fallacy (Line vs Apex):**
    *   **Issue:** The *Line vs Apex Blueprint* treats the **4-Step Reversal Counter** as binary (0 steps = Trend, 4 steps = Reversal). Markets are analog. What about 2/4 or 3/4 steps?
    *   **Risk:** A 3/4 step completion often indicates a **Pullback Entry** in the direction of the trend, not a reversal. Treating this as neutral or reversal will cause you to fade strong trends.
    *   **Fix:** Implement a **Weighted Step Score**. 1 Step = 0.25, 4 Steps = 1.0. Map scores 0.0–0.5 to "Trend Continuation," 0.5–0.75 to "Chop/Pullback," and 0.75–1.0 to "Reversal."

*   **NFP Holiday Shifts:**
    *   **Issue:** Your NFP logic (`dayofweek == Friday` & `dayofmonth <= 7`) is brittle. When the 1st falls on a weekend or holiday, NFP shifts.
    *   **Risk:** False positives on non-NFP Fridays will trigger incorrect "Macro Anomaly" flags, skewing your HTF EMA excursion data.
    *   **Fix:** Ingest a **US Economic Calendar JSON** for exact NFP timestamps rather than algorithmic date guessing.

*   **Weekly EMA Close Time Mismatch:**
    *   **Issue:** The *HTF EMA Blueprint* assumes a standard Weekly Close. **CL (Crude)** and **GC (Gold)** settle differently than **NQ/ES**. CL often settles Friday 14:30 CT; NQ settles Friday 16:00 ET (or Sunday 17:00 depending on data feed).
    *   **Risk:** Your 52-week lookback will calculate excursions off the wrong anchor price for commodities, invalidating the 2%-3% magnet zones.
    *   **Fix:** The `ticker_registry.json` must include `weekly_settlement_offset_minutes` to align EMA calculations per asset class.

---

## 2. Backtesting & Verification Integrity: Phase 0 Framework

Your **Phase 0 Validation-First** approach is excellent for unit testing but insufficient for **Integration Risk**.

*   **Isolation vs. Confluence:**
    *   **Critique:** You are validating Candle Science, HTF EMA, and Line vs Apex in isolation (`v_02`, `v_03`, `v_04`). You are **not** validating what happens when they **contradict**.
    *   **Risk:** What if Candle Science says "Bullish Continuation" ($C_2$ Open hold) but HTF EMA says "Overextended +2.8%" (Mean Reversion)? Your current plan has no logic to resolve this conflict.
    *   **Requirement:** Add **Phase 0.7: Signal Confluence Stress Test**. Run historical dates where signals conflicted and verify which signal dominated price action.

*   **Continuous Contract Splice Artifacts:**
    *   **Critique:** You are testing on `NQ1`/`ES1`. If these are continuous futures, roll dates create artificial gaps.
    *   **Risk:** A roll gap might trigger a false "C2 Open Breach" or distort the "0-5 Box" calculation.
    *   **Requirement:** Your validation scripts must flag **Roll Dates** and exclude them from Phase 0 validation or use **Back-Adjusted** data only.

*   **Lookahead Bias in "Daily" Metrics:**
    *   **Critique:** In `v_05_profiler_features.py`, ensure you are not using the **Daily Close** to calculate intraday levels (like P12 Mid) during the session.
    *   **Requirement:** Explicitly assert in code comments and tests that all levels available at 09:30 AM must be calculated using data **prior to 09:30 AM** only.

---

## 3. Multi-Ticker Scalability: The "10 bps" Trap

Your plan claims **Ticker-Agnostic** architecture, but your thresholds are **Index-Centric**.

*   **The 10 Basis Point (0.10%) Fallacy:**
    *   **Critique:** 10 bps on NQ (~24 points) is a standard scalp. 10 bps on CL (Crude @ $70 = $0.07) is **7 ticks**. CL noise often exceeds 7 ticks in seconds. 10 bps on GC (Gold @ $2000 = $2.00) is manageable but volatility profiles differ.
    *   **Risk:** Applying a static 10 bps threshold across assets will result in **100% stop-outs on CL** due to noise and **missed fills on GC** due to wider spreads.
    *   **Fix:** The `ticker_registry.json` must define `momentum_threshold_ticks` OR `atr_multiple` instead of static basis points.
        *   *NQ:* 24 points (approx 10 bps)
        *   *CL:* 15 cents (approx 20 bps volatility adjusted)
        *   *GC:* $2.50 (approx 12 bps)
    *   **Action:** Replace "10 bps" hardcoding with `config.min_momentum_move` loaded per ticker.

*   **Session Hour Fragility:**
    *   **Critique:** Your Line vs Apex blueprint assumes 09:30–16:00 EST. **CL** trading halts briefly daily; **GC** has different liquid hours.
    *   **Risk:** The "09:44 AM Exit" rule might coincide with a liquidity drought in Commodities, causing slippage that destroys the "Cover the Queen" edge.
    *   **Fix:** Add `liquidity_quality_score` to the ticker registry. If score is low (Commodities), widen TP1 targets or switch to limit orders only.

---

## 4. Execution Playbook & Risk Alignment

Mickey's execution rules are heuristic. Your system must be algorithmic.

*   **Static TP vs. Dynamic Volatility:**
    *   **Critique:** **TP1 (Cover the Queen)** is fixed at 10 bps. On an **R1 (Range 1)** day, the total daily range might only be 15 bps. Taking 10 bps leaves nothing for the runner. On a **DNP (Directional No Pullback)** day, 10 bps is reached in 2 minutes, and price runs 100 bps.
    *   **Risk:** You are capping upside on trend days and exposing runners on chop days.
    *   **Fix:** Make TP1 dynamic: `Max(10 bps, 0.25 \times ATR(Daily))`.
    *   **Fix:** Make TP3 (09:44 Exit) conditional. If `Line Score > 0.8`, switch TP3 to **Trailing Stop (2 ATR)** instead of hard time exit.

*   **Position Sizing (Dump Pouch) Implementation:**
    *   **Critique:** The Tool Inventory lists "Dump Pouch" as ⚠️ Manual Math. This is a single point of failure.
    *   **Risk:** In a live automated system, manual sizing leads to fat-finger errors or hesitation.
    *   **Fix:** Phase 0.5 **Must** include a `risk_engine.py` that calculates contract size based on `Account_Equity * Risk_% / (Stop_Distance * Tick_Value)`. This must be validated in Phase 0.

*   **The 09:44 AM Exit Rigidity:**
    *   **Critique:** Why 09:44? This is likely based on NQ liquidity patterns.
    *   **Risk:** ES often pivots at 09:55. CL pivots at 10:00.
    *   **Fix:** Parameterize the "Morning Pivot Exit" in the ticker registry (`morning_pivot_offset_minutes`).

---

## 5. Concrete Actionable Recommendations (Phase 0.4 & 0.5)

Do not proceed to Phase 1 (Knowledge Mining) until these specific enhancements are integrated into Phase 0.

### For Phase 0.4 (Line vs Apex & 0-5 Box)
1.  **Add "Partial Step" Logic:** Update `v_04_line_vs_apex_pa.py` to record not just Pass/Fail, but **Step Count (0-4)**. Correlate Step Count with subsequent 1-hour price direction to verify if 2/3 steps indicates continuation rather than neutral.
2.  **Volatility-Normalized 0-5 Box:** Replace the static "10 bps" check in the validator with a **Ticker-Specific Threshold** loaded from `ticker_registry.json`.
    *   *Action:* Add `momentum_threshold_units` to registry.
3.  **Gap Filter:** Add a check in the validator: If `Open - PrevClose > Threshold`, flag the day as "Gap Regime" and exclude from standard Line/Apex scoring until proven otherwise.

### For Phase 0.5 (Profiler Feature Extractor)
1.  **Implement Risk Engine Unit Test:** Create `v_05_risk_engine.py`.
    *   *Input:* Account Size, Risk %, Stop Distance, Ticker Tick Value.
    *   *Output:* Contract Count.
    *   *Verification:* Compare against manual "Dump Pouch" calculations for 5 historical trades.
2.  **Signal Conflict Matrix:** Add a output to the Profiler Extractor that flags **Signal Contradictions**.
    *   *Example:* `HTF_Excursion > 2.5%` (Bearish) AND `Candle_Science = Bullish`.
    *   *Goal:* Quantify the win-rate of "Conflicted Days" vs. "Aligned Days."
3.  **Roll Date Handling:** Ensure the Profiler Extractor detects Futures Roll Dates (using volume/open interest crossover or registry dates) and **excludes** them from statistical averages (P12, DRO) to prevent splice data from corrupting levels.

### Immediate Code Change Request
**File:** `scripts/config/ticker_registry.json`
**Action:** Expand schema immediately to prevent hardcoding later.
```json
{
  "NQ1": {
    "tick_size": 0.25,
    "tick_value": 5.0,
    "momentum_threshold_points": 24,
    "weekly_settlement_hour": 16,
    "morning_pivot_exit_minute": 44
  },
  "CL1": {
    "tick_size": 0.01,
    "tick_value": 10.0,
    "momentum_threshold_points": 15,
    "weekly_settlement_hour": 14,
    "morning_pivot_exit_minute": 55
  }
}
```

---

**Final Verdict:**
The architecture is **85% sound** but the remaining **15% (Asset Specific Nuances & Signal Conflict Logic)** represents **100% of the live trading risk**. Do not scale to batch backtesting (Phase 5) until Phase 0.4 and 0.5 incorporate the volatility normalization and conflict matrix recommendations above.

**Proceed with Phase 0.4 only after updating the Ticker Registry and adding the "Partial Step" logic.**