# OR Re-test Forensics Report
**Generated**: 2026-01-08 18:27
**Total Days Analyzed**: 28807

## CL1_1m Strategy Forensics
### 1. Touch Analysis
- **Total Days Scanned**: 4481
- **Days with Retest**: 4283 (95.6%)
- **Total Retest Events (Raw)**: 713659
- **Retest Events Analyzed (Filtered)**: 3250
- **First Retest Success (Continuation)**: 2610 (**80.3%**)
- **First Retest Failure (Reversal)**: 640 (**19.7%**) - CRITICAL
- *Filter applied: Min Pre-Retest Displacement > 0.5x OR Height*

### 1.1 Sensitivity: Excluding First 5 Mins (09:30-09:35)
| Metric | All First Retests | Excluding 9:30-9:35 | Delta |
| :--- | :--- | :--- | :--- |
| **Count** | 3250 | 1770 | -1480 |
| **Win Rate** | 80.3% | 81.7% | +1.4% |
| **Failure Rate** | 19.7% | 18.3% | -1.4% |

### 1.2 Hourly Isolation Analysis (Performance by Hour)
Comparing each hour's performance independent of volume:

| Hour (EST) | Count | Share% | Win Rate | Fail Rate |
| :--- | :--- | :--- | :--- | :--- |
| **09:00** | 2853 | 87.8% | **80.4%** | 19.6% |
| **10:00** | 273 | 8.4% | **79.1%** | 20.9% |
| **11:00** | 63 | 1.9% | **77.8%** | 22.2% |
| **12:00** | 23 | 0.7% | **95.7%** | 4.3% |
| **13:00** | 20 | 0.6% | **80.0%** | 20.0% |
| **14:00** | 16 | 0.5% | **75.0%** | 25.0% |
| **15:00** | 2 | 0.1% | **100.0%** | 0.0% |

### 2. Timing Forensics (EST)
- **Mode Retest Time**: 09:32 (Most frequent time for First Retest)
- **Median Retest Time**: 09:34

### 3. Risk/Reward Forensics (Time Agnostic)
- **Avg MFE**: +1.2978% Price / 8.89x OR Height
- **Avg MAE (Heat)**: -0.0690% Price / -0.33x OR Height
- **Implied Reward:Risk**: 27.11R

### 4. Winner Turn-Around Profile (Where do Survivors Stop?)
Analyzing 2610 successful continuations:
| Depth Bucket | Count | % of Winners |
|---|---|---|
| **Kiss (<25%)** | 1568.0 | **60.1%** |
| **Shallow (25-50%)** | 468.0 | **17.9%** |
| **Deep (50-75%)** | 226.0 | **8.7%** |
| **Critical (75-100%)** | 198.0 | **7.6%** |

### 5. Hourly Precision Matrices (First Retest Only)
> **Distribution**: % of all First Retests that start in this 5-min window.
**Distribution**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 45.5% | 26.2% | 7.6% | 4.4% | 2.6% | 1.6% |
| **10:00** | 1.8% | 1.4% | 0.9% | 0.7% | 0.6% | 0.4% | 1.0% | 0.4% | 0.3% | 0.2% | 0.4% | 0.2% |
| **11:00** | 0.2% | 0.3% | 0.1% | 0.3% | 0.1% | 0.1% | 0.1% | 0.2% | 0.1% | 0.1% | 0.0% | 0.3% |
| **12:00** | 0.2% | 0.1% | 0.0% | 0.0% | - | 0.0% | 0.1% | 0.0% | 0.1% | 0.1% | 0.0% | 0.1% |
| **13:00** | 0.0% | 0.2% | - | - | 0.1% | - | 0.2% | 0.0% | 0.1% | - | - | 0.0% |
| **14:00** | 0.1% | - | 0.1% | 0.0% | 0.1% | 0.1% | - | - | 0.1% | 0.0% | 0.0% | - |
| **15:00** | - | - | - | - | 0.0% | 0.0% | - | - | - | - | - | - |

> **Failure Rate**: % of First Retests in this window that FAIL (Reversal).
**Failure Rate**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 21% | 18% | 13% | 22% | 28% | 16% |
| **10:00** | 32% | 13% | 13% | 12% | 16% | 21% | 34% | 14% | 20% | 14% | 23% | 0% |
| **11:00** | 43% | 22% | 25% | 20% | 0% | 0% | 33% | 40% | 0% | 67% | 0% | 10% |
| **12:00** | 14% | 0% | 0% | 0% | - | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| **13:00** | 0% | 29% | - | - | 33% | - | 0% | 100% | 0% | - | - | 0% |
| **14:00** | 0% | - | 0% | 0% | 0% | 75% | - | - | 0% | 0% | 100% | - |
| **15:00** | - | - | - | - | 0% | 0% | - | - | - | - | - | - |

