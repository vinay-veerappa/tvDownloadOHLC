# VWAP Strategy Suite Directory

This directory contains the Python strategy implementations, research runners, and documentation for the **Institutional Multi-Timeframe VWAP Suite**.

## Contents

- **Core Strategies**:
  - [`core/vwap_institutional.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/vwap_reclaim/core/vwap_institutional.py): Institutional multi-timeframe engine with 5m ADX/SMA50 trend fusion, 09:30 ORB real-time bias, and Pack Quarterly Theory expansion windows.
  - [`core/vwap_reclaim.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/vwap_reclaim/core/vwap_reclaim.py): Baseline 1-minute reclaim hunter.
- **Runners**:
  - [`runners/run_vwap_validation_report.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/vwap_reclaim/runners/run_vwap_validation_report.py): 10-year historical validation across NQ1 and ES1.
  - [`runners/run_vwap_optimization.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/vwap_reclaim/runners/run_vwap_optimization.py): Optuna hyperparameter optimization suite.
- **Documentation & Research**:
  - [**Strategy Specification & Research Findings**](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/vwap_reclaim/INSTITUTIONAL_VWAP_SPEC.md): Full empirical benchmarks, MAE/MFE statistics, and "Cover the Queen" prop-firm execution math.
