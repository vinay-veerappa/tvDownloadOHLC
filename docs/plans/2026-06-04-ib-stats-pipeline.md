# Multi-Session Initial Balance (IB) Statistics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and deploy a complete statistics pipeline (v5) for multi-session Initial Balance (IB) statistics across multiple instruments (ES, NQ, YM, RTY, CL, GC) over 20+ years of 1-minute data, exporting clean Parquet tables to power on-chart Pine indicators and a Next.js/DuckDB-WASM research dashboard.

**Architecture:**
- Computations are performed in a fully vectorized, ADR-017 compliant Python engine inside `scripts/libs_py/nqstats/ib.py`.
- An orchestrator script `scripts/edgeful/ib_pipeline.py` executes data loads via the Phase 1 `DataLoader`, Tagging via `session_tagger`, and runs calculation sweeps for both `ET_fixed` and `event_anchored` (Tokyo/London DST offsetted) slot variants.
- The pipeline outputs five long-format Parquet files to `data/derived/`: `ib_facts`, `ib_ext_detail`, `ib_play_detail`, `ib_level_touch_detail`, and `ib_fvg_detail`.
- The Next.js data proxy handles range requests for these files, loading them into client-side DuckDB-WASM for query execution inside a new dashboard at `web/app/research/ib-stats/page.tsx`.

**Tech Stack:** Python (Pandas, NumPy, PyArrow), Pytest, Next.js (React, TypeScript, Tailwind, shadcn/ui), DuckDB-WASM.

---

### Task 1: DST & Event-Anchored Sessions Config

**Files:**
- Modify: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/nqstats/ib.py`
- Create: Test configuration under `scripts/trading_framework/tests/test_ib_dst.py`

**Step 1: Define updated session slots configuration**
Modify `SESSION_CONFIGS` in `ib.py` to support `time_basis` ('ET_fixed' | 'event_anchored') and define the shifts:
```python
SESSION_CONFIGS = {
    "Globex IB":   {"ib_start": "18:00", "ib_end": "19:00", "out_end": "20:00", "time_basis": "ET_fixed"},
    "Tokyo IB":    {"ib_start": "20:00", "ib_end": "21:00", "out_end": "02:00", "time_basis": "event_anchored"},
    "London IB":   {"ib_start": "03:00", "ib_end": "04:00", "out_end": "06:00", "time_basis": "event_anchored"},
    "Midnight OR": {"ib_start": "00:00", "ib_end": "00:30", "out_end": "16:00", "time_basis": "ET_fixed"},
    "NY AM IB":    {"ib_start": "09:30", "ib_end": "10:30", "out_end": "16:00", "time_basis": "ET_fixed"},
    "NY PM IB":    {"ib_start": "13:30", "ib_end": "14:30", "out_end": "16:00", "time_basis": "ET_fixed"}
}
```

**Step 2: Write timezone DST helper functions**
Add the following functions to `ib.py` to calculate US and UK DST boundaries:
```python
import pytz

def get_dst_flags(timestamps: pd.DatetimeIndex) -> Tuple[pd.Series, pd.Series]:
    """
    Given a DatetimeIndex in UTC or naive ET, returns us_dst and uk_dst boolean Series.
    """
    # Force convert timestamps to UTC first to avoid ambiguity
    if timestamps.tz is None:
        utc_ts = timestamps.tz_localize('UTC')
    else:
        utc_ts = timestamps.tz_convert('UTC')
        
    # Convert to America/New_York
    ny_tz = pytz.timezone('America/New_York')
    ny_dt = [t.astimezone(ny_tz) for t in utc_ts]
    us_dst = pd.Series([dt.dst().total_seconds() > 0 for dt in ny_dt], index=timestamps)
    
    # Convert to Europe/London
    ld_tz = pytz.timezone('Europe/London')
    ld_dt = [t.astimezone(ld_tz) for t in ld_tz]
    uk_dst = pd.Series([dt.dst().total_seconds() > 0 for dt in ld_dt], index=timestamps)
    
    return us_dst, uk_dst

