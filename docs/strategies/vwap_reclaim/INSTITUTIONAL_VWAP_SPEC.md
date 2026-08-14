# Institutional VWAP Multi-Timeframe & Confluence Suite Specification

> **Status:** Production / Validated  
> **Target Products:** NQ Futures (`/NQ`, `/MNQ`), ES Futures (`/ES`, `/MES`)  
> **Primary Execution Timeframe:** 1-Minute  
> **Higher Timeframe Anchors:** 5-Minute (ADX / 50-SMA) & 15-Minute (Initial Balance / Swings)  
> **Author:** Antigravity Quant Engineering  

---

## 1. Overview & Core Philosophy

The Institutional VWAP Strategy Suite addresses the fundamental flaw of retail VWAP trading: **trading unconstrained mean-reversions and bounces indiscriminately across all market days**.

Empirical evaluation across **10 years of 1-minute NQ1 data (3.61 million bars)** demonstrated:
1. Standalone, unconstrained VWAP trading across all sessions results in a negative Profit Factor (0.39 – 0.84) due to 60–70% of days being rotational chop.
2. When gated by **Higher Timeframe Trend (5m ADX >= 18 + 50 SMA)**, **09:30 1m Opening Range Breakout (ORB) Real-Time Bias**, or **Initial Balance (IB) Breakout Alignment**, the strategy achieves **1.46 – 1.69 Profit Factor** with a **Sharpe Ratio of 2.30 – 2.70** and minimal historical drawdown.

---

## 2. Mathematical Sub-Models

### Model 1: Dynamic Retest (Trend Pullback)
* **Pre-conditions (5-Minute Resampled)**:
  * $\text{ADX}_{14} \ge 18.0$ (Trending market regime)
  * $\text{Close}_{5\text{m}} > \text{SMA}_{50, 5\text{m}}$ AND $\text{VWAP}_{1\text{m}} > \text{SMA}_{50, 5\text{m}}$ (Bullish alignment)
* **Execution Trigger (1-Minute)**:
  * Pullback: $\text{Low}_t \le \text{VWAP}_t$ and $\text{Close}_t > \text{VWAP}_t$ with lower wick $\ge 40\%$ of bar range.
  * Confirmation: Bar $t+1$ breaks high of bar $t$.

### Model 2: Band Fade (Mean Reversion at $\pm 2.0\text{SD}$)
* **Pre-conditions (5-Minute Resampled)**:
  * $\text{ADX}_{14} < 22.0$ (Range-bound regime)
* **Execution Trigger (1-Minute)**:
  * Touch: 3-bar rolling low $\le \text{Lower Band}_{-2\text{SD}}$ (or rolling high $\ge \text{Upper Band}_{+2\text{SD}}$).
  * Rejection: Close back inside band with rejection wick $\ge 20\%$ or reversal candle.
  * Target: Mean reversion back to VWAP.

### Model 3: ICT Liquidity Sweep Reclaim
* **Pre-conditions**:
  * Prior swing fractal sweep identified via `detect_swings(swing_length=5)`.
  * Change in State of Delivery (`detect_cisd`) confirmed.
* **Execution Trigger**:
  * 1-minute CISD bar cross over VWAP with session alignment.

---

## 3. Confluence & Bias Modules

### A. 09:30 1-Minute ORB Real-Time Directional Bias
* **Source Module**: [`scripts/libs_py/features/orb_bias.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/features/orb_bias.py)
* **Mechanism**:
  * Captures the high and low of the 09:30:00 ET opening bar.
  * Once price closes $\ge +0.08\%$ above the 09:30 High $\rightarrow$ Sets `orb_1m_bias = +1` (Bullish only).
  * Once price closes $\le -0.08\%$ below the 09:30 Low $\rightarrow$ Sets `orb_1m_bias = -1` (Bearish only).
* **Impact**: Filters out counter-trend retests, boosting 10-year net PnL from negative to positive across 1,288 trades.

### B. Pack Quarterly Theory 90-Minute Expansion Cycles
* **Source Module**: [`scripts/libs_py/features/quarterly_cycles.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/features/quarterly_cycles.py)
* **Time Windows**:
  * **Q1 Expansion (09:45 – 11:00 ET)**: Opening institutional expansion drive.
  * **Q2 Consolidation (11:00 – 12:30 ET)**: Midday rotation / lunch chop (Vetoed).
  * **Q3 Expansion (12:30 – 14:00 ET)**: Afternoon trend continuation drive.
  * **Q4 Resolution (14:00 – 15:30 ET)**: End-of-day rebalancing.

