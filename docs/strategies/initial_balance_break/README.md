# Initial Balance (IB) Multi-Variant Strategy Framework

## 1. Overview
**Objective**: Trade Initial Balance (IB) range expansions and reversions across global trading sessions, leveraging dynamic 5-minute Fair Value Gap (FVG) and Inversion FVG (IFVG) bias models.

*   **Primary Assets**: NQ1 (Nasdaq 100), ES1 (S&P 500), CL1 (Crude Oil), GC1 (Gold)
*   **Timeframe**: 5-minute bars
*   **Sessions**: 
    *   **RTH** (Regular Trading Hours): Starts at **09:30 AM ET**
    *   **Globex**: Starts at **06:00 PM (18:00) ET**
    *   **Tokyo**: Starts at **07:00 PM (19:00) ET**

---

## 2. Validated Results (Historical & Multi-Asset 2024–2025)

Extensive multi-variant validation sweeps confirm highly profitable edges across global futures assets:

| Ticker | Config Name | Session | Duration | Variant | Level | Trades | Win Rate % | Profit Factor | Sharpe | Return % |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **NQ1** | RTH_45m_PreBreak_Q25 | RTH | 45m | `pre_break` | `q_25` | 187 | **54.0%** | **1.43** | **1.50** | **+21.12%** |
| **CL1** | Globex_45m_PostBreak_Edge_FVG_Inversion | Globex | 45m | `post_break` | `ib_edge` | 429 | **49.0%** | **1.13** | **0.75** | **+10.15%** |
| **NQ1** | RTH_30m_PreBreak_Fib50 | RTH | 30m | `pre_break` | `fib_50` | 102 | **58.8%** | **1.54** | **1.56** | **+6.83%** |
| **NQ1** | Globex_45m_PostBreak_Edge_FVG_Inversion | Globex | 45m | `post_break` | `ib_edge` | 443 | **54.0%** | **1.11** | **0.65** | **+5.12%** |
| **ES1** | Globex_45m_PostBreak_Edge_FVG_Inversion | Globex | 45m | `post_break` | `ib_edge` | 428 | **52.1%** | **1.11** | **0.69** | **+3.80%** |
| **CL1** | Tokyo_60m_PostBreak_Fib618 | Tokyo | 60m | `post_break` | `fib_618` | 302 | **59.9%** | **1.20** | **1.14** | **+2.91%** |
| **NQ1** | Tokyo_60m_PostBreak_Fib618 | Tokyo | 60m | `post_break` | `fib_618` | 241 | **66.4%** | **1.33** | **1.37** | **+2.14%** |
| **GC1** | Tokyo_60m_PostBreak_Fib618 | Tokyo | 60m | `post_break` | `fib_618` | 321 | **63.9%** | **1.15** | **0.76** | **+1.51%** |

> [!IMPORTANT]
> **Key Finding**:
> *   **RTH Reversion (`pre_break`)**: Perfect for highly volatile indices/metals inside the range before breakouts. NQ1 (`+21.12%`) and GC1 (`+0.26%`) excel here.
> *   **Globex Momentum + FVG Inversion**: Inverting the first hour's FVG dynamically unlocks high-expectancy trend breakout continuation across overnight indices/commodities (CL1 `+10.15%`, ES1 `+3.80%`, YM1 `+3.09%`, RTY1 `+2.90%`).

---

## 3. 🔬 Comprehensive Strategy Documentation

Deep-dive analytical findings and complete system guides are preserved in the [**research/**](research/) folder:

*   **[Validation Results (All Tickers)](research/VALIDATION_RESULTS.md)**: Full performance matrix with Sharpe, drawdown, and MAE/MFE excursions.
*   **[Bias Effectiveness Report](research/BIAS_COMPARISON_REPORT.md)**: Quantitative comparison of IB Close, FVG, and FVG Inversion bias filters over 5 years.
*   **[Strategy Complete Guide](research/STRATEGY_COMPLETE_GUIDE.md)**: Conceptual guide detailing pullback and breakout mechanics.

---

## 4. 📂 Backtest Data (CSV)

Raw backtest trade files and matrix sweep results are located in the [**results/**](results/) folder:

*   **[Multi-Asset Sweep Matrix Results](results/multi_asset_matrix_results.csv)**: Detailed results for NQ1, ES1, RTY1, YM1, GC1, CL1.
*   **[NQ1 Parameter Matrix Results](results/matrix_results.csv)**: Sweep logs across 15 configurations on NQ.

---

## 5. Strategy Implementation Reference

The modular strategy core and sweep pipeline adhere strictly to **ADR-017 (Zero-Loop requirement)**:
*   **Core Strategy**: [initial_balance_pullback.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/initial_balance/core/initial_balance_pullback.py)
*   **Matrix Sweep Script**: [verify_multi_asset_comprehensive.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/initial_balance/tests/verify_multi_asset_comprehensive.py)
