# Fix Spec: Mid Retest Entry Analytics

## Overview

When price retests the macro mid (50% of the macro range) after the macro completes, that retest is a potential entry point for Strategy 2. We need to measure what happens AFTER the retest — how far does price move favorably (MFE) and adversely (MAE) from that specific entry point. This is the data needed to define stop and target placement for the macro mid entry strategy.

---

## Fix 1: Compute Mid Retest MFE/MAE in post_macro.py

**File:** `scripts/edgeful/post_macro.py`

### What Exists Currently

The `mid_retests` CTE already detects whether the mid was retested and when:
- `post_macro_retested_mid` — boolean
- `first_mid_retest_time` — timestamp of first retest bar
- `mid_retest_time_m` — minutes after macro end when retest occurred

### What Needs to Be Added

After detecting the retest, compute what happened from the retest bar forward to the lookforward end.

**Add a new CTE after the existing `mid_retests` CTE:**

```sql
CREATE TEMP TABLE mid_retest_outcomes AS
WITH retest_info AS (
    SELECT 
        macro_id,
        first_mid_retest_time,
        macro_mid
    FROM mid_retests
    CROSS JOIN (
        SELECT macro_id as mid, (high + low) / 2 as macro_mid 
        FROM macros
    ) mm
    WHERE mid_retests.macro_id = mm.mid
    AND post_macro_retested_mid = TRUE
)
-- Actually, simpler approach: join mid_retests back to macros to get the mid and lookforward_end

-- Corrected approach:
WITH retest_context AS (
    SELECT 
        r.macro_id,
        r.first_mid_retest_time,
        m.lookforward_end,
        m.open as macro_open,
        (m.high + m.low) / 2 as macro_mid,
        m.judas_classification
    FROM mid_retests r
    JOIN macros m ON r.macro_id = m.macro_id
    WHERE r.post_macro_retested_mid = TRUE
),
post_retest_bars AS (
    SELECT 
        rc.macro_id,
        rc.macro_open,
        rc.macro_mid,
        rc.judas_classification,
        b.high as bar_h,
        b.low as bar_l,
        b.close as bar_c,
        b.bar_time
    FROM retest_context rc
    JOIN bars b ON b.bar_time >= rc.first_mid_retest_time 
               AND b.bar_time <= rc.lookforward_end
)
SELECT 
    macro_id,
    MAX(bar_h) as post_retest_high,
    MIN(bar_l) as post_retest_low,
    LAST(bar_c ORDER BY bar_time) as post_retest_close,
    COUNT(*) as post_retest_bars
FROM post_retest_bars
GROUP BY macro_id
```

**Then in the Pandas section, compute the directional MFE/MAE:**

```python
# Merge the retest outcomes
res_df = res_df.merge(retest_outcomes, on='macro_id', how='left')

# Compute macro_mid for reference
macro_mid = (res_df['high'] + res_df['low']) / 2

# MFE from mid retest entry (favorable move in the real direction)
# Entry price is the macro_mid
# bullish_judas / trend_down → real direction DOWN → favorable = mid - post_retest_low
# bearish_judas / trend_up → real direction UP → favorable = post_retest_high - mid
res_df['mid_retest_mfe_pct'] = np.where(
    res_df['real_direction'] == 'down',
    (macro_mid - res_df['post_retest_low']) / res_df['open'] * 100,
    np.where(
        res_df['real_direction'] == 'up',
        (res_df['post_retest_high'] - macro_mid) / res_df['open'] * 100,
        np.nan
    )
).clip(min=0)

# MAE from mid retest entry (adverse move against the real direction)
# bullish_judas / trend_down → real direction DOWN → adverse = post_retest_high - mid
# bearish_judas / trend_up → real direction UP → adverse = mid - post_retest_low
res_df['mid_retest_mae_pct'] = np.where(
    res_df['real_direction'] == 'down',
    (res_df['post_retest_high'] - macro_mid) / res_df['open'] * 100,
    np.where(
        res_df['real_direction'] == 'up',
        (macro_mid - res_df['post_retest_low']) / res_df['open'] * 100,
        np.nan
    )
).clip(min=0)

# Net result from mid entry
res_df['mid_retest_net_pct'] = np.where(
    res_df['real_direction'] == 'down',
    (macro_mid - res_df['post_retest_close']) / res_df['open'] * 100,
    np.where(
        res_df['real_direction'] == 'up',
        (res_df['post_retest_close'] - macro_mid) / res_df['open'] * 100,
        np.nan
    )
)

# Win rate helper: did the trade close in profit?
res_df['mid_retest_win'] = res_df['mid_retest_net_pct'] > 0

# R:R ratio from mid entry
res_df['mid_retest_rr'] = np.where(
    res_df['mid_retest_mae_pct'] > 0,
    (res_df['mid_retest_mfe_pct'] / res_df['mid_retest_mae_pct']).round(2),
    np.nan
)
```