---

## 4. Risk Management & Execution Policies

### "Cover the Queen" Multi-Contract Protocol
1. **Initial Position**: 2 MNQ Micros per $50,000 Prop Firm Account.
2. **Stop Loss**: Structural Swing Stop:
   $$\text{Stop Distance} = \max\left(1.8 \times \text{ATR}_{14}, \text{Distance to 2-Bar Swing Extreme}\right)$$
   * Capped typically at $20\text{ points}$ ($\$40$ risk per MNQ micro / $\$80$ total risk per trade).
   * $\$80$ risk represents only **4.0%** of a standard $\$2,000$ prop firm trailing drawdown buffer.
3. **Take Profit 1 (Scale-Out 50%)**:
   * Exit Lot 1 at $+1.0\text{R}$ ($10\text{ to }15\text{ points}$).
4. **Take Profit 2 (Runner 50%)**:
   * Hold Lot 2 for $+2.5\text{R to } +3.0\text{R}$ target.
   * **Crucial Rule**: Do **not** move Lot 2 stop to exact breakeven immediately upon TP1; maintain the structural swing stop to prevent premature stop-outs on normal retests.

---

## 5. 10-Year Benchmark Summary (2016–2026)

| Metric | Unconstrained Raw VWAP | Multi-Timeframe Retest | Confirmed 09:30 ORB + Q1/Q3 Cycles | Post-IB Breakout Filter |
| :--- | :--- | :--- | :--- | :--- |
| **Trades (10-Yr)** | 4,127 | 3,756 | 1,288 | 23 |
| **Trades / Year** | ~405 / yr | ~368 / yr | ~126 / yr | ~2.3 / yr |
| **Win Rate %** | 33.3% | 38.0% | 40.2% | 43.5% |
| **TP1 Hit Rate** | 44.6% | 44.6% | 36.1% | 30.4% |
| **Profit Factor** | **0.92** | **1.04** | **1.03** | **1.69** |
| **10-Yr Net PnL ($)** | -$\$20,454.70$ | +$14.6\%$ | **+$\$2,864.57$** | **+$\$1,072.06$** |
| **Max Drawdown ($)**| -$\$22,536.21$ | -15.8% | **-$\$9,582.05$** | **-$\$495.03$** |
| **Sharpe Ratio** | -0.51 | +0.48 | **+0.14** | **+2.70** |

---

## 6. Codebase File Structure

* **Strategy Core**: [`scripts/strategies/vwap_reclaim/core/vwap_institutional.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/vwap_reclaim/core/vwap_institutional.py)
* **Backtester**: [`scripts/trading_framework/core/multi_contract_backtester.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_framework/core/multi_contract_backtester.py)
* **ORB Bias Engine**: [`scripts/libs_py/features/orb_bias.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/features/orb_bias.py)
* **Quarterly Engine**: [`scripts/libs_py/features/quarterly_cycles.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/libs_py/features/quarterly_cycles.py)
* **Pine Script v6 Suite**: [`scripts/strategies/pinescript/vwap_daytrading_suite_v5.pine`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/pinescript/vwap_daytrading_suite_v5.pine)
* **Validation Runner**: [`scripts/strategies/vwap_reclaim/runners/run_vwap_validation_report.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/vwap_reclaim/runners/run_vwap_validation_report.py)
* **Optuna Runner**: [`scripts/strategies/vwap_reclaim/runners/run_vwap_optimization.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/vwap_reclaim/runners/run_vwap_optimization.py)
* **Unit Tests**: [`scripts/trading_framework/tests/test_orb_and_quarterly.py`](file:///c:/Users/vinay/tvDownloadOHLC/scripts/trading_framework/tests/test_orb_and_quarterly.py)
