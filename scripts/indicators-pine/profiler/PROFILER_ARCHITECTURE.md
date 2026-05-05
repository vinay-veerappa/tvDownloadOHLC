# Profiler Indicator Architecture

## 1. System Overview

The Profiler system consists of **two indicators** and a **Python-to-Pine Generation Pipeline**:

1. **ProfilerIndicator.pine** — The main profiler with session boxes, statistics table, reference levels, and embedded price models.
2. **PriceModelIndicator.pine** — A standalone contextual price model indicator with hierarchical fallback logic.

Both use Python scripts to process large datasets and programmatically generate valid Pine Script code. This approach handles the complexity of managing ~50,000 lines of data and repetitive visualization logic.

## 2. Pipeline Components

### 2.1 Main Profiler Generator (`generate_profiler_pine.py`)

- **Role**: Orchestrator for the main profiler indicator.
- **Functionality**:
  1.  **Data Loading**: Reads JSON files containing probability models and session statistics.
  2.  **String Construction**: Assembles Pine Script strings for inputs, variables, and drawing logic.
  3.  **File Generation**: Writes individual `.pine` component files (`ProfilerData_*.pine`) to `scripts/profiler/`.
  4.  **Assembly**: Concatenates all components into the final `ProfilerIndicator.pine`.

### 2.2 Price Model Generator (`generate_price_model_indicator.py`)

- **Role**: Generates the standalone PriceModelIndicator and its data library.
- **Functionality**:
  1.  **Context Table**: Builds a cross-day context table from `NQ1_profiler.json` mapping each date to its session directions (L/S/N).
  2.  **Model Generation**: Fetches price models for 243 contextual combinations via API endpoints (`/stats/custom-price-model` and `/stats/filtered-price-model`).
  3.  **Quantized Packing**: Multiplies percentage values by 1000 and rounds to integers (e.g., `0.009` → `9`) for ~40% size reduction.
  4.  **Chunked Library Output**: Splits models into helper functions (`f_add_chunk_1` through `f_add_chunk_7`) to avoid TradingView's function size limits.
  5.  **Indicator Separation**: The library (`PriceModelData.pine`) is auto-generated; the indicator (`PriceModelIndicator.pine`) is manually maintained to prevent overwriting user edits.

### 2.3 Component Files (Main Profiler)

To avoid hitting Pine Script's size limits per file during development and to maintain modularity, data is split:

- `ProfilerData_Asia.pine` / `London.pine` / `NY.pine`: Session-specific stats.
- `ProfilerData_Levels.pine`: Price levels (Open, Mid, etc.).
- `ProfilerData_Times.pine`: Time-based probability arrays.
- `ProfilerData_Touches.pine`: Session-indexed touch arrays (bit-packed).
- `ProfilerData_Context.pine`: Previous-day NY1/NY2 context arrays for cross-day filtering.
- `ProfilerData_Broken.pine`: Broken session flag arrays.
- `ProfilerData_Model_*.pine`: High-fidelity price model polylines (LT/LF/ST/SF).
- `ProfilerData_AsiaPred.pine` / `LondonPred.pine`: Prediction-specific datasets.

### 2.4 Component Files (Standalone Price Model)

- `PriceModelData.pine`: TradingView library containing 243 pre-computed contextual price models as quantized integer strings.
- `PriceModelIndicator.pine`: Standalone indicator that detects the current session, builds context keys, and renders polylines.

## 3. Key Technical Decisions

### 3.1 Scope Management (Viz Logic)

- **Problem**: Variables defined inside `if barstate.islast` are not accessible outside that block. Variables assigned inside `if/else` blocks create local scope in Pine Script.
- **Solution**: All visualization logic—including Table rendering (`f_render_row_adv`) and Probability Masking (visibility flags)—is strictly nested within the main `if barstate.islast` block.
  - _Implementation_: Indentation in `generate_profiler_pine.py` enforces this nesting.
  - _Ternary Pattern_: Conditional assignments use ternary expressions (`v = cond ? a : b`) instead of `if/else` blocks to avoid scope issues.

### 3.2 Garbage Collection (Visual Artifacts)

- **Problem**: TradingView drawing objects (lines, labels, boxes) persist and stack on top of each other when the script re-executes or data updates, causing "bolding" or double text.
- **Solution**:
  - Global `var` arrays store IDs of all active drawing objects.
  - Before creating new objects, the script iterates through these arrays and calls `line.delete()`, `label.delete()`, etc.
  - Arrays are cleared and repopulated with new IDs.

### 3.3 Distribution Logic (Mode-to-Median)

