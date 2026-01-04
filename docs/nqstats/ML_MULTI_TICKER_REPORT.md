# Multi-Ticker ML Bias Prediction Report

**Generated**: January 3, 2026  
**Tickers**: ES1, RTY1, YM1, NQ1

---

## Cross-Ticker Model Accuracy

| Ticker | Samples | Accuracy | vs Random (17%) |
|--------|---------|----------|-----------------|
| **RTY1** | 2,167 | **67.5%** | +297% |
| **NQ1** | 4,605 | **66.9%** | +294% |
| YM1 | 4,598 | 60.5% | +256% |
| ES1 | 4,604 | 58.4% | +244% |

---

## Top Predictive Features (All Tickers)

| Rank | Feature | ES1 | RTY1 | YM1 | NQ1 | Avg |
|------|---------|-----|------|-----|-----|-----|
| 1 | **london_expansion** | 23.3% | 23.6% | 22.6% | 25.0% | **23.6%** |
| 2 | **prev_day_range** | 20.8% | 26.5% | 21.6% | 19.7% | **22.2%** |
| 3 | **gap_pts** | 19.2% | 21.8% | 18.6% | 20.5% | **20.0%** |
| 4 | london_broken | 10.4% | 6.3% | 10.9% | 10.4% | 9.5% |
| 5 | or_vs_asia | 7.1% | 6.0% | 8.7% | 5.7% | 6.9% |

### Key Insight
**London Expansion Ratio** (London range / Asia range) is the #1 predictor across all tickers, followed by **Prior Day Range** and **Gap Size**.

---

## Trading Signals (Most Recent 5 Days)

### ES1
| Date | ALN | Broken | Gap | Prediction | Confidence |
|------|-----|--------|-----|------------|------------|
| 2025-12-18 | LPEU | 0/0 | -1.0 | **LONG** | 75.6% |
| 2025-12-19 | LPEU | 0/1 | +25.8 | NEUTRAL | 66.5% |
| 2025-12-22 | LPEU | 1/1 | +33.2 | NEUTRAL | 84.7% |
| 2025-12-23 | LPED | 1/1 | -0.5 | NEUTRAL | 63.3% |
| 2025-12-24 | LPED | 1/0 | +8.0 | **LONG** | 58.4% |

### NQ1
| Date | ALN | Broken | Gap | Prediction | Confidence |
|------|-----|--------|-----|------------|------------|
| 2025-12-18 | LPEU | 0/0 | +52.2 | **LONG** | 70.2% |
| 2025-12-19 | LPEU | 0/1 | +165.2 | NEUTRAL | 63.8% |
| 2025-12-22 | LPEU | 1/1 | +204.5 | NEUTRAL | 86.6% |
| 2025-12-23 | LPED | 1/1 | -15.8 | NEUTRAL | 77.3% |
| 2025-12-24 | LPED | 1/1 | +56.2 | **SHORT** | 67.6% |

---

## Model Files

- `data/ml_models/ES1_bias_model.pkl`
- `data/ml_models/RTY1_bias_model.pkl`
- `data/ml_models/YM1_bias_model.pkl`
- `data/ml_models/NQ1_bias_model.pkl`

---

## Usage: Generate Daily Signals

```python
import joblib
from datetime import date

# Load model
model_data = joblib.load('data/ml_models/NQ1_bias_model.pkl')
model = model_data['model']
scaler = model_data['scaler']

# Create feature vector and predict
# (See ml_multi_ticker.py for feature engineering)
```

---

## Next Steps

1. **Improve LONG/SHORT precision**: Currently ~45-48%, can improve with class rebalancing
2. **Real-time integration**: Feed live session data to generate morning bias
3. **Backtest with actual entries**: Use model predictions as directional filter for intraday strategies
