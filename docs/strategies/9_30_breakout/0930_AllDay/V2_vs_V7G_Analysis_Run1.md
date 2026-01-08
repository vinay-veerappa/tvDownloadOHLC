# V2 vs V7G Comprehensive Strategy Analysis
## Generated: 2026-01-07 11:53:51

---

## 📊 EXECUTIVE SUMMARY

| Metric | V2 | V7G | Winner |
|--------|-----|-----|--------|
| **Trades** | 3315 | 1921 | **V2** |
| **Win Rate %** | 39.10 | 47.11 | **V7G** |
| **Total P&L** | $15,992.00 | $11,429.00 | **V2** |
| **Avg P&L** | $4.82 | $5.95 | **V7G** |
| **Avg MFE %** | 0.11 | 0.09 | **V2** |
| **Avg MAE %** | -0.07 | -0.07 | **V2** |
| **Stopped Out** | 1601 | 807 | **V7G** |
| **Stopped %** | 48.30 | 42.01 | **V7G** |
| **Avg Win** | $68.07 | $50.78 | **V2** |
| **Avg Loss** | $-35.78 | $-33.98 | **V2** |

---

## 📊 RISK PROFILING ANALYSIS

*Based on risk profiling methodology: EV, PF, SQN, Combined Edge*

### Core Risk Metrics Comparison

| Metric | V2 | V7G | Winner | Interpretation |
|--------|-----|-----|--------|----------------|
| **Expected Value (EV)** | $4.82 | $5.95 | **V7G** | Average profit per trade |
| **Profit Factor** | 1.221 | 1.331 | **V7G** | >1.25 is "acceptable", >1.5 is "good" |
| **Combined Edge** | 0.165 | 0.233 | **V7G** | Quality-adjusted edge (EV/Loss × PF) |
| **Normalized EV** | 0.0214 | 0.0264 | **V7G** | EV per unit risk |
| **SQN (System Quality Number)** | 4.30 | 2.92 | **V2** | V2 "Excellent", V7G "Good" |
| **Max Consecutive Losses** | 15 | 13 | **V7G** | Fewer max streak = safer |
| **Payoff Ratio (Win/Loss)** | 1.90 | 1.49 | **V2** | V2 captures bigger winners |
| **Edge** | 0.135 | 0.175 | **V7G** | (WR × Payoff) - LR |

### SQN Interpretation Scale
| SQN Range | Rating | Assessment |
|-----------|--------|------------|
| < 1.6 | Poor | System not tradeable |
| 1.6 - 2.0 | Below Average | Needs improvement |
| **2.0 - 3.0** | **Good** | V7G is here (2.92) |
| **3.0 - 5.0** | **Excellent** | V2 is here (4.30) |
| > 5.0 | Superb | Holy grail territory |

### Risk of Ruin Considerations

**V2 Characteristics:**
- Higher SQN (4.30) = more consistent system
- Higher payoff ratio (1.90) = bigger winners relative to losers
- BUT: 15 max consecutive losses × $35.78 avg loss = **$537 max streak loss**

**V7G Characteristics:**
- Lower SQN (2.92) = more variance in outcomes
- Higher Combined Edge (0.233) = better quality-adjusted returns
- 13 max consecutive losses × $33.98 avg loss = **$442 max streak loss**

### Key Insight

> **V2 is a higher-quality system (SQN 4.30) but with smaller average edge ($4.82/trade)**
> 
> **V7G has a better edge ($5.95/trade) but with more outcome variance (SQN 2.92)**

The choice depends on your trading style:
- **V2**: Grindier, more trades, more consistent, smaller edge per trade
- **V7G**: Fewer trades, higher win rate, better per-trade edge, more variance

### Drawdown & Recovery Analysis

| Metric | V2 | V7G | Winner |
|--------|-----|-----|--------|
| **Max Drawdown** | -$2,108 | -$1,063 | **V7G** |
| **Peak Equity** | $16,243 | $11,656 | V2 |
| **Final P&L** | $15,992 | $11,429 | V2 |
| **Return/DD Ratio** | 7.58 | 10.75 | **V7G** |
| **DD as % of Peak** | 13.0% | 9.1% | **V7G** |

**V7G has a significantly better drawdown profile:**
- 50% smaller max drawdown (-$1,063 vs -$2,108)
- Better return per unit of drawdown risk (10.75x vs 7.58x)
- More capital-efficient for prop firm trading

---

## 📈 MFE/MAE ANALYSIS (Price Percentages - Time Agnostic)

### Distribution Statistics

| Metric | V2 | V7G |
|--------|-----|-----|
| Avg MFE % | 0.108% | 0.091% |
| Median MFE % | 0.100% | 0.100% |
| 25th Pctl MFE % | 0.030% | 0.030% |
| 75th Pctl MFE % | 0.150% | 0.100% |
| Max MFE % | 1.790% | 3.200% |
| Avg MAE % | -0.074% | -0.069% |
| Median MAE % | -0.080% | -0.070% |
| 25th Pctl MAE % | -0.110% | -0.110% |
| 75th Pctl MAE % | -0.020% | -0.020% |
| Min MAE % | -0.340% | -0.230% |

### MFE/MAE by Outcome

| Outcome | Strategy | Avg MFE % | Avg MAE % | Median MFE % | Median MAE % |
|---------|----------|-----------|-----------|--------------|--------------|
| Winners | V2 | 0.181% | -0.039% | 0.150% | -0.030% |
| Losers | V2 | 0.061% | -0.097% | 0.040% | -0.110% |
| Winners | V7G | 0.130% | -0.038% | 0.100% | -0.030% |
| Losers | V7G | 0.056% | -0.097% | 0.030% | -0.110% |

---

## 🛑 STOP-OUT ANALYSIS

### Overall Stop-Out Comparison

| Metric | V2 | V7G |
|--------|-----|-----|
| Total Stopped | 1601 | 807 |
| % of Trades Stopped | 48.3% | 42.0% |
| Avg Loss on Stop | $-32.66 | $-30.28 |
| Total Stop Loss | $-52,283.00 | $-24,437.50 |

### Exit Signal Breakdown

#### V2 Exit Signals

| Exit Signal | Count | Total P&L | Avg P&L | Avg MFE % | Avg MAE % |
|-------------|-------|-----------|---------|-----------|-----------|
| MAE Exit | 1601 | $-52,283.00 | $-32.66 | 0.060% | -0.093% |
| TP1 | 1563 | $50,336.50 | $32.21 | 0.127% | -0.057% |
| TP2 | 58 | $2,182.00 | $37.62 | 0.119% | -0.030% |
| Time Exit | 93 | $15,756.50 | $169.42 | 0.605% | -0.056% |

#### V7G Exit Signals

| Exit Signal | Count | Total P&L | Avg P&L | Avg MFE % | Avg MAE % |
|-------------|-------|-----------|---------|-----------|-----------|
| MAE Exit | 750 | $-21,925.00 | $-29.23 | 0.034% | -0.091% |
| T1 | 992 | $26,440.50 | $26.65 | 0.091% | -0.050% |
| SL | 57 | $-2,512.50 | $-44.08 | 0.118% | -0.098% |
| DP1 | 55 | $-2,297.00 | $-41.76 | 0.206% | -0.101% |
| EOD Exit | 57 | $11,963.00 | $209.88 | 0.603% | -0.049% |
| DP2 | 7 | $0.00 | $0.00 | 0.646% | -0.019% |
| DP3 | 3 | $-240.00 | $-80.00 | 0.783% | -0.190% |

---

## 🔄 ENTRY/EXIT SIGNAL COMPARISON

### Entry Signal Distribution

#### V2 Entry Signals

