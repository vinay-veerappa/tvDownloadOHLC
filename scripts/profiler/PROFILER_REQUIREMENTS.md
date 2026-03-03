# Profiler Indicator Requirements

## 1. Overview

The Profiler system is a specialized trading toolset designed to visualize market profile statistics across four key sessions: Asia, London, NY1, and NY2. It aggregates historical probability data to display distinct "Trend" (True) or "Fail" (False) outcomes for Long and Short biases. The system consists of two TradingView indicators:

1. **ProfilerIndicator** — Full-featured profiler with session boxes, statistics, reference levels, and embedded price models.
2. **PriceModelIndicator** — Standalone contextual price model overlay with hierarchical fallback.

## 2. Core Features

### 2.1 Session Logic

- **Time Segregation** (Classification Windows):
  - **Asia**: 18:00 – 19:29 ET.
  - **London**: 02:30 – 03:29 ET.
  - **NY1**: 07:30 – 08:29 ET.
  - **NY2**: 11:30 – 12:29 ET.
- **Full Session Windows**:
  - **Asia**: 18:00 – 02:29 ET.
  - **London**: 02:30 – 07:29 ET.
  - **NY1**: 07:30 – 11:29 ET.
  - **NY2**: 11:30 – 15:59 ET.
- **Day Start**: Aligned to 18:00 ET (Session change).
- **Direction Classification**: Close relative to session midpoint → L (Long) or S (Short).

### 2.2 Statistics Table (Dashboard)

- **Structure**: Fixed table positioned at Bottom Center.
- **Rows**:
  - **Long True**: Upward trend sustained.
  - **Long False**: Upward trend failed/reversed.
  - **Short True**: Downward trend sustained.
  - **Short False**: Downward trend failed/reversed.
- **Columns** (21 total):
  - **Col 0**: Outcome label (LT/LF/ST/SF).
  - **Col 1**: Stats (Count & % Occurrence).
  - **Col 2-3**: LOD/HOD Time (most frequent 15-min bucket).
  - **Col 4-5**: LOD/HOD Dist (mode-to-median % range).
  - **Col 6-8**: PDH/PDM/PDL (Previous Day level touch probabilities).
  - **Col 9-11**: NY P12H/NY P12M/NY P12L (NY Prior 12-Hour level touch probabilities).
  - **Col 12-14**: P12H/P12M/P12L (Prior 12-Hour level touch probabilities).
  - **Col 15-18**: Asia Mid / Lon Mid / NY1 Mid / NY2 Mid (session midpoint touch probabilities).
    - When `tgt_idx <= 1` (Asia/London prediction): Headers become "Prev Asia Mid", "Prev Lon Mid", "Prev NY1 Mid", "Prev NY2 Mid" and visibility is forced to `true` since these reference completed previous-day data.
  - **Col 19**: Midnight Open touch probability.
  - **Col 20**: 07:30 Open touch probability.
- **Visibility Rules**:
  - **Conditional Mask**: P12, Asia Mid, and London Mid values are **hidden** ("...") until their respective session/time thresholds are crossed (e.g., P12 hidden until 06:00 ET).
  - **Previous Day Override**: When viewing Asia/London prediction context (`tgt_idx <= 1`), all session mid columns show previous-day data and are always visible.
  - **Scope**: Rendered only on the last bar (`barstate.islast`) for performance.

### 2.3 Distribution Analysis

- **Time Histograms**:
  - **Granularity**: 15-minute intervals.
  - **Metric**: Mode (Most frequent interval).
  - **Display**: Time Range (e.g., "10:00-10:15").
- **Price Histograms (HOD/LOD Dist)**:
  - **Granularity**: 0.1% price buckets.
  - **Metric**: **Mode-to-Median Span** (Union of Mode bucket and Median bucket).
  - **Sorting**: Displayed as **Highest Magnitude to Lowest** (e.g., `0.5 to 0.1%`).
  - **Precision**: 0.1% steps.

