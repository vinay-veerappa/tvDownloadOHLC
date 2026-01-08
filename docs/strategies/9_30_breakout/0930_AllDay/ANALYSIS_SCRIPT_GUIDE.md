# Analysis Script Guide: `analyze_v3_comprehensive.py`

## 1. Overview
This Python script generates a comprehensive comparative analysis report for multiple TradingView backtest strategies. It was specifically designed to compare:
1.  **V3 Fixed TP**
2.  **V3 Adaptive**
3.  **V3 Time Exit**
4.  **V2 Baseline**

It ingests Excel exports (`.xlsx`) from TradingView's "List of Trades" and outputs a Markdown report (`V3_Comprehensive_Analysis.md`) containing:
-   **Executive Summary**: High-level P&L, Win Rate, and Trade Counts.
-   **Risk Profiling**: Advanced metrics like SQN, Profit Factor, Edge, and Combined Edge.
-   **Time Analysis**: Hourly, Daily, and Monthly performance breakdowns.
-   **MFE/MAE Distributions**: Statistics on Maximum Favorable/Adverse Excursion.
-   **Configuration**: A summary of parameter settings for each strategy.

## 2. Usage

### Prerequisites
-   **Python 3.x**
-   **Pandas**: `pip install pandas openpyxl`

### Running the Script
1.  Open a terminal in the folder containing the script and the `.xlsx` backtest files.
    ```powershell
    cd c:\Users\vinay\tvDownloadOHLC\docs\strategies\9_30_breakout\0930_AllDay
    python analyze_v3_comprehensive.py
    ```
2.  The script will:
    -   Load the 4 defined Excel files.
    -   Process the trades (merging Entry and Exit rows to avoid double-counting).
    -   Calculate all metrics.
    -   Generate `V3_Comprehensive_Analysis.md`.

## 3. Configuration & Customization

### Changing Input Files
The script currently has **hardcoded file paths** at the top of the file. To analyze different backtests, edit these lines in `analyze_v3_comprehensive.py`:

```python
# Files
V3_FIXED_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_620dd.xlsx'
V3_ADAPTIVE_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_52358.xlsx'
V3_TIME_FILE = 'ORB_V3_CME_MINI_MNQ1!_2026-01-07_cfbde.xlsx'
V2_FILE = r'old\ORB_All-Day_V2_CME_MINI_MNQ1!_2026-01-07_06a7f.xlsx'
```

### Modifying Risk Formulas
The core risk metrics are calculated in the `calc_stats_extended()` function.
-   **Edge**: `(Win Rate * Payoff) - Loss Rate`
-   **Combined Edge**: `Edge * Profit Factor`
-   **SQN**: `(Avg P&L / Std Dev P&L) * sqrt(Trades)`

## 4. Script Design

### Data Loading (`load_strategy_data`)
-   Reads the "List of trades" sheet.
-   **Critical Step**: Filters for rows with `Type="Exit..."` to get P&L data, then merges with `Type="Entry..."` rows to get Entry Time and Signal info.
-   *Why?* TradingView exports often duplicate the P&L on both entry and exit rows, leading to double-counting if naive summation is used. This script solves that.

### Time Bucketing
-   Automatically creates columns for `Hour`, `Minute`, `DayOfWeek`, `Month`, `Year`.
-   This enables the granular "Hourly Performance" and "Month-by-Month" tables in the report.

## 5. Output Report
The `generate_report()` function constructs the Markdown string. It is organized into modular sections:
1.  Executive Summary
2.  Risk Profiling (The "Edge" analysis)
3.  Hourly Performance
4.  Day/Month Breakdown
5.  MFE/MAE Stats
6.  Configuration Table (Hardcoded text at the end of the function - update this if you change strategy parameters).