| Entry Signal | Count | Win Rate | Total P&L | Avg P&L | Avg MFE % | Avg MAE % |
|--------------|-------|----------|-----------|---------|-----------|-----------|
| L1-09-IM-FR-MTP | 360 | 40.0% | $2,795.50 | $7.77 | 0.121% | -0.077% |
| L2-09-IM-FR-MTP | 217 | 35.9% | $-1,169.50 | $-5.39 | 0.093% | -0.085% |
| L3-09-IM-FR-MTP | 97 | 38.1% | $-62.00 | $-0.64 | 0.100% | -0.079% |
| S3-10-IM-FR-MTP | 97 | 29.9% | $-732.50 | $-7.55 | 0.088% | -0.090% |
| L4-10-IM-FR-MTP | 81 | 48.1% | $1,128.50 | $13.93 | 0.132% | -0.079% |
| S1-09-IM-FR-MTP | 381 | 39.6% | $2,390.00 | $6.27 | 0.119% | -0.076% |
| L4-09-IM-FR-MTP | 31 | 45.2% | $748.00 | $24.13 | 0.141% | -0.077% |
| L5-10-IM-FR-MTP | 62 | 46.8% | $403.50 | $6.51 | 0.101% | -0.073% |
| L6-10-IM-FR-MTP | 22 | 36.4% | $-62.50 | $-2.84 | 0.103% | -0.102% |
| S7-10-IM-FR-MTP | 12 | 33.3% | $-85.00 | $-7.08 | 0.074% | -0.103% |
| L8-11-IM-FR-MTP | 6 | 66.7% | $146.50 | $24.42 | 0.138% | -0.057% |
| S2-10-IM-FR-MTP | 49 | 40.8% | $86.00 | $1.76 | 0.112% | -0.079% |
| S4-10-IM-RE-MTP | 26 | 53.8% | $1,640.50 | $63.10 | 0.249% | -0.042% |
| S4-10-IM-FR-MTP | 83 | 44.6% | $133.00 | $1.60 | 0.103% | -0.081% |
| S5-13-IM-FR-MTP | 20 | 45.0% | $94.00 | $4.70 | 0.092% | -0.082% |
| L6-13-IM-FR-MTP | 19 | 31.6% | $-229.50 | $-12.08 | 0.081% | -0.097% |
| L5-09-IM-RE-MTP | 8 | 37.5% | $42.50 | $5.31 | 0.101% | -0.068% |
| S2-10-IM-RE-MTP | 13 | 30.8% | $28.50 | $2.19 | 0.158% | -0.062% |
| S3-09-IM-FR-MTP | 77 | 42.9% | $679.50 | $8.82 | 0.093% | -0.071% |
| L4-09-IM-RE-MTP | 8 | 50.0% | $154.00 | $19.25 | 0.170% | -0.049% |
| S2-09-IM-FR-MTP | 172 | 33.1% | $-274.00 | $-1.59 | 0.098% | -0.085% |
| L5-09-IM-FR-MTP | 10 | 40.0% | $64.50 | $6.45 | 0.152% | -0.064% |
| S6-10-IM-FR-MTP | 39 | 30.8% | $-314.00 | $-8.05 | 0.080% | -0.082% |
| S3-09-IM-RE-MTP | 57 | 36.8% | $296.50 | $5.20 | 0.113% | -0.051% |
| S5-10-IM-FR-MTP | 55 | 54.5% | $1,101.00 | $20.02 | 0.137% | -0.077% |
| S6-13-IM-FR-MTP | 21 | 33.3% | $-72.00 | $-3.43 | 0.094% | -0.092% |
| L7-14-IM-FR-MTP | 16 | 37.5% | $-61.50 | $-3.84 | 0.086% | -0.071% |
| L8-14-IM-FR-MTP | 10 | 50.0% | $4.50 | $0.45 | 0.101% | -0.081% |
| L3-09-IM-RE-MTP | 44 | 40.9% | $693.50 | $15.76 | 0.097% | -0.033% |
| S5-10-IM-RE-MTP | 23 | 69.6% | $377.00 | $16.39 | 0.098% | -0.030% |
| S4-09-IM-FR-MTP | 25 | 32.0% | $-217.50 | $-8.70 | 0.093% | -0.090% |
| S5-09-IM-FR-MTP | 11 | 72.7% | $1,117.00 | $101.55 | 0.260% | -0.054% |
| L2-09-IM-RE-MTP | 71 | 28.2% | $288.00 | $4.06 | 0.136% | -0.061% |
| L3-10-IM-FR-MTP | 80 | 37.5% | $-391.50 | $-4.89 | 0.090% | -0.081% |
| L2-10-IM-FR-MTP | 64 | 39.1% | $53.00 | $0.83 | 0.117% | -0.086% |
| L3-10-IM-RE-MTP | 25 | 48.0% | $429.50 | $17.18 | 0.087% | -0.036% |
| S7-13-IM-FR-MTP | 17 | 41.2% | $80.50 | $4.74 | 0.092% | -0.088% |
| L8-13-IM-FR-MTP | 9 | 33.3% | $-52.50 | $-5.83 | 0.066% | -0.091% |
| S9-13-IM-RE-MTP | 3 | 66.7% | $106.50 | $35.50 | 0.180% | -0.067% |
| S9-14-IM-FR-MTP | 6 | 16.7% | $-165.00 | $-27.50 | 0.065% | -0.093% |
| S10-14-IM-FR-MTP | 6 | 66.7% | $196.00 | $32.67 | 0.107% | -0.038% |
| L11-14-IM-RE-MTP | 2 | 100.0% | $175.00 | $87.50 | 0.295% | -0.025% |
| L12-14-IM-FR-MTP | 3 | 66.7% | $60.00 | $20.00 | 0.103% | -0.040% |
| S13-14-IM-FR-MTP | 1 | 0.0% | $0.00 | $0.00 | 0.000% | 0.000% |
| L14-14-IM-RE-MTP | 1 | 100.0% | $45.00 | $45.00 | 0.150% | -0.050% |
| L7-13-IM-FR-MTP | 11 | 36.4% | $-15.00 | $-1.36 | 0.115% | -0.105% |
| L9-14-IM-FR-MTP | 5 | 40.0% | $52.00 | $10.40 | 0.170% | -0.092% |
| L10-14-IM-FR-MTP | 8 | 37.5% | $24.50 | $3.06 | 0.082% | -0.085% |
| L7-10-IM-FR-MTP | 17 | 47.1% | $239.50 | $14.09 | 0.096% | -0.065% |
| S10-13-IM-FR-MTP | 4 | 0.0% | $-149.00 | $-37.25 | 0.048% | -0.115% |
| L11-13-IM-RE-MTP | 1 | 0.0% | $-3.50 | $-3.50 | 0.000% | -0.010% |
| S11-13-IM-FR-MTP | 6 | 50.0% | $55.50 | $9.25 | 0.102% | -0.053% |
| L4-10-IM-RE-MTP | 23 | 39.1% | $138.00 | $6.00 | 0.092% | -0.058% |
| L7-11-IM-FR-MTP | 8 | 37.5% | $-14.50 | $-1.81 | 0.095% | -0.080% |
| S2-09-IM-RE-MTP | 85 | 41.2% | $984.00 | $11.58 | 0.108% | -0.046% |
| S5-14-IM-FR-MTP | 14 | 21.4% | $-191.50 | $-13.68 | 0.066% | -0.087% |
| L6-14-IM-RE-MTP | 15 | 40.0% | $467.00 | $31.13 | 0.061% | -0.021% |
| L4-13-IM-FR-MTP | 23 | 47.8% | $219.00 | $9.52 | 0.108% | -0.075% |
| L6-14-IM-FR-MTP | 14 | 57.1% | $87.00 | $6.21 | 0.119% | -0.089% |
| S7-14-IM-FR-MTP | 12 | 41.7% | $94.00 | $7.83 | 0.091% | -0.061% |
| S8-14-IM-FR-MTP | 15 | 33.3% | $-36.00 | $-2.40 | 0.076% | -0.080% |
| S11-14-IM-FR-MTP | 1 | 100.0% | $44.50 | $44.50 | 0.150% | -0.060% |
| L5-14-IM-FR-MTP | 24 | 20.8% | $-486.00 | $-20.25 | 0.073% | -0.105% |
| S6-14-IM-FR-MTP | 18 | 22.2% | $-318.50 | $-17.69 | 0.075% | -0.092% |
| L6-11-IM-FR-MTP | 6 | 16.7% | $-133.50 | $-22.25 | 0.090% | -0.113% |
| S2-13-IM-FR-MTP | 4 | 75.0% | $117.50 | $29.38 | 0.115% | -0.060% |
| L4-14-IM-FR-MTP | 20 | 55.0% | $351.50 | $17.57 | 0.107% | -0.068% |
| S3-11-IM-FR-MTP | 7 | 42.9% | $40.00 | $5.71 | 0.109% | -0.081% |
| S4-13-IM-FR-MTP | 21 | 57.1% | $392.50 | $18.69 | 0.121% | -0.068% |
| L2-14-IM-FR-MTP | 8 | 25.0% | $-77.00 | $-9.62 | 0.087% | -0.082% |
| L2-10-IM-RE-MTP | 8 | 12.5% | $121.50 | $15.19 | 0.180% | -0.079% |
| L4-11-IM-RE-MTP | 5 | 40.0% | $128.00 | $25.60 | 0.194% | -0.048% |
| L6-11-IM-RE-MTP | 2 | 0.0% | $-11.50 | $-5.75 | 0.050% | -0.055% |
| S4-09-IM-RE-MTP | 24 | 33.3% | $617.50 | $25.73 | 0.167% | -0.053% |
| L9-13-IM-FR-MTP | 8 | 12.5% | $-180.00 | $-22.50 | 0.086% | -0.095% |
| L10-13-IM-FR-MTP | 5 | 0.0% | $-172.50 | $-34.50 | 0.044% | -0.106% |
| S6-10-IM-RE-MTP | 14 | 21.4% | $-39.50 | $-2.82 | 0.069% | -0.053% |
| S5-11-IM-RE-MTP | 10 | 40.0% | $75.50 | $7.55 | 0.056% | -0.018% |
| S2-11-IM-FR-MTP | 6 | 33.3% | $-24.00 | $-4.00 | 0.143% | -0.088% |
| L3-14-IM-FR-MTP | 16 | 31.2% | $-48.00 | $-3.00 | 0.088% | -0.084% |
| L3-11-IM-FR-MTP | 10 | 20.0% | $-283.50 | $-28.35 | 0.102% | -0.112% |
| S2-14-IM-FR-MTP | 10 | 50.0% | $160.00 | $16.00 | 0.119% | -0.090% |
| L3-14-IM-RE-MTP | 3 | 66.7% | $98.00 | $32.67 | 0.203% | -0.043% |
| S4-11-IM-FR-MTP | 12 | 25.0% | $-145.00 | $-12.08 | 0.114% | -0.092% |
| L5-14-IM-RE-MTP | 2 | 0.0% | $-57.50 | $-28.75 | 0.030% | -0.090% |
| L3-13-IM-FR-MTP | 19 | 15.8% | $-452.50 | $-23.82 | 0.065% | -0.093% |
| S4-13-IM-RE-MTP | 6 | 50.0% | $54.00 | $9.00 | 0.075% | -0.047% |
| L5-13-IM-FR-MTP | 22 | 40.9% | $103.00 | $4.68 | 0.094% | -0.077% |
| S7-14-IM-RE-MTP | 1 | 0.0% | $-10.00 | $-10.00 | 0.000% | -0.030% |
| L7-10-IM-RE-MTP | 4 | 50.0% | $72.50 | $18.12 | 0.082% | -0.033% |
| S3-13-IM-FR-MTP | 16 | 31.2% | $-45.50 | $-2.84 | 0.091% | -0.081% |
| S8-10-IM-RE-MTP | 3 | 0.0% | $-73.00 | $-24.33 | 0.083% | -0.073% |
| S8-13-IM-FR-MTP | 6 | 33.3% | $24.00 | $4.00 | 0.080% | -0.067% |
| S3-14-IM-FR-MTP | 9 | 55.6% | $104.00 | $11.56 | 0.133% | -0.053% |
| L5-10-IM-RE-MTP | 9 | 44.4% | $115.00 | $12.78 | 0.090% | -0.048% |
| L8-10-IM-FR-MTP | 14 | 28.6% | $-136.50 | $-9.75 | 0.088% | -0.092% |
| S9-11-IM-FR-MTP | 5 | 20.0% | $-104.50 | $-20.90 | 0.106% | -0.104% |
| S5-09-IM-RE-MTP | 7 | 14.3% | $19.00 | $2.71 | 0.069% | -0.044% |
| L6-10-IM-RE-MTP | 10 | 40.0% | $326.00 | $32.60 | 0.133% | -0.030% |
| S6-11-IM-FR-MTP | 9 | 33.3% | $17.50 | $1.94 | 0.081% | -0.078% |
| L5-11-IM-FR-MTP | 6 | 16.7% | $-159.00 | $-26.50 | 0.073% | -0.102% |
| S6-11-IM-RE-MTP | 1 | 0.0% | $-11.00 | $-11.00 | 0.000% | -0.030% |
| L2-13-IM-FR-MTP | 10 | 40.0% | $-19.50 | $-1.95 | 0.109% | -0.074% |
| L4-11-IM-FR-MTP | 11 | 45.5% | $59.00 | $5.36 | 0.132% | -0.089% |
| S3-10-IM-RE-MTP | 43 | 46.5% | $939.50 | $21.85 | 0.128% | -0.049% |
| S4-14-IM-FR-MTP | 15 | 40.0% | $-47.00 | $-3.13 | 0.095% | -0.075% |
| S9-13-IM-FR-MTP | 6 | 66.7% | $179.50 | $29.92 | 0.107% | -0.072% |
| S6-13-IM-RE-MTP | 2 | 50.0% | $44.50 | $22.25 | 0.075% | -0.010% |
| L2-11-IM-FR-MTP | 3 | 0.0% | $-147.00 | $-49.00 | 0.090% | -0.080% |
| L5-13-IM-RE-MTP | 2 | 0.0% | $-40.00 | $-20.00 | 0.060% | -0.060% |
| S8-10-IM-FR-MTP | 5 | 40.0% | $-5.50 | $-1.10 | 0.124% | -0.098% |
| S9-10-IM-RE-MTP | 1 | 0.0% | $-0.50 | $-0.50 | 0.000% | 0.000% |
| S6-09-IM-FR-MTP | 3 | 0.0% | $-231.50 | $-77.17 | 0.073% | -0.203% |
| L9-10-IM-FR-MTP | 5 | 20.0% | $-20.00 | $-4.00 | 0.038% | -0.046% |
| S7-11-IM-FR-MTP | 4 | 0.0% | $-111.50 | $-27.88 | 0.055% | -0.090% |
| S10-13-IM-RE-MTP | 2 | 50.0% | $38.00 | $19.00 | 0.075% | -0.025% |
| L8-10-IM-RE-MTP | 1 | 100.0% | $49.50 | $49.50 | 0.150% | -0.050% |
| S9-10-IM-FR-MTP | 1 | 100.0% | $49.50 | $49.50 | 0.150% | -0.010% |
| L10-11-IM-FR-MTP | 2 | 100.0% | $109.00 | $54.50 | 0.150% | -0.050% |
| S8-11-IM-FR-MTP | 2 | 50.0% | $32.50 | $16.25 | 0.085% | -0.055% |
| S5-14-IM-RE-MTP | 2 | 100.0% | $117.00 | $58.50 | 0.150% | -0.010% |
| S4-14-IM-RE-MTP | 2 | 0.0% | $-25.00 | $-12.50 | 0.055% | -0.065% |
| S6-14-IM-RE-MTP | 2 | 50.0% | $18.00 | $9.00 | 0.105% | -0.060% |
| S5-11-IM-FR-MTP | 4 | 25.0% | $-67.50 | $-16.88 | 0.058% | -0.082% |
| S7-10-IM-RE-MTP | 5 | 60.0% | $172.50 | $34.50 | 0.090% | -0.024% |
| L11-14-IM-FR-MTP | 4 | 25.0% | $-49.50 | $-12.38 | 0.052% | -0.103% |
| L11-13-IM-FR-MTP | 1 | 100.0% | $60.00 | $60.00 | 0.150% | -0.030% |
| L13-14-IM-FR-MTP | 1 | 100.0% | $60.00 | $60.00 | 0.150% | -0.020% |
| L12-13-IM-FR-MTP | 4 | 50.0% | $69.50 | $17.38 | 0.122% | -0.077% |
| L13-13-IM-RE-MTP | 5 | 40.0% | $107.50 | $21.50 | 0.060% | -0.016% |
| L13-13-IM-FR-MTP | 1 | 100.0% | $59.00 | $59.00 | 0.150% | -0.070% |
| L14-14-IM-FR-MTP | 2 | 0.0% | $-117.00 | $-58.50 | 0.030% | -0.155% |
| L15-14-IM-FR-MTP | 2 | 50.0% | $35.50 | $17.75 | 0.105% | -0.100% |
| L9-14-IM-RE-MTP | 2 | 50.0% | $-3.00 | $-1.50 | 0.085% | -0.075% |
| L6-09-IM-FR-MTP | 3 | 33.3% | $-15.50 | $-5.17 | 0.070% | -0.067% |
| S11-13-IM-RE-MTP | 1 | 100.0% | $66.50 | $66.50 | 0.150% | -0.040% |
| S12-14-IM-RE-MTP | 1 | 0.0% | $-6.50 | $-6.50 | 0.000% | -0.010% |
| S12-14-IM-FR-MTP | 1 | 0.0% | $-46.50 | $-46.50 | 0.030% | -0.110% |
| L9-11-IM-FR-MTP | 2 | 100.0% | $131.00 | $65.50 | 0.150% | -0.035% |
| S10-11-IM-RE-MTP | 1 | 0.0% | $0.00 | $0.00 | 0.000% | 0.000% |
| S11-11-IM-FR-MTP | 1 | 0.0% | $-44.50 | $-44.50 | 0.000% | -0.180% |
| S3-11-IM-RE-MTP | 1 | 100.0% | $62.00 | $62.00 | 0.150% | -0.020% |
| L6-13-IM-RE-MTP | 2 | 0.0% | $-64.00 | $-32.00 | 0.000% | -0.075% |
| L6-09-IM-RE-MTP | 1 | 100.0% | $63.50 | $63.50 | 0.150% | -0.020% |
| S10-10-IM-FR-MTP | 2 | 100.0% | $130.00 | $65.00 | 0.150% | -0.045% |
| L4-14-IM-RE-MTP | 2 | 50.0% | $488.50 | $244.25 | 0.585% | 0.000% |
| S3-14-IM-RE-MTP | 3 | 0.0% | $-129.50 | $-43.17 | 0.000% | -0.100% |
| L4-13-IM-RE-MTP | 1 | 0.0% | $-30.00 | $-30.00 | 0.090% | -0.100% |
| S10-14-IM-RE-MTP | 2 | 50.0% | $26.00 | $13.00 | 0.345% | -0.080% |
| S11-14-IM-RE-MTP | 1 | 100.0% | $66.50 | $66.50 | 0.150% | -0.010% |
| S7-09-IM-RE-MTP | 1 | 0.0% | $-6.00 | $-6.00 | 0.000% | -0.010% |
| L11-10-IM-FR-MTP | 1 | 0.0% | $0.00 | $0.00 | 0.000% | 0.000% |
| L12-10-IM-FR-MTP | 1 | 0.0% | $-44.50 | $-44.50 | 0.030% | -0.100% |
| S13-11-IM-RE-MTP | 1 | 100.0% | $67.00 | $67.00 | 0.150% | -0.040% |
| S13-13-IM-FR-MTP | 2 | 0.0% | $-46.50 | $-23.25 | 0.005% | -0.050% |
| L14-13-IM-FR-MTP | 1 | 100.0% | $67.00 | $67.00 | 0.150% | -0.010% |
| S15-13-IM-FR-MTP | 1 | 100.0% | $67.00 | $67.00 | 0.150% | 0.000% |
| S7-13-IM-RE-MTP | 1 | 100.0% | $68.50 | $68.50 | 0.150% | -0.010% |
| L2-11-IM-RE-MTP | 2 | 0.0% | $-56.50 | $-28.25 | 0.040% | -0.085% |
| S7-09-IM-FR-MTP | 2 | 50.0% | $63.50 | $31.75 | 0.075% | 0.000% |
| L10-10-IM-FR-MTP | 1 | 100.0% | $65.00 | $65.00 | 0.150% | -0.010% |
| S12-13-IM-RE-MTP | 8 | 37.5% | $3.50 | $0.44 | 0.028% | -0.035% |
| S6-09-IM-RE-MTP | 3 | 66.7% | $-6.00 | $-2.00 | 0.007% | -0.010% |
| S9-11-IM-RE-MTP | 1 | 0.0% | $-51.50 | $-51.50 | 0.110% | -0.130% |
| S3-13-IM-RE-MTP | 10 | 50.0% | $69.00 | $6.90 | 0.022% | -0.006% |
| S5-13-IM-RE-MTP | 3 | 33.3% | $11.50 | $3.83 | 0.073% | -0.040% |
| L3-13-IM-RE-MTP | 2 | 0.0% | $-88.00 | $-44.00 | 0.120% | -0.125% |
| L1-10-IM-FR-MTP | 2 | 100.0% | $163.50 | $81.75 | 0.280% | -0.100% |

