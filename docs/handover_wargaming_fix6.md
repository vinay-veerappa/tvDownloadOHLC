# Wargaming Engine — Session Handover

**Date**: 2026-08-06  
**Commit**: `7ecb79ce` — `feat(wargaming): wire compute_live_prediction + 5 methodology fixes`

---

## What Was Achieved This Session

### Root Cause Found
`pilot_single_day.py` was calling `analyze_daily_classification_bias.py` (a coarse R1/R2/DWP/DNP% CSV lookup) instead of the proper profiler pipeline. The module `scripts/libs_py/profiler/live_prediction.py::compute_live_prediction()` already existed and wires `SessionBoxEngine → compute_profiler() → NQ1_profiler_lookup.json`. It was simply never called from the wargaming script.

### Fixes Implemented & Committed (`7ecb79ce`)

All 5 fixes are in [`scripts/wargaming/pilot_single_day.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/pilot_single_day.py).

#### Fix 1 — Wire `compute_live_prediction()` (lines ~130–175)
- Replaced `analyze_daily_classification_bias` block with `compute_live_prediction()`
- Now gets: `probabilities` (LT/LF/ST/SF %), `hod_lod_times`, `price_stats`, `level_hit_rates_per_outcome` per outcome
- Source: `scripts/libs_py/profiler/live_prediction.py`

#### Fix 2 — InStat: Timing-Based (lines ~177–207)
- Old: checked if 06:00–07:00 bar was within 5 pts of P12H/P12L (wrong concept)
- New: compares overnight HOD/LOD **print time** against per-outcome profiler `hod_mode`/`lod_mode` 15-min bucket windows
- Added `_time_in_bucket(t_str, bucket)` helper
- All 4 outcomes (LT/LF/ST/SF) shown with their expected windows

#### Fix 3 — True/False Scenarios with Cutoff Times (lines ~209–245)
- Old: generic "Scenario A/B/C" with P12 price levels
- New: `false_scenario` / `true_scenario` dicts containing:
  - Outcome name + probability
  - HOD/LOD mode time windows (from profiler)
  - HOD/LOD distance spans (h_span/l_span from price_stats)
  - Cutoff times: mode=`09:30–09:45`, final=`10:15`
  - Key level hit rates: `p12m`, `midnight_open`, `pdh`, `pdl` with mode times

#### Fix 4 — Candle Science Both-Sided P30/P50/P70 (lines ~94–101)
- `cs_read["mfe"]` = upside MFE `{p30, p50, p70}`
- `cs_read["mae"]` = downside depth `{p30, p50, p70}`
- Both now shown in output: `BULL: P30=0.85 / P50=1.28 / P70=1.88 | BEAR: P30=-1.4 / P50=-0.79 / P70=-0.42`

#### Fix 5 — Step 4 Q1 InStat (line ~235)
- Old: `step4 = True` (hardcoded always True)
- New: checks if 10:00 AM Q1 (10:00–10:14) established the hour's HOD or LOD
- Verified: July 28 (known apex day) → `step4=False` ✓

---

## Verified Test Output (July 29, 2026)

```
NY1 Profiler (66 samples): {'SF': 0.394, 'LF': 0.333, 'LT': 0.136, 'ST': 0.136}

InStat HOD/LOD Timing:
  Overnight HOD@06:05 | LOD@08:30
  LT: HOD(06:05) vs mode 18:00-18:15 → out of stat | LOD(08:30) vs mode 05:45-06:00 → out of stat
  LF: HOD(06:05) vs mode 18:00-18:15 → out of stat | LOD(08:30) vs mode 11:30-11:45 → out of stat
  ST: HOD(06:05) vs mode 18:00-18:15 → out of stat | LOD(08:30) vs mode 09:45-10:00 → out of stat
  SF: HOD(06:05) vs mode 18:00-18:15 → out of stat | LOD(08:30) vs mode 09:30-09:45 → out of stat

📋 FALSE SCENARIO (Reversion):
  Outcome: LF (33.3%) | HOD mode: 18:00-18:15 | LOD mode: 11:30-11:45
  HOD dist: 0.0 to 0.1% | LOD dist: -1.6 to -1.5%
  Cutoff: mode=09:30-09:45 | final=10:15
    p12m: 88.1% (mode 09:30) | midnight_open: 85.6% | pdh: 50.8% | pdl: 48.2%

📋 TRUE SCENARIO (Continuation):
  Outcome: SF (39.4%) | HOD mode: 18:00-18:15 | LOD mode: 09:30-09:45
  Cutoff: mode=09:30-09:45 | final=10:15 (if no reversal by 10:15 → True locks)
  CS Targets → BULL: P30=0.85 / P50=1.28 / P70=1.88 | BEAR: P30=-1.4 / P50=-0.79 / P70=-0.42

EOD: Step4 Q1 InStat: True | 4/4 Line Trend
```

---

## What Still Needs To Be Done

### Fix 6 — Rebuild SFT Dataset + LLM Re-evaluation

**Problem**: `build_wargaming_dataset.py` still uses the old field names from before the fixes:
- Line 89: reads `pre.get('profiler_most_likely')`, `pre.get('profiler_n_samples')`, `dt_probs.get('R1%')` etc. — **these keys no longer exist** in the report dict
- Line 90: reads `pre.get('instat_high_locked')` / `pre.get('instat_low_locked')` — **these keys no longer exist**
- Lines 116–118: reads `pre['scenarios']['Scenario A...']` etc. — **old scenarios dict format, now replaced by `false_scenario`/`true_scenario`**
- `SYSTEM_PROMPT` (line 36–44): still describes the old P12-proximity InStat and R1/R2/DWP/DNP framing

**What to do**:

1. **Update `build_wargaming_dataset.py`**:
   - Update `user_input` block (lines 86–97) to use new field names:
     - `pre.get('overnight_context')` (dict of session states)
     - `pre.get('profiler_ny1_probabilities')` (LT/LF/ST/SF %)
     - `pre.get('profiler_ny1_samples')`
     - `pre.get('instat_timing')` (the full multi-line InStat string)
     - `pre.get('instat_per_outcome')` (dict of {outcome: {hod_mode, lod_mode, hod_in_stat, lod_in_stat}})
     - `pre.get('false_scenario')` / `pre.get('true_scenario')` (full dicts)
     - `pre.get('candle_science_target_boxes')` (bull/bear P30/P50/P70)
   - Update `sft_assistant_response` (lines 100–119) to generate a briefing matching Mickey's format:
     - Section 1: Overnight session states + NY1 outcome probabilities
     - Section 2: InStat HOD/LOD per outcome
     - Section 3: False scenario (outcome, prob, HOD/LOD modes, dist, cutoffs, level hits)
     - Section 4: True scenario (same)
     - Section 5: CS target boxes + 4-step counter
   - Update `SYSTEM_PROMPT` (line 36–44) with corrected InStat definition:
     - Old: "P12 early rejection 06:00-07:00: 84.52%..."
     - New: "InStat = HOD/LOD printed within the profiler's expected 15-min mode window for the day's scenario. Compare actual overnight print time vs hod_mode/lod_mode bucket per outcome."
   - Also add EOD fields to `postmortem_user`/`postmortem_assistant`:
     - `eod['4step_score']`
     - `eod['step4_q1_instat']`

2. **Update `evaluate_wargaming_llm.py`**:
   - Add new rule checks for the fields added in Fixes 1–5
   - Check that LLM output references per-outcome HOD/LOD mode times
   - Check that LLM output includes True/False cutoff times
   - Check that InStat is described correctly (timing-based not P12-proximity)

3. **Re-run the dataset builder and re-evaluate**:
   ```powershell
   .\.venv\Scripts\python.exe scripts\wargaming\build_wargaming_dataset.py
   .\.venv\Scripts\python.exe scripts\wargaming\evaluate_wargaming_llm.py
   ```

---

## Key Files

| File | Purpose | Status |
|---|---|---|
| [`scripts/wargaming/pilot_single_day.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/pilot_single_day.py) | Main wargame engine | ✅ Updated |
| [`scripts/wargaming/build_wargaming_dataset.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/build_wargaming_dataset.py) | SFT dataset builder | ❌ Needs update |
| [`scripts/wargaming/evaluate_wargaming_llm.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/wargaming/evaluate_wargaming_llm.py) | LLM benchmark runner | ❌ Needs new rule checks |
| [`scripts/libs_py/profiler/live_prediction.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/profiler/live_prediction.py) | `compute_live_prediction()` — the correct profiler API | ✅ Existing, working |
| [`scripts/trader/signals/profiler.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trader/signals/profiler.py) | `compute_profiler()` — underlying engine | ✅ Existing, working |
| [`data/derived/NQ1_profiler_lookup.json`](file:///c:/Users/vinay/tvDownloadOHLC/data/derived/NQ1_profiler_lookup.json) | Ground truth lookup (hod_lod_times, price_stats, level hits) | ✅ Existing, complete |

---

## Profiler Data Structure Reference

The `NQ1_profiler_lookup.json` key structure that powers everything:

```
tables["NY1"]["ST|T|LF|T"]  (Asia|broken|London|broken overnight key)
  ├── probabilities: {LT: 0.173, LF: 0.297, ST: 0.208, SF: 0.318}
  ├── samples: 283
  ├── hod_lod_times:
  │   ├── LT: {hod_mode: "10:15-10:30", lod_mode: "20:15-20:30"}
  │   ├── LF: {hod_mode: "09:30-09:45", lod_mode: "20:15-20:30"}
  │   ├── ST: {hod_mode: "07:30-07:45", lod_mode: "15:45-16:00"}
  │   └── SF: {hod_mode: "15:45-16:00", lod_mode: "20:00-20:15"}
  ├── price_stats:
  │   ├── LF: {h_med: 0.8, h_mode: 0.8, h_span: "0.8 to 0.9%", l_med: -0.3, l_mode: -0.2, l_span: "-0.2 to -0.1%"}
  │   └── ...per outcome
  └── per_outcome_level_hits:
      └── LF:
          ├── p12m: {hit_rate: 88.1, mode_time: "09:30"}
          ├── midnight_open: {hit_rate: 85.6, mode_time: "09:30"}
          ├── pdh: {hit_rate: 50.8, mode_time: "09:30"}
          └── pdl: {hit_rate: 48.2, mode_time: "09:45"}
```

---

## Known Issue to Investigate

The NY1 profiler shows **identical probabilities across all 3 test dates** (July 28, July 29, Aug 3):
```
NY1 Profiler (66 samples): {'SF': 0.394, 'LF': 0.333, 'LT': 0.136, 'ST': 0.136}
```
All 3 days had the same overnight context: `Asia: Short True | London: Short True`. This is expected behaviour (same context key = same lookup), but should be confirmed: if the `now_et` cutoff passed to `compute_live_prediction()` is correct (08:30 ET), then NY1 is still "pending" and the lookup is conditioned only on Asia+London. This is correct and expected.
