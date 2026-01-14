# Profiler Indicator Architecture

## 1. System Overview
The Profiler Indicator is built using a **Python-to-Pine Generation Pipeline**. Instead of writing raw Pine Script, we use a Python script (`generate_profiler_pine.py`) to process large probability datasets and programmatically generate valid Pine Script code. This approach handles the complexity of managing ~50,000 lines of data and repetitive visualization logic.

## 2. Pipeline Components

### 2.1 Generator Script (`generate_profiler_pine.py`)
*   **Role**: Orchestrator.
*   **Functionality**:
    1.  **Data Loading**: Reads JSON files containing probability models and session statistics.
    2.  **String Construction**: Assembles Pine Script strings for inputs, variables, and drawing logic.
    3.  **File Generation**: Writes individual `.pine` component files (`ProfilerData_*.pine`) to `scripts/profiler/`.
    4.  **Assembly**: Concatenates all components into the final `ProfilerIndicator.pine`.

### 2.2 Component Files
To avoid hitting Pine Script's size limits per file during development and to maintain modularity, data is split:
*   `ProfilerData_Asia.pine` / `London.pine` / `NY.pine`: Session-specific stats.
*   `ProfilerData_Levels.pine`: Price levels (Open, Mid, etc.).
*   `ProfilerData_Times.pine`: Time-based probability arrays.
*   `ProfilerData_Model_*.pine`: High-fidelity price model polylines for visualization.

## 3. Key Technical Decisions

### 3.1 Scope Management (Viz Logic)
*   **Problem**: Variables defined inside `if barstate.islast` are not accessible outside that block.
*   **Solution**: All visualization logic—including Table rendering (`f_render_row_adv`) and Probability Masking (visibility flags)—is strictly nested within the main `if barstate.islast` block.
    *   *Implementation*: Indentation in `generate_profiler_pine.py` enforces this nesting.

### 3.2 Garbage Collection (Visual Artifacts)
*   **Problem**: TradingView drawing objects (lines, labels, boxes) persist and stack on top of each other when the script re-executes or data updates, causing "bolding" or double text.
*   **Solution**:
    *   Global `var` arrays store IDs of all active drawing objects.
    *   Before creating new objects, the script iterates through these arrays and calls `line.delete()`, `label.delete()`, etc.
    *   Arrays are cleared and repopulated with new IDs.

### 3.3 Distribution Logic (Mode-to-Median)
*   **Problem**: Small sample sizes make "Mode" (most frequent bucket) volatile. "Median" alone doesn't capture the spread.
*   **Solution**: **Union Range**.
    *   Calculate **Mode Bucket** (0.1% width).
    *   Calculate **Median Bucket** (0.1% width).
    *   Display the range spanning `min(Mode, Median)` to `max(Mode, Median)`.
    *   Format: "Highest Magnitude to Lowest" (e.g., `0.5 to 0.1%`) to align with trader intuition.

### 3.4 Timezone Handling
*   All time calculations use `timestamp("America/New_York", ...)` to ensure consistency with the 18:00 ET session start, regardless of the user's local chart time.

### 3.5 Multi-Tier Bit-Packing (Size Optimization)
*   **Problem**: Large historical datasets (e.g., 44 session-indexed touch arrays) exceeded TradingView's script compilation size limits.
*   **Solution**: **Multi-Tier Packing**.
    *   **Packing Ratio**: **15:1**. 15 values are packed into a single integer. This ratio is selected to stay within the 52-bit mantissa of 64-bit floats, ensuring mathematical precision during decompression in Pine Script.
    *   **Data Types Packed**:
        *   **Binary (1-bit)**: Broken status, touch flags.
        *   **Codes (3-bit)**: Session outcome codes (Neutral, Long True/False, Short True/False).
    *   **Decompression**: Implemented version-aware math-based helpers (`f_get_bit`, `f_get_code`) in the indicator.
        *   *Logic*: `math.floor(val / math.pow(base, pos)) % base`.
    *   **Benefits**: ~90% reduction in compiled script size, allowing expansion to 15+ years of daily data without splitting libraries.
