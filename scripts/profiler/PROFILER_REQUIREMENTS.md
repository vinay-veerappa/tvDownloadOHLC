# Profiler Indicator Requirements

## 1. Overview
The Profiler Indicator is a specialized trading tool designed to visualize market profile statistics across three key sessions: Asia, London, and New York. It aggregates historical probability data to distinct "Trend" (True) or "Fail" (False) outcomes for Long and Short biases.

## 2. Core Features

### 2.1 Session Logic
*   **Time Segregation**:
    *   **Asia**: 18:00 - 02:00 ET (Next Day).
    *   **London**: 02:00 - 08:00 ET.
    *   **New York**: 08:00 - 17:00 ET.
*   **Day Start**: Aligned to 18:00 ET (Session change).

### 2.2 Statistics Table (Dashboard)
*   **Structure**: Fixed table positioned at Top-Right.
*   **Rows**:
    *   **Long True**: Upward trend sustained.
    *   **Long False**: Upward trend failed/reversed.
    *   **Short True**: Downward trend sustained.
    *   **Short False**: Downward trend failed/reversed.
*   **Columns**:
    *   **Stats**: Count & % Occurrence.
    *   **LOD/HOD Time**: Most frequent time for High/Low of Day.
    *   **LOD/HOD Dist**: Price distribution (distance from Open).
    *   **Probabilities**: P12 High/Mid/Low, Asia Mid, London Mid.
*   **Visibility Rules**:
    *   **Conditional Mask**: P12, Asia Mid, and London Mid values are **hidden** ("...") until their respective session/time thresholds are crossed (e.g., P12 hidden until 06:00 ET).
    *   **Scope**: Rendered only on the last bar (`barstate.islast`) for performance.

### 2.3 Distribution Analysis
*   **Time Histograms**:
    *   **Granularity**: 15-minute intervals.
    *   **Metric**: Mode (Most frequent interval).
    *   **Display**: Time Range (e.g., "10:00-10:15").
*   **Price Histograms (HOD/LOD Dist)**:
    *   **Granularity**: 0.1% price buckets.
    *   **Metric**: **Mode-to-Median Span** (Union of Mode bucket and Median bucket).
    *   **Sorting**: Displayed as **Highest Magnitude to Lowest** (e.g., `0.5 to 0.1%`).
    *   **Precision**: 0.1% steps.

### 2.4 Visualization
*   **Reference Lines**:
    *   Dynamic drawing of Session Highs/Lows, Midpoints, and Open prices.
    *   **Reference Extension**: Lines extend 20 bars into the future for visibility.
    *   **Garbage Collection**: Previous drawings are deleted before updates to prevent "ghosting" or label doubling.
*   **Price Models**:
    *   Polyline rendering of projected price paths based on historical models.
    *   Clean visuals (No debug labels).

## 3. User Customization
*   **Toggles**:
    *   Show/Hide specific Sessions (Asia, Lon, NY).
    *   Show/Hide specific Models (Start, Volatility, Distribution, etc.).
    *   Show/Hide Table.
*   **Styling**:
    *   Customizable colors for Long/Short, True/False, and Sessions.
    *   Table text size and position options.

## 4. Performance & Optimization

### 4.1 Script Size Optimization
*   **Historical Data Scale**: Supporting 15+ years of daily historical data (~4,000+ records).
*   **Compilation Limit**: Must stay under TradingView's bytecode limit.
*   **Solution**: **Multi-Tier Packing**.
    *   All binary data and outcome codes must be packed into a 15:1 ratio within 64-bit integers.
    *   Unpacking must be handled via math-based helper functions to ensure compatibility across all TradingView runtime versions.
    *   No more than 15 values per integer to maintain bitwise parity using floating-point math.
