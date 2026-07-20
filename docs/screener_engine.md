# Screener Engine Architecture

The Screener Engine (`scripts/screener/`) is a modular, YAML-driven system designed to screen thousands of stocks against specific technical setups like High Tight Flags, Episodic Pivots, and Stage 2 Breakouts. 

## Core Pipeline

The screener pipeline executes in the following order:
1. **Regime Gatekeeper (`regime.py`)**: Checks SPY technicals and macro events (FOMC/CPI via dev.db) to establish a global regime (e.g., `BULL_EXPLOSIVE`). It also applies a `MACRO_HIGH_RISK` overlay.
2. **Universe Funnel (`funnel.py`)**: Pulls base candidate tickers from Finviz based on broad liquidity and volume parameters.
3. **Data Fetching**: Pulls 6-months of daily OHLCV data for all candidates via `yfinance`.
4. **Feature Matrix (`features.py`)**: Vectorizes all technical indicators (EMA, SMA, ATR, RVOL) and shifts (Runups, Gaps).
5. **YAML Evaluator (`yaml_evaluator.py`)**: Loads a declarative strategy from `config/*.yaml` and uses `pandas.query()` to filter the feature matrix.
6. **Logging (`setup_logger.py`)**: Persists matched candidates into DuckDB for historical analysis and dashboarding.

## Feature Engineering (`features.py`)

All complex calculations, time-series shifts, and indicator alignments MUST be pre-calculated inside `features.py` and appended to the output dataframe as lowercase columns. 

**Critical Design Pattern**: Do NOT use `pandas.shift()` or `.rolling()` inside the YAML rule expressions! The `yaml_evaluator.py` operates on the *latest single row per ticker*, meaning `.shift(60)` will fail or shift across different tickers. Pre-calculate metrics like `runup_60d` in `features.py` first.

*Available Custom Features:*
- `closing_range_strength`: Safe metric from 0.0 to 1.0 showing where the close was relative to the high/low. Returns 0.5 on dojis/halts.
- `ma_aligned_fast_momentum`: True if close > ema10 > ema20 > sma50.
- `vcp_tightness_ratio`: atr5 / atr20. Lower means tighter range contraction.
- `runup_60d`: 60-day relative total return performance.
- `gap_up`: Current open / Previous close.
- `momentum_burst`: Current close / Previous close.
- `sma150_slope_1m`: 1-month slope of the 150 SMA.
- `industry_rs_rank`: 0-100 Relative Strength percentile for the stock's industry sector calculated via `industry_rs.py`.
- `has_upcoming_earnings_7d`: Boolean flag indicating if ticker has an earnings event scheduled in the next 7 days via `sync_earnings_calendar.py` and `dev.db`.
- `float_discrepancy_pct`: Percentage mismatch between reported Finviz float and secondary sources via `float_validator.py`.
- `float_flagged`: True if float discrepancy > 15%.

## Rule Evaluator Strictness (`yaml_evaluator.py`)

Rule expressions in strategy YAML files are evaluated vectorially. If a rule expression fails to evaluate (e.g. invalid syntax or missing feature column), the evaluator logs an explicit error and excludes candidate stocks rather than silently passing invalid candidates.

## YAML Configuration Strategy

Strategies are defined in `scripts/screener/config/`. Each YAML file contains filters (used for Finviz/Universe selection) and rules (used for Pandas querying).

```yaml
strategy_id: "example_strategy"
version: "1.0.0"
author: "Name"
description: "Description of the strategy"

global_regime_required: ["BULL_EXPLOSIVE", "BULL_CHOPIER"]

filters:
  price_min: 10.0
  avg_volume_min: 500000

rules:
  - name: "historic_runup"
    expression: "runup_60d > 2.0"
  - name: "vcp_tightening"
    expression: "vcp_tightness_ratio < 0.6"
```

## Available Strategies
1. `qullamaggie_hft.yaml`: High Tight Flags (100% runup, ATR tightening, volume dry up).
2. `parabolic_short.yaml`: Extended parabolic runners far from the 10/20 EMA.
3. `stockbee_ep.yaml`: Episodic Pivots (8%+ volume gap up in top industries).
4. `stockbee_momentum.yaml`: 4%+ momentum bursts in top industries.
5. `minervini_trend.yaml`: 8-point trend template for market leaders.
6. `oneil_breakout.yaml`: CAN SLIM Stage 2 base breakouts.
7. `weinstein_stage2.yaml`: 30-week SMA uptrend breakouts on massive volume.
8. `kell_ema_bounce.yaml`: Momentum leaders bouncing off the 10/20 EMA.
9. `wheel_income.yaml`: High IV, no upcoming earnings, cash-secured put setup on strong blue chips.
10. `zanger_volume_surge.yaml`: 3-day extreme volume surges.
11. `rs_vs_spy.yaml`: Relative Strength vs SPY/QQQ proxy scanner.

## Multi-Strategy Reporting & Watchlist Exports (`generate_reports.py`)

Run all strategies simultaneously to generate a multi-strategy comparison matrix and watchlists for external platforms:

```bash
# Run a single strategy scan
python -m scripts.screener.cli --strategy minervini_trend --limit 50

# Run multi-strategy scan and generate matrix & watchlists
python -m scripts.screener.cli --report --limit 100
# or: python -m scripts.screener.cli --strategy all --limit 100
```

*Generated Artifacts (`reports/screener/`):*
- `strategy_comparison_matrix.csv`: 1/0 strategy matrix sorted by `matched_strategies_count` descending (common subset at the top).
- `tradingview_watchlist.csv`: Symbol list formatted for TradingView Watchlist Import.
- `thinkorswim_watchlist.csv`: Symbol list formatted for Thinkorswim (TOS) Watchlist Import.

