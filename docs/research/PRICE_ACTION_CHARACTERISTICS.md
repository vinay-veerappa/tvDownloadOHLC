# Price-Action Characteristic Analysis

_Generated: 2026-08-26 12:45_

_Data: ES 09-26 MergeBackAdjusted 5m, 2025-01-01 -> 2026-08-21_

_Confluence data: FVG 5m, HTF levels (PDH/PDL/PWH/PWL), Liquidity sweeps_

---

## 1. BB Mean Reversion — Signal Funnel Diagnosis

Total raw BB touches (close beyond band, 11:30-16:00 ET): **137**
Touches with RSI extreme (<33/>67): **98**
Touches with hook back inside: **68**
Touches passing ADX<25: **99**
Touches passing IB<0.4: **104**
Touches passing ALL E14 filters: **28**
Final trades (after risk cap + TP1 valid): **26**

### Filter Choke Points:
| Filter | Rejected | Cumulative Pass |
| :--- | :---: | :---: |
| Raw touches | - | 137 |
| RSI extreme | 39 | 98 |
| Hook back | 30 | 68 |
| ADX<25 | -31 | 99 |
| IB<0.4 | -5 | 104 |
| All E14 | 76 | 28 |


## 2. BB Characteristics vs Trade Outcomes (quartile bins)

| Characteristic | Bin | N | WR | Avg R | Total P&L | Avg MFE(R) | Avg MAE(R) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| displacement_bps | Q1(low) | 7 | 14.3% | +1.584 | $+323 | 0.00 | 0.00 |
| displacement_bps | Q2 | 6 | 16.7% | +0.270 | $+309 | 0.00 | 0.00 |
| displacement_bps | Q3 | 6 | 16.7% | -0.791 | $-675 | 0.00 | 0.00 |
| displacement_bps | Q4(high) | 7 | 14.3% | -0.340 | $-140 | 0.00 | 0.00 |
| rsi_at_touch | Q1(low) | 7 | 14.3% | -0.236 | $-132 | 0.00 | 0.00 |
| rsi_at_touch | Q2 | 6 | 16.7% | -0.105 | $-40 | 0.00 | 0.00 |
| rsi_at_touch | Q3 | 6 | 16.7% | +1.747 | $+363 | 0.00 | 0.00 |
| rsi_at_touch | Q4(high) | 7 | 14.3% | -0.373 | $-374 | 0.00 | 0.00 |
| rsi_change | Q1(low) | 7 | 14.3% | +0.757 | $+198 | 0.00 | 0.00 |
| rsi_change | Q2 | 6 | 16.7% | +1.154 | $+29 | 0.00 | 0.00 |
| rsi_change | Q3 | 6 | 16.7% | -0.637 | $-294 | 0.00 | 0.00 |
| rsi_change | Q4(high) | 7 | 14.3% | -0.401 | $-116 | 0.00 | 0.00 |
| bandwidth | Q1(low) | 7 | 14.3% | +1.584 | $+323 | 0.00 | 0.00 |
| bandwidth | Q2 | 6 | 16.7% | +0.270 | $+309 | 0.00 | 0.00 |
| bandwidth | Q3 | 6 | 16.7% | -0.797 | $-676 | 0.00 | 0.00 |
| bandwidth | Q4(high) | 7 | 14.3% | -0.335 | $-139 | 0.00 | 0.00 |
| prior_bar_range_vs_atr | Q1(low) | 7 | 14.3% | -0.118 | $+13 | 0.00 | 0.00 |
| prior_bar_range_vs_atr | Q2 | 6 | 16.7% | +0.194 | $-102 | 0.00 | 0.00 |
| prior_bar_range_vs_atr | Q3 | 6 | 16.7% | +0.653 | $-85 | 0.00 | 0.00 |
| prior_bar_range_vs_atr | Q4(high) | 7 | 14.3% | +0.190 | $-9 | 0.00 | 0.00 |
| vwap_dist_bps | Q1(low) | 7 | 14.3% | +0.684 | $+15 | 0.00 | 0.00 |
| vwap_dist_bps | Q2 | 6 | 16.7% | +0.291 | $+82 | 0.00 | 0.00 |
| vwap_dist_bps | Q3 | 6 | 16.7% | +0.292 | $+157 | 0.00 | 0.00 |
| vwap_dist_bps | Q4(high) | 7 | 14.3% | -0.385 | $-437 | 0.00 | 0.00 |

## 3. Supertrend Characteristics vs Trade Outcomes (quartile bins)

