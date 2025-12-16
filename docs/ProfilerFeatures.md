# Profiler Features Documentation

## 1. Profiler Clipboard Export
The **Clipboard Export** feature allows users to verify and share profiler statistics easily.

### Core Functionality
-   **Bulk Export**: Extracts statistics for all visible outcomes (e.g., Long True, Long False) compatible with the current filter view.
-   **Session Context**: Ensures data is strictly filtered for the **Target Session** (e.g., NY1), preventing leakage from other trading sessions.
-   **Format**: Pipe-delimited string with a header row, ready for spreadsheet analysis.

### Export Columns
`Session | Direction | Stats | LOD Time Mode | HOD Time Mode | LOD Distribution | HOD Distribution | P12 High | P12 Mid | P12 Low | Asia Mid | London Mid | Captured At`

### Usage
-   Click **"Copy All Outcomes"** in the Profiler Analysis header.
-   Data is copied to clipboard.

---

## 2. HOD/LOD Chart Improvements
The **High/Low of Day (HOD/LOD) Chart** has been enhanced for better readability and precision.

### Key Features
-   **Diverging Bars**: HOD (Green) bars extend upward, LOD (Red) bars extend downward.
-   **Zero-Line Alignment**: Bars are now stacked (`stackOffset="sign"`) to ensure they originate from the exact same central axis, eliminating visual shifts.
-   **Reference Lines**:
    -   **00:00 (Midnight)**: Grey dashed line.
    -   **09:30 (RTH Open)**: Orange dashed line.
-   **Tooltip**: Detailed breakdown of % occurrences and day counts.
