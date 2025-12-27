# Backtest Reporting Standards

To ensure consistency across all strategy backtests and allow for "apples-to-apples" comparison, all backtest scripts and reports must adhere to the following standards.

> [!TIP]
> **Data Sources:** See [DERIVED_DATA.md](../data/DERIVED_DATA.md) for precomputed data (HOD/LOD, Profiler, Sessions) and [DATA_SOURCES.md](../data/DATA_SOURCES.md) for raw OHLC formats.

## 1. Metric Standardization
All value-based metrics must be captured in **Percentages** relative to the Entry Price (or Open Price for context).

| Metric | Unit | Description |
| :--- | :--- | :--- |
| **Range Size** | % | `(High - Low) / Open` |
| **PnL** | % | Net Profit/Loss per trade |
| **MAE** | % | max Adverse Excursion (Drawdown from Entry) |
| **MFE** | % | max Favorable Excursion (Run-up from Entry) |

## 2. Required Data Fields (CSV Export)
Every backtest run must generate a `details.csv` containing at least:

### A. Context
*   `Date`: YYYY-MM-DD
*   `DayOfWeek`: Mon-Fri
*   `Range_Pct`: Size of the defining range (e.g., 9:30 Candle).

### B. Execution
*   `Variant`: Strategy Name (e.g., "Original", "Option A").
*   `Entry_Time`: HH:MM:SS (Exact second of fill).
*   `Entry_Price`: Numerical.
*   `Direction`: LONG / SHORT.
*   `Entry_Delay`: Seconds/Minutes from Session Open.
*   `Is_Outside_Range`: Boolean (TRUE if Entry Price is outside the initial defining range).

### C. Outcome
*   `Result`: WIN / LOSS / BREAKEVEN.
*   `PnL_Pct`: Final outcome.
*   `MAE_Pct`: Depth of pain.
*   `MFE_Pct`: Max potential profit.
*   `Exit_Reason`: TP, SL, TIME, EOD.
*   `Chart_Link`: *(Future Enhancement)* Path/URL to annotated chart snapshot showing entry, exit, and key levels with metadata (date, time, strategy name, metrics).

## 3. Visualization Standards (Charts)
All visual samples must include:
1.  **Reference Lines**: Horizontal lines clarifying the "Defining Range" (e.g., 9:30 High/Low).
2.  **Context Window**: 5-10 minutes *before* the setup to show approach.
3.  **Hilighted Setup**: Distinct color/box for the setup accumulation (e.g., FVG Box).
4.  **Markers**: Explicit Arrow/Dot for Entry and Exit.

## 5. Market Condition Validation
To prove robustness, strategies must be tested across the following benchmark market regimes:

| Regime | Period | Key Characteristics |
| :--- | :--- | :--- |
| **Strong Bull** | 2020-04 to 2021-12 | V-shape recovery, high liquidity, trend persistence. |
| **Strong Bear** | 2022-01 to 2022-10 | Interest rate hikes, high volatility, downward trend. |
| **Consolidation** | 2023-01 to 2023-06 | Range-bound/choppy behavior before recovery. |
| **Standard Bull** | 2023-11 to Present | Steady expansion, moderate volatility. |

**Standard Backtest Window**: 5 Years (Minimum). All reporting must include a breakdown of Win% and PnL by these specific identified regimes.
