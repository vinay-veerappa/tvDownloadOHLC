# Fix Spec: Inflection Timing, Neutral Removal & Dashboard Stats

Status: Implemented in code. Use this document as an implementation and validation reference.

## Overview

This feature set consolidates three analytics improvements:

1. Removal of neutral Judas classification
2. Explicit separation of Judas inflection timing vs real-move extreme timing
3. Distribution-chart statistics summaries for quick interpretation

Core runtime docs are now aligned in:

- `scripts/edgeful/MACRO_RESEARCH_PIPELINE_DESIGN.md`
- `scripts/edgeful/SPRINT_3_DASHBOARD_SPEC.md`

---

## Fix 1: Remove Neutral Classification

**File:** `scripts/edgeful/classifiers.py`
**File:** `scripts/edgeful/config.py`

### Problem
The `NEUTRAL_THRESHOLD` (0.1%) is too aggressive. On ES at 7000, any macro where close is within 7 points of the open gets classified as neutral. This incorrectly suppresses legitimate Judas setups.

### Solution
Remove the neutral classification entirely. Every macro is either a Judas (close on opposite side of open from the excursion) or a trend (close on same side, no excursion on the other side). The magnitude fields already capture how strong or weak the move was — a separate "neutral" bucket adds no analytical value. Doji-like macros get filtered out through `macro_range_pct` during analysis.

### Changes

**config.py** — Remove `NEUTRAL_THRESHOLD` constant entirely.

**classifiers.py** — Replace `classify_judas_vectorized` with:

```python
def classify_judas_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """
    ICT Judas classification based on macro open as reference.
    No neutral category — every macro is classified directionally.
    Magnitude fields capture setup strength.
    """
    macro_open = df['open']
    macro_high = df['high']
    macro_low = df['low']
    macro_close = df['close']
    
    has_excursion_above = macro_high > macro_open
    has_excursion_below = macro_low < macro_open
    close_above = macro_close >= macro_open   # ties go to "above"
    close_below = macro_close < macro_open
    
    # Four mutually exclusive classifications, no neutral
    bull_judas = close_below & has_excursion_above
    bear_judas = close_above & has_excursion_below
    trend_up = close_above & ~has_excursion_below
    trend_down = close_below & ~has_excursion_above
    
    # Default is trend_up (covers the exact open==high==low==close edge case)
    classification = pd.Series("trend_up", index=df.index)
    classification = np.where(bull_judas, "bullish_judas", classification)
    classification = np.where(bear_judas, "bearish_judas", classification)
    classification = np.where(trend_up, "trend_up", classification)
    classification = np.where(trend_down, "trend_down", classification)
    
    df['judas_classification'] = classification
    
    df['judas_extreme'] = np.where(
        classification == "bullish_judas", macro_high,
        np.where(classification == "bearish_judas", macro_low, np.nan)
    )
    
    df['judas_magnitude_pct'] = np.where(
        classification == "bullish_judas", 
        (macro_high - macro_open) / macro_open * 100,
        np.where(
            classification == "bearish_judas",
            (macro_open - macro_low) / macro_open * 100,
            0.0
        )
    )
    
    df['real_move_magnitude_pct'] = (macro_close - macro_open).abs() / macro_open * 100
    
    df['judas_to_real_ratio'] = np.where(
        df['real_move_magnitude_pct'] > 0,
        (df['judas_magnitude_pct'] / df['real_move_magnitude_pct']).round(2),
        np.nan
    )
    
    return df
```

### Downstream Impact
- Dashboard filter for `judas_classification` no longer needs a "neutral" option — remove it from the filter panel
- Any place in the codebase that checks `== 'neutral'` or handles neutral as a case needs to be updated
- The `real_direction` derivation in `post_macro.py` currently maps neutral to None — update the fallback: `close >= open` maps to "up", `close < open` maps to "down"

---

## Fix 2: Add Separate Inflection Timing Fields

**File:** `scripts/edgeful/macro_extractor.py`

### Problem
The current fields `high_offset_m` and `low_offset_m` record when the macro high and low occurred, but they don't distinguish which one is the Judas extreme vs. the real move extreme. The dashboard has no way to chart "when does the Judas inflection happen" separately from "when does the real move extreme happen." This causes the inflection timing chart to conflate both, producing misleading clustering at minute 19 (which is where the real move extreme often falls, not the Judas).

### Solution
Add two computed fields AFTER the Judas classification step:

```python
# Add this in macro_extractor.py after classify_judas_vectorized runs

# Judas inflection = when the fake move peaked
# bullish_judas: the Judas extreme is the HIGH → inflection is high_offset_m
# bearish_judas: the Judas extreme is the LOW → inflection is low_offset_m
macro_df['judas_inflection_m'] = np.where(
    macro_df['judas_classification'] == 'bullish_judas', macro_df['high_offset_m'],
    np.where(
        macro_df['judas_classification'] == 'bearish_judas', macro_df['low_offset_m'],
        np.nan
    )
)

# Real move extreme = when the real displacement hit its furthest point
# bullish_judas (real move DOWN): extreme is the LOW → real_move_extreme is low_offset_m
# bearish_judas (real move UP): extreme is the HIGH → real_move_extreme is high_offset_m
macro_df['real_move_extreme_m'] = np.where(
    macro_df['judas_classification'] == 'bullish_judas', macro_df['low_offset_m'],
    np.where(
        macro_df['judas_classification'] == 'bearish_judas', macro_df['high_offset_m'],
        np.nan
    )
)
```

### Add to final_cols
Add `'judas_inflection_m'` and `'real_move_extreme_m'` to the `final_cols` list in macro_extractor.py so they're included in the parquet output.