### 6. Visual Distribution
![CL1_1m Time Dist](charts/CL1_1m_time_dist.png)

---

## ES1_1m Strategy Forensics
### 1. Touch Analysis
- **Total Days Scanned**: 4621
- **Days with Retest**: 4406 (95.3%)
- **Total Retest Events (Raw)**: 658639
- **Retest Events Analyzed (Filtered)**: 3124
- **First Retest Success (Continuation)**: 2601 (**83.3%**)
- **First Retest Failure (Reversal)**: 523 (**16.7%**) - CRITICAL
- *Filter applied: Min Pre-Retest Displacement > 0.5x OR Height*

### 1.1 Sensitivity: Excluding First 5 Mins (09:30-09:35)
| Metric | All First Retests | Excluding 9:30-9:35 | Delta |
| :--- | :--- | :--- | :--- |
| **Count** | 3124 | 1605 | -1519 |
| **Win Rate** | 83.3% | 83.4% | +0.1% |
| **Failure Rate** | 16.7% | 16.6% | -0.1% |

### 1.2 Hourly Isolation Analysis (Performance by Hour)
Comparing each hour's performance independent of volume:

| Hour (EST) | Count | Share% | Win Rate | Fail Rate |
| :--- | :--- | :--- | :--- | :--- |
| **09:00** | 2809 | 89.9% | **83.1%** | 16.9% |
| **10:00** | 177 | 5.7% | **83.1%** | 16.9% |
| **11:00** | 58 | 1.9% | **87.9%** | 12.1% |
| **12:00** | 20 | 0.6% | **85.0%** | 15.0% |
| **13:00** | 19 | 0.6% | **78.9%** | 21.1% |
| **14:00** | 25 | 0.8% | **88.0%** | 12.0% |
| **15:00** | 15 | 0.5% | **86.7%** | 13.3% |
| **16:00** | 1 | 0.0% | **100.0%** | 0.0% |

### 2. Timing Forensics (EST)
- **Mode Retest Time**: 09:32 (Most frequent time for First Retest)
- **Median Retest Time**: 09:34

### 3. Risk/Reward Forensics (Time Agnostic)
- **Avg MFE**: +0.4968% Price / 6.19x OR Height
- **Avg MAE (Heat)**: -0.0209% Price / -0.25x OR Height
- **Implied Reward:Risk**: 24.45R

### 4. Winner Turn-Around Profile (Where do Survivors Stop?)
Analyzing 2601 successful continuations:
| Depth Bucket | Count | % of Winners |
|---|---|---|
| **Kiss (<25%)** | 1763.0 | **67.8%** |
| **Shallow (25-50%)** | 409.0 | **15.7%** |
| **Deep (50-75%)** | 184.0 | **7.1%** |
| **Critical (75-100%)** | 131.0 | **5.0%** |

### 5. Hourly Precision Matrices (First Retest Only)
> **Distribution**: % of all First Retests that start in this 5-min window.
**Distribution**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 48.6% | 26.0% | 8.4% | 3.6% | 1.7% | 1.6% |
| **10:00** | 1.4% | 0.7% | 0.8% | 0.5% | 0.3% | 0.2% | 0.5% | 0.4% | 0.1% | 0.3% | 0.3% | 0.1% |
| **11:00** | 0.2% | 0.2% | 0.2% | 0.1% | 0.2% | 0.3% | 0.1% | 0.1% | 0.2% | 0.1% | 0.1% | 0.2% |
| **12:00** | 0.2% | - | 0.1% | 0.0% | 0.1% | 0.2% | 0.0% | - | 0.1% | 0.1% | - | - |
| **13:00** | 0.1% | - | 0.1% | 0.0% | - | 0.1% | 0.0% | 0.1% | 0.1% | 0.0% | 0.0% | 0.0% |
| **14:00** | 0.2% | 0.2% | 0.2% | - | 0.1% | - | 0.1% | - | - | 0.1% | - | 0.1% |
| **15:00** | 0.1% | 0.1% | - | - | 0.0% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0% | 0.0% | 0.1% |