def get_event_anchored_times(
    date_val: date, 
    session: str, 
    us_dst: bool, 
    uk_dst: bool
) -> Tuple[time, time, int, str]:
    """
    Computes shifted ET hours for event-anchored foreign slots.
    Returns (start_time, end_time, et_window_offset_hours, dst_regime)
    """
    if session == "Tokyo IB":
        # Tokyo opens 09:00 JST = 00:00 UTC (No JST DST).
        # In ET: US EST (winter, us_dst=False) -> 19:00 ET. US EDT (summer, us_dst=True) -> 20:00 ET.
        if us_dst:
            return time(20, 0), time(21, 0), 0, "aligned"
        else:
            return time(19, 0), time(20, 0), -1, "shifted"
            
    elif session == "London IB":
        # London opens 08:00 local time.
        # US EDT & UK BST aligned -> 03:00 ET.
        # US EST & UK GMT aligned -> 03:00 ET.
        # Misaligned (spring/autumn shoulder weeks): 08:00 local UK is 04:00 ET.
        if us_dst == uk_dst:
            return time(3, 0), time(4, 0), 0, "aligned"
        elif us_dst and not uk_dst: # US EDT, UK GMT (March shoulder)
            return time(4, 0), time(5, 0), 1, "shifted"
        else: # US EST, UK BST (October/November shoulder)
            return time(2, 0), time(3, 0), -1, "shifted"
            
    # Default fallback
    cfg = SESSION_CONFIGS[session]
    start_t = datetime.strptime(cfg["ib_start"], "%H:%M").time()
    end_t = datetime.strptime(cfg["ib_end"], "%H:%M").time()
    return start_t, end_t, 0, "aligned"
```

**Step 3: Run pytest to verify DST detection**
Run: `pytest scripts/trading_framework/tests/test_phase1.py` to make sure existing setups compile and pass.

**Step 4: Commit**
`git commit -am "feat: add DST helper functions and session configuration"`

---

### Task 2: Advanced Bias Calculations & Order-Sensitive Grading

**Files:**
- Modify: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/nqstats/ib.py`

**Step 1: Implement firstreach and lasttouch formation biases**
In `calculate_ib_statistics()`, replace the provisional `bFormation` logic with:
```python
# First reach extreme
high_first_idx = ib_bars.groupby('logical_date')['high'].idxmax()
low_first_idx = ib_bars.groupby('logical_date')['low'].idxmin()

# Last touch extreme (using >= and <= scans)
# Find last occurrence index by reversing the groupby order
ib_bars_rev = ib_bars.iloc[::-1]
high_last_idx = ib_bars_rev.groupby('logical_date')['high'].idxmax()
low_last_idx = ib_bars_rev.groupby('logical_date')['low'].idxmin()

# bFormation_firstreach: Low first -> Bullish (+1), High first -> Bearish (-1)
bias_firstreach = np.where(
    low_first_idx < high_first_idx, 1,
    np.where(high_first_idx < low_first_idx, -1,
             np.where(ib_agg['ib_close'] > ib_agg['ib_open'], 1, -1))
)

# bFormation_lasttouch: High last (low first/last) -> Bullish (+1), Low last -> Bearish (-1)
bias_lasttouch = np.where(
    low_last_idx < high_last_idx, 1,
    np.where(high_last_idx < low_last_idx, -1,
             np.where(ib_agg['ib_close'] > ib_agg['ib_open'], 1, -1))
)
```

**Step 2: Implement dual FVG and IFVG logics**
- `bias_fvg_rth`: first 5m FVG starting 09:30.
- `bias_fvg_1011`: first 5m FVG starting between 09:50 and 11:00.
```python
# resample and shift 5m bars to compute FVGs
# FVG Inversion check (close-based invalidation)
```