| Characteristic | Bin | N | WR | Avg R | Total P&L | Avg MFE(R) | Avg MAE(R) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| flip_disp_bps | Q1(low) | 191 | 34.0% | +0.210 | $+151 | 1.50 | 1.74 |
| flip_disp_bps | Q2 | 190 | 34.2% | +0.144 | $+105 | 1.38 | 1.61 |
| flip_disp_bps | Q3 | 191 | 40.8% | +0.236 | $+479 | 1.44 | 1.80 |
| flip_disp_bps | Q4(high) | 190 | 44.2% | +0.568 | $+1140 | 1.78 | 2.08 |
| band_dist_bps | Q1(low) | 191 | 40.3% | +0.553 | $+695 | 1.86 | 1.58 |
| band_dist_bps | Q2 | 190 | 40.0% | +0.232 | $+598 | 1.47 | 1.64 |
| band_dist_bps | Q3 | 190 | 38.9% | +0.132 | $+554 | 1.31 | 1.77 |
| band_dist_bps | Q4(high) | 191 | 34.0% | +0.240 | $+29 | 1.45 | 2.23 |
| atr_5m | Q1(low) | 193 | 23.3% | -0.212 | $-485 | 1.07 | 1.89 |
| atr_5m | Q2 | 188 | 37.8% | +0.257 | $+17 | 1.51 | 1.98 |
| atr_5m | Q3 | 193 | 39.4% | +0.118 | $-41 | 1.29 | 1.70 |
| atr_5m | Q4(high) | 188 | 53.2% | +1.013 | $+2385 | 2.24 | 1.66 |
| st_atr | Q1(low) | 192 | 24.5% | -0.162 | $-429 | 1.12 | 1.80 |
| st_atr | Q2 | 189 | 39.2% | +0.301 | $+118 | 1.56 | 1.80 |
| st_atr | Q3 | 190 | 37.4% | +0.155 | $+59 | 1.34 | 1.77 |
| st_atr | Q4(high) | 191 | 52.4% | +0.866 | $+2128 | 2.08 | 1.86 |
| atr_regime_pct | Q1(low) | 199 | 29.6% | -0.102 | $-196 | 1.14 | 1.71 |
| atr_regime_pct | Q2 | 183 | 37.2% | +0.546 | $+505 | 1.83 | 1.85 |
| atr_regime_pct | Q3 | 190 | 38.4% | +0.201 | $+75 | 1.40 | 1.76 |
| atr_regime_pct | Q4(high) | 190 | 48.4% | +0.541 | $+1492 | 1.76 | 1.91 |
| vwap_dist_bps | Q1(low) | 191 | 38.2% | +0.197 | $+96 | 1.48 | 1.97 |
| vwap_dist_bps | Q2 | 190 | 30.5% | +0.032 | $+66 | 1.26 | 1.81 |
| vwap_dist_bps | Q3 | 190 | 37.4% | +0.193 | $+323 | 1.41 | 1.80 |
| vwap_dist_bps | Q4(high) | 191 | 47.1% | +0.734 | $+1392 | 1.94 | 1.63 |
| fvg_dist_bps | Q1(low) | 191 | 40.8% | +0.173 | $+197 | 1.35 | 1.86 |
| fvg_dist_bps | Q2 | 190 | 36.3% | +0.213 | $+458 | 1.42 | 1.72 |
| fvg_dist_bps | Q3 | 190 | 34.7% | +0.489 | $+543 | 1.79 | 1.82 |
| fvg_dist_bps | Q4(high) | 191 | 41.4% | +0.282 | $+678 | 1.53 | 1.82 |

## 4. Confluence Impact (FVG, HTF Levels, Liquidity Sweeps)


### BB_E14

| Confluence | Filter | N | WR | Avg R | Total P&L |
| :--- | :--- | :---: | :---: | :---: | :---: |
| has_fvg_confluence | has_fvg_confluence | 4 | 25.0% | -0.731 | $-145 |
| has_fvg_confluence | NOT has_fvg_confluence | 22 | 4.5% | +0.387 | $-38 |
| at_htf_level | at_htf_level | 8 | 12.5% | -0.202 | $+3 |
| at_htf_level | NOT at_htf_level | 18 | 5.6% | +0.400 | $-186 |
| had_liquidity_sweep | had_liquidity_sweep | 26 | 3.8% | +0.215 | $-183 |

### ST_S09

| Confluence | Filter | N | WR | Avg R | Total P&L |
| :--- | :--- | :---: | :---: | :---: | :---: |
| has_fvg_confluence | has_fvg_confluence | 73 | 32.9% | +0.141 | $-76 |
| has_fvg_confluence | NOT has_fvg_confluence | 689 | 38.9% | +0.305 | $+1953 |
| at_htf_level | at_htf_level | 83 | 33.7% | +0.100 | $+71 |
| at_htf_level | NOT at_htf_level | 679 | 38.9% | +0.313 | $+1806 |
| had_liquidity_sweep | had_liquidity_sweep | 762 | 38.3% | +0.289 | $+1877 |

## 5. Key Statistical Findings & Recommendations

### BB — Characteristics That Discriminate Winners


### Supertrend — Characteristics That Discriminate Winners

- **flip_disp_bps**: Q1 WR=34.0% vs Q4 WR=44.2% (delta +10.2%) -> HIGHER values win more
- **band_dist_bps**: Q1 WR=40.3% vs Q4 WR=34.0% (delta -6.3%) -> LOWER values win more
- **atr_5m**: Q1 WR=23.3% vs Q4 WR=53.2% (delta +29.9%) -> HIGHER values win more
- **st_atr**: Q1 WR=24.5% vs Q4 WR=52.4% (delta +27.9%) -> HIGHER values win more
- **atr_regime_pct**: Q1 WR=29.6% vs Q4 WR=48.4% (delta +18.8%) -> HIGHER values win more
- **vwap_dist_bps**: Q1 WR=38.2% vs Q4 WR=47.1% (delta +8.9%) -> HIGHER values win more

---

_Correlates indicator characteristics (displacement, RSI depth, ADX, bandwidth, VWAP distance, FVG confluence, HTF level proximity, liquidity sweeps) with trade outcomes to find the statistical edge for trade structuring._