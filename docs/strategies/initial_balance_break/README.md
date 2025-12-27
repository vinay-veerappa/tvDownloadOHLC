# Initial Balance (IB) Break Strategy

## Overview
**Objective**: Trade breakouts of the Initial Balance range with high statistical probability based on 10 years of NQ historical data (2014-2024).

**Market**: NQ Futures ONLY (Validated)  
**Timeframe**: 5-minute bars  
**Session**: NY Regular Trading Hours (9:30 AM - 4:00 PM ET)

---

## 📊 Validated Results (Historical & Multi-Asset)

Extensive validation research (**2015-2025**) reveals that this strategy is highly sensitive to asset selection and market regime.

| Period | Asset | Trades | Win Rate | Net Return | Status |
|:---|:---|:---:|:---:|:---|:---|
| **2019-2025** | **NQ1** | 270+ | **61%** | **+11.6%** | ✅ **VALIDATED** |
| **2017-2018** | **NQ1** | 86 | 56% | +7.9% | ✅ **VALIDATED** |
| **2015-2020** | **ES1** | 85 | 67% | -3.0% | ❌ **FAIL** (Profit Factor < 1) |
| **2019-2020** | **RTY/YM** | 500+ | ~53% | -14% | ❌ **FAIL** (Too Choppy) |

> [!IMPORTANT]
> **NQ1 Specificity**: Strategy is only validated for **NQ1 (Nasdaq 100)** in modern market structures (2017+). It fails on ES, RTY, YM, and GC due to smaller average wins relative to losses.

---

## 🔬 Research & Findings

We have conducted deep-dive analysis on every mechanic of the IB Break strategy. Detailed reports are available in the [**research/**](research/) folder:

- **[Validation Results](research/VALIDATION_RESULTS.md)**: Full breakdown of historical performance by year and asset.
- **[MAE/MFE Optimization](research/MAE_MFE_FINDINGS.md)**: Analysis of trade heat and expansion potential.
- **[Stop Loss Comparison](research/STOP_LOSS_COMPARISON.md)**: Comparing fixed vs. dynamic (opposite IB) stops.
- **[Mechanism Evaluation](research/MECHANISM_EVALUATION_RESULTS.md)**: Comparing aggressive vs. pullback entry styles.
- **[Asset Optimization](research/ASSET_OPTIMIZATION_GUIDE.md)**: Why NQ works and how to filter for it.
- **[ICT Concepts](research/ICT_CONCEPTS.md)**: Alignment with Institutional Order Flow and Liquidity.

---

## 📂 Backtest Data (CSV)

Raw trade logs and comparison files are stored in the [**results/**](results/) folder:

- **[Multi-Asset Comparison](results/comparison.csv)**: Side-by-side metrics for ES, NQ, RTY, YM, GC.
- **[Timeframe Comparison](results/timeframe_comparison.csv)**: Impact of 15m vs 30m vs 60m IB windows.
- **[Pullback Stats (45m)](results/pullback_results_45min.csv)**: Detailed logs for the conservative entry variant.

---

## Strategy Definition

### Initial Balance (IB)
The **Initial Balance** is the high and low range established during the first hour of the NY session:
- **IB Period**: 9:30 AM - 10:30 AM ET
- **IB High**: Highest price during this 1-hour window
- **IB Low**: Lowest price during this 1-hour window
- **IB Midpoint**: `(IB_High + IB_Low) / 2`

### Core Statistics (Benchmark)
- **96% probability** of an IB break occurring before 4:00 PM ET.
- **83% probability** of break before 12:00 PM ET.
- **81% accuracy** in predicting break direction based on 10:30 AM close location.

## Entry Rules
1. **Wait for 10:30 AM ET** to define the IB range.
2. **Determine Bias**: 
   - Close > 50% IB → Long Bias.
   - Close < 50% IB → Short Bias.
3. **Pullback Entry (Recommended)**: Wait for a breakout, then enter on a 38.2% Fibonacci pullback toward the IB boundary.

## Exit Rules
- **Stop Loss**: Opposite side of IB range (Structural Stop).
- **Take Profit**: 0.5R (Partial) and 1.0R (Full) based on IB range size.
- **Time Exit**: Hard exit at 3:30 PM EST.

---

## Implementation
- **Logic**: `scripts/backtest/initial_balance/run_ib_backtest.py`
- **Verifier**: `scripts/backtest/initial_balance/run_comprehensive_validation.py`