### Downstream Impact
- `fvg_detector.py` can optionally use `judas_inflection_m` instead of computing it from `high_offset_m`/`low_offset_m` — but the existing logic is equivalent, so no change required
- Dashboard needs new chart options (see Fix 3 below)

---

## Fix 3: Dashboard — Separate Charts + Statistics Panel

**Files:** Dashboard components (DistributionChart, chart configuration, query templates)

### Problem 1: Inflection timing chart mixes Judas and real move extremes
The current "Inflection Timing" chart likely plots `high_offset_m` or `low_offset_m` for all macros without distinguishing which is the Judas extreme vs. the real move extreme.

### Solution: Replace with two separate chart options

**Chart Option A: "Judas Inflection Timing"**
- Source column: `judas_inflection_m`
- Auto-filter: only include rows where `judas_classification IN ('bullish_judas', 'bearish_judas')` (i.e., where `judas_inflection_m IS NOT NULL`)
- X-axis: minutes 0 to 19
- This answers: "When does the fake move peak?"

**Chart Option B: "Real Move Extreme Timing"**
- Source column: `real_move_extreme_m`
- Same auto-filter as above
- X-axis: minutes 0 to 19
- This answers: "When does the real displacement reach its extreme?"

**Chart Option C: "Extreme Spread" (already exists but rename for clarity)**
- Source column: `extreme_spread`
- No auto-filter (applies to all macros)
- This answers: "How many minutes between the high and the low?"

### Problem 2: No summary statistics alongside charts
A histogram alone doesn't answer "what is the typical inflection time." The user needs median, mode, percentiles.

### Solution: Add a StatsSummary component

Create a `StatsSummary` component that appears below (or beside) every distribution chart. It computes and displays:

| Stat | Description | SQL Function |
|------|-------------|-------------|
| N | Sample size | `COUNT(col) WHERE col IS NOT NULL` |
| Mean | Average | `AVG(col)` |
| Median | 50th percentile | `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col)` |
| Mode | Most frequent value | `MODE() WITHIN GROUP (ORDER BY col)` |
| Std Dev | Spread | `STDDEV(col)` |
| P25 | 25th percentile | `PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY col)` |
| P75 | 75th percentile | `PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY col)` |
| IQR | Interquartile range | P75 - P25 |
| Min | Minimum value | `MIN(col)` |
| Max | Maximum value | `MAX(col)` |

**SQL query template for stats:**

```sql
SELECT
    COUNT({column}) as n,
    AVG({column}) as mean,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {column}) as p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY {column}) as median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {column}) as p75,
    MODE() WITHIN GROUP (ORDER BY {column}) as mode,
    STDDEV({column}) as std_dev,
    MIN({column}) as min_val,
    MAX({column}) as max_val
FROM macro_records
WHERE {column} IS NOT NULL
{AND_additional_filter_conditions}
```

**This component is GENERIC** — it works for every distribution chart, not just inflection timing. When the user selects "MFE Distribution," the same stats panel shows MFE statistics. When they select "Macro Range Distribution," it shows range statistics. One component, reusable everywhere.

### Display Format

The stats should be displayed as a compact horizontal row or small card grid below the chart:

```
N: 45,230  |  Median: 8.0  |  Mode: 7  |  Mean: 8.4  |  Std Dev: 3.2  |  P25: 6  |  P75: 11  |  IQR: 5
```

Or as a small 2×5 grid:

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│  N       │  Median  │  Mode    │  Mean    │  Std Dev │
│  45,230  │  8.0     │  7       │  8.4     │  3.2     │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│  Min     │  P25     │  P75     │  IQR     │  Max     │
│  0       │  6       │  11      │  5       │  19      │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

Use the same color coding as sample size elsewhere: N > 100 green, 30-100 yellow, < 30 red.

---

## Fix 4: Update post_macro.py — Remove Neutral Handling

**File:** `scripts/edgeful/post_macro.py`

### Problem
The `real_direction` derivation maps unrecognized classifications to `None`. With neutral removed, this is less of an issue, but the logic should be tightened.

### Solution
Update the real_direction derivation to handle the four remaining classifications cleanly:

```python
res_df['real_direction'] = np.where(
    res_df['judas_classification'].isin(['bullish_judas', 'trend_down']), 'down',
    'up'  # bearish_judas, trend_up, and any edge case
)
```

No more `None` for real_direction. Every macro has a direction. The magnitude fields tell you how meaningful it is.

---

## Execution Order (Historical)

1. Apply Fix 1 (classifiers.py, config.py) — remove neutral
2. Apply Fix 2 (macro_extractor.py) — add judas_inflection_m, real_move_extreme_m
3. Apply Fix 4 (post_macro.py) — remove neutral handling in real_direction
4. Rerun the pipeline for all instruments to regenerate parquet files
5. Apply Fix 3 (dashboard) — add new chart options, stats panel component
6. Verify: load dashboard, check inflection timing chart with stats, confirm no neutral in classification filter

Code implementation for steps 1, 2, 3, and 5 is complete. Step 4 is intentionally user-run.

---

## Validation After Fixes

1. **Classification distribution check:** Run `df['judas_classification'].value_counts()` — should show only four categories: bullish_judas, bearish_judas, trend_up, trend_down. Zero neutral.

2. **Inflection timing sanity check:** Filter to bullish_judas macros in the dashboard, view "Judas Inflection Timing" chart. The distribution should peak somewhere in the 5-12 minute range (hypothesis). If it still clusters at 19, there's a deeper issue with the timestamp computation.

3. **Spot check the January 13, 2026 macro from the screenshot:** Macro_0150 on that date should now classify as bullish_judas (or bearish_judas depending on exact OHLC). It should NOT be neutral.

4. **Stats panel check:** The median and mode for Judas inflection timing should be single-digit numbers (5-12 range expected). If the median is 15+, something is still wrong with the field computation.
