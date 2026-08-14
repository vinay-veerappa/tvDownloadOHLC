# 5-Minute MTF Inversion FVG (IFVG) & CISD Strategy

This directory contains the strategy code and specification for the **5-Minute Multi-Timeframe Inversion FVG & Change in State of Delivery (CISD) Strategy**.

## Strategy Files
- **Specification**: [`IFVG_CISD_5M_SPEC.md`](file:///c:/Users/vinay/tvDownloadOHLC/docs/strategies/ifvg_cisd/IFVG_CISD_5M_SPEC.md)
- **Strategy Implementation**: [`scripts/strategies/ifvg_cisd/core/ifvg_cisd_strategy.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/ifvg_cisd/core/ifvg_cisd_strategy.py)
- **Unit Tests**: [`scripts/trading_framework/tests/test_ifvg_cisd_strategy.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_framework/tests/test_ifvg_cisd_strategy.py)

## Strategy Overview
- **Timeframe**: 5-Minute HTF Structure + 1-Minute Execution Timeline
- **Core Signal**: 5m CISD Delivery Bias Flip + 5m Inversion FVG (IFVG) / FVG Retest
- **Execution Rules**: Cover the Queen Scale-Out (50% at +1.0R, 50% at +2.5R)
- **10-Year Out-of-Sample Results (NQ1)**:
  - **Trades**: 2,660 (~21/month)
  - **Win Rate**: 49.96% (~50%)
  - **Profit Factor**: 1.44
  - **Net PnL**: +$84,809.14
  - **Max Drawdown**: -$8,718.20
  - **Sharpe Ratio**: 1.80