#### V7G Entry Signals

| Entry Signal | Count | Win Rate | Total P&L | Avg P&L | Avg MFE % | Avg MAE % |
|--------------|-------|----------|-----------|---------|-----------|-----------|
| JUDAS L | 297 | 50.2% | $1,455.50 | $4.90 | 0.068% | -0.063% |
| REV S1 | 226 | 41.2% | $3,456.00 | $15.29 | 0.130% | -0.076% |
| REV S2 | 171 | 46.2% | $982.00 | $5.74 | 0.105% | -0.067% |
| REV S3 | 107 | 49.5% | $771.00 | $7.21 | 0.104% | -0.061% |
| JUDAS S | 322 | 49.7% | $1,532.00 | $4.76 | 0.066% | -0.065% |
| REV L1 | 257 | 41.6% | $-86.50 | $-0.34 | 0.097% | -0.078% |
| REV L2 | 200 | 48.5% | $754.00 | $3.77 | 0.082% | -0.068% |
| REV L3 | 121 | 50.4% | $1,396.50 | $11.54 | 0.104% | -0.069% |
| REV L4 | 70 | 51.4% | $451.50 | $6.45 | 0.086% | -0.071% |
| REV S4 | 62 | 48.4% | $467.50 | $7.54 | 0.096% | -0.078% |
| REV L5 | 45 | 44.4% | $311.50 | $6.92 | 0.149% | -0.073% |
| REV S5 | 43 | 46.5% | $-62.00 | $-1.44 | 0.066% | -0.064% |

