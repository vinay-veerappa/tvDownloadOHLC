# Reversal Strategies

This category focuses on identifying price exhaustion and false breakout reversals using the high-performance **ADR-017 Modular Architecture**.

---

## 🏗️ Architectural Standard: ADR-017

All reversal hunters in this folder are **100% Vectorized ("Zero-Loop")**, designed for massive hyperparameter sweeps using the Optuna framework.

### Mandatory Interface
Each hunter implements the standard research interface:
- `hunt(data, params)`: Returns a standardized Signal DataFrame.
- `get_param_grid()`: Defines the search space for optimization.

---

## 🏹 Strategy Inventory

### 1. Box Reversion (False Breakout)
**Overview**: Detects false breakouts of key session levels (RTH Open, NY1 Session High/Low, or user-defined boxes).
- **Core Signal**: Price breaks a box high/low by `break_offset` ATR, then reverses and closes back inside the box.
- **Filters**: Trend-aware and ADX-based exhaustion filters.
- **File**: [box_reversion.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/reversal/core/box_reversion.py)

### 2. Mean Reversion (Bollinger)
**Overview**: Identifying over-extended price action relative to statistical volatility bands.
- **Core Signal**: Price closes outside the Bollinger Upper/Lower band and then reverses back inside the band on a follow-up candle.
- **Technical Layers**: Uses Bollinger Bands (Standard Dev) and ATR-based stop/target generation.
- **File**: [mean_reversion.py](file:///c:/Users/vinay/tvDownloadOHLC/scripts/strategies/reversal/core/mean_reversion.py)

---

## 🧪 Validation Results (ADR-017 Audit)

Verified across 10 days of **NQ1** 1-minute data:

| Hunter | Status | Logic | Sample Count |
| :--- | :--- | :--- | :--- |
| **Box Reversion** | **✅ Verified** | False Breakout | 9 signals |
| **Mean Reversion** | **✅ Verified** | BB Excursion | 2 signals |

---

### 🛡️ Institutional Guidance
These strategies should be utilized during **Low-Regime** or **Exhaustion** sessions as identified by the [Unified Bias Algorithm](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/ADR.md).
