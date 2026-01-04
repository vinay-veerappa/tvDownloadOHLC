# NY Session Bias Prediction System
## Comprehensive Design & Results Documentation

**Project**: Unified Bias Prediction using ALN + Profiler + ML  
**Tickers**: NQ, ES, YM, RTY (Index Futures)  
**Last Updated**: January 3, 2026

---

## 1. Executive Summary

This system predicts **NY AM session direction (LONG/SHORT)** using pre-market data from Asia and London sessions. The final model achieves **60-62% accuracy** across 5+ years of out-of-sample validation.

### Key Results

| Ticker | Average OOS Accuracy | Consistency (Std) |
|--------|---------------------|-------------------|
| **YM1** | 62.4% | 4.5% |
| **ES1** | 62.3% | 2.8% |
| **NQ1** | 60.7% | **1.2%** (most stable) |
| RTY1 | 56.2% | 5.0% |

### vs Baseline
- **Random guess**: 50% (binary)
- **Our model**: 60-62% (**20-24% improvement**)

---

## 2. Problem Statement

**Goal**: At 8:00 AM ET, predict whether the NY AM session (9:30-12:00) will close LONG or SHORT based on overnight (Asia) and pre-market (London) data.

**Why this matters**:
- Sets directional bias for the trading day
- Filters out counter-trend trades
- Improves entry timing

---

## 3. Data Sources

All data is in `data/` directory:

| Source | File | Description |
|--------|------|-------------|
| **Profiler** | `{ticker}_profiler.json` | Session ranges, status, broken flags |
| **HOD/LOD** | `{ticker}_daily_hod_lod.json` | Daily high/low times for ICT profiles |
| **Opening Range** | `{ticker}_opening_range.json` | 9:30-9:35 OHLC |
| **TradingView** | `TV_OHLC/CME_MINI_{ticker}...csv` | 1-min OHLC for Dec 2025 |

### Session Definitions (ET)
- **Asia**: 18:00 - 02:00 (crosses midnight)
- **London**: 03:00 - 08:00
- **NY1 (AM)**: 09:30 - 12:00
- **NY2 (PM)**: 12:00 - 16:00

---

## 4. Algorithm Design

### 4.1 Rule-Based Foundation (ALN Framework)

```
STEP 1: Classify ALN Pattern (8:00 AM)
┌─────────────────────────────────────────────────────────┐
│ LPEU: London High > Asia High, London Low ≥ Asia Low   │ → Bullish
│ LPED: London Low < Asia Low, London High ≤ Asia High   │ → Bearish
│ LEA:  London breaks BOTH Asia extremes                 │ → Volatile
│ AEL:  London range inside Asia range                   │ → Wait
└─────────────────────────────────────────────────────────┘

STEP 2: Check Broken Status
┌─────────────────────────────────────────────────────────┐
│ Held/Held:   Asia held, London held     → HIGH conviction
│ Broken/Held: Asia broken, London held   → Good setup
│ Both Broken: Both broken                → LOW conviction
└─────────────────────────────────────────────────────────┘

STEP 3: Check Profiler Status (Asia/London Long or Short)
```

### 4.2 Machine Learning Enhancement

**Model Type**: Gradient Boosting Classifier (Binary: LONG/SHORT)

**Features** (16 total):
| Feature | Importance | Description |
|---------|------------|-------------|
| `london_expansion` | 20-25% | London range / Asia range |
| `prev_day_range` | 16-22% | Prior day's high-low |
| `gap_pts` | 18-20% | London open - prior close |
| `or_vs_asia` | 7-14% | Opening position vs Asia |
| `london_broken` | 6-11% | Was London range broken |
| `asia_broken` | 5-10% | Was Asia range broken |
| `aln_encoded` | 6-8% | ALN pattern (0-3) |
| `day_of_week` | 5-7% | Monday=0 to Friday=4 |
| `asia_long/short` | 3-5% | Asia session direction |
| `london_long/short` | 3-5% | London session direction |
| `gap_up/gap_down` | 2-4% | Gap > 10 pts flag |
| `prev_classic_buy/sell` | 1-3% | Prior day ICT profile |

**Class Balancing**: Sample weights to balance LONG/SHORT classes

---

## 5. Validation Results

### 5.1 Walk-Forward Validation (5 OOS Periods)

Training uses all data before test period. Each year is a separate test.

| Period | NQ1 | ES1 | YM1 | RTY1 |
|--------|-----|-----|-----|------|
| 2020 | 60.9% | 62.0% | 63.6% | 53.1% |
| 2021 | 59.8% | 59.3% | 63.2% | 49.4% |
| 2022 | 60.8% | 59.3% | **68.9%** | 60.2% |
| 2023 | 59.1% | **65.7%** | 55.0% | 63.4% |
| 2024-25 | 62.7% | 65.3% | 61.2% | 54.7% |
| **Average** | **60.7%** | **62.3%** | **62.4%** | **56.2%** |

### 5.2 December 2025 Out-of-Sample (TradingView Data)

