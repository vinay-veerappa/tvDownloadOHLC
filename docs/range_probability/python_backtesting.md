# Python Backtesting Guide: Range Probability Strategies

This guide demonstrates how to extract features, build custom backtest strategies, and evaluate trading performance in Python.

---

## 1. Quick Backtest CLI

Run automated strategy simulations across multiple tickers and timeframes:

```bash
# Backtest NQ, ES, YM on 60m and 15m ranges with prior boundary targets
python -m scripts.range_probability.backtest_runner --tickers NQ,ES,YM --intervals 60,15 --min-prob 70.0 --target-mode prior_boundary --stop-mode prior_midpoint
```

### CLI Parameters
- `--tickers`: Comma-separated list (`NQ,ES,YM,RTY,CL,GC,SPY,QQQ,NVDA,TSLA`).
- `--intervals`: Range sizes in minutes (`15,30,60,120,240`).
- `--min-prob`: Minimum conditional probability threshold (default `70.0%`).
- `--min-resolve`: Minimum range resolve rate threshold (default `40.0%`).
- `--min-sample`: Minimum historical sample size (default `20`).
- `--target-mode`: Profit target model:
  - `prior_boundary`: Target the Prior High (for Long) or Prior Low (for Short).
  - `fixed_rr`: Target multiple of risk distance.
  - `range_close`: Hold to the end of the range bar.
- `--stop-mode`: Stop loss model:
  - `prior_midpoint`: Stop placed at prior range 50% midpoint.
  - `prior_opposite`: Stop placed at opposite prior boundary.
  - `fixed_pts`: Fixed point stop.

---

## 2. Programmatic Python API

You can easily integrate the Range Probability Engine into your own research notebooks, Optuna optimizations, or VectorBT backtests:

```python
import pandas as pd
from src.range_prob.calculator import build_ranges_from_ohlc, compute_probability_matrix
from src.range_prob.backtest_adapter import RangeProbBacktester
from scripts.range_probability.extractor import extract_features_for_ticker

# 1. Extract enriched features
df_features = extract_features_for_ticker(
    ticker="NQ",
    interval_minutes=60,
    min_prob=70.0,
    min_sample=20
)

# 2. Initialize backtester
tester = RangeProbBacktester(
    min_prob=70.0,
    min_resolve_rate=40.0,
    min_sample_size=20,
    target_mode="prior_boundary",
    stop_mode="prior_midpoint",
    point_value=20.0,  # $20/pt for NQ
    slippage_pts=0.5,
    commission_per_contract=2.0
)

# 3. Execute backtest
results = tester.run_backtest(df_features)

# 4. Inspect performance metrics
print(f"Total Trades:  {results['total_trades']}")
print(f"Win Rate:      {results['win_rate']}%")
print(f"Net Profit:    ${results['net_profit']:,.2f}")
print(f"Profit Factor: {results['profit_factor']}")
print(f"Max Drawdown:  ${results['max_drawdown']:,.2f}")
print(f"Sharpe Ratio:  {results['sharpe_ratio']}")

# 5. Access trade log
df_trades = results['trades']
print(df_trades.head(10))
```

---

## 3. Backtest Feeds Schema

The extracted feeds (`data/range_prob/backtest_feeds/{TICKER}_{TF}m_features.parquet`) contain:

| Column | Type | Description |
|---|---|---|
| `start_time_ny` | `datetime` | Range open timestamp in Eastern Time |
| `open`, `high`, `low`, `close` | `float` | Range OHLC bar values |
| `prior_high`, `prior_low` | `float` | Previous completed range levels |
| `open_pos` | `float` | Normalized position ($0.0 \dots 1.0$) |
| `bucket` | `int` | Bucket index ($0 \dots 11$) |
| `s_dir` | `string` | Historical bias direction (`U` or `D`) |
| `s_prob` | `float` | Historical winning probability (%) |
| `s_train`, `s_test` | `float` | Train/Test split probabilities (%) |
| `s_n` | `int` | Sample size count |
| `s_res_rate` | `float` | Historical resolve rate (%) |
| `z_score` | `float` | Statistical significance Z-score |
| `is_qualified` | `bool` | True if edge meets probability and sample filters |
| `realized_outcome` | `string` | Actual outcome (`UP`, `DOWN`, `INSIDE`) |
| `trade_win` | `int` | $1$ if signal won, $0$ if lost, `NaN` if no signal |