> **Failure Rate**: % of First Retests in this window that FAIL (Reversal).
**Failure Rate**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 17% | 17% | 14% | 22% | 28% | 14% |
| **10:00** | 20% | 13% | 20% | 12% | 0% | 29% | 18% | 9% | 0% | 22% | 30% | 0% |
| **11:00** | 17% | 20% | 0% | 25% | 0% | 25% | 0% | 0% | 17% | 0% | 33% | 0% |
| **12:00** | 0% | - | 0% | 0% | 50% | 20% | 0% | - | 0% | 50% | - | - |
| **13:00** | 33% | - | 33% | 0% | - | 0% | 0% | 0% | 33% | 100% | 0% | 0% |
| **14:00** | 0% | 20% | 20% | - | 0% | - | 25% | - | - | 0% | - | 0% |
| **15:00** | 33% | 0% | - | - | 0% | 0% | 50% | 0% | 0% | 0% | 0% | 0% |

### 6. Visual Distribution
![ES1_1m Time Dist](charts/ES1_1m_time_dist.png)

---

## GC1_1m Strategy Forensics
### 1. Touch Analysis
- **Total Days Scanned**: 4558
- **Days with Retest**: 4348 (95.4%)
- **Total Retest Events (Raw)**: 695518
- **Retest Events Analyzed (Filtered)**: 3259
- **First Retest Success (Continuation)**: 2590 (**79.5%**)
- **First Retest Failure (Reversal)**: 669 (**20.5%**) - CRITICAL
- *Filter applied: Min Pre-Retest Displacement > 0.5x OR Height*

### 1.1 Sensitivity: Excluding First 5 Mins (09:30-09:35)
| Metric | All First Retests | Excluding 9:30-9:35 | Delta |
| :--- | :--- | :--- | :--- |
| **Count** | 3259 | 1715 | -1544 |
| **Win Rate** | 79.5% | 80.3% | +0.9% |
| **Failure Rate** | 20.5% | 19.7% | -0.9% |

### 1.2 Hourly Isolation Analysis (Performance by Hour)
Comparing each hour's performance independent of volume:

| Hour (EST) | Count | Share% | Win Rate | Fail Rate |
| :--- | :--- | :--- | :--- | :--- |
| **09:00** | 2886 | 88.6% | **79.5%** | 20.5% |
| **10:00** | 253 | 7.8% | **79.8%** | 20.2% |
| **11:00** | 56 | 1.7% | **80.4%** | 19.6% |
| **12:00** | 24 | 0.7% | **75.0%** | 25.0% |
| **13:00** | 17 | 0.5% | **82.4%** | 17.6% |
| **14:00** | 15 | 0.5% | **73.3%** | 26.7% |
| **15:00** | 8 | 0.2% | **87.5%** | 12.5% |

### 2. Timing Forensics (EST)
- **Mode Retest Time**: 09:32 (Most frequent time for First Retest)
- **Median Retest Time**: 09:34

### 3. Risk/Reward Forensics (Time Agnostic)
- **Avg MFE**: +0.3560% Price / 8.12x OR Height
- **Avg MAE (Heat)**: -0.0161% Price / -0.32x OR Height
- **Implied Reward:Risk**: 25.46R

### 4. Winner Turn-Around Profile (Where do Survivors Stop?)
Analyzing 2590 successful continuations:
| Depth Bucket | Count | % of Winners |
|---|---|---|
| **Kiss (<25%)** | 1517.0 | **58.6%** |
| **Shallow (25-50%)** | 486.0 | **18.8%** |
| **Deep (50-75%)** | 241.0 | **9.3%** |
| **Critical (75-100%)** | 186.0 | **7.2%** |

### 5. Hourly Precision Matrices (First Retest Only)
> **Distribution**: % of all First Retests that start in this 5-min window.
**Distribution**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 47.4% | 24.5% | 8.3% | 4.4% | 2.2% | 1.7% |
| **10:00** | 2.5% | 1.1% | 1.0% | 0.8% | 0.5% | 0.3% | 0.3% | 0.3% | 0.3% | 0.4% | 0.1% | 0.1% |
| **11:00** | 0.2% | 0.2% | 0.2% | 0.2% | 0.1% | 0.2% | 0.1% | 0.2% | 0.2% | - | 0.1% | 0.2% |
| **12:00** | 0.1% | 0.1% | 0.1% | 0.1% | 0.0% | 0.0% | - | 0.2% | 0.0% | 0.1% | 0.1% | 0.0% |
| **13:00** | 0.1% | 0.0% | 0.0% | 0.1% | 0.1% | 0.2% | - | - | 0.1% | 0.1% | - | - |
| **14:00** | 0.1% | 0.1% | 0.1% | 0.0% | - | - | 0.0% | 0.1% | - | - | - | - |
| **15:00** | 0.1% | - | - | - | - | - | 0.0% | - | - | 0.1% | 0.0% | 0.0% |