### Fields Added to macro_records

| Field | Description |
|-------|-------------|
| `post_retest_high` | Highest price from mid retest to lookforward end |
| `post_retest_low` | Lowest price from mid retest to lookforward end |
| `post_retest_close` | Close price at lookforward end |
| `post_retest_bars` | Number of bars in the post-retest window |
| `mid_retest_mfe_pct` | Max favorable excursion from macro mid entry, as % of macro open |
| `mid_retest_mae_pct` | Max adverse excursion from macro mid entry, as % of macro open |
| `mid_retest_net_pct` | Net P&L from macro mid entry to lookforward close, as % of macro open (signed: positive = profitable) |
| `mid_retest_win` | Boolean — did the trade close in profit? |
| `mid_retest_rr` | Reward-to-risk ratio (MFE / MAE) |

All fields are NULL for macros where the mid was not retested (`post_macro_retested_mid = false`).

### Important: The Entry Price is the Macro Mid

The macro mid is `(macro_high + macro_low) / 2` — the 50% retracement of the completed macro range. This is the entry price for Strategy 2. All MFE/MAE/net calculations use this as the reference, NOT the macro open or close.

### Cleanup

Don't drop `post_retest_high`, `post_retest_low`, `post_retest_close` — keep them in the output. They're useful for further analysis (e.g., what session level did the post-retest move reach).

---

## Fix 2: FVG Entry Analytics (Same Pattern)

**File:** `scripts/edgeful/fvg_tracker.py`

Apply the same logic for the FVG entry (Strategy 1). For FVGs tagged as `is_first_presented = true`, compute MFE/MAE from the FVG test point forward.

### What Needs to Be Added

The FVG tracker already detects when an FVG was tested (`was_tested`, `test_time_m`). Now compute what happened after the test:

**Add to the DuckDB query in fvg_tracker.py:**

```sql
-- Add to fvg_outcomes CTE:

-- MFE after test (max favorable move from test point)
-- For bullish FVG (entry is long): favorable = max high after test - fvg_mid
-- For bearish FVG (entry is short): favorable = fvg_mid - min low after test
MAX(CASE 
    WHEN fvg_type = 'bullish' AND bar_l <= fvg_high  -- bar that tests the FVG
    THEN NULL  -- skip the test bar itself for subsequent calc
    ELSE NULL
END) as placeholder,

-- Actually, simpler to do in a second pass:
-- After identifying test_time, get all bars AFTER the test and compute max/min
```

**Simpler approach — second CTE after fvg_outcomes:**