---

## ⏰ HOURLY ANALYSIS (ET)

### Performance by Hour

| Hour (ET) | V2 Trades | V2 Win% | V2 P&L | V7G Trades | V7G Win% | V7G P&L |
|-----------|-----------|---------|--------|------------|----------|---------|
| 09:00 | 1676 | 38.2% | $8,896 | 848 | 46.0% | $2,873 |
| 10:00 | 917 | 41.8% | $6,064 | 470 | 46.2% | $5,358 |
| 11:00 | 134 | 33.6% | $-365 | 187 | 54.5% | $1,968 |
| 12:00 | 0 | 0.0% | $0 | 114 | 52.6% | $690 |
| 13:00 | 301 | 39.5% | $586 | 105 | 43.8% | $-172 |
| 14:00 | 286 | 38.1% | $823 | 108 | 46.3% | $470 |
| 15:00 | 1 | 0.0% | $-12 | 89 | 44.9% | $244 |

### Performance by 15-Minute Buckets (After 9:30 ET)

| Time Bucket | V2 Trades | V2 Win% | V2 Avg P&L | V7G Trades | V7G Win% | V7G Avg P&L |
|-------------|-----------|---------|------------|------------|----------|-------------|
| 09:30 | 1191 | 37.9% | $4.19 | 619 | 49.9% | $4.83 |
| 09:45 | 485 | 39.0% | $8.05 | 229 | 35.4% | $-0.50 |
| 10:00 | 341 | 38.7% | $4.10 | 180 | 40.6% | $2.09 |
| 10:15 | 228 | 44.7% | $9.80 | 122 | 49.2% | $6.80 |
| 10:30 | 178 | 38.8% | $1.25 | 90 | 48.9% | $4.34 |
| 10:45 | 170 | 47.1% | $12.99 | 78 | 51.3% | $48.21 |
| 11:00 | 123 | 33.3% | $-2.99 | 58 | 44.8% | $7.70 |
| 11:15 | 11 | 36.4% | $0.23 | 53 | 62.3% | $14.21 |
| 11:30 | 0 | 0.0% | $0.00 | 35 | 54.3% | $3.60 |
| 11:45 | 0 | 0.0% | $0.00 | 41 | 58.5% | $15.66 |
| 12:00 | 0 | 0.0% | $0.00 | 30 | 50.0% | $7.85 |
| 12:15 | 0 | 0.0% | $0.00 | 34 | 55.9% | $2.99 |
| 12:30 | 0 | 0.0% | $0.00 | 21 | 57.1% | $7.21 |
| 12:45 | 0 | 0.0% | $0.00 | 29 | 48.3% | $6.93 |
| 13:00 | 94 | 38.3% | $-3.30 | 26 | 38.5% | $-6.94 |
| 13:15 | 73 | 43.8% | $4.58 | 22 | 63.6% | $12.52 |
| 13:30 | 76 | 36.8% | $3.16 | 37 | 45.9% | $3.04 |
| 13:45 | 58 | 39.7% | $5.55 | 20 | 25.0% | $-19.00 |
| 14:00 | 97 | 41.2% | $15.84 | 38 | 42.1% | $0.04 |
| 14:15 | 69 | 39.1% | $-3.70 | 28 | 53.6% | $0.11 |
| 14:30 | 69 | 31.9% | $-6.46 | 25 | 44.0% | $22.74 |
| 14:45 | 51 | 39.2% | $-0.24 | 17 | 47.1% | $-6.03 |
| 15:00 | 1 | 0.0% | $-11.50 | 33 | 42.4% | $12.03 |
| 15:15 | 0 | 0.0% | $0.00 | 25 | 32.0% | $-14.42 |
| 15:30 | 0 | 0.0% | $0.00 | 23 | 56.5% | $5.57 |
| 15:45 | 0 | 0.0% | $0.00 | 8 | 62.5% | $9.88 |

