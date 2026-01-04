# Machine Learning Bias Prediction Report

**Ticker**: NQ1  
**Samples**: 4,605 trading days (80/20 train/test split)  
**Generated**: January 3, 2026

---

## Model Performance Comparison

| Approach | Accuracy | vs Baseline |
|----------|----------|-------------|
| **Random Guess** | 17% | — |
| **Rule-Based Algorithm** | 31% | +82% |
| **Logistic Regression** | 67.9% | **+299%** |
| **Random Forest** | 66.9% | +294% |
| **Gradient Boosting** | 67.0% | +294% |

---

## Feature Importance (Gradient Boosting)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | **gap_pts** (London Open vs Prior Close) | **47.2%** |
| 2 | london_broken | 13.3% |
| 3 | or_vs_asia (Opening Range vs Asia) | 7.4% |
| 4 | day_of_week | 7.0% |
| 5 | aln_encoded | 6.0% |

### Key Insight
The **Gap** (price difference between London Open and Prior Day Close) is the **single most important predictor** - contributing nearly half of the model's predictive power.

---

## Classification Report (Gradient Boosting)

| Class | Precision | Recall | F1-Score | Support |
|-------|-----------|--------|----------|---------|
| LONG | 45% | 18% | 26% | 157 |
| NEUTRAL | 70% | 91% | 79% | 624 |
| SHORT | 47% | 16% | 24% | 140 |
| **Accuracy** | — | — | **67%** | 921 |

### Interpretation
- Model is **best at predicting NEUTRAL** days (70% precision, 91% recall)
- LONG/SHORT predictions are less reliable (45-47% precision) but still 3x better than random
- The model shows **class imbalance bias** - tends to predict NEUTRAL too often

---

## Recommendations for Improvement

1. **Focus on Gap Size**: Use gap > 20 pts as a strong directional filter
2. **Class Rebalancing**: Use SMOTE or class weights to improve LONG/SHORT recall
3. **Threshold Optimization**: Only trade when model confidence > 60%
4. **Ensemble with Rules**: Combine ML prediction with GOLD setups for higher conviction

---

## Files Created
- **ML Script**: `scripts/nqstats/aln_sessions/ml_bias_prediction.py`
- **Feature Matrix**: `data/ml_feature_matrix.csv`
