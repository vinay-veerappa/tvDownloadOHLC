# 5-Minute MTF Inversion FVG (IFVG) & CISD Strategy Specification

## 1. Executive Summary
The **5-Minute Multi-Timeframe Inversion FVG (IFVG) & Change in State of Delivery (CISD) Strategy** is an institutional execution model designed to capture sustained accumulation and distribution waves on equity index futures (**NQ1, ES1**).

By decoupling **higher-timeframe (5m/3m) structure and orderflow absorption** from **1-minute execution and risk management**, the strategy eliminates sub-minute noise while maintaining surgical risk-to-reward control.

---

## 2. Core Strategy Mechanics

### Phase 1: Higher-Timeframe (5m) Change in State of Delivery (CISD)
* **Bullish CISD (Accumulation)**: A 5-minute displacement candle closes above the highest open of the prior downward delivery run.
* **Bearish CISD (Distribution)**: A 5-minute displacement candle closes below the lowest open of the prior upward delivery run.

### Phase 2: Inversion Fair Value Gap (IFVG) Confirmation
* When smart money aggressively distributes, price closes completely through prior support imbalances:
  * **Bearish IFVG**: 5m candle closes below the bottom of a previously active Bullish FVG. Trapped buyers are now forced to exit, inverting old support into dynamic overhead resistance.
  * **Bullish IFVG**: 5m candle closes above the top of a previously active Bearish FVG.

### Phase 3: Precision 1m Execution & Scale-Out Rules
* **Entry**: On confirmation of 5m CISD + IFVG alignment during RTH (09:45–15:30 ET, excluding 11:30–13:30 lunch lull).
* **Stop Loss**: 2-bar swing extreme or $1.8\times \text{ATR}_{14}$ (whichever is larger).
* **Scale-Out Target 1 (TP1)**: $+1.0\text{R}$ on 50% of position (locks in base gain).
* **Scale-Out Target 2 (TP2)**: $+2.5\text{R}$ on remaining 50% runner.

---

## 3. 10-Year Empirical Performance Matrix (NQ1 Out-of-Sample)

| Metric | 1-Minute Baseline | 3-Minute MTF | 5-Minute MTF (Primary Model) |
| :--- | :--- | :--- | :--- |
| **Dataset Window** | 2016 – 2026 (10.2 Years) | 2016 – 2026 | **2016 – 2026 (3.61M Bars)** |
| **Total Trades** | 2,708 | 2,699 | **2,660 (~21 trades/mo)** |
| **Win Rate %** | 40.92% | 45.31% | **49.96% (~50.0%)** |
| **TP1 Reach Rate %** | 32.27% | 38.01% | **41.17%** |
| **TP2 Reach Rate %** | 14.99% | 17.23% | **19.29%** |
| **Profit Factor** | 1.00 | 1.10 | **1.44** |
| **10-Year Net PnL ($)** | $+\$324.50$ | $+\$23,037.35$ | **$+\$84,809.14** |
| **Max Drawdown ($)** | $-\$9,625.39$ | $-\$11,807.36$ | **$-\$8,718.20** |
| **Sharpe Ratio** | 0.01 | 0.46 | **1.80** |

---

## 4. Architectural Implementation & Usage

```python
from scripts.trading_framework.strategies.registry import get_strategy
from scripts.trading_framework.core.multi_contract_backtester import MultiContractBacktester

# 1. Instantiate Strategy via Registry
strategy = get_strategy("ifvg_cisd", ticker="NQ1")

# 2. Generate Signals
signals = strategy.generate_signals(df_1m, config={
    "resample_tf": "5min",
    "max_trades_per_day": 1,
    "r_mult_tp1": 1.0,
    "r_mult_tp2": 2.5,
    "filter_lunch": True,
})

# 3. Simulate Backtest
backtester = MultiContractBacktester(contracts=2, tp1_qty_pct=0.5, point_value=2.0)
results = backtester.run(signals, df_1m)
```