> **Failure Rate**: % of First Retests in this window that FAIL (Reversal).
**Failure Rate**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 22% | 19% | 21% | 16% | 21% | 23% |
| **10:00** | 19% | 19% | 27% | 11% | 13% | 27% | 36% | 0% | 33% | 23% | 25% | 33% |
| **11:00** | 17% | 17% | 0% | 0% | 50% | 17% | 0% | 40% | 17% | - | 50% | 20% |
| **12:00** | 0% | 0% | 50% | 50% | 0% | 0% | - | 17% | 0% | 100% | 0% | 0% |
| **13:00** | 0% | 0% | 0% | 0% | 50% | 40% | - | - | 0% | 0% | - | - |
| **14:00** | 50% | 50% | 25% | 0% | - | - | 0% | 0% | - | - | - | - |
| **15:00** | 33% | - | - | - | - | - | 0% | - | - | 0% | 0% | 0% |

### 6. Visual Distribution
![GC1_1m Time Dist](charts/GC1_1m_time_dist.png)

---

## NQ1_1m Strategy Forensics
### 1. Touch Analysis
- **Total Days Scanned**: 4622
- **Days with Retest**: 4310 (93.2%)
- **Total Retest Events (Raw)**: 646454
- **Retest Events Analyzed (Filtered)**: 2959
- **First Retest Success (Continuation)**: 2383 (**80.5%**)
- **First Retest Failure (Reversal)**: 576 (**19.5%**) - CRITICAL
- *Filter applied: Min Pre-Retest Displacement > 0.5x OR Height*

### 1.1 Sensitivity: Excluding First 5 Mins (09:30-09:35)
| Metric | All First Retests | Excluding 9:30-9:35 | Delta |
| :--- | :--- | :--- | :--- |
| **Count** | 2959 | 1604 | -1355 |
| **Win Rate** | 80.5% | 80.9% | +0.4% |
| **Failure Rate** | 19.5% | 19.1% | -0.4% |

### 1.2 Hourly Isolation Analysis (Performance by Hour)
Comparing each hour's performance independent of volume:

| Hour (EST) | Count | Share% | Win Rate | Fail Rate |
| :--- | :--- | :--- | :--- | :--- |
| **09:00** | 2592 | 87.6% | **80.3%** | 19.7% |
| **10:00** | 226 | 7.6% | **84.5%** | 15.5% |
| **11:00** | 53 | 1.8% | **81.1%** | 18.9% |
| **12:00** | 30 | 1.0% | **76.7%** | 23.3% |
| **13:00** | 20 | 0.7% | **75.0%** | 25.0% |
| **14:00** | 18 | 0.6% | **72.2%** | 27.8% |
| **15:00** | 20 | 0.7% | **85.0%** | 15.0% |

### 2. Timing Forensics (EST)
- **Mode Retest Time**: 09:32 (Most frequent time for First Retest)
- **Median Retest Time**: 09:34

### 3. Risk/Reward Forensics (Time Agnostic)
- **Avg MFE**: +0.4823% Price / 5.52x OR Height
- **Avg MAE (Heat)**: -0.0288% Price / -0.31x OR Height
- **Implied Reward:Risk**: 17.55R

### 4. Winner Turn-Around Profile (Where do Survivors Stop?)
Analyzing 2383 successful continuations:
| Depth Bucket | Count | % of Winners |
|---|---|---|
| **Kiss (<25%)** | 1457.0 | **61.1%** |
| **Shallow (25-50%)** | 441.0 | **18.5%** |
| **Deep (50-75%)** | 205.0 | **8.6%** |
| **Critical (75-100%)** | 151.0 | **6.3%** |

### 5. Hourly Precision Matrices (First Retest Only)
> **Distribution**: % of all First Retests that start in this 5-min window.
**Distribution**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 45.8% | 25.0% | 7.8% | 4.4% | 2.9% | 1.8% |
| **10:00** | 2.0% | 1.2% | 0.8% | 0.6% | 0.5% | 0.4% | 0.3% | 0.3% | 0.4% | 0.3% | 0.3% | 0.3% |
| **11:00** | 0.2% | 0.2% | 0.1% | 0.1% | 0.2% | 0.2% | 0.1% | 0.2% | 0.2% | 0.1% | 0.1% | 0.0% |
| **12:00** | 0.1% | 0.2% | 0.1% | 0.0% | 0.1% | 0.1% | 0.0% | 0.0% | 0.1% | 0.1% | 0.0% | - |
| **13:00** | 0.1% | 0.1% | 0.1% | 0.1% | 0.1% | - | - | 0.1% | 0.0% | 0.1% | - | - |
| **14:00** | 0.2% | 0.0% | 0.0% | - | 0.0% | 0.1% | - | 0.1% | 0.1% | 0.1% | 0.0% | - |
| **15:00** | 0.1% | 0.0% | 0.1% | 0.0% | 0.0% | 0.1% | 0.1% | 0.1% | 0.0% | 0.0% | 0.1% | 0.0% |

