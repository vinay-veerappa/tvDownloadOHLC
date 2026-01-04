# ML Price Curve Prediction System
## Comprehensive Results Documentation

**Project**: Predict NY AM/PM session price curves using pre-market features  
**Ticker**: NQ (NASDAQ Futures)  
**Last Updated**: January 4, 2026

---

## Executive Summary

> **Conclusion**: ML adds minimal value over Profiler filtering for curve shape and timing prediction. Use the Profiler's filtered curves directly.

| Task | ML Advantage | Recommendation |
|------|--------------|----------------|
| **Binary Bias (LONG/SHORT)** | +10% (60% vs 50%) | ✅ Use ML |
| **Session Timing** | +1% (33.6% vs 32.6%) | ❌ Use Profiler |
| **Curve Shape** | ~0% | ❌ Use Profiler |

---

## 1. What We Tested

### Approaches
1. **Curve Shape Classification** - Cluster curves into archetypes, predict cluster
2. **Magnitude Prediction** - Predict session high% and low%
3. **Timing Prediction** - Predict when session high/low occurs (15-min buckets)
4. **ML vs Filtered Profiler** - Compare ML against simple profiler filtering

### Data
- **Train**: 2008-2022 (3,839 sessions)
- **Out-of-Sample**: 2024-2025 (384 sessions)
- **Session**: NY AM (9:30-12:00 ET, 150 minutes)

---

## 2. Results

### Session Timing Prediction (10 buckets @ 15 min each)

| Method | Session HIGH | Session LOW |
|--------|--------------|-------------|
| Random (10 buckets) | 10% | 10% |
| Majority class | 32.6% | 31.2% |
| Filtered Profiler | 32.6% | 31.2% |
| **ML Classifier** | **33.6%** | **31.5%** |

**Conclusion**: ML gains only ~1% over profiler filtering. Not worth the complexity.

### Curve Shape Classification (5 clusters)

| Session | In-Sample | Out-of-Sample |
|---------|-----------|---------------|
| NY_AM | 35.6% | 29.4% |
| NY_PM | 44.9% | 45.8% |

**Conclusion**: Shape prediction is challenging. Degradation from IS to OOS.

### Magnitude Prediction (RMSE)

| Session | High% RMSE | Low% RMSE |
|---------|------------|-----------|
| NY_AM | 0.56% | 0.56% |
| NY_PM | 0.69% | 0.54% |

**Conclusion**: Useful for setting stop-loss bounds, but typical range is ±0.3%.

---

## 3. Why ML Doesn't Help for Timing/Curves

1. **Timing is highly variable** - Session extremes are largely random within the session
2. **Pre-market features predict direction, not timing** - Asia/London tell you bias, not when
3. **Historical filtering captures the same patterns** - ML learns the same majority buckets
4. **Curve shapes are too diverse** - Even with 5 clusters, prediction is weak

---

## 4. Recommendations

### Use the Profiler
- Filter by Asia/London conditions
- Use filtered median curves for expected path
- Use filtered HOD/LOD distributions for timing

### Use ML Binary Classifier
- For directional bias prediction (LONG/SHORT)
- 60-62% accuracy is actionable
- See `ml_binary_classifier.py`

### Don't Use ML For
- Curve shape prediction
- Session timing prediction
- Exact price level prediction

---

## 5. Files Created

### Scripts
| File | Purpose |
|------|---------|
| `scripts/research/ml_price_curves/extract_curves.py` | Extract session curves |
| `scripts/research/ml_price_curves/predict_curves.py` | Full ML pipeline |
| `scripts/research/ml_price_curves/predict_session_timing.py` | Session timing prediction |
| `scripts/research/ml_price_curves/compare_ml_vs_profiler.py` | ML vs Filtered comparison |

### Data (in `output/`)
| File | Content |
|------|---------|
| `NQ1_NY_AM_curves.npz` | 4,625 session curves |
| `NQ1_NY_AM_metrics.csv` | Session metrics |
| `ny_am_session_timing.html` | Timing distribution chart |

---

## 6. Quick Reference

```
When to use ML:
  ✅ Binary bias prediction (LONG/SHORT) → 60% accuracy

When to use Profiler Filtering:
  ✅ Session timing (when high/low occurs)
  ✅ Price curve shapes (median curves)
  ✅ HOD/LOD distributions
```

---

*End of Report*