### 2.4 Reference Level Visualization

- **Previous Day Levels**: PDH, PDL, PDM, Settle, Previous Week Close.
- **Session Opens**: Globex (18:00), Midnight (00:00), 07:30.
- **Prior 12-Hour Range (P12)**:
  - P12H, P12L, P12M — Visible from 06:00 ET onward.
  - **NY P12H, NY P12L, NY P12M** — Current-day NY portion (06:00-16:59 range). Drawn from 06:00 ET onward.
  - **Prev NY P12H, Prev NY P12L, Prev NY P12M** — Previous day's NY P12 range. Drawn from session start (18:00 ET), outside the `time >= t_0600` gate.
- **Session Midpoints**: Asia Mid, London Mid, NY1 Mid, NY2 Mid.
- **Reference Extension**: Lines extend 20 bars into the future for visibility.
- **Garbage Collection**: Previous drawings are deleted before updates to prevent "ghosting" or label doubling.

### 2.5 Embedded Price Models (ProfilerIndicator)

- Polyline rendering of projected price paths based on historical outcome models (LT/LF/ST/SF).
- Clean visuals (No debug labels).
- Anchor options: Day Open or Prev Mid.

### 2.6 Standalone Price Model Indicator (PriceModelIndicator)

- **Purpose**: Dedicated overlay for contextual price curve visualization, independent of the main profiler.
- **Architecture**: Strategy S3 (Direction-Only Context + Full Outcome).
  - Context filters use Long/Short/Neutral directions to keep sample sizes high.
  - Outcome curves preserve full LT/LF/ST/SF granularity.
- **Hierarchical Fallback**:
  - Level 1: Full directional context (all predecessor sessions).
  - Level 2: Single closest predecessor fallback.
  - Level 3: Baseline (unfiltered by context).
- **Data Format**: Quantized integer strings (`high:low` pairs × 1000) at 10-minute resolution.
- **Session Tracking**: Full high/low/direction tracking for all 4 sessions including NY2 for accurate next-day context.
- **TradingView Library**: `PriceModelData` published as a TradingView library (author: `vveerappa`).

## 3. User Customization

- **Toggles**:
  - Show/Hide specific Sessions (Asia, London, NY1, NY2).
  - Show/Hide specific Reference Levels (P12, PD, Opens, Settle, Weekly).
  - Show/Hide Table, Price Models, Time Histograms.
  - Debug mode for library size verification.
- **Styling**:
  - Theme selection: Default, Dark Pro, Light Pro, Neon.
  - Customizable colors for Long/Short, True/False, Sessions, and Reference Lines.
  - Table text size and position options.
  - Line styles (Solid/Dotted/Dashed) and widths.
- **Price Model Controls**:
  - Session override (Auto/Asia/London/NY1/NY2).
  - Outcome override (Auto/Long True/Long False/Short True/Short False).
  - Scale multiplier and anchor selection.

## 4. Performance & Optimization

### 4.1 Script Size Optimization

- **Historical Data Scale**: Supporting 15+ years of daily historical data (~5,000+ records).
- **Compilation Limit**: Must stay under TradingView's 100,000 token bytecode limit.
- **Solutions**:
  - **Multi-Tier Bit-Packing (15:1)**: All binary data and outcome codes packed into integers.
  - **Quantized String Packing**: Price model data stored as integer strings (×1000 quantization).
  - **10-Minute Resolution**: Price model buckets reduced from 5-min to 10-min for 50% token savings.
  - **Chunked Helper Functions**: Large data maps split into `f_add_chunk_N()` functions to avoid function size limits.

### 4.2 Cross-Day Context Filtering

- Asia and London prediction modes filter historical data by previous-day NY1 and NY2 outcomes.
- Context arrays (`ctx_prev_ny1`, `ctx_prev_ny2`) are bit-packed and stored in `ProfilerData_Context.pine`.
- State change detection triggers full recomputation only when session status, broken flags, or prev-day context changes.
