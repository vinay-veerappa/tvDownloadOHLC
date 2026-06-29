filepath = r'C:\Users\vinay\tvDownloadOHLC\scripts\indicators-pine\daily-ny-levels\DailyNYLevelsAnalytics_ANALYSIS.md'

content_to_append = """

### 6.7 1800 Breakout (1800 Break) Replay Dataset (2026-06-29)
The user enabled the **1800 Breakout (1800 Break)** preset on the chart in replay mode. The live summary table and drawn levels were successfully captured using TradingView MCP tools.

#### 6.7.1 1800 Break Summary Statistics (Live Chart Table)
* **Preset Name**: `1800 Break`
* **Breakout Sample Size (N)**: `75`
* **FULL (Wins)**: `35`
* **FAILED (Losses)**: `40`
* **FULL%**: `46.7%`
* **p50 MAE ▲ (Bullish)**: `0.091%`
* **p50 MAE ▼ (Bearish)**: `0.138%`
* **Status**: `Active` | **Result**: `Failed (live)`
* **Entry Price**: `29,558.75`

#### 6.7.2 1800 Break Drawn Levels & Price Projections
Below are the exact coordinates of the lines and labels drawn on the chart for today's session:

| Level Label | Price Level | Derived Metric (%) | Description / Tooltip |
| :--- | :---: | :---: | :--- |
| **BO Entry Price** | 29,558.75 | - | Breakout entry close at range boundary |
| **PB Entry (Pullback Activation)** | 29,549.17 | `0.032%` | PB entry — p25 MAE from breakout price |
| **BO Cashflow (P20)** | 29,637.80 | `0.267%` | BO Cashflow — p20 MFE from breakout |
| **MED MFE Target (P50)** | 29,626.85 | - | MED MFE — p50 MFE of Red zone sessions |
| **MAX MFE Target (P75)** | 29,763.67 | - | MAX MFE — p75 MFE of Red zone sessions |
| **BO Inval / PB Inval** | 29,522.76 | - | PB Invalidation — p80 MAE from breakout |
| **Pivot Level** | 29,614.61 | `0.189%` | Pivot — p50 MFE of fakes |
| **BO Confirm** | 29,677.51 | `0.402%` | BO Confirm — p75 MFE of fakes (N=18 fakes) |
| **REVERSAL TARGET ZONE** | 29,442.70 | - | Reversal Zone — p25-p50 MAE of fakes |
| **Max Reversal** | 29,231.37 | `1.108%` | Max Rev — p90 MAE of fakes |
| **Midpoint** | 29,416.38 | `22.900%` | Range Midpoint (Hit rate 22.9%) |
"""

with open(filepath, 'a', encoding='utf-8') as f:
    f.write(content_to_append)
print('Successfully appended 1800 Break data to ANALYSIS.md.')