### 5-Minute Bucket Analysis (9:30-10:30 AM Focus)

| Time | V2 Trades | V2 Win% | V2 P&L | V7G Trades | V7G Win% | V7G P&L |
|------|-----------|---------|--------|------------|----------|---------|
| 09:30 | 645 | 40.6% | $5,477 | 503 | 50.9% | $3,190 |
| 09:35 | 336 | 36.0% | $566 | 102 | 46.1% | $-77 |
| 09:40 | 210 | 32.4% | $-1,049 | 14 | 42.9% | $-126 |
| 09:45 | 204 | 38.2% | $1,134 | 104 | 31.7% | $-1,151 |
| 09:50 | 163 | 40.5% | $2,656 | 73 | 28.8% | $544 |
| 09:55 | 118 | 38.1% | $112 | 52 | 51.9% | $492 |
| 10:00 | 135 | 38.5% | $1,344 | 63 | 36.5% | $627 |
| 10:05 | 99 | 37.4% | $-208 | 55 | 32.7% | $-732 |
| 10:10 | 107 | 40.2% | $263 | 62 | 51.6% | $482 |
| 10:15 | 70 | 34.3% | $-76 | 41 | 43.9% | $274 |
| 10:20 | 80 | 53.8% | $1,362 | 42 | 52.4% | $214 |
| 10:25 | 78 | 44.9% | $949 | 39 | 51.3% | $342 |
| 10:30 | 56 | 37.5% | $149 | 26 | 38.5% | $-339 |

### Entry Time Analysis (Mode/Median)

#### V2 Entry Time Patterns

- **Winning trades mode time**: 9:32
- **Losing trades mode time**: 9:32
- **Most successful hour**: 9 ($46,402)
- **Least successful hour**: 11 ($-365)

#### V7G Entry Time Patterns

- **Winning trades mode time**: 9:32
- **Losing trades mode time**: 9:32
- **Most successful hour**: 9 ($17,710)
- **Least successful hour**: 13 ($-172)

---

## 📅 DAY OF WEEK ANALYSIS

| Day | V2 Trades | V2 Win% | V2 P&L | V7G Trades | V7G Win% | V7G P&L |
|-----|-----------|---------|--------|------------|----------|---------|
| Monday | 670 | 35.2% | $56 | 392 | 45.2% | $744 |
| Tuesday | 632 | 37.3% | $657 | 345 | 44.9% | $386 |
| Wednesday | 722 | 42.4% | $6,864 | 430 | 48.8% | $2,554 |
| Thursday | 633 | 45.5% | $7,656 | 379 | 48.8% | $1,234 |
| Friday | 658 | 35.0% | $760 | 375 | 47.5% | $6,512 |

---

## 📆 MONTH BY MONTH ANALYSIS

| Year-Month | V2 Trades | V2 Win% | V2 P&L | V7G Trades | V7G Win% | V7G P&L |
|------------|-----------|---------|--------|------------|----------|---------|
| 2023-01 | 98 | 39.8% | $437 | 48 | 37.5% | $-169 |
| 2023-02 | 104 | 55.8% | $1,430 | 51 | 51.0% | $514 |
| 2023-03 | 67 | 47.8% | $483 | 46 | 54.3% | $206 |
| 2023-04 | 95 | 38.9% | $481 | 57 | 56.1% | $380 |
| 2023-05 | 109 | 31.2% | $-380 | 71 | 53.5% | $465 |
| 2023-06 | 113 | 29.2% | $-706 | 65 | 41.5% | $-154 |
| 2023-07 | 98 | 36.7% | $-10 | 60 | 56.7% | $502 |
| 2023-08 | 105 | 39.0% | $647 | 65 | 36.9% | $26 |
| 2023-09 | 102 | 32.4% | $-539 | 55 | 47.3% | $230 |
| 2023-10 | 118 | 43.2% | $750 | 60 | 46.7% | $24 |
| 2023-11 | 102 | 38.2% | $-50 | 60 | 50.0% | $34 |
| 2023-12 | 81 | 45.7% | $660 | 47 | 51.1% | $126 |
| 2024-01 | 108 | 45.4% | $696 | 66 | 47.0% | $156 |
| 2024-02 | 104 | 31.7% | $-270 | 69 | 42.0% | $102 |
| 2024-03 | 94 | 39.4% | $408 | 54 | 44.4% | $538 |
| 2024-04 | 120 | 35.8% | $214 | 57 | 40.4% | $-292 |
| 2024-05 | 100 | 40.0% | $827 | 60 | 48.3% | $208 |
| 2024-06 | 119 | 30.3% | $-234 | 85 | 44.7% | $1,228 |
| 2024-07 | 145 | 32.4% | $-796 | 77 | 37.7% | $-510 |
| 2024-08 | 63 | 33.3% | $-66 | 36 | 52.8% | $162 |
| 2024-09 | 94 | 37.2% | $470 | 44 | 47.7% | $133 |
| 2024-10 | 44 | 31.8% | $-201 | 21 | 14.3% | $-418 |
| 2024-11 | 63 | 36.5% | $22 | 44 | 50.0% | $216 |
| 2024-12 | 72 | 37.5% | $430 | 52 | 46.2% | $761 |
| 2025-01 | 65 | 41.5% | $692 | 39 | 43.6% | $80 |
| 2025-02 | 104 | 30.8% | $378 | 58 | 46.6% | $591 |
| 2025-03 | 75 | 41.3% | $1,258 | 28 | 50.0% | $398 |
| 2025-04 | 21 | 57.1% | $372 | 5 | 20.0% | $40 |
| 2025-05 | 131 | 35.9% | $-59 | 66 | 45.5% | $385 |
| 2025-06 | 72 | 38.9% | $75 | 61 | 59.0% | $360 |
| 2025-07 | 93 | 40.9% | $408 | 57 | 43.9% | $154 |
| 2025-08 | 88 | 45.5% | $730 | 56 | 51.8% | $282 |
| 2025-09 | 97 | 50.5% | $2,094 | 73 | 56.2% | $830 |
| 2025-10 | 91 | 50.5% | $2,114 | 48 | 54.2% | $3,494 |
| 2025-11 | 47 | 40.4% | $664 | 19 | 36.8% | $-347 |
| 2025-12 | 99 | 47.5% | $2,696 | 51 | 49.0% | $832 |
| 2026-01 | 14 | 35.7% | $-136 | 10 | 30.0% | $-138 |

---

## 📊 YEAR BY YEAR ANALYSIS

| Year | V2 Trades | V2 Win% | V2 P&L | V2 Avg Trade | V7G Trades | V7G Win% | V7G P&L | V7G Avg Trade |
|------|-----------|---------|--------|--------------|------------|----------|---------|---------------|
| 2023 | 1192 | 39.4% | $3,204 | $2.69 | 685 | 48.5% | $2,185 | $3.19 |
| 2024 | 1126 | 36.0% | $1,502 | $1.33 | 665 | 43.9% | $2,282 | $3.43 |
| 2025 | 983 | 42.3% | $11,422 | $11.62 | 561 | 49.6% | $7,100 | $12.66 |
| 2026 | 14 | 35.7% | $-136 | $-9.71 | 10 | 30.0% | $-138 | $-13.80 |