> **Failure Rate**: % of First Retests in this window that FAIL (Reversal).
**Failure Rate**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 20% | 19% | 20% | 21% | 22% | 10% |
| **10:00** | 18% | 11% | 16% | 12% | 19% | 38% | 10% | 44% | 0% | 0% | 0% | 10% |
| **11:00** | 14% | 17% | 0% | 50% | 50% | 20% | 33% | 20% | 0% | 0% | 25% | 0% |
| **12:00** | 0% | 20% | 33% | 100% | 25% | 0% | 0% | 100% | 0% | 33% | 100% | - |
| **13:00** | 0% | 0% | 0% | 50% | 0% | - | - | 50% | 100% | 33% | - | - |
| **14:00** | 40% | 0% | 100% | - | 0% | 67% | - | 0% | 0% | 0% | 0% | - |
| **15:00** | 0% | 0% | 33% | 100% | 0% | 0% | 0% | 50% | 0% | 0% | 0% | 0% |

### 6. Visual Distribution
![NQ1_1m Time Dist](charts/NQ1_1m_time_dist.png)

---

## QQQ_1m Strategy Forensics
### 1. Touch Analysis
- **Total Days Scanned**: 5
- **Days with Retest**: 4 (80.0%)
- **Total Retest Events (Raw)**: 970
- **Retest Events Analyzed (Filtered)**: 2
- **First Retest Success (Continuation)**: 2 (**100.0%**)
- **First Retest Failure (Reversal)**: 0 (**0.0%**) - CRITICAL
- *Filter applied: Min Pre-Retest Displacement > 0.5x OR Height*

### 1.1 Sensitivity: Excluding First 5 Mins
> No events found after 09:35.

### 1.2 Hourly Isolation Analysis (Performance by Hour)
Comparing each hour's performance independent of volume:

| Hour (EST) | Count | Share% | Win Rate | Fail Rate |
| :--- | :--- | :--- | :--- | :--- |
| **09:00** | 2 | 100.0% | **100.0%** | 0.0% |

### 2. Timing Forensics (EST)
- **Mode Retest Time**: 09:32 (Most frequent time for First Retest)
- **Median Retest Time**: 09:33

### 3. Risk/Reward Forensics (Time Agnostic)
- **Avg MFE**: +0.2451% Price / 1.68x OR Height
- **Avg MAE (Heat)**: -nan% Price / -nanx OR Height
- **Implied Reward:Risk**: N/A (No heat)

### 4. Winner Turn-Around Profile (Where do Survivors Stop?)
Analyzing 2 successful continuations:
| Depth Bucket | Count | % of Winners |
|---|---|---|
| **Kiss (<25%)** | 2.0 | **100.0%** |
| **Shallow (25-50%)** | 0.0 | **0.0%** |
| **Deep (50-75%)** | 0.0 | **0.0%** |
| **Critical (75-100%)** | 0.0 | **0.0%** |

### 5. Hourly Precision Matrices (First Retest Only)
> **Distribution**: % of all First Retests that start in this 5-min window.
**Distribution**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 100.0% | - | - | - | - | - |

> **Failure Rate**: % of First Retests in this window that FAIL (Reversal).
**Failure Rate**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |

### 6. Visual Distribution
![QQQ_1m Time Dist](charts/QQQ_1m_time_dist.png)

---

## RTY1_1m Strategy Forensics
### 1. Touch Analysis
- **Total Days Scanned**: 2173
- **Days with Retest**: 2002 (92.1%)
- **Total Retest Events (Raw)**: 289698
- **Retest Events Analyzed (Filtered)**: 1315
- **First Retest Success (Continuation)**: 1106 (**84.1%**)
- **First Retest Failure (Reversal)**: 209 (**15.9%**) - CRITICAL
- *Filter applied: Min Pre-Retest Displacement > 0.5x OR Height*

### 1.1 Sensitivity: Excluding First 5 Mins (09:30-09:35)
| Metric | All First Retests | Excluding 9:30-9:35 | Delta |
| :--- | :--- | :--- | :--- |
| **Count** | 1315 | 744 | -571 |
| **Win Rate** | 84.1% | 82.8% | -1.3% |
| **Failure Rate** | 15.9% | 17.2% | +1.3% |

### 1.2 Hourly Isolation Analysis (Performance by Hour)
Comparing each hour's performance independent of volume:

| Hour (EST) | Count | Share% | Win Rate | Fail Rate |
| :--- | :--- | :--- | :--- | :--- |
| **09:00** | 1148 | 87.3% | **84.1%** | 15.9% |
| **10:00** | 91 | 6.9% | **79.1%** | 20.9% |
| **11:00** | 29 | 2.2% | **86.2%** | 13.8% |
| **12:00** | 15 | 1.1% | **100.0%** | 0.0% |
| **13:00** | 10 | 0.8% | **100.0%** | 0.0% |
| **14:00** | 11 | 0.8% | **81.8%** | 18.2% |
| **15:00** | 10 | 0.8% | **90.0%** | 10.0% |
| **16:00** | 1 | 0.1% | **100.0%** | 0.0% |

### 2. Timing Forensics (EST)
- **Mode Retest Time**: 09:32 (Most frequent time for First Retest)
- **Median Retest Time**: 09:34

### 3. Risk/Reward Forensics (Time Agnostic)
- **Avg MFE**: +0.7724% Price / 4.47x OR Height
- **Avg MAE (Heat)**: -0.0525% Price / -0.29x OR Height
- **Implied Reward:Risk**: 15.28R

### 4. Winner Turn-Around Profile (Where do Survivors Stop?)
Analyzing 1106 successful continuations:
| Depth Bucket | Count | % of Winners |
|---|---|---|
| **Kiss (<25%)** | 676.0 | **61.1%** |
| **Shallow (25-50%)** | 200.0 | **18.1%** |
| **Deep (50-75%)** | 107.0 | **9.7%** |
| **Critical (75-100%)** | 67.0 | **6.1%** |

### 5. Hourly Precision Matrices (First Retest Only)
> **Distribution**: % of all First Retests that start in this 5-min window.
**Distribution**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 43.5% | 25.3% | 8.8% | 5.3% | 3.2% | 1.3% |
| **10:00** | 1.8% | 0.7% | 0.9% | 0.7% | 0.5% | 0.4% | 0.5% | 0.6% | 0.2% | 0.2% | 0.2% | 0.2% |
| **11:00** | 0.4% | 0.5% | 0.1% | 0.2% | 0.3% | 0.2% | 0.2% | 0.2% | 0.2% | 0.1% | - | 0.1% |
| **12:00** | 0.1% | 0.1% | 0.3% | 0.2% | - | - | 0.2% | 0.1% | 0.2% | - | 0.1% | 0.1% |
| **13:00** | - | 0.2% | - | - | 0.1% | 0.1% | 0.1% | - | - | 0.2% | 0.2% | - |
| **14:00** | 0.2% | 0.2% | 0.2% | 0.1% | - | 0.1% | 0.1% | 0.1% | - | 0.1% | - | - |
| **15:00** | 0.1% | 0.1% | - | - | 0.1% | 0.1% | - | 0.2% | 0.1% | - | 0.2% | - |

> **Failure Rate**: % of First Retests in this window that FAIL (Reversal).
**Failure Rate**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 14% | 18% | 15% | 23% | 12% | 18% |
| **10:00** | 17% | 22% | 42% | 0% | 14% | 0% | 29% | 25% | 67% | 0% | 50% | 0% |
| **11:00** | 0% | 17% | 0% | 33% | 25% | 0% | 50% | 0% | 0% | 0% | - | 0% |
| **12:00** | 0% | 0% | 0% | 0% | - | - | 0% | 0% | 0% | - | 0% | 0% |
| **13:00** | - | 0% | - | - | 0% | 0% | 0% | - | - | 0% | 0% | - |
| **14:00** | 50% | 0% | 0% | 0% | - | 0% | 0% | 0% | - | 100% | - | - |
| **15:00** | 0% | 0% | - | - | 0% | 0% | - | 0% | 0% | - | 33% | - |

### 6. Visual Distribution
![RTY1_1m Time Dist](charts/RTY1_1m_time_dist.png)

---

## SPX_1m Strategy Forensics
### 1. Touch Analysis
- **Total Days Scanned**: 3732
- **Days with Retest**: 3336 (89.4%)
- **Total Retest Events (Raw)**: 442711
- **Retest Events Analyzed (Filtered)**: 1941
- **First Retest Success (Continuation)**: 1439 (**74.1%**)
- **First Retest Failure (Reversal)**: 502 (**25.9%**) - CRITICAL
- *Filter applied: Min Pre-Retest Displacement > 0.5x OR Height*

### 1.1 Sensitivity: Excluding First 5 Mins (09:30-09:35)
| Metric | All First Retests | Excluding 9:30-9:35 | Delta |
| :--- | :--- | :--- | :--- |
| **Count** | 1941 | 1426 | -515 |
| **Win Rate** | 74.1% | 74.8% | +0.6% |
| **Failure Rate** | 25.9% | 25.2% | -0.6% |