**Step 3: Implement order-sensitive grading with Leakage Guard**
For each bias variant, compute `bias_correct_{variant}_05x` and `bias_correct_{variant}_1x` bar-by-bar:
```python
def grade_bias_order_sensitive(
    df_day: pd.DataFrame, 
    bias: int, 
    target_mult: float, 
    finalized_time: Optional[pd.Timestamp]
) -> bool:
    """
    Grades bias. Returns True if target reached before opposite boundary close.
    Applies Leakage Guard: only counts events after finalized_time.
    """
    if bias == 0:
        return False
        
    # Apply leakage guard window filter
    if finalized_time is not None:
        df_window = df_day[df_day.index > finalized_time]
    else:
        df_window = df_day
        
    if df_window.empty:
        return False
        
    ib_high = df_day['ib_high'].iloc[0]
    ib_low = df_day['ib_low'].iloc[0]
    ib_range = ib_high - ib_low
    
    if bias == 1: # Bullish
        target = ib_high + target_mult * ib_range
        stop_cond = df_window['close'] < ib_low
        target_cond = df_window['high'] >= target
    else: # Bearish
        target = ib_low - target_mult * ib_range
        stop_cond = df_window['close'] > ib_high
        target_cond = df_window['low'] <= target
        
    # Get first occurrence index
    stop_idx = df_window.index[stop_cond].min()
    target_idx = df_window.index[target_cond].min()
    
    if pd.isnull(target_idx):
        return False
    if pd.isnull(stop_idx):
        return True
    return target_idx < stop_idx
```

**Step 4: Commit**
`git commit -am "feat: implement advanced biases and order-sensitive grading"`

---

### Task 3: Level-Touch & Front-Running Mid Tracking

**Files:**
- Modify: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/nqstats/ib.py`

**Step 1: Compute mid-lock time**
Find `mid_lock_time` (last bar in IB window setting high or low):
```python
# Group by logical_date and find index of maximum high and minimum low
# mid_lock_time = max(high_last_idx, low_last_idx)
# mid_lock_frac = (mid_lock_time - ib_start_time) / ib_duration
```

**Step 2: Add level-touch tracking**
For levels {0, 25, 50, 75, 100}%:
Determine touch occurrences in `pre_lock`, `post_lock`, and `outcome` phases:
- `pre_lock`: timestamp < `mid_lock_time`
- `post_lock`: `mid_lock_time` <= timestamp < `ib_end`
- `outcome`: `ib_end` <= timestamp < `out_end`
Store details in the long-format `ib_level_touch_detail` list:
`first_touch_time`, `last_touch_time`, `touch_count`.

**Step 3: Implement early_mid_event flag**
```python
# early_mid_event = (mid_lock_frac <= 2/3) & (final_mid touched in post_lock phase)
```

**Step 4: Commit**
`git commit -am "feat: implement level-touch and front-running mid analytics"`

---

### Task 4: Plays Evaluation & FVG Reuse

**Files:**
- Modify: `c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/nqstats/ib.py`

**Step 1: Implement the three plays bar-by-bar**
- **Play 1 (Breakout):** target = 1.0x, stop = opposite boundary close.
- **Play 2 (Retest-continuation):** enter on mid touch after breakout; target = 0.5x, stop = opposite boundary close.
- **Play 3 (Fade-to-mid):** overshoot to 0.25x; require a touch-back to boundary to fill; target = mid; stop = 0.5x overshoot. If never fills -> no-setup (0).
Track MFE / MAE excursions in percent.

**Step 2: Implement FVG reuse tracking**
Output rows to `ib_fvg_detail` long table containing FVG boundaries, touch times, reaction (held / closed_through), and inversion flags.

**Step 3: Commit**
`git commit -am "feat: implement three plays evaluation and FVG reuse tracking"`

---

### Task 5: Parquet Export Pipeline Orchestrator

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/edgeful/ib_pipeline.py`

