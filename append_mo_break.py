import os

filepath = r'C:\Users\vinay\tvDownloadOHLC\scripts\indicators-pine\daily-ny-levels\DailyNYLevelsAnalytics_ANALYSIS.md'

content_to_append = """

### 6.5 Market Open Breakout (MO Break) Replay Dataset (2026-06-29)
The user enabled the **Market Open Breakout (MO Break)** preset on the chart in replay mode. The live summary table and drawn levels were successfully captured from the chart using TradingView MCP tools.

#### 6.5.1 MO Break Summary Statistics (Live Chart Table)
* **Preset Name**: `Market Open Break`
* **Breakout Sample Size (N)**: `74`
* **FULL (Wins)**: `32`
* **FAILED (Losses)**: `42`
* **FULL%**: `43.2%`
* **p50 MAE ▲ (Bullish)**: `0.12%`
* **p50 MAE ▼ (Bearish)**: `0.15%`
* **Status**: `Active` | **Result**: `Failed (live)`
* **Entry Price**: `29,785`

#### 6.5.2 MO Break Drawn Levels & Price Projections
Below are the exact coordinates of the lines and labels drawn on the chart for today's session:

| Level Label | Price Level | Derived Metric (%) | Description / Tooltip |
| :--- | :---: | :---: | :--- |
| **BO Entry Price** | 29,785.00 | - | Breakout entry close at range boundary |
| **PB Entry (Pullback Activation)** | 29,767.84 | `0.058%` | PB entry — p25 MAE from breakout price |
| **BO Cashflow (P20)** | 29,882.68 | `0.328%` | BO Cashflow — p20 MFE from breakout |
| **MED MFE Target (P50)** | 29,928.19 | - | MED MFE — p50 MFE of Red zone sessions |
| **MAX MFE Target (P75)** | 30,052.30 | - | MAX MFE — p75 MFE of Red zone sessions |
| **BO Inval / PB Inval** | 29,698.40 | - | PB Invalidation — p80 MAE from breakout |
| **Pivot Level** | 29,835.50 | `0.170%` | Pivot — p50 MFE of fakes |
| **BO Confirm** | 29,888.50 | `0.347%` | BO Confirm — p75 MFE of fakes (N=24 fakes) |
| **REVERSAL TARGET ZONE** | 29,611.69 | - | Reversal Zone — p25-p50 MAE of fakes |
| **Max Reversal** | 29,346.84 | `1.471%` | Max Rev — p90 MAE of fakes |
| **Midpoint** | 29,662.50 | `9.400%` | Range Midpoint (Hit rate 9.4%) |
"""

with open(filepath, 'a', encoding='utf-8') as f:
    f.write(content_to_append)
print('Successfully appended MO Break data to ANALYSIS.md.')