### 1.2 Hourly Isolation Analysis (Performance by Hour)
Comparing each hour's performance independent of volume:

| Hour (EST) | Count | Share% | Win Rate | Fail Rate |
| :--- | :--- | :--- | :--- | :--- |
| **09:00** | 1435 | 73.9% | **71.6%** | 28.4% |
| **10:00** | 293 | 15.1% | **79.2%** | 20.8% |
| **11:00** | 73 | 3.8% | **75.3%** | 24.7% |
| **12:00** | 46 | 2.4% | **84.8%** | 15.2% |
| **13:00** | 31 | 1.6% | **90.3%** | 9.7% |
| **14:00** | 40 | 2.1% | **92.5%** | 7.5% |
| **15:00** | 23 | 1.2% | **87.0%** | 13.0% |

### 2. Timing Forensics (EST)
- **Mode Retest Time**: 09:32 (Most frequent time for First Retest)
- **Median Retest Time**: 09:35

### 3. Risk/Reward Forensics (Time Agnostic)
- **Avg MFE**: +0.5114% Price / 4.98x OR Height
- **Avg MAE (Heat)**: -0.0400% Price / -0.32x OR Height
- **Implied Reward:Risk**: 15.72R

### 4. Winner Turn-Around Profile (Where do Survivors Stop?)
Analyzing 1439 successful continuations:
| Depth Bucket | Count | % of Winners |
|---|---|---|
| **Kiss (<25%)** | 849.0 | **59.0%** |
| **Shallow (25-50%)** | 255.0 | **17.7%** |
| **Deep (50-75%)** | 161.0 | **11.2%** |
| **Critical (75-100%)** | 107.0 | **7.4%** |

### 5. Hourly Precision Matrices (First Retest Only)
> **Distribution**: % of all First Retests that start in this 5-min window.
**Distribution**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 26.5% | 23.6% | 10.3% | 6.5% | 4.0% | 2.9% |
| **10:00** | 3.0% | 2.3% | 1.7% | 1.2% | 0.8% | 0.9% | 1.4% | 1.0% | 0.9% | 0.6% | 0.7% | 0.6% |
| **11:00** | 0.5% | 0.2% | 0.4% | 0.3% | 0.4% | 0.6% | 0.5% | 0.2% | 0.2% | 0.2% | 0.3% | 0.2% |
| **12:00** | 0.3% | 0.3% | 0.4% | 0.1% | 0.2% | 0.3% | 0.2% | 0.2% | 0.1% | 0.2% | 0.1% | 0.2% |
| **13:00** | 0.2% | 0.3% | 0.2% | - | 0.1% | 0.1% | 0.3% | 0.1% | 0.2% | 0.2% | 0.1% | - |
| **14:00** | 0.3% | 0.3% | 0.2% | 0.2% | 0.2% | 0.4% | 0.3% | 0.1% | 0.1% | 0.1% | 0.1% | 0.2% |
| **15:00** | 0.1% | 0.2% | - | 0.1% | 0.1% | 0.1% | 0.2% | 0.1% | 0.1% | 0.2% | 0.2% | - |

> **Failure Rate**: % of First Retests in this window that FAIL (Reversal).
**Failure Rate**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 28% | 36% | 26% | 17% | 19% | 18% |
| **10:00** | 24% | 22% | 18% | 33% | 13% | 6% | 15% | 32% | 6% | 50% | 15% | 9% |
| **11:00** | 22% | 25% | 29% | 50% | 43% | 36% | 0% | 25% | 0% | 33% | 17% | 0% |
| **12:00** | 0% | 40% | 29% | 0% | 0% | 20% | 0% | 0% | 0% | 33% | 50% | 0% |
| **13:00** | 25% | 0% | 0% | - | 0% | 0% | 17% | 100% | 0% | 0% | 0% | - |
| **14:00** | 17% | 0% | 0% | 0% | 0% | 14% | 0% | 0% | 0% | 0% | 0% | 33% |
| **15:00** | 100% | 0% | - | 0% | 0% | 0% | 67% | 0% | 0% | 0% | 0% | - |

### 6. Visual Distribution
![SPX_1m Time Dist](charts/SPX_1m_time_dist.png)

---

## YM1_1m Strategy Forensics
### 1. Touch Analysis
- **Total Days Scanned**: 4615
- **Days with Retest**: 4327 (93.8%)
- **Total Retest Events (Raw)**: 630237
- **Retest Events Analyzed (Filtered)**: 2909
- **First Retest Success (Continuation)**: 2390 (**82.2%**)
- **First Retest Failure (Reversal)**: 519 (**17.8%**) - CRITICAL
- *Filter applied: Min Pre-Retest Displacement > 0.5x OR Height*