**Step 1: Implement the orchestrator script**
Write `ib_pipeline.py` to:
1. Parse CLI args: `--instruments`, `--start`, `--end`, `--force`.
2. Load 1m data via `DataLoader` for target instruments (ES1, NQ1, etc.).
3. Loop through slots and time bases (`ET_fixed`, `event_anchored`).
4. Perform core computations using `ib.py`.
5. Materialize and save the five tables to `data/derived/` as Parquet files:
   - `ib_facts.parquet`
   - `ib_ext_detail.parquet`
   - `ib_play_detail.parquet`
   - `ib_level_touch_detail.parquet`
   - `ib_fvg_detail.parquet`

**Step 2: Test orchestrator execution**
Run: `python scripts/edgeful/ib_pipeline.py --instruments NQ1 --start 2025-01-01`
Verify files exist in `data/derived/`.

**Step 3: Commit**
`git add scripts/edgeful/ib_pipeline.py`
`git commit -m "feat: implement ib_pipeline.py data export orchestrator"`

---

### Task 6: Unit and Regression Tests

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/scripts/trading_framework/tests/test_ib_pipeline.py`

**Step 1: Write test cases**
- Verify DST offset mapping (EST vs EDT months).
- Verify Play 3 touch-back fill logic.
- Verify order-sensitive grading with leakage guard.
- Verify memory-safe vectorized execution (ADR-017 / ADR-011 compliance).

**Step 2: Run tests**
Run: `pytest scripts/trading_framework/tests/test_ib_pipeline.py -v`
Expected: ALL PASS.

**Step 3: Commit**
`git add scripts/trading_framework/tests/test_ib_pipeline.py`
`git commit -m "test: add comprehensive test suite for IB stats calculations"`

---

### Task 7: Next.js API Proxy and DuckDB Types Update

**Files:**
- Modify: `c:/Users/vinay/tvDownloadOHLC/web/types/duckdb-browser-module.d.ts` (if needed)
- Create: Types in `web/types/ib-stats.ts`

**Step 1: Define TypeScript schemas**
Create `web/types/ib-stats.ts` matching the parquet output schemas for facts, extensions, plays, level touches, and FVG details.

**Step 2: Commit**
`git add web/types/ib-stats.ts`
`git commit -m "types: add TypeScript interfaces for IB statistics tables"`

---

### Task 8: Research Dashboard Page for IB Stats

**Files:**
- Create: `c:/Users/vinay/tvDownloadOHLC/web/app/research/ib-stats/page.tsx`

**Step 1: Write dashboard UI structure**
Create `page.tsx` to:
1. Initialize DuckDB-WASM and load the five parquet tables: `/api/data/ib_facts.parquet`, `/api/data/ib_ext_detail.parquet`, etc.
2. Render filters: Symbol dropdown, Session Slot dropdown, Time Basis, VIX Regime, Day of Week, prior-day result, DST regime.
3. Query DuckDB to build the aggregate panels specified in §3:
   - **SUGGESTED** Line (Heuristic synthesis using trailing terciles).
   - **DIRECTION** Panel (A/B bias accuracy).
   - **FAKE-OUT** Panel (False-break %, contained, double-break, retrace).
   - **PLAYS** Panel (expectancy table).
   - **TARGETS** Panel (conditional ladder).
   - **DAY TYPE** Panel (mid-retest, gap, range terciles, DOW).
   - **RANGE Δ** Panel (size distribution).
   - **DST Validation** Panel (fixed vs event-anchored comparison).
   - **Level-Touch / Front-Running** Panel.
4. Render panels with traffic-light styling (≥60% green, 50-60% orange, <50% red) and tooltips.

**Step 2: Build validation**
Run: `npm run build` inside `web/` to verify TypeScript compile and component rendering.

**Step 3: Commit**
`git add web/app/research/ib-stats/page.tsx`
`git commit -m "feat: implement research dashboard page for IB Stats"`