```sql
CREATE TEMP TABLE fvg_post_test AS
WITH test_times AS (
    SELECT 
        fvg_id,
        fvg_type,
        fvg_high,
        fvg_low,
        (fvg_high + fvg_low) / 2 as fvg_mid,
        fvg_timestamp,
        -- The test bar timestamp
        MIN(CASE 
            WHEN (fvg_type = 'bullish' AND bar_l <= fvg_high) 
              OR (fvg_type = 'bearish' AND bar_h >= fvg_low)
            THEN bar_time
        END) as test_bar_time
    FROM fvg_lookforward
    GROUP BY fvg_id, fvg_type, fvg_high, fvg_low, fvg_timestamp
)
SELECT 
    t.fvg_id,
    t.fvg_mid,
    t.fvg_type,
    MAX(b.high) as post_test_high,
    MIN(b.low) as post_test_low,
    LAST(b.close ORDER BY b.bar_time) as post_test_close
FROM test_times t
JOIN fvg_lookforward b ON t.fvg_id = b.fvg_id 
                       AND b.bar_time >= t.test_bar_time
WHERE t.test_bar_time IS NOT NULL
GROUP BY t.fvg_id, t.fvg_mid, t.fvg_type
```

**Then in Pandas:**

```python
# Merge post-test outcomes
res_df = res_df.merge(post_test_outcomes, on='fvg_id', how='left')

fvg_mid = res_df['fvg_mid']

# For bullish FVG (long entry at fvg_mid):
# MFE = post_test_high - fvg_mid
# MAE = fvg_mid - post_test_low

# For bearish FVG (short entry at fvg_mid):
# MFE = fvg_mid - post_test_low
# MAE = post_test_high - fvg_mid

res_df['fvg_entry_mfe_pct'] = np.where(
    res_df['fvg_type'] == 'bullish',
    (res_df['post_test_high'] - fvg_mid) / res_df['macro_open_lvl'] * 100,
    np.where(
        res_df['fvg_type'] == 'bearish',
        (fvg_mid - res_df['post_test_low']) / res_df['macro_open_lvl'] * 100,
        np.nan
    )
).clip(min=0)

res_df['fvg_entry_mae_pct'] = np.where(
    res_df['fvg_type'] == 'bullish',
    (fvg_mid - res_df['post_test_low']) / res_df['macro_open_lvl'] * 100,
    np.where(
        res_df['fvg_type'] == 'bearish',
        (res_df['post_test_high'] - fvg_mid) / res_df['macro_open_lvl'] * 100,
        np.nan
    )
).clip(min=0)

res_df['fvg_entry_net_pct'] = np.where(
    res_df['fvg_type'] == 'bullish',
    (res_df['post_test_close'] - fvg_mid) / res_df['macro_open_lvl'] * 100,
    np.where(
        res_df['fvg_type'] == 'bearish',
        (fvg_mid - res_df['post_test_close']) / res_df['macro_open_lvl'] * 100,
        np.nan
    )
)

res_df['fvg_entry_win'] = res_df['fvg_entry_net_pct'] > 0

res_df['fvg_entry_rr'] = np.where(
    res_df['fvg_entry_mae_pct'] > 0,
    (res_df['fvg_entry_mfe_pct'] / res_df['fvg_entry_mae_pct']).round(2),
    np.nan
)
```

### Fields Added to fvg_detail

| Field | Description |
|-------|-------------|
| `post_test_high` | Highest price from FVG test to lookforward end |
| `post_test_low` | Lowest price from FVG test to lookforward end |
| `post_test_close` | Close at lookforward end |
| `fvg_entry_mfe_pct` | Max favorable excursion from FVG mid entry, as % of macro open |
| `fvg_entry_mae_pct` | Max adverse excursion from FVG mid entry, as % of macro open |
| `fvg_entry_net_pct` | Net P&L from FVG mid entry (positive = profitable) |
| `fvg_entry_win` | Boolean — profitable trade? |
| `fvg_entry_rr` | Reward-to-risk ratio |

### Entry Price Note

The entry price for FVG trades is the **FVG mid** (consequent encroachment level), not the FVG edge. This is standard ICT — you wait for price to fill to the 50% level of the gap before entering.

---

## Fix 3: Dashboard Updates

### New Filters (Advanced Section)

| Filter | Type | Source |
|--------|------|--------|
| Mid Retested | Toggle: Yes / No / Any | `post_macro_retested_mid` |
| Mid Retest Win | Toggle: Yes / No / Any | `mid_retest_win` |