### 1.1 Sensitivity: Excluding First 5 Mins (09:30-09:35)
| Metric | All First Retests | Excluding 9:30-9:35 | Delta |
| :--- | :--- | :--- | :--- |
| **Count** | 2909 | 1585 | -1324 |
| **Win Rate** | 82.2% | 83.0% | +0.8% |
| **Failure Rate** | 17.8% | 17.0% | -0.8% |

### 1.2 Hourly Isolation Analysis (Performance by Hour)
Comparing each hour's performance independent of volume:

| Hour (EST) | Count | Share% | Win Rate | Fail Rate |
| :--- | :--- | :--- | :--- | :--- |
| **09:00** | 2514 | 86.4% | **81.6%** | 18.4% |
| **10:00** | 232 | 8.0% | **87.1%** | 12.9% |
| **11:00** | 74 | 2.5% | **85.1%** | 14.9% |
| **12:00** | 28 | 1.0% | **82.1%** | 17.9% |
| **13:00** | 19 | 0.7% | **84.2%** | 15.8% |
| **14:00** | 16 | 0.6% | **81.2%** | 18.8% |
| **15:00** | 26 | 0.9% | **80.8%** | 19.2% |

### 2. Timing Forensics (EST)
- **Mode Retest Time**: 09:32 (Most frequent time for First Retest)
- **Median Retest Time**: 09:34

### 3. Risk/Reward Forensics (Time Agnostic)
- **Avg MFE**: +0.5087% Price / 5.62x OR Height
- **Avg MAE (Heat)**: -0.0270% Price / -0.29x OR Height
- **Implied Reward:Risk**: 19.62R

### 4. Winner Turn-Around Profile (Where do Survivors Stop?)
Analyzing 2390 successful continuations:
| Depth Bucket | Count | % of Winners |
|---|---|---|
| **Kiss (<25%)** | 1532.0 | **64.1%** |
| **Shallow (25-50%)** | 408.0 | **17.1%** |
| **Deep (50-75%)** | 193.0 | **8.1%** |
| **Critical (75-100%)** | 145.0 | **6.1%** |

### 5. Hourly Precision Matrices (First Retest Only)
> **Distribution**: % of all First Retests that start in this 5-min window.
**Distribution**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 45.5% | 25.6% | 7.4% | 3.9% | 2.4% | 1.5% |
| **10:00** | 1.9% | 1.0% | 1.1% | 0.7% | 0.6% | 0.5% | 0.6% | 0.3% | 0.5% | 0.2% | 0.3% | 0.2% |
| **11:00** | 0.3% | 0.2% | 0.2% | 0.3% | 0.2% | 0.3% | 0.1% | 0.2% | 0.1% | 0.2% | 0.2% | 0.2% |
| **12:00** | 0.1% | 0.0% | 0.0% | 0.1% | 0.1% | 0.1% | 0.2% | 0.1% | 0.1% | 0.0% | 0.1% | - |
| **13:00** | 0.1% | 0.2% | 0.0% | 0.1% | - | - | 0.0% | 0.1% | 0.1% | 0.0% | 0.0% | 0.0% |
| **14:00** | 0.0% | 0.2% | - | 0.0% | 0.1% | 0.0% | 0.0% | 0.1% | - | 0.1% | - | - |
| **15:00** | 0.1% | 0.0% | 0.1% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0% | 0.0% | 0.1% | 0.1% | 0.2% |

> **Failure Rate**: % of First Retests in this window that FAIL (Reversal).
**Failure Rate**

| Hour | 00 | 05 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 | 50 | 55 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **9:00** | - | - | - | - | - | - | 19% | 18% | 19% | 12% | 24% | 13% |
| **10:00** | 23% | 3% | 16% | 10% | 11% | 0% | 6% | 20% | 21% | 0% | 0% | 14% |
| **11:00** | 12% | 14% | 50% | 10% | 60% | 0% | 0% | 20% | 0% | 14% | 0% | 0% |
| **12:00** | 0% | 100% | 0% | 0% | 33% | 0% | 20% | 50% | 0% | 100% | 0% | - |
| **13:00** | 100% | 20% | 0% | 0% | - | - | 0% | 0% | 0% | 0% | 0% | 0% |
| **14:00** | 0% | 0% | - | 0% | 50% | 100% | 0% | 33% | - | 0% | - | - |
| **15:00** | 33% | 100% | 50% | 0% | 0% | 0% | 100% | 0% | 0% | 0% | 0% | 17% |

### 6. Visual Distribution
![YM1_1m Time Dist](charts/YM1_1m_time_dist.png)

---
