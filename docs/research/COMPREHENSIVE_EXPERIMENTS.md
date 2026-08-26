# Comprehensive RSI + Filter Experiments

_Generated: 2026-08-26 13:05_

_Data: ES+NQ 09-26 MergeBackAdjusted 5m, 2025-01-01 -> 2026-08-21_

---

## Part 1: RSI Variants on BB (ES only)

| Variant | Trades | WR | PF | Net $ | Avg R |
| :--- | :---: | :---: | :---: | :---: | :---: |
| wilder_33_67 | 25 | 48.0% | 1.12 | $+109 | +0.325 |
| wilder_35_65 | 26 | 46.2% | 1.06 | $+58 | +0.269 |
| wilder_40_60 | 30 | 43.3% | 0.84 | $-198 | +0.127 |
| adaptive_zones | 15 | 46.7% | 1.05 | $+34 | +0.417 |
| adaptive_relaxed | 31 | 45.2% | 0.87 | $-160 | +0.235 |
| chande_dmi | 12 | 33.3% | 0.28 | $-501 | -0.635 |
| kaufman_er | 16 | 56.2% | 1.90 | $+450 | +0.730 |
| ehlers_cycle | 10 | 60.0% | 2.03 | $+296 | +0.211 |
| connors_rsi | 6 | 50.0% | 0.39 | $-208 | -0.326 |
| wilder_33_67_2bar | 48 | 54.2% | 1.14 | $+240 | +0.183 |
| chande_dmi_2bar | 22 | 31.8% | 0.24 | $-918 | -0.650 |
| kaufman_er_2bar | 28 | 60.7% | 1.81 | $+652 | +0.471 |
| connors_2bar | 16 | 37.5% | 0.45 | $-382 | -0.451 |
| wilder_33_67_short | 14 | 64.3% | 2.12 | $+420 | +0.885 |
| chande_short | 5 | 20.0% | 0.14 | $-309 | -0.870 |
| kaufman_short | 11 | 63.6% | 2.12 | $+389 | +1.113 |
| wilder_33_67_ib0.6 | 32 | 50.0% | 1.02 | $+21 | +0.207 |
| chande_ib0.6 | 16 | 37.5% | 0.26 | $-609 | -0.548 |

## Part 2: NQ Addition

| Variant | Trades | WR | PF | Net $ | Avg R |
| :--- | :---: | :---: | :---: | :---: | :---: |

## Part 3: Supertrend Filters

| Variant | Trades | WR | PF | Net $ | Avg R |
| :--- | :---: | :---: | :---: | :---: | :---: |
| ST_baseline | 762 | 38.3% | 1.50 | $+1876 | +0.289 |
| ST_atr_regime | 353 | 40.5% | 1.56 | $+1059 | +0.383 |
| ST_time_filter | 478 | 42.3% | 1.80 | $+1958 | +0.463 |
| ST_htf_skip | 762 | 38.3% | 1.50 | $+1876 | +0.289 |
| ST_atr+time | 250 | 42.0% | 1.79 | $+1046 | +0.526 |
| ST_atr+htf | 353 | 40.5% | 1.56 | $+1059 | +0.383 |
| ST_time+htf | 478 | 42.3% | 1.80 | $+1958 | +0.463 |
| ST_all_filters | 250 | 42.0% | 1.79 | $+1046 | +0.526 |
| ST_atr+time_1.0trail | 250 | 55.6% | 3.37 | $+1844 | +0.564 |