| Ticker | Binary Model | Old 3-Class | Improvement |
|--------|--------------|-------------|-------------|
| **YM1** | **66.7%** | 44.4% | +50% |
| RTY1 | 61.1% | 0.0% | ∞ |
| ES1 | 55.6% | 50.0% | +11% |
| NQ1 | 44.4% | 22.2% | +100% |

### 5.3 In-Sample Test (2024 hold-out)

| Ticker | Train | Test | Accuracy | Long Precision | Short Precision |
|--------|-------|------|----------|----------------|-----------------|
| ES1 | 1,662 | 163 | 63.8% | 67.8% | 59.0% |
| NQ1 | 1,396 | 148 | 62.2% | 66.1% | 59.0% |
| YM1 | 1,616 | 162 | 61.7% | 72.5% | 54.0% |
| RTY1 | 518 | 166 | 54.2% | 48.3% | 58.0% |

---

## 6. Scripts & Files

### 6.1 Analysis Scripts (in `scripts/nqstats/aln_sessions/`)

| Script | Purpose |
|--------|---------|
| `analyze_aln_profiler.py` | Basic ALN pattern analysis |
| `analyze_unified_bias.py` | Combined ALN + Profiler + ICT analysis |
| `ml_bias_prediction.py` | Single-ticker 3-class ML model |
| `ml_multi_ticker.py` | Multi-ticker 3-class with signals |
| `ml_binary_classifier.py` | Binary LONG/SHORT with class balancing |
| `ml_walk_forward.py` | Walk-forward validation across 5 periods |
| `test_tv_data.py` | Test on TradingView December data |
| `test_live_data.py` | Test on live storage parquet |

### 6.2 Saved Models (in `data/ml_models/`)

| File | Description |
|------|-------------|
| `{ticker}_binary_model.pkl` | Binary classifier (RECOMMENDED) |
| `{ticker}_bias_model.pkl` | 3-class model (legacy) |

### 6.3 Documentation (in `docs/nqstats/`)

| File | Description |
|------|-------------|
| `UNIFIED_BIAS_ALGORITHM.md` | Step-by-step trading algorithm |
| `ML_BIAS_PREDICTION_REPORT.md` | Initial ML findings |
| `ML_MULTI_TICKER_REPORT.md` | Multi-ticker results |
| `BIAS_VALIDATION_REPORT.md` | Validation summary |
| `aln_sessions/ALN_PROFILER_ANALYSIS.md` | ALN pattern deep dive |

---

## 7. How to Use

### 7.1 Generate Daily Prediction

```python
import joblib
from pathlib import Path

# Load model
model_data = joblib.load('data/ml_models/NQ1_binary_model.pkl')
model = model_data['model']
scaler = model_data['scaler']
feature_cols = model_data['features']
le_aln = model_data['le_aln']

# Create feature vector (see ml_binary_classifier.py for feature engineering)
# X = [aln_encoded, asia_broken, london_broken, ...]
X_scaled = scaler.transform([X])
prediction = model.predict(X_scaled)[0]  # 'LONG' or 'SHORT'
confidence = model.predict_proba(X_scaled).max()

print(f"Prediction: {prediction} ({confidence:.0%})")
```

### 7.2 Run Walk-Forward Validation

```bash
cd c:\Users\vinay\tvDownloadOHLC
python scripts\nqstats\aln_sessions\ml_walk_forward.py
```

### 7.3 Test on New Data

```bash
# Test on TradingView data
python scripts\nqstats\aln_sessions\test_tv_data.py

# Retrain models
python scripts\nqstats\aln_sessions\ml_binary_classifier.py
```

---

## 8. Future Improvements

### 8.1 To Try
- [ ] Add VIX data properly (currently uses default=20)
- [ ] Add prior day's return as feature
- [ ] Feature selection to reduce overfitting
- [ ] Hyperparameter tuning (GridSearchCV)
- [ ] Combine with intraday entry logic (IB breakout, P12 touches)

### 8.2 Production Integration
- [ ] Real-time feature generation from live data
- [ ] Morning alert system (8:00 AM ET)
- [ ] Integration with TradingView alerts
- [ ] Position sizing based on confidence

### 8.3 Research Questions
- Does accuracy vary by month/quarter?
- Are certain ALN + ICT combinations better?
- Can we predict ICT profile (Classic Buy/Sell) in advance?

---

## 9. Quick Resume Prompt

If you want to continue this work later, use this prompt:

> "I'm working on the NY Session Bias Prediction System documented in `docs/nqstats/NY_BIAS_PREDICTION_MASTER.md`. 
> 
> The system uses ALN patterns + Profiler data + ML to predict NY AM direction. Binary classifier achieves 60-62% accuracy across 5 years. 
> 
> Scripts are in `scripts/nqstats/aln_sessions/`. Models are in `data/ml_models/`.
>
> I want to [YOUR NEXT TASK]."

---

## 10. Appendix: ALN Pattern Reference

| Pattern | Condition | NY AM Bias | Probability |
|---------|-----------|------------|-------------|
| **LPEU** | London High > Asia High, Low held | Bullish | 47% of days |
| **LPED** | London Low < Asia Low, High held | Bearish | 37% of days |
| **LEA** | London breaks both | Volatile | 10% of days |
| **AEL** | London inside Asia | Wait | 6% of days |

---

*End of Documentation*
