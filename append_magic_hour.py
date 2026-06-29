filepath = r'C:\Users\vinay\tvDownloadOHLC\scripts\indicators-pine\daily-ny-levels\DailyNYLevelsAnalytics_ANALYSIS.md'

content_to_append = """

### 6.6 Magic Hour Replay Dataset (2026-06-29)
The user enabled the **Magic Hour** preset on the chart in replay mode. The live summary table and drawn levels were successfully captured using TradingView MCP tools.

#### 6.6.1 Magic Hour Summary Statistics (Live Chart Table)
* **Preset Name**: `Magic Hour`
* **Breakout Sample Size (N)**: `61`
* **FULL (Wins)**: `55`
* **FAILED (Losses)**: `6`
* **FULL%**: `90.2%`
* **p50 MAE ▲ (Bullish)**: `0.152%`
* **p50 MAE ▼ (Bearish)**: `0.238%`
* **Status**: `Active` | **Result**: `Failed (live)`
* **Entry Price**: `29,748.75`

#### 6.6.2 Magic Hour Drawn Levels & Price Projections
Below are the exact coordinates of the lines and labels drawn on the chart for today's session:

| Level Label | Price Level | Derived Metric (%) | Description / Tooltip |
| :--- | :---: | :---: | :--- |
| **BO Entry Price** | 29,748.75 | - | Breakout entry close at range boundary |
| **PB Entry (Pullback Activation)** | 29,741.96 | `0.023%` | PB entry — p25 MAE from breakout price |
| **BO Cashflow (P20)** | 29,759.58 | `0.036%` | BO Cashflow — p20 MFE from breakout |
| **MED MFE Target (P50)** | 29,762.43 | - | MED MFE — p50 MFE of Red zone sessions |
| **MAX MFE Target (P75)** | 29,762.43 | - | MAX MFE — p75 MFE of Red zone sessions |
| **BO Inval / PB Inval** | 29,655.43 | - | PB Invalidation — p80 MAE from breakout |
| **Pivot Level** | 29,764.80 | `0.054%` | Pivot — p50 MFE of fakes |
| **BO Confirm** | 29,801.61 | `0.178%` | BO Confirm — p75 MFE of fakes (N=6 fakes) |
| **REVERSAL TARGET ZONE** | 29,636.56 | - | Reversal Zone — p25-p50 MAE of fakes |
| **Max Reversal** | 29,572.71 | `0.592%` | Max Rev — p90 MAE of fakes |
| **Midpoint** | 29,662.38 | `20.000%` | Range Midpoint (Hit rate 20.0%) |
"""

with open(filepath, 'a', encoding='utf-8') as f:
    f.write(content_to_append)
print('Successfully appended Magic Hour data to ANALYSIS.md.')