- **Problem**: Small sample sizes make "Mode" (most frequent bucket) volatile. "Median" alone doesn't capture the spread.
- **Solution**: **Union Range**.
  - Calculate **Mode Bucket** (0.1% width).
  - Calculate **Median Bucket** (0.1% width).
  - Display the range spanning `min(Mode, Median)` to `max(Mode, Median)`.
  - Format: "Highest Magnitude to Lowest" (e.g., `0.5 to 0.1%`) to align with trader intuition.

### 3.4 Timezone Handling

- All time calculations use `timestamp("America/New_York", ...)` to ensure consistency with the 18:00 ET session start, regardless of the user's local chart time.

### 3.5 Multi-Tier Bit-Packing (Size Optimization)

- **Problem**: Large historical datasets (e.g., 44 session-indexed touch arrays) exceeded TradingView's script compilation size limits.
- **Solution**: **Multi-Tier Packing**.
  - **Packing Ratio**: **15:1**. 15 values are packed into a single integer. This ratio is selected to stay within the 52-bit mantissa of 64-bit floats, ensuring mathematical precision during decompression in Pine Script.
  - **Data Types Packed**:
    - **Binary (1-bit)**: Broken status, touch flags.
    - **Codes (3-bit)**: Session outcome codes (Neutral, Long True/False, Short True/False).
  - **Decompression**: Implemented version-aware math-based helpers (`f_get_bit`, `f_get_code`) in the indicator.
    - _Logic_: `math.floor(val / math.pow(base, pos)) % base`.
  - **Benefits**: ~90% reduction in compiled script size, allowing expansion to 15+ years of daily data without splitting libraries.

### 3.6 String-Packed Price Models (PriceModelData)

- **Problem**: The standalone price model indicator needs to store 243 models with ~48 data points each. Array-based storage would exceed TradingView's code length limits.
- **Solution**: **Quantized String Packing**.
  - Each model's 48 high/low pairs are packed into a single string: `"9:-5,6:0,7:0,..."`.
  - Values are quantized to integers (original % × 1000) for ~40% size reduction (131KB → 69KB).
  - A string literal counts as only 1 token in Pine Script, keeping the entire 243-model library under TradingView's 100,000 token limit.
  - Resolution: 10-minute buckets (down from 5-minute) to further halve token count.
  - Decoding in the indicator: `str.tonumber(value) / 1000.0` to recover the original percentage.

### 3.7 Hierarchical Contextual Fallback (S3 Architecture)

- **Problem**: Contextual price models filtered by multiple session directions can have insufficient sample sizes.
- **Solution**: **Three-Level Hierarchical Lookup**.
  - **Level 1 (Full Context)**: `SESSION_DIR1_DIR2_OUTCOME` (e.g., `NY1_L_S_LT`). Uses all predecessor directions.
  - **Level 2 (Single Predecessor)**: `SESSION_F_DIR_OUTCOME` (e.g., `NY1_F_S_LT`). Falls back to closest predecessor only.
  - **Level 3 (Baseline)**: `SESSION_B_OUTCOME` (e.g., `NY1_B_LT`). No contextual filter, maximum sample size.
  - Minimum sample size: N ≥ 30 for any model to be included.

## 4. Reference Levels Drawn

### 4.1 Previous Day Levels

- PDH, PDL, PDM (Previous Day High/Low/Mid)
- Settle (Previous Day Close)
- Previous Week Close

### 4.2 Session Opens

- Globex Open (18:00 ET)
- Midnight Open (00:00 ET)
- 07:30 Open

### 4.3 Prior 12-Hour Range (P12)

- P12H, P12L, P12M — Current prior 12-hour range (18:00-05:59 ET)
- NY P12H, NY P12L, NY P12M — Current NY portion of prior 12 hours (06:00-16:59 ET)
- Prev NY P12H, Prev NY P12L, Prev NY P12M — Previous day's NY P12 range (always visible from session start)

### 4.4 Session Midpoints

- Asia Mid, London Mid, NY1 Mid, NY2 Mid — Current day session midpoints
- When viewing Asia/London prediction context, these become "Prev Asia Mid", "Prev NY1 Mid" etc.

## 5. Session Definitions

| Session | Classification Window | Full Session Window |
| ------- | --------------------- | ------------------- |
| Asia    | 18:00 – 19:29 ET      | 18:00 – 02:29 ET    |
| London  | 02:30 – 03:29 ET      | 02:30 – 07:29 ET    |
| NY1     | 07:30 – 08:29 ET      | 07:30 – 11:29 ET    |
| NY2     | 11:30 – 12:29 ET      | 11:30 – 15:59 ET    |

## 6. Context Dependency Chains (Price Model)

| Target Session | Context Dependencies            |
| -------------- | ------------------------------- |
| Asia           | Prev NY1 Dir + Prev NY2 Dir     |
| London         | Asia Dir + Prev NY2 Dir         |
| NY1            | Asia Dir + London Dir           |
| NY2            | Asia Dir + London Dir + NY1 Dir |
