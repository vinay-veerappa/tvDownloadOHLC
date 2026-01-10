# 0930 All-Day ORB Strategy

This folder contains the 09:30 Opening Range Breakout strategy for futures trading.

## Folder Structure

| Folder | Contents |
|--------|----------|
| **pine/** | PineScript strategies for TradingView |
| **scripts/** | Python analysis and research scripts |
| **analysis/** | Research reports, forensics, and documentation |
| **backtests/** | Excel exports from TradingView backtests |
| **reports/** | Generated retest analysis reports |
| **charts/** | Saved chart images |
| **Presentation/** | Slides and graphics for strategy presentation |
| **old/** | Deprecated versions and backups |

## Current Strategy Versions (pine/)

| File | Description |
|------|-------------|
| `orb_v4_simplified.pine` | **LATEST** - Day-of-week removed, MAE fix, Toxic Windows |
| `orb_v3_toxic_windows.pine` | V3 with toxic time windows |
| `orb_v3_adaptive.pine` | V3 base version |
| `orb_v2.pine` | Legacy V2 |

## Key Features (V4)

- **Toxic Time Windows**: Skip 10AM, 10:30AM, 11:10-11:25 (lunch chop), 1PM news
- **MAE Filter**: Now correctly uses Range Boundary when configured
- **Doji Filter**: Skip entry on weak breakout candles
- **Multi-TP**: Split exits at TP1/TP2 with runner management
- **Fresh/Immediate Re-entry**: Simplified re-entry logic
