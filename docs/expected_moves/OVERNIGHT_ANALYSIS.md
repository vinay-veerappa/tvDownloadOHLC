# ES Overnight Session EM Analysis

This analysis evaluates how the previous day's EM levels perform during the ES futures overnight session (16:00 - 09:30).

## Analysis Parameters

| Parameter | Value |
| :--- | :--- |
| **Ticker** | ES (/ES Futures) |
| **Session** | Overnight (16:00 - 09:30 next day) |
| **Date Range** | 2023-12-19 to 2025-12-18 |
| **Trading Days** | 389 (with matching ES/SPY data) |
| **EM Source** | SPY straddle-based, scaled per-day to ES |

---

## Summary Results

### Anchor: Previous Day's Close

| Level | Containment | Touch Upper | Touch Lower | Median MFE | Median MAE |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **50% EM** | 31.9% | 62.4% | 9.0% | 0.179 | 0.135 |
| **100% EM** | **90.0%** | 9.0% | 1.1% | 0.179 | 0.135 |

### Anchor: Previous Day's Open

| Level | Containment | Touch Upper | Touch Lower | Median MFE | Median MAE |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **50% EM** | 29.7% | 68.5% | 5.4% | 0.179 | 0.135 |
| **100% EM** | **92.1%** | 7.2% | 0.7% | 0.179 | 0.135 |

---

## Key Findings

1. **Previous Open is Better for Overnight**: The `prev_open` anchor achieves **92.1% containment** vs 90.0% for `prev_close` at 100% EM.

2. **50% EM is a Magnet**: The upper 50% level is touched on **62-68% of overnight sessions**, making it a high-probability target.

3. **Strong Upward Bias Overnight**: Touch upper rates (62-68%) far exceed touch lower rates (5-9%), indicating the overnight session has a bullish bias.

4. **100% EM is the Overnight Boundary**: Only ~8-10% of overnight sessions breach the 100% EM level.

---

## Trading Implications

### Overnight Long Strategy
- **Entry**: Buy ES at the previous day's Close or Open
- **Target**: 50% EM Upper (~62% hit rate)
- **Stop**: 100% EM Lower (~1% breach rate)
- **Risk/Reward**: Excellent asymmetry

### Overnight Short Fade
- **Condition**: If ES reaches 50% EM Upper overnight
- **Entry**: Short at 50% EM Upper
- **Target**: Previous Close/Open (mean reversion)
- **Stop**: 100% EM Upper

---

## Data Files

| File | Description |
| :--- | :--- |
| `em_overnight_es.csv` | Per-day overnight session details (1,116 rows) |
| `em_overnight_summary.csv` | Aggregated statistics by anchor/level |