### New Chart Options

Add these to the distribution chart selector dropdown:

| Chart | Column | Auto-Filter | Description |
|-------|--------|-------------|-------------|
| Mid Retest MFE | `mid_retest_mfe_pct` | `post_macro_retested_mid = true` | How far does price move favorably from mid entry? |
| Mid Retest MAE | `mid_retest_mae_pct` | `post_macro_retested_mid = true` | How far does price move against mid entry? |
| Mid Retest Net P&L | `mid_retest_net_pct` | `post_macro_retested_mid = true` | Net outcome distribution |
| Mid Retest R:R | `mid_retest_rr` | `post_macro_retested_mid = true` | Reward-to-risk distribution |
| Mid Retest Time | `mid_retest_time_m` | `post_macro_retested_mid = true` | How long until mid is retested? |
| FVG Entry MFE | `fvg_entry_mfe_pct` | `is_first_presented = true AND was_tested = true` | From fvg_detail table |
| FVG Entry MAE | `fvg_entry_mae_pct` | `is_first_presented = true AND was_tested = true` | From fvg_detail table |
| FVG Entry Net P&L | `fvg_entry_net_pct` | `is_first_presented = true AND was_tested = true` | From fvg_detail table |

### New Summary Cards (Strategy Performance Section)

Add a new row of summary cards that appears when `indicator_label = Manip` is selected (or always visible as a "Strategy 2 Performance" section):

| Card | Metric | SQL |
|------|--------|-----|
| Mid Retest Rate | % of macros where mid was retested | `COUNT(CASE WHEN post_macro_retested_mid THEN 1 END) / COUNT(*)` |
| Mid Entry Win Rate | % of retested macros that were profitable | `AVG(CASE WHEN mid_retest_win THEN 1.0 ELSE 0.0 END) WHERE post_macro_retested_mid` |
| Avg Mid MFE | Mean mid_retest_mfe_pct | `AVG(mid_retest_mfe_pct) WHERE post_macro_retested_mid` |
| Avg Mid MAE | Mean mid_retest_mae_pct | `AVG(mid_retest_mae_pct) WHERE post_macro_retested_mid` |
| Avg Mid R:R | Mean reward-to-risk | `AVG(mid_retest_rr) WHERE post_macro_retested_mid` |
| Avg Time to Retest | Mean minutes until mid retested | `AVG(mid_retest_time_m) WHERE post_macro_retested_mid` |

### Stats Panel

All new chart options should include the standard stats panel (median, mode, P25, P75, IQR, std dev) as specified in the previous fix spec.

---

## Execution Order

1. Update `post_macro.py` — add mid retest MFE/MAE/net/win/rr computation
2. Update `fvg_tracker.py` — add FVG entry MFE/MAE/net/win/rr computation
3. Rerun pipeline to regenerate both parquet files
4. Update dashboard — add new filters, chart options, and summary cards
5. Validate: filter to Manip macros on ES, check mid retest win rate and R:R

---

## Validation

After implementation, run this query to sanity-check:

```sql
SELECT 
    indicator_label,
    COUNT(*) as total,
    COUNT(CASE WHEN post_macro_retested_mid THEN 1 END) as retested,
    ROUND(COUNT(CASE WHEN post_macro_retested_mid THEN 1 END) * 100.0 / COUNT(*), 1) as retest_rate,
    ROUND(AVG(CASE WHEN mid_retest_win THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
    ROUND(AVG(mid_retest_mfe_pct), 4) as avg_mfe,
    ROUND(AVG(mid_retest_mae_pct), 4) as avg_mae
FROM macro_records
WHERE post_macro_retested_mid = TRUE
AND judas_classification IN ('bullish_judas', 'bearish_judas')
GROUP BY indicator_label
ORDER BY win_rate DESC
```

Expected: Manip macros should show a higher win rate and better R:R than Accum or Expansion when entering at the macro mid. If Manip shows ~55%+ win rate with R:R > 1.5, the Strategy 2 entry is validated.