---

## 🎯 OPTIMAL ENTRY TIME ANALYSIS

### Best Entry Minutes (Ranked by Win Rate, min 10 trades)

#### V2 Top 10 Entry Minutes

| Time (ET) | Trades | Win Rate | Avg P&L | Total P&L |
|-----------|--------|----------|---------|-----------|
| 10:21 | 15 | 73.3% | $41.30 | $620 |
| 10:22 | 21 | 66.7% | $44.48 | $934 |
| 10:46 | 18 | 61.1% | $14.25 | $256 |
| 10:27 | 23 | 60.9% | $34.35 | $790 |
| 10:59 | 10 | 60.0% | $24.15 | $242 |
| 09:55 | 27 | 55.6% | $14.22 | $384 |
| 10:51 | 11 | 54.5% | $18.86 | $208 |
| 10:48 | 11 | 54.5% | $11.86 | $130 |
| 09:39 | 50 | 54.0% | $17.73 | $886 |
| 14:01 | 13 | 53.8% | $18.46 | $240 |

#### V7G Top 10 Entry Minutes

| Time (ET) | Trades | Win Rate | Avg P&L | Total P&L |
|-----------|--------|----------|---------|-----------|
| 10:27 | 12 | 66.7% | $11.29 | $136 |
| 09:34 | 81 | 60.5% | $10.11 | $819 |
| 10:11 | 17 | 52.9% | $5.97 | $102 |
| 09:32 | 291 | 50.5% | $7.44 | $2,166 |
| 10:04 | 12 | 50.0% | $-1.58 | $-19 |
| 09:57 | 18 | 50.0% | $10.58 | $190 |
| 09:35 | 42 | 50.0% | $5.86 | $246 |
| 10:21 | 10 | 50.0% | $4.30 | $43 |
| 09:36 | 31 | 48.4% | $-2.98 | $-92 |
| 09:33 | 131 | 45.8% | $1.57 | $206 |

### Worst Entry Minutes (Ranked by Win Rate, min 10 trades)

#### V2 Bottom 10 Entry Minutes

| Time (ET) | Trades | Win Rate | Avg P&L | Total P&L |
|-----------|--------|----------|---------|-----------|
| 11:04 | 12 | 16.7% | $-24.58 | $-295 |
| 10:19 | 11 | 18.2% | $-18.95 | $-208 |
| 10:43 | 11 | 18.2% | $-12.91 | $-142 |
| 09:43 | 41 | 19.5% | $-10.95 | $-449 |
| 09:38 | 60 | 23.3% | $-16.36 | $-982 |
| 10:07 | 25 | 24.0% | $-12.34 | $-308 |
| 10:10 | 20 | 25.0% | $-3.45 | $-69 |
| 13:34 | 12 | 25.0% | $-3.46 | $-42 |
| 09:56 | 26 | 26.9% | $-2.60 | $-68 |
| 10:42 | 11 | 27.3% | $-9.45 | $-104 |

#### V7G Bottom 10 Entry Minutes

| Time (ET) | Trades | Win Rate | Avg P&L | Total P&L |
|-----------|--------|----------|---------|-----------|
| 09:53 | 15 | 20.0% | $29.83 | $448 |
| 09:50 | 14 | 21.4% | $-16.64 | $-233 |
| 09:46 | 18 | 22.2% | $-0.42 | $-8 |
| 10:00 | 13 | 23.1% | $-19.31 | $-251 |
| 09:37 | 12 | 25.0% | $-23.92 | $-287 |
| 09:51 | 19 | 26.3% | $-6.92 | $-132 |
| 10:02 | 11 | 27.3% | $-15.23 | $-168 |
| 09:52 | 17 | 29.4% | $7.03 | $120 |
| 10:29 | 10 | 30.0% | $-12.90 | $-129 |
| 10:08 | 10 | 30.0% | $-18.30 | $-183 |

---

## 🔍 STRATEGY DISCREPANCY ANALYSIS

### Entry Signal Differences

