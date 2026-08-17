# Range Probability Engine: Multi-Asset Empirical Probability Suite

The **Range Probability Suite** is an intraday quantitative framework that calculates empirical range expansion and directional resolution probabilities conditioned on the opening price position relative to the previous range.

---

## Table of Contents
1. [Core Features](#core-features)
2. [Project Architecture](#project-architecture)
3. [Supported Tickers & Datasets](#supported-tickers--datasets)
4. [Quick Start](#quick-start)
   - [1. Generate Probability Matrices](#1-generate-probability-matrices)
   - [2. Extract Backtest Feeds](#2-extract-backtest-feeds)
   - [3. Run Python Backtests](#3-run-python-backtests)
5. [TradingView Pine Script v6 Integration](#tradingview-pine-script-v6-integration)
6. [NinjaTrader 8 Suite](#ninjatrader-8-suite)
7. [Mathematical Methodology](#mathematical-methodology)

---

## Core Features

- **Multi-Asset Support**: Extends the single-ticker NQ concept to **NQ, ES, YM, RTY, CL, GC, SPY, QQQ, AAPL, NVDA, TSLA** (and any custom instrument).
- **Multi-Timeframe Partitions**: Built-in support for **15m, 30m, 60m, 120m, and 240m** range durations anchored to **18:00 ET** (futures open) or custom equity anchors.
- **Normalized 12-Decile Bucketing**: Classifies the open into 12 discrete states ($<0.0$, 10 internal deciles, and $\ge 1.0$).
- **Statistical Significance & Out-of-Sample Scorecard**: Computes sample size $N$, Z-scores, train/test split, and live drift tracking (claimed vs actual win rates).
- **Universal Pine Script v6 Indicator**: Single Pine script with automatic symbol detection and visual decile levels, range boxes, and HUD statistics table.
- **NinjaTrader 8 Custom Indicator & Strategy**: Complete C# NinjaScript indicator and automated strategy with ATM brackets.
- **High-Speed Vectorized Python Backtester**: Instant performance reporting with PnL, Win Rate, Profit Factor, Sharpe Ratio, and Drawdowns.

---

## Project Architecture

```
tvDownloadOHLC/
├── scripts/
│   ├── indicators-pine/
│   │   └── range_probability/
│   │       ├── RangeProbability_NQ.pine            # Original NQ reference indicator
│   │       └── RangeProbability_Universal.pine     # Universal multi-asset Pine Script v6
│   ├── ninjatrader/
│   │   ├── indicators/
│   │   │   └── range_probability/
│   │   │       └── RangeProbabilityIndicator.cs    # NinjaTrader 8 Custom Indicator (C#)
│   │   └── strategies/
│   │       └── range_probability/
│   │           └── RangeProbabilityStrategy.cs     # NinjaTrader 8 Automated Strategy (C#)
│   └── range_probability/
│       ├── __init__.py
│       ├── engine.py                               # Batch probability matrix generator
│       ├── extractor.py                            # One-click feature dataset extractor
│       ├── backtest_runner.py                      # Python backtest runner CLI
│       └── build_universal_pine.py                 # Pine Script universal compiler
├── src/
│   └── range_prob/
│       ├── __init__.py
│       ├── calculator.py                           # Core range partitioning & probability matrix engine
│       ├── matrix_store.py                         # JSON, Parquet, and Pine LUT serializer
│       └── backtest_adapter.py                     # Vectorized & event-driven Python backtester
├── data/
│   └── range_prob/
│       ├── matrices/                               # Ticker JSON transition matrices
│       ├── pine_lut/                               # Pine Script LUT code constants
│       ├── backtest_feeds/                         # Enriched Parquet/CSV backtest feeds
│       └── reports/                                # Consolidated performance reports
└── docs/
    └── range_probability/
        ├── README.md                               # Master documentation
        ├── methodology_math.md                     # Theoretical & mathematical specification
        ├── python_backtesting.md                   # Python strategy backtesting guide
        └── ninjatrader_guide.md                    # NinjaTrader 8 installation & deployment guide
```

---

## Quick Start

### 1. Generate Probability Matrices
Compute empirical probability lookup matrices across all tickers in batch:
```bash
python -m scripts.range_probability.engine --tickers NQ,ES,YM,RTY,CL,GC,SPY,QQQ,AAPL,NVDA,TSLA --intervals 15,30,60,120,240 --anchor 18 --min-prob 70.0
```

### 2. Extract Backtest Feeds
Extract pre-calculated feature tables (Parquet and CSV) with bar-by-bar probabilities and realized outcomes:
```bash
python -m scripts.range_probability.extractor --tickers NQ,ES,YM,RTY,CL,GC,SPY,QQQ,NVDA,TSLA --intervals 15,30,60,120,240
```

### 3. Run Python Backtests
Run automated strategy simulations:
```bash
python -m scripts.range_probability.backtest_runner --tickers NQ,ES,YM,RTY --intervals 60,15,30,120,240 --min-prob 70.0 --target-mode prior_boundary --stop-mode prior_midpoint
```

---

## Documentation Links
- [Methodology & Mathematical Foundations](file:///c:/Users/vinay/tvDownloadOHLC/docs/range_probability/methodology_math.md)
- [Python Strategy Backtesting Guide](file:///c:/Users/vinay/tvDownloadOHLC/docs/range_probability/python_backtesting.md)
- [NinjaTrader 8 Integration Guide](file:///c:/Users/vinay/tvDownloadOHLC/docs/range_probability/ninjatrader_guide.md)
