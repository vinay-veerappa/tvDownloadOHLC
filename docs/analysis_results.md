# Options Pipeline Diagnostic & Lineage Report

This diagnostic report details the data lineage and architectural causes of the four contradictions observed within the dealer-levels and regime-monitor pipelines.

---

## 1. Zero Gamma Contradiction (7581.22 vs. 7598.93)

### Lineage Mapping

#### A. Header Block + Execution Plan Value (7581.22)
*   **Source Function & Call Site:** 
    *   **Header:** `_build_embed` in [discord_notifier.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/discord_notifier.py#L369) reads `levels.zero_gamma`.
    *   **Execution Plan:** `build_plan` in [formatting.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/formatting.py#L284) reads `levels.zero_gamma`.
*   **Full Call Chain:**
    1.  `run_options_levels.py` calls `calculate_dealer_levels` in [gex_calculator.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/gex_calculator.py#L1251) to get `levels_intraday: DealerLevels` (raw cash ZG = `7598.93`).
    2.  `run_options_levels.py` calls `translate_to_futures` in [futures_translator.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/futures_translator.py#L115).
    3.  `translate_to_futures` shifts the cash level using `_shift(levels.zero_gamma)` which adds the `basis_spread` ($-17.71$), returning `TranslatedLevels.zero_gamma` = `7581.22`.
    4.  `run_options_levels.py` passes `TranslatedLevels` into `send_discord_update` -> `_build_embed`.

#### B. Transitions & Inflections Section Value (7598.93)
*   **Source Function & Call Site:** `_build_scored_fields` in [discord_notifier.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/discord_notifier.py#L291) reads `l.strike` from `scored.tagged_levels`.
*   **Full Call Chain:**
    1.  `run_options_levels.py` calls `score_levels` in [level_scorer.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/level_scorer.py#L511) passing raw, untranslated `levels_intraday` (cash ZG = `7598.93`).
    2.  `score_levels` calls `_find_inflection_points` which appends an `InflectionPoint` to `ScoredLevels.tagged_levels` using the raw strike value `levels.zero_gamma` (`7598.93`).
    3.  `run_options_levels.py` passes `scored_intraday: ScoredLevels` into `send_discord_update`.
    4.  `_build_embed` calls `_build_scored_fields(scored)` and outputs the strike (`7598.93`) directly.

### Inputs Consumed
*   **Underlying Ticker:** SPX options chain (cash).
*   **IV Value/Surface:** ATM implied volatility of the front contract (Schwab API).
*   **Expiry/DTE Scope:** Intraday chain ($\le 13$ DTE).
*   **Spot Price Reference:** Cash SPX Spot (~`7600`).
*   **Snapshot Timestamp:** Fresh real-time options fetch.

### Basis Handling
*   **Basis Spread:** $-17.71$ (derived as `/ES` futures price minus SPX cash spot price).
*   **Application:** In `translate_to_futures`, the basis is added to cash-space levels: `round(levels.zero_gamma + spread, 2)`.
*   **Why they differ:** The header and plan display translated futures-space strikes (shifted by basis), while the Three-Filter transitions section prints the raw cash strikes from `ScoredLevels` because the scorer is executed on the untranslated cash-space object (`levels_intraday`) and the output card renders those scored strikes without shifting them by the basis spread.

### Classification
**(c) basis/units misapplied in one path** (scored levels printed in cash space rather than translated futures space).

### Hypothesis for Root Cause
The Three-Filter Scorer runs exclusively on untranslated cash-space objects, and the Discord card builder renders these scored strikes directly without passing them through the futures translation helper.

---

## 2. Expected Move Band Contradiction (±20.83 vs. ±35.00)

### Lineage Mapping

#### A. Footer Block (EM ±20.83) + Plan Risk Band (7571.24 ↔ 7612.90)
*   **Source Function & Call Site:** `calculate_dealer_levels` in [gex_calculator.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/gex_calculator.py#L1274) calls `_expected_move`.
*   **Full Call Chain:**
    1.  `calculate_dealer_levels` calls `_expected_move(chain.calls, chain.puts, spot, chain.chain_volatility)`.
    2.  `_expected_move` receives `chain.chain_volatility` (e.g. `0.15` decimal) in its `dte` parameter.
    3.  `_expected_move` computes `t_eff_yr = (0.637 * 0.15 + 0.24) / 365.0 = 0.000919` years (equivalent to $\sim 0.33$ days).
    4.  `_expected_move` returns `em_value = 20.83`.
    5.  `run_options_levels.py` runs `translate_to_futures` which copies `em_value` as `20.83` (printed in the footer as `EM ±20.83` and in `build_plan` risk band as `7592.07 - 20.83 ↔ 7592.07 + 20.83`, or `7571.24 ↔ 7612.90`).

#### B. Header Block (EM HI 7626.99 / EM LO 7557.15)
*   **Source Function & Call Site:** `_build_embed` in [discord_notifier.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/discord_notifier.py#L370) reads `front_em.em_upper` and `front_em.em_lower`.
*   **Full Call Chain:**
    1.  `calculate_dealer_levels` calls `_calculate_all_ems` in [gex_calculator.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/gex_calculator.py#L1354).
    2.  `_calculate_all_ems` computes the DTE for the nearest expiration: `dte = (expiry - now_ny.date()).days` (e.g., `1` day).
    3.  `_calculate_all_ems` calls `_expected_move(calls, puts, spot, dte=dte, is_futures=is_futures)`.
    4.  `_expected_move` correctly receives `dte = 1`.
    5.  `_expected_move` computes `t_eff_yr = (0.637 * 1.0 + 0.24) / 365 = 0.00240` years.
    6.  It returns `move ≈ 34.92` (±~35pt).
    7.  `_build_embed` extracts the first item from `levels.expected_moves` as `front_em` and renders `em_upper` and `em_lower`.

### Inputs Consumed
*   **Underlying Ticker:** SPX options chain (cash).
*   **IV Value/Surface:** ATM implied volatility of the front contract.
*   **Expiry/DTE Scope:** The front contract (1 DTE).
*   **Spot Price Reference:** SPX Spot (~`7600`).

### Basis Handling
*   Both values are shifted appropriately by the basis spread downstream in `translate_to_futures` and `_translate_weekly_scope_record`. The difference in value is strictly due to the parameter mismatch.

### Horizon/Sigma Definition
*   **TOS Expected Move Formula:** $\text{Spot} \times \text{Blended IV} \times \sqrt{\frac{0.637 \times \text{DTE} + \text{intercept}}{365}}$
*   **Footer/Plan:** Understates the horizon because it passes fractional chain volatility (`0.15`) instead of calendar `DTE` (`1`), effectively scaling the time horizon down to $\sim 0.33$ days.
*   **Header:** Scaled correctly to `1` calendar DTE.

### Classification
**(c) basis/units misapplied in one path** (chain volatility passed to DTE parameter).

### Hypothesis for Root Cause
In `gex_calculator.py`, `calculate_dealer_levels` incorrectly passes `chain.chain_volatility` to the `dte` parameter of `_expected_move`, treating implied volatility as the number of days to expiration.

---

## 3. Straddle vs. EM Contradiction (30.65 vs. ±35.00)

### Lineage Mapping

#### A. Header Straddle Value (30.65)
*   **Source Function & Call Site:** `_atm_straddle_cost` in [gex_calculator.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/gex_calculator.py#L740) sums the mark price of ATM call and put options.
*   **Full Call Chain:**
    1.  `calculate_dealer_levels` -> `_expected_move` -> `_atm_straddle_cost`.
    2.  `_atm_straddle_cost` finds the nearest ATM Call and ATM Put contract in the front expiry.
    3.  Returns `atm_call.mark + atm_put.mark` = `30.65`.

#### B. Header EM Band Width (±35.00)
*   **Source Function & Call Site:** `_expected_move` in [gex_calculator.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/gex_calculator.py#L778).
*   **Full Call Chain:**
    1.  `calculate_dealer_levels` -> `_calculate_all_ems` -> `_expected_move`.
    2.  Returns the TOS expected move formula output: `tos_expected_move = spot * blended_iv * math.sqrt(t_eff_yr)` = `34.92` (±~35pt).

### Inputs Consumed
*   **Straddle Cost:** Bid/Ask mid-marks of SPX ATM Call and Put options.
*   **TOS Expected Move:** Blended implied volatility of SPX ATM Call and Put, calendar DTE, spot price.

### Classification
**(b) correct values mislabeled as the same thing** (market-priced ATM straddle cost vs. time-scaled model expected move).

### Hypothesis for Root Cause
The card displays two different indicators of expected volatility: the actual market mid-price of the front ATM straddle ($30.65$) alongside a standardized model-derived TOS expected move ($34.92$), which use different calculations and pricing assumptions.

---

## 4. IV Discrepancy Contradiction (9.4% vs. ~18%)

### Lineage Mapping

#### A. Briefing Value (9.4%)
*   **Source Function & Call Site:** `calculate_dealer_levels` in [gex_calculator.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/streaming/options/gex_calculator.py#L1463) reads `_atm_contract(chain.calls, spot).iv`.
*   **Full Call Chain:**
    1.  `run_options_levels.py` fetches the option chain filtered to `DTE_TARGETS` ($\le 13$ days).
    2.  `calculate_dealer_levels` identifies the nearest ATM call contract (which is 0DTE/1DTE) and reads its implied volatility (`9.4%`).
    3.  Printed in `build_coaches_note` (Volatility Dash).

#### B. Regime-Monitor Value (~18%)
*   **Source Function & Call Site:** `get_iv_snapshot` in [iv_service.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/strategy_engine/services/iv_service.py#L127).
*   **Full Call Chain:**
    1.  `IvService.get_iv_snapshot` queries the historical daily close table `volatility_history` via Dolt SQL, returning `iv_current` for SPY/SPX (~`18.0%`).
    2.  Alternatively, the monitor tracks the $VIX index directly (which represents a standardized 30-day implied volatility of SPX options, sitting at ~`18.0%`).

### Inputs Consumed
*   **Briefing IV:** Real-time implied volatility of the immediate 0DTE/1DTE SPX option.
*   **Monitor IV:** Standard 30-day options implied volatility or VIX index.

### Timestamp & Caching
*   **Briefing IV:** Calculated in real-time on the live options chain snapshot.
*   **Monitor IV:** Fetched from cached DB tables, Dolt daily close history, or the VIX spot price index.

### Classification
**(b) correct values mislabeled as the same thing** (ultra-short-term 0DTE/1DTE option implied volatility vs. standardized 30-day index volatility / VIX).

### Hypothesis for Root Cause
The briefing dashboard displays the immediate near-term contract ATM IV (0DTE/1DTE, which is $9.4\%$), whereas the regime-monitor tracks VIX/30-day standardized implied volatility (which is $18\%$) under the generic label "IV".

---

## 5. Structural & Architectural Findings

### Logic Replication vs. Downstream Transformations
*   **Zero Gamma:** This is a transformation mismatch. The same source data is used, but the `ScoredLevels` object bypasses the futures translation pipeline entirely and is rendered in raw cash-index units.
*   **Expected Move:** This is duplicated calculation logic with parameter drift. `_expected_move` is called in two separate places in `gex_calculator.py`: one inside the main levels pipeline (with the buggy parameter) and one inside the multi-expiry calculator (with the correct parameter).

### Sources of Truth for Spot, IV, Basis, and Expiry Scope
There is no unified single source of truth for these metrics. They are fetched or derived independently across multiple files:

| Metric | Independent Fetch / Derivation Sites |
| :--- | :--- |
| **Spot Price** | <ul><li>Option chain metadata fetched via `Schwab API` in `run_options_levels.py`</li><li>Fallback Yahoo Finance (`yfinance`) fetched in `macro_pipeline.py`</li><li>Prisma DB queries in `regime_service.py` (`spotPrice` from `GexSnapshot`/`MacroSnapshot`)</li></ul> |
| **Implied Volatility (IV)** | <ul><li>Schwab option contract details (`OptionContract.iv`) parsed in `gex_calculator.py`</li><li>ATM contract selection `_atm_contract().iv` in `gex_calculator.py`</li><li>Dolt database `volatility_history` table in `iv_service.py`</li><li>Prisma DB `GexSnapshot` table (`put25dIv` and `call25dIv` average) in `iv_service.py`</li><li>VIX index spot price via Yahoo Finance in `config.py`</li></ul> |
| **Basis Spread** | <ul><li>Dynamic calculation `futures.price - levels.spot` in `futures_translator.py`</li><li>Market-open anchors file `BASIS_ANCHORS_JSON` loaded in `run_options_levels.py`</li><li>Completely ignored/unapplied in `level_scorer.py` / `ScoredLevels`</li></ul> |
| **Expiry Scope (DTE)** | <ul><li>`DTE_TARGETS` (0-13 DTE) in `config.py` (Intraday pipeline constraint)</li><li>`MACRO_DTE_TARGETS` (up to 365 days) in `config.py` (Macro pipeline constraint)</li><li>`wall_dte_range` default `(0, 14)` DTE hardcoded in `gex_calculator.py`</li></ul> |