- **V2 Entry Signals**: L6-14-IM-RE-MTP, L11-10-IM-FR-MTP, L8-11-IM-FR-MTP, S7-14-IM-FR-MTP, S3-09-IM-FR-MTP, S4-13-IM-RE-MTP, L13-13-IM-RE-MTP, S10-13-IM-FR-MTP, L3-14-IM-RE-MTP, L4-13-IM-RE-MTP, S2-10-IM-RE-MTP, S8-11-IM-FR-MTP, S9-11-IM-RE-MTP, L6-10-IM-FR-MTP, L8-14-IM-FR-MTP, L6-09-IM-RE-MTP, L7-14-IM-FR-MTP, S12-14-IM-FR-MTP, S2-09-IM-RE-MTP, L5-09-IM-RE-MTP, S13-14-IM-FR-MTP, S6-13-IM-FR-MTP, S11-14-IM-FR-MTP, L3-14-IM-FR-MTP, L5-09-IM-FR-MTP, L7-11-IM-FR-MTP, L2-13-IM-FR-MTP, L5-13-IM-FR-MTP, S9-11-IM-FR-MTP, L13-14-IM-FR-MTP, L7-10-IM-FR-MTP, L5-14-IM-FR-MTP, S10-10-IM-FR-MTP, S10-14-IM-RE-MTP, S2-10-IM-FR-MTP, L5-10-IM-RE-MTP, S6-11-IM-FR-MTP, S9-10-IM-FR-MTP, S15-13-IM-FR-MTP, S3-14-IM-FR-MTP, S3-11-IM-FR-MTP, S8-13-IM-FR-MTP, S13-13-IM-FR-MTP, L10-10-IM-FR-MTP, S4-14-IM-RE-MTP, S13-11-IM-RE-MTP, S4-13-IM-FR-MTP, S2-13-IM-FR-MTP, L14-14-IM-RE-MTP, S5-09-IM-RE-MTP, S3-13-IM-FR-MTP, L6-13-IM-RE-MTP, S5-09-IM-FR-MTP, S9-10-IM-RE-MTP, S3-10-IM-RE-MTP, L3-09-IM-FR-MTP, S7-11-IM-FR-MTP, L1-10-IM-FR-MTP, L4-11-IM-FR-MTP, L12-13-IM-FR-MTP, S5-11-IM-FR-MTP, S9-14-IM-FR-MTP, L2-11-IM-RE-MTP, S7-13-IM-FR-MTP, L12-14-IM-FR-MTP, L8-10-IM-FR-MTP, S4-09-IM-FR-MTP, S5-10-IM-FR-MTP, L6-11-IM-FR-MTP, L7-10-IM-RE-MTP, S4-11-IM-FR-MTP, L4-13-IM-FR-MTP, L3-13-IM-FR-MTP, S5-14-IM-RE-MTP, S5-14-IM-FR-MTP, L9-13-IM-FR-MTP, S7-10-IM-RE-MTP, S7-10-IM-FR-MTP, L10-13-IM-FR-MTP, S2-14-IM-FR-MTP, L5-10-IM-FR-MTP, L4-09-IM-FR-MTP, S8-14-IM-FR-MTP, L4-14-IM-FR-MTP, S6-11-IM-RE-MTP, S3-09-IM-RE-MTP, L10-11-IM-FR-MTP, L10-14-IM-FR-MTP, L11-14-IM-RE-MTP, L5-11-IM-FR-MTP, S9-13-IM-FR-MTP, S7-09-IM-RE-MTP, S11-14-IM-RE-MTP, L5-14-IM-RE-MTP, L2-10-IM-RE-MTP, L8-13-IM-FR-MTP, L13-13-IM-FR-MTP, S4-10-IM-RE-MTP, S3-11-IM-RE-MTP, S10-14-IM-FR-MTP, L11-14-IM-FR-MTP, S5-13-IM-FR-MTP, L6-13-IM-FR-MTP, S8-10-IM-RE-MTP, L2-09-IM-RE-MTP, S4-10-IM-FR-MTP, S7-14-IM-RE-MTP, L1-09-IM-FR-MTP, L3-10-IM-FR-MTP, S5-10-IM-RE-MTP, L2-10-IM-FR-MTP, S12-13-IM-RE-MTP, S6-14-IM-FR-MTP, S4-09-IM-RE-MTP, L12-10-IM-FR-MTP, L15-14-IM-FR-MTP, L5-13-IM-RE-MTP, L2-09-IM-FR-MTP, S2-09-IM-FR-MTP, L4-10-IM-FR-MTP, S1-09-IM-FR-MTP, S9-13-IM-RE-MTP, L11-13-IM-RE-MTP, S6-10-IM-RE-MTP, L3-13-IM-RE-MTP, L14-13-IM-FR-MTP, S3-10-IM-FR-MTP, S3-14-IM-RE-MTP, L11-13-IM-FR-MTP, L4-14-IM-RE-MTP, L9-11-IM-FR-MTP, L3-09-IM-RE-MTP, L8-10-IM-RE-MTP, S11-11-IM-FR-MTP, L7-13-IM-FR-MTP, S6-13-IM-RE-MTP, S4-14-IM-FR-MTP, S6-14-IM-RE-MTP, S6-10-IM-FR-MTP, L4-09-IM-RE-MTP, L9-14-IM-RE-MTP, L6-10-IM-RE-MTP, S7-09-IM-FR-MTP, L2-14-IM-FR-MTP, L2-11-IM-FR-MTP, S7-13-IM-RE-MTP, S5-11-IM-RE-MTP, S8-10-IM-FR-MTP, L4-11-IM-RE-MTP, S2-11-IM-FR-MTP, L3-11-IM-FR-MTP, L6-09-IM-FR-MTP, S5-13-IM-RE-MTP, S11-13-IM-RE-MTP, L3-10-IM-RE-MTP, S12-14-IM-RE-MTP, L4-10-IM-RE-MTP, S6-09-IM-FR-MTP, L9-10-IM-FR-MTP, L9-14-IM-FR-MTP, L6-14-IM-FR-MTP, S11-13-IM-FR-MTP, S10-13-IM-RE-MTP, S6-09-IM-RE-MTP, L6-11-IM-RE-MTP, S3-13-IM-RE-MTP, L14-14-IM-FR-MTP, S10-11-IM-RE-MTP
- **V7G Entry Signals**: JUDAS S, REV L4, REV L1, REV S3, REV S4, REV L2, REV S5, REV S1, REV L3, REV S2, REV L5, JUDAS L
- **V7G-only signals**: REV L4, REV L1, REV S3, REV S4, JUDAS L, REV L2, REV S5, REV S1, REV L3, REV S2, REV L5, JUDAS S
- **V2-only signals**: L6-14-IM-RE-MTP, L11-10-IM-FR-MTP, L8-11-IM-FR-MTP, S7-14-IM-FR-MTP, S3-09-IM-FR-MTP, S4-13-IM-RE-MTP, L13-13-IM-RE-MTP, S10-13-IM-FR-MTP, L3-14-IM-RE-MTP, L4-13-IM-RE-MTP, S2-10-IM-RE-MTP, S8-11-IM-FR-MTP, S9-11-IM-RE-MTP, L6-10-IM-FR-MTP, L8-14-IM-FR-MTP, L6-09-IM-RE-MTP, L7-14-IM-FR-MTP, S12-14-IM-FR-MTP, S2-09-IM-RE-MTP, L5-09-IM-RE-MTP, S13-14-IM-FR-MTP, S6-13-IM-FR-MTP, S11-14-IM-FR-MTP, L3-14-IM-FR-MTP, L5-09-IM-FR-MTP, L7-11-IM-FR-MTP, L2-13-IM-FR-MTP, L5-13-IM-FR-MTP, S9-11-IM-FR-MTP, L13-14-IM-FR-MTP, L7-10-IM-FR-MTP, L5-14-IM-FR-MTP, S10-10-IM-FR-MTP, S10-14-IM-RE-MTP, S2-10-IM-FR-MTP, L5-10-IM-RE-MTP, S6-11-IM-FR-MTP, S9-10-IM-FR-MTP, S15-13-IM-FR-MTP, S3-14-IM-FR-MTP, S3-11-IM-FR-MTP, S8-13-IM-FR-MTP, S13-13-IM-FR-MTP, L10-10-IM-FR-MTP, S4-14-IM-RE-MTP, S13-11-IM-RE-MTP, S4-13-IM-FR-MTP, S2-13-IM-FR-MTP, L14-14-IM-RE-MTP, S5-09-IM-RE-MTP, S3-13-IM-FR-MTP, L6-13-IM-RE-MTP, S5-09-IM-FR-MTP, S9-10-IM-RE-MTP, S3-10-IM-RE-MTP, L3-09-IM-FR-MTP, S7-11-IM-FR-MTP, L1-10-IM-FR-MTP, L4-11-IM-FR-MTP, L12-13-IM-FR-MTP, S5-11-IM-FR-MTP, S9-14-IM-FR-MTP, L2-11-IM-RE-MTP, S7-13-IM-FR-MTP, L12-14-IM-FR-MTP, L8-10-IM-FR-MTP, S4-09-IM-FR-MTP, S5-10-IM-FR-MTP, L6-11-IM-FR-MTP, L7-10-IM-RE-MTP, S4-11-IM-FR-MTP, L4-13-IM-FR-MTP, L3-13-IM-FR-MTP, S5-14-IM-RE-MTP, S5-14-IM-FR-MTP, L9-13-IM-FR-MTP, S7-10-IM-RE-MTP, S7-10-IM-FR-MTP, L10-13-IM-FR-MTP, S2-14-IM-FR-MTP, L5-10-IM-FR-MTP, L4-09-IM-FR-MTP, S8-14-IM-FR-MTP, L4-14-IM-FR-MTP, S6-11-IM-RE-MTP, S3-09-IM-RE-MTP, L10-11-IM-FR-MTP, L10-14-IM-FR-MTP, L11-14-IM-RE-MTP, L5-11-IM-FR-MTP, S9-13-IM-FR-MTP, S7-09-IM-RE-MTP, S11-14-IM-RE-MTP, L5-14-IM-RE-MTP, L2-10-IM-RE-MTP, L8-13-IM-FR-MTP, L13-13-IM-FR-MTP, S4-10-IM-RE-MTP, S3-11-IM-RE-MTP, S10-14-IM-FR-MTP, L11-14-IM-FR-MTP, S5-13-IM-FR-MTP, L6-13-IM-FR-MTP, S8-10-IM-RE-MTP, L2-09-IM-RE-MTP, S4-10-IM-FR-MTP, S7-14-IM-RE-MTP, L1-09-IM-FR-MTP, L3-10-IM-FR-MTP, S5-10-IM-RE-MTP, L2-10-IM-FR-MTP, S12-13-IM-RE-MTP, S6-14-IM-FR-MTP, S4-09-IM-RE-MTP, L12-10-IM-FR-MTP, L15-14-IM-FR-MTP, L5-13-IM-RE-MTP, L2-09-IM-FR-MTP, S2-09-IM-FR-MTP, L4-10-IM-FR-MTP, S1-09-IM-FR-MTP, S9-13-IM-RE-MTP, L11-13-IM-RE-MTP, S6-10-IM-RE-MTP, L3-13-IM-RE-MTP, L14-13-IM-FR-MTP, S3-10-IM-FR-MTP, S3-14-IM-RE-MTP, L11-13-IM-FR-MTP, L4-14-IM-RE-MTP, L9-11-IM-FR-MTP, L3-09-IM-RE-MTP, L8-10-IM-RE-MTP, S11-11-IM-FR-MTP, L7-13-IM-FR-MTP, S6-13-IM-RE-MTP, S4-14-IM-FR-MTP, S6-14-IM-RE-MTP, S6-10-IM-FR-MTP, L4-09-IM-RE-MTP, L9-14-IM-RE-MTP, L6-10-IM-RE-MTP, S7-09-IM-FR-MTP, L2-14-IM-FR-MTP, L2-11-IM-FR-MTP, S7-13-IM-RE-MTP, S5-11-IM-RE-MTP, S8-10-IM-FR-MTP, L4-11-IM-RE-MTP, S2-11-IM-FR-MTP, L3-11-IM-FR-MTP, L6-09-IM-FR-MTP, S5-13-IM-RE-MTP, S11-13-IM-RE-MTP, L3-10-IM-RE-MTP, S12-14-IM-RE-MTP, L4-10-IM-RE-MTP, S6-09-IM-FR-MTP, L9-10-IM-FR-MTP, L9-14-IM-FR-MTP, L6-14-IM-FR-MTP, S11-13-IM-FR-MTP, S10-13-IM-RE-MTP, S6-09-IM-RE-MTP, L6-11-IM-RE-MTP, S3-13-IM-RE-MTP, L14-14-IM-FR-MTP, S10-11-IM-RE-MTP

