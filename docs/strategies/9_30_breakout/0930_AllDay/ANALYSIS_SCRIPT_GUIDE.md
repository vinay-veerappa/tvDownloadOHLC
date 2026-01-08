# Generic Strategy Analysis & Grading Tool (The Edge System)
**Script**: `analyze_v3_comprehensive.py`
**Version**: 2.0 (The Edge System Edition)

## 1. Overview
This is a **universal strategy grading tool**. 
It ingests backtest exports (currently TradingView Excel) and generates a standardized **System Report** containing:
1.  **The 10-Metric Card**: Every critical risk metric (EV, PF, RoR, Combined Edge, etc.).
2.  **System Grade (A-F)**: Automated quality scoring based on "Edge System" rules.
3.  **Actionable Recommendations**: A "Fix Table" telling you exactly what to tune (e.g. "Fix EV", "Reduce Risk").
4.  **Granular Time Analysis**: Performance broken down by 5-min, 15-min, Hour, Day, Quarter, and Year.

## 2. Usage

### Prerequisites
-   **Python 3.x**
-   **Pandas**: `pip install pandas openpyxl`

### Configuration
Open `analyze_v3_comprehensive.py` and edit the file paths at the top:
```python
# --- CONFIGURATION: INPUT FILES ---
V3_FIXED_FILE = 'Your_Strategy_Export_1.xlsx'
V2_FILE = 'Your_Strategy_Export_2.xlsx'
```

### Running
```powershell
python analyze_v3_comprehensive.py
```
**Output**: Generates `V3_Comprehensive_Analysis.md`.

## 3. The 10 Metrics (Calculated)
The script implements the exact formulas from `RISK_PROFILE_DEFINITIONS.md`:
1.  **Risk ($)**: `Abs(AvgLoss)`
2.  **EV ($)**: `(Win% * AvgWin) - (Loss% * AvgLoss)`
3.  **Profit Factor**: `GrossWin / GrossLoss`
4.  **MAE/MFE Ratio**: `AvgMFE / AvgMAE`
5.  **SQN**: `(MeanR / StdR) * sqrt(Trades)`
6.  **Max Streak**: `ln(N) / ln(1/LossRate)`
7.  **DRR**: `MaxDD / Risk`
8.  **Combined Edge**: `(EV/Risk) * ProfitFactor`
9.  **RoR**: `((1-Edge)/(1+Edge))^Units`
10. **Max Drawdown**: Peak-to-Valley ($)

## 4. Extending to NinjaTrader / Other Platforms
The script is designed to be **generic**. To add a new platform:
1.  Go to `load_strategy_data()` function.
2.  Add a generic mapper. The script only needs a DataFrame with these normalized columns:
    *   `Entry Time` (datetime)
    *   `Exit Time` (datetime)
    *   `Entry Price` (float)
    *   `Exit Price` (float)
    *   `Net P&L USD` (float)
    *   `MAE USD` (optional)
    *   `MFE USD` (optional)
3.  Once the DataFrame is created, pass it to `calc_stats_extended()` and it will automatically generate the Grade and Report.

## 5. Output Sections
*   **Executive Grading**: The 10-Metric Card + Final Grade (A-F).
*   **Recommendations**: Automated advice (e.g. "Grade C: Risk 0.5-1%").
*   **Time Analysis**:
    *   **5-Min & 15-Min Buckets**: Great for finding "Toxic Time Zones" (e.g. 11am-12pm).
    *   **Quarterly/Yearly**: For consistency checks.
