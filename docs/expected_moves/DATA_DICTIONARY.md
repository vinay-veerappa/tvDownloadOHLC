# Expected Move Data Dictionary

This document describes the comprehensive Expected Move (EM) datasets generated for intraday trading analysis.

## Analysis Parameters

| Parameter | Value |
| :--- | :--- |
| **Ticker** | SPY |
| **Date Range** | 2023-12-19 to 2025-12-18 |
| **Trading Days** | 502 |
| **Data Location** | `docs/expected_moves/analysis_data/` |

## Generated Files

| File | Rows | Description |
| :--- | :--- | :--- |
| `em_daily_levels.csv` | 31,542 | Daily EM levels for each method at each multiple |
| `em_daily_performance.csv` | 31,542 | Daily realized performance vs each EM level |
| `em_level_touches.csv` | 2,244 | 5-minute intraday touch/reversal data |
| `em_method_summary.csv` | 70 | Summary statistics for each method/level combo |
| `em_master_dataset.csv` | 502 | Raw daily data with all EM calculations |
| `em_multimethod_results.csv` | 49 | Multi-method comparison results |

---

## EM Calculation Methods

| Method ID | Description | Anchor | Formula |
| :--- | :--- | :--- | :--- |
| `straddle_085_close` | ATM Straddle x 0.85 | Prev Close | `Straddle * 0.85` |
| `straddle_100_close` | ATM Straddle x 1.0 | Prev Close | `Straddle * 1.0` |
| `iv365_close` | IV-based (365 days) | Prev Close | `Price * IV * sqrt(1/365)` |
| `iv252_close` | IV-based (252 trading days) | Prev Close | `Price * IV * sqrt(1/252)` |
| `vix_raw_close` | VIX theoretical 1-day | Prev Close | `Price * (VIX/100) * sqrt(1/252)` |
| `vix_scaled_close` | VIX scaled 2.0x | Prev Close | `Price * (VIX/100) * sqrt(1/252) * 2.0` |
| `straddle_085_open` | Straddle % applied to Open | Daily Open | `Open * (Straddle%_from_Close)` |
| `straddle_100_open` | Full Straddle % applied to Open | Daily Open | `Open * (Straddle%_from_Close)` |
| `synth_vix_085_open` | Synthetic VIX x 0.85 at 9:30 AM | Daily Open | `Open * (VIX_Open/100) * sqrt(1/252) * 2.0 * 0.85` |
| `synth_vix_100_open` | Synthetic VIX x 1.0 at 9:30 AM | Daily Open | `Open * (VIX_Open/100) * sqrt(1/252) * 2.0` |
| `iv252_open` | IV-252 applied to Open | Daily Open | `Open * IV * sqrt(1/252)` |

---

## Level Multiples

| Multiple | Description | Use Case |
| :--- | :--- | :--- |
| **0.500** | 50% of EM | High-frequency intraday pivot |
| **0.618** | Fibonacci 61.8% | Retracement target |
| **1.000** | 100% EM (1 SD) | Standard boundary |
| **1.272** | Fibonacci extension | Trend continuation target |
| **1.500** | 150% EM | Extended boundary |
| **1.618** | Fibonacci golden ratio | Momentum exhaustion |
| **2.000** | 200% EM (2 SD) | Extreme volatility boundary |

---

## File: em_daily_levels.csv

Daily EM levels calculated for each method and multiple.

| Column | Type | Description |
| :--- | :--- | :--- |
| `date` | string | Trading date (YYYY-MM-DD) |
| `prev_close` | float | Previous day's closing price |
| `open` | float | Daily open price |
| `high` | float | Daily high |
| `low` | float | Daily low |
| `close` | float | Daily close |
| `prev_week_close` | float | Previous week's closing price (for confluence) |
| `method` | string | EM calculation method ID |
| `em_value` | float | Raw EM value in price terms |
| `anchor` | float | Anchor price (Open or Prev Close) |
| `multiple` | float | Level multiple (0.5, 1.0, etc.) |
| `level_upper` | float | Upper level price (`anchor + em * mult`) |
| `level_lower` | float | Lower level price (`anchor - em * mult`) |

---

## File: em_daily_performance.csv

How each day performed against each EM level.

| Column | Type | Description |
| :--- | :--- | :--- |
| `date` | string | Trading date |
| `method` | string | EM calculation method ID |
| `multiple` | float | Level multiple |
| `em_value` | float | Raw EM value |
| `mfe_mult` | float | Max Favorable Excursion as multiple of EM |
| `mae_mult` | float | Max Adverse Excursion as multiple of EM |
| `contained` | bool | Did price stay within the level? |
| `touched_upper` | bool | Did price touch the upper level? |
| `touched_lower` | bool | Did price touch the lower level? |

---

## File: em_level_touches.csv

5-minute intraday analysis of level interactions.

| Column | Type | Description |
| :--- | :--- | :--- |
| `date` | string | Trading date |
| `method` | string | EM calculation method ID |
| `multiple` | float | Level multiple (0.5, 1.0, 1.5) |
| `level_upper` | float | Upper level price |
| `level_lower` | float | Lower level price |
| `touched_upper` | bool | Did 5m bar touch upper level? |
| `touched_lower` | bool | Did 5m bar touch lower level? |
| `reversed_upper` | bool | Did price reverse after touching upper? |
| `reversed_lower` | bool | Did price reverse after touching lower? |
| `touch_time_upper` | datetime | Time of first upper touch |
| `touch_time_lower` | datetime | Time of first lower touch |

---

## File: em_method_summary.csv

Aggregated statistics for each method/level combination.

| Column | Type | Description |
| :--- | :--- | :--- |
| `method` | string | EM calculation method ID |
| `multiple` | float | Level multiple |
| `containment_pct` | float | % of days price stayed within level |
| `touch_upper_pct` | float | % of days upper level was touched |
| `touch_lower_pct` | float | % of days lower level was touched |
| `median_mfe` | float | Median MFE as multiple of EM |
| `median_mae` | float | Median MAE as multiple of EM |
| `sample_size` | int | Number of days in sample |

---

## Usage Notes

1. **For S/R Analysis**: Use `em_level_touches.csv` to identify which levels have the highest reversal rates.
2. **For Target Setting**: Use `em_daily_performance.csv` to find containment rates at different multiples.
3. **For Method Selection**: Use `em_method_summary.csv` to compare all methods head-to-head.
4. **For Confluence**: Join `em_daily_levels.csv` with `prev_week_close` to identify days where EM levels align with major static levels.