### Exit Signal Differences

- **V2 Exit Signals**: TP2, Time Exit, MAE Exit, TP1
- **V7G Exit Signals**: EOD Exit, DP3, DP2, MAE Exit, T1, DP1, SL
- **V7G-only exits**: EOD Exit, DP3, DP2, T1, DP1, SL
- **V2-only exits**: Time Exit, TP2, TP1

### Daily Trade Count Comparison

- **V2 avg trades/day**: 5.2
- **V7G avg trades/day**: 3.1
- **V2 max trades/day**: 27
- **V7G max trades/day**: 18

---

## 💔 LOSING TRADE ANALYSIS

### V2 Losing Trade Breakdown

- **Total losing trades**: 2019
- **Total loss**: $-72,231.50
- **Avg loss**: $-35.78
- **Median loss**: $-36.50
- **Worst loss**: $-250.00

#### V2 Losses by Exit Signal

| Exit Signal | Count | Total Loss | Avg Loss |
|-------------|-------|------------|----------|
| MAE Exit | 1543 | $-53,305.00 | $-34.55 |
| TP1 | 428 | $-18,752.00 | $-43.81 |
| TP2 | 39 | $-74.00 | $-1.90 |
| Time Exit | 9 | $-100.50 | $-11.17 |

#### V2 Losses by Hour

| Hour | Count | Total Loss | Avg Loss |
|------|-------|------------|----------|
| 09:00 | 1036 | $-37,506.00 | $-36.20 |
| 10:00 | 534 | $-19,099.00 | $-35.77 |
| 11:00 | 89 | $-3,144.00 | $-35.33 |
| 13:00 | 182 | $-6,425.00 | $-35.30 |
| 14:00 | 177 | $-6,046.00 | $-34.16 |
| 15:00 | 1 | $-11.50 | $-11.50 |

### V7G Losing Trade Breakdown

- **Total losing trades**: 1016
- **Total loss**: $-34,525.50
- **Avg loss**: $-33.98
- **Median loss**: $-36.50
- **Worst loss**: $-230.00

#### V7G Losses by Exit Signal

| Exit Signal | Count | Total Loss | Avg Loss |
|-------------|-------|------------|----------|
| MAE Exit | 724 | $-22,191.50 | $-30.65 |
| T1 | 158 | $-7,154.50 | $-45.28 |
| SL | 57 | $-2,512.50 | $-44.08 |
| DP1 | 55 | $-2,297.00 | $-41.76 |
| DP2 | 7 | $0.00 | $0.00 |
| EOD Exit | 12 | $-130.00 | $-10.83 |
| DP3 | 3 | $-240.00 | $-80.00 |

#### V7G Losses by Hour

| Hour | Count | Total Loss | Avg Loss |
|------|-------|------------|----------|
| 09:00 | 458 | $-14,836.50 | $-32.39 |
| 10:00 | 253 | $-8,768.50 | $-34.66 |
| 11:00 | 85 | $-3,324.50 | $-39.11 |
| 12:00 | 54 | $-1,999.00 | $-37.02 |
| 13:00 | 59 | $-2,114.00 | $-35.83 |
| 14:00 | 58 | $-2,053.00 | $-35.40 |
| 15:00 | 49 | $-1,430.00 | $-29.18 |

---

## 💡 KEY INSIGHTS & RECOMMENDATIONS

### Timing Insights

| Insight | V2 | V7G |
|---------|-----|-----|
| **Best Hour** | 9:00 ET (+$8,896) | 10:00 ET (+$5,358) |
| **Worst Hour** | 11:00 ET (-$365) | 13:00 ET (-$172) |
| **Best Day** | Thursday (+$7,656) | Friday (+$6,512) |
| **Worst Day** | Monday (+$56) | Tuesday (+$386) |
| **Best Year** | 2025 (+$11,422) | 2025 (+$7,100) |
| **Mode Entry Time (Winners)** | 9:32 | 9:32 |
| **Mode Entry Time (Losers)** | 9:32 | 9:32 |

### Entry Timing Patterns

**Both strategies have 9:32 as mode entry time for both wins AND losses**
- This is expected since most entries occur right after OR formation
- The edge is NOT in timing alone, but in the filtering and exit management

**V2 vs V7G Entry Distribution:**
- V2 concentrates 50% of trades in the 9:30-9:45 window
- V7G spreads trades more throughout the day (extends to 15:45)
- V7G's afternoon trading (12:00-16:00) adds $1,232 net profit

### Risk/Reward Insights

| Metric | V2 | V7G | Implication |
|--------|-----|-----|-------------|
| **MFE/MAE Ratio** | 1.46 | 1.32 | V2 captures more favorable excursion |
| **Profit Factor** | 1.22 | 1.33 | V7G converts risk to profit more efficiently |
| **Win Capture Rate** | 37.4%* | 39.0%* | *MFE converted to actual profit |

### Strategy Scorecard

| Dimension | V2 | V7G | Notes |
|-----------|-----|-----|-------|
| **Absolute Returns** | ⭐⭐⭐⭐ | ⭐⭐⭐ | V2: $16K vs V7G: $11K |
| **Per-Trade Edge** | ⭐⭐⭐ | ⭐⭐⭐⭐ | V7G: $5.95 vs V2: $4.82 |
| **Consistency (SQN)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | V2 SQN 4.30 is excellent |
| **Win Rate** | ⭐⭐⭐ | ⭐⭐⭐⭐ | V7G: 47% vs V2: 39% |
| **Drawdown Control** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | V7G half the drawdown |
| **Capital Efficiency** | ⭐⭐⭐ | ⭐⭐⭐⭐ | V7G: 10.75 R/DD ratio |
| **Scalability** | ⭐⭐⭐⭐ | ⭐⭐⭐ | V2: More trade opportunities |

### Actionable Recommendations

#### For Prop Firm Trading (Priority: Drawdown Control)
✅ **Recommend V7G** — Lower max DD ($1,063) and better R/DD ratio (10.75x) makes it safer for prop accounts with trailing drawdown rules.

#### For Personal Account (Priority: Absolute Returns)
✅ **Consider V2** — Higher total P&L ($15,992) and better SQN (4.30) despite larger drawdowns.

#### Hybrid Approach (Best of Both)
Consider combining:
1. **V7G's entry logic** (Judas bias, reversal structure) — higher win rate
2. **V2's exit management** (MAE filter, TP1/TP2) — better MFE capture
3. **V2's trade frequency** (15 attempts) — more opportunities

### Time-Based Trading Recommendations

| Time Window | Recommendation | Rationale |
|-------------|----------------|-----------|
| 9:30-9:45 | ✅ Trade both | Highest volume, V7G +$3K, V2 +$5K |
| 9:45-10:00 | ⚠️ V2 preferred | V7G win rate drops to 35% |
| 10:00-10:30 | ✅ Trade both | Good for both strategies |
| 10:30-11:00 | ✅ V7G preferred | V7G 48-51% WR, V2 drops |
| 11:00-12:00 | ✅ V7G only | V2 loses money, V7G profitable |
| 12:00-14:00 | ⚠️ V7G only | V2 not trading, V7G marginal |
| 14:00-15:00 | ⚠️ Caution | Both have reduced edge |
| 15:00+ | ✅ V7G only | End of day momentum plays |

---

## 📝 SUMMARY

### V2 Strengths
- Higher SQN (4.30) = more consistent system
- Better payoff ratio (1.90) = bigger winners
- More trades = more opportunities
- Higher absolute returns

### V7G Strengths
- Higher win rate (47% vs 39%)
- Better drawdown profile (50% less DD)
- Better per-trade edge ($5.95 vs $4.82)
- Better capital efficiency (10.75x R/DD)
- Extended trading hours (captures afternoon moves)

### Key Takeaway

> **V7G is the better choice for prop firm trading due to superior drawdown control.**
> 
> **V2 is better for personal accounts prioritizing total returns over consistency.**

### Next Steps for Analysis
1. Overlay with economic calendar to identify high-impact news effects
2. Compare trade clustering on specific dates
3. Analyze correlation between strategies (diversification potential)
4. Test combining V7G entries with V2 exit logic

