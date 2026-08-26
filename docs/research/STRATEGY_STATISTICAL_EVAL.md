# Strategy Statistical Evaluation (ADR-002, 010, 021, 023)

_Generated: 2026-08-26 12:29_

_Data: ES 09-26 MergeBackAdjusted 5m, 2025-01-01 → 2026-08-21_

_Engine: 1×MES $5/pt, $1.20/rt commission, 1-tick slippage_

---

## 1. Summary Metrics

### BB_E14
| Metric | Value |
| :--- | :--- |
| Trades | 24 |
| Win Rate | 45.8% |
| Profit Factor | 1.06 |
| Net P&L | $54 |
| Max Drawdown | $384 |
| Avg R | 0.323 |
| Median R | -0.031 |
| Avg MFE (R) | 2.00 |
| Avg MAE (R) | 0.71 |

### ST_S09
| Metric | Value |
| :--- | :--- |
| Trades | 762 |
| Win Rate | 38.3% |
| Profit Factor | 1.50 |
| Net P&L | $1,876 |
| Max Drawdown | $182 |
| Avg R | 0.093 |
| Median R | -0.155 |
| Avg MFE (R) | 1.27 |
| Avg MAE (R) | 1.71 |


## 2. Excursion Analysis (ADR-023)

### BB_E14 (n=24)

| Percentile | MFE (bps) | MAE (bps) | MFE (R) | MAE (R) | Risk (bps) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| p10 | 0.87 | 0.68 | 0.15 | 0.17 | 2.02 |
| p25 | 1.65 | 1.07 | 0.34 | 0.29 | 3.32 |
| p50 | 6.46 | 4.27 | 0.70 | 0.61 | 5.34 |
| p75 | 13.06 | 7.76 | 2.57 | 1.14 | 14.73 |
| p90 | 14.98 | 11.99 | 5.87 | 1.35 | 21.72 |
| p95 | 19.44 | 12.63 | 6.75 | 1.42 | 28.14 |

**Reach Probability (P[MFE ≥ threshold]):**

| Threshold | Probability |
| :--- | :---: |
| 0.5R | 58.3% |
| 1.0R | 37.5% |
| 1.5R | 37.5% |
| 2.0R | 33.3% |
| 3.0R | 20.8% |
| 5.0R | 12.5% |

**MAE-Conditioned Win-Rate Survival Curve:**

| MAE Bin | Trades | Win Rate |
| :--- | :---: | :---: |
| 0.00-0.25R | 4 | 75.0% |
| 0.25-0.50R | 7 | 71.4% |
| 0.50-0.75R | 4 | 50.0% |
| 0.75-1.00R | 1 | 100.0% |
| 1.00-1.50R | 7 | 0.0% |
| 1.50-2.00R | 0 | 0.0% |

Trades surviving under 1R MAE: **66.7%** (higher = stops are well-placed)

### ST_S09 (n=762)

| Percentile | MFE (bps) | MAE (bps) | MFE (R) | MAE (R) | Risk (bps) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| p10 | 0.37 | 1.54 | 0.19 | 0.54 | 1.42 |
| p25 | 1.36 | 2.58 | 0.48 | 0.84 | 2.03 |
| p50 | 3.13 | 4.34 | 1.00 | 1.38 | 3.14 |
| p75 | 7.08 | 7.63 | 1.74 | 2.24 | 5.17 |
| p90 | 13.00 | 13.42 | 2.75 | 3.26 | 7.83 |
| p95 | 19.48 | 17.74 | 3.53 | 4.06 | 9.68 |

**Reach Probability (P[MFE ≥ threshold]):**

| Threshold | Probability |
| :--- | :---: |
| 0.5R | 74.1% |
| 1.0R | 50.0% |
| 1.5R | 31.5% |
| 2.0R | 19.3% |
| 3.0R | 7.3% |
| 5.0R | 0.8% |

**MAE-Conditioned Win-Rate Survival Curve:**

| MAE Bin | Trades | Win Rate |
| :--- | :---: | :---: |
| 0.00-0.25R | 12 | 91.7% |
| 0.25-0.50R | 49 | 69.4% |
| 0.50-0.75R | 94 | 60.6% |
| 0.75-1.00R | 91 | 49.5% |
| 1.00-1.50R | 174 | 39.7% |
| 1.50-2.00R | 112 | 29.5% |

Trades surviving under 1R MAE: **32.3%** (higher = stops are well-placed)


## 3. Trade-Level Statistics

### BB_E14

**Expectancy:** 0.323R | **Median R:** -0.031

**Duration:** p25=2min p50=14min p75=27min p90=35min

**By Direction:**

| Dir | N | WR | Avg P&L | Total | Avg R |
| :--- | :---: | :---: | :---: | :---: | :---: |
| LONG | 10 | 20.0% | $-37 | $-366 | -0.46 |
| SHORT | 14 | 64.0% | $30 | $420 | 0.88 |

**By Hour (ET):**

| Hour | N | WR | Avg P&L | Total | Avg R |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 15:00 | 23 | 48.0% | $9 | $208 | 0.36 |
| 16:00 | 1 | 0.0% | $-155 | $-155 | -0.61 |

**By Day of Week:**

| Day | N | WR | Avg P&L | Total |
| :--- | :---: | :---: | :---: | :---: |
| Mon | 7 | 29.0% | $-27 | $-190 |
| Tue | 6 | 50.0% | $6 | $34 |
| Wed | 2 | 50.0% | $-10 | $-19 |
| Thu | 3 | 100.0% | $92 | $277 |
| Fri | 6 | 33.0% | $-8 | $-48 |

**R-Multiple Distribution:**

| Range | Count |
| :--- | :---: |
| [-3.0, -2.0) | 0 |
| [-2.0, -1.0) | 9 |
| [-1.0, 0.0) | 4 |
| [0.0, 0.5) | 4 |
| [0.5, 1.0) | 1 |
| [1.0, 1.5) | 1 |
| [1.5, 2.0) | 1 |
| [2.0, 3.0) | 3 |
| [3.0, 5.0) | 0 |
| [5.0, 10.0) | 1 |

### ST_S09

**Expectancy:** 0.093R | **Median R:** -0.155

**Duration:** p25=5min p50=5min p75=5min p90=5min

**By Direction:**

| Dir | N | WR | Avg P&L | Total | Avg R |
| :--- | :---: | :---: | :---: | :---: | :---: |
| LONG | 393 | 35.0% | $2 | $710 | 0.02 |
| SHORT | 369 | 42.0% | $3 | $1167 | 0.17 |

**By Hour (ET):**

| Hour | N | WR | Avg P&L | Total | Avg R |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 10:00 | 1 | 100.0% | $5 | $5 | 0.16 |
| 11:00 | 91 | 49.0% | $3 | $241 | 0.13 |
| 12:00 | 226 | 45.0% | $5 | $1155 | 0.35 |
| 13:00 | 160 | 34.0% | $3 | $557 | -0.03 |
| 14:00 | 91 | 34.0% | $-0 | $-37 | -0.04 |
| 15:00 | 185 | 32.0% | $-0 | $-15 | -0.06 |
| 16:00 | 8 | 0.0% | $-4 | $-30 | -0.34 |

**By Day of Week:**

| Day | N | WR | Avg P&L | Total |
| :--- | :---: | :---: | :---: | :---: |
| Mon | 123 | 39.0% | $1 | $151 |
| Tue | 170 | 32.0% | $0 | $48 |
| Wed | 191 | 37.0% | $3 | $621 |
| Thu | 146 | 42.0% | $2 | $301 |
| Fri | 132 | 44.0% | $6 | $756 |

**R-Multiple Distribution:**

| Range | Count |
| :--- | :---: |
| [-3.0, -2.0) | 0 |
| [-2.0, -1.0) | 110 |
| [-1.0, 0.0) | 320 |
| [0.0, 0.5) | 119 |
| [0.5, 1.0) | 83 |
| [1.0, 1.5) | 47 |
| [1.5, 2.0) | 32 |
| [2.0, 3.0) | 29 |
| [3.0, 5.0) | 20 |
| [5.0, 10.0) | 2 |


## 4. Prop Firm Viability (ADR-021)


## BB_E14 — Prop Firm Viability
### Prop Firm Viability Summary

| Firm | MC Pass Rate | Grade | Blow Rate | Max DD Used | Hist Blown | Avg Days |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Apex 50K | 0.0% | [F] | 0.0% | $384 | No | N/A |
| Apex 100K | 0.0% | [F] | 0.0% | $384 | No | N/A |
| TopStep 50K | 0.0% | [F] | 0.0% | $384 | No | N/A |
| TopStep 100K | 0.0% | [F] | 0.0% | $384 | No | N/A |
| FTMO 50K | 0.0% | [F] | 0.0% | $315 | No | N/A |
| Generic 50K (no constraints) | 0.0% | [F] | 0.0% | $384 | No | N/A |

### Prop Firm Simulation — Apex 50K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+53.67 |
| **Max DD Used** | $384.43 |
| **Trading Days** | 24 |
| **Total Trades** | 24 |
| **Win Rate** | 45.8% |
| **Avg Win / Loss** | $90.99 / $72.86 |
| **Profit Factor** | 1.06 |
| **Avg Daily P&L** | $+2.24 |
| **Best / Worst Day** | $+224.33 / $-186.80 |
| **Longest Loss Streak** | 4 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+53.67 / $+53.67 / $+53.67 |
| **Avg Max Drawdown** | $450.80 |


### Prop Firm Simulation — Apex 100K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+53.67 |
| **Max DD Used** | $384.43 |
| **Trading Days** | 24 |
| **Total Trades** | 24 |
| **Win Rate** | 45.8% |
| **Avg Win / Loss** | $90.99 / $72.86 |
| **Profit Factor** | 1.06 |
| **Avg Daily P&L** | $+2.24 |
| **Best / Worst Day** | $+224.33 / $-186.80 |
| **Longest Loss Streak** | 4 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+53.67 / $+53.67 / $+53.67 |
| **Avg Max Drawdown** | $450.84 |


### Prop Firm Simulation — TopStep 50K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+53.67 |
| **Max DD Used** | $384.43 |
| **Trading Days** | 24 |
| **Total Trades** | 24 |
| **Win Rate** | 45.8% |
| **Avg Win / Loss** | $90.99 / $72.86 |
| **Profit Factor** | 1.06 |
| **Avg Daily P&L** | $+2.24 |
| **Best / Worst Day** | $+224.33 / $-186.80 |
| **Longest Loss Streak** | 4 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+53.67 / $+53.67 / $+53.67 |
| **Avg Max Drawdown** | $450.29 |


### Prop Firm Simulation — TopStep 100K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+53.67 |
| **Max DD Used** | $384.43 |
| **Trading Days** | 24 |
| **Total Trades** | 24 |
| **Win Rate** | 45.8% |
| **Avg Win / Loss** | $90.99 / $72.86 |
| **Profit Factor** | 1.06 |
| **Avg Daily P&L** | $+2.24 |
| **Best / Worst Day** | $+224.33 / $-186.80 |
| **Longest Loss Streak** | 4 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+53.67 / $+53.67 / $+53.67 |
| **Avg Max Drawdown** | $446.70 |


### Prop Firm Simulation — FTMO 50K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+53.67 |
| **Max DD Used** | $315.08 |
| **Trading Days** | 24 |
| **Total Trades** | 24 |
| **Win Rate** | 45.8% |
| **Avg Win / Loss** | $90.99 / $72.86 |
| **Profit Factor** | 1.06 |
| **Avg Daily P&L** | $+2.24 |
| **Best / Worst Day** | $+224.33 / $-186.80 |
| **Longest Loss Streak** | 4 trades |
| **Consistency Rule** | 🚨 VIOLATED |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+53.67 / $+53.67 / $+53.67 |
| **Avg Max Drawdown** | $236.92 |


### Prop Firm Simulation — Generic 50K (no constraints) ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+53.67 |
| **Max DD Used** | $384.43 |
| **Trading Days** | 24 |
| **Total Trades** | 24 |
| **Win Rate** | 45.8% |
| **Avg Win / Loss** | $90.99 / $72.86 |
| **Profit Factor** | 1.06 |
| **Avg Daily P&L** | $+2.24 |
| **Best / Worst Day** | $+224.33 / $-186.80 |
| **Longest Loss Streak** | 4 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+53.67 / $+53.67 / $+53.67 |
| **Avg Max Drawdown** | $452.10 |



## ST_S09 — Prop Firm Viability
### Prop Firm Viability Summary

| Firm | MC Pass Rate | Grade | Blow Rate | Max DD Used | Hist Blown | Avg Days |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Apex 50K | 0.0% | [F] | 0.0% | $177 | No | N/A |
| Apex 100K | 0.0% | [F] | 0.0% | $177 | No | N/A |
| TopStep 50K | 0.0% | [F] | 0.0% | $177 | No | N/A |
| TopStep 100K | 0.0% | [F] | 0.0% | $177 | No | N/A |
| FTMO 50K | 0.0% | [F] | 0.0% | $8 | No | N/A |
| Generic 50K (no constraints) | 0.0% | [F] | 0.0% | $177 | No | N/A |

### Prop Firm Simulation — Apex 50K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+1,876.40 |
| **Max DD Used** | $177.25 |
| **Trading Days** | 292 |
| **Total Trades** | 762 |
| **Win Rate** | 48.6% |
| **Avg Win / Loss** | $29.09 / $15.03 |
| **Profit Factor** | 1.83 |
| **Avg Daily P&L** | $+6.43 |
| **Best / Worst Day** | $+435.66 / $-67.84 |
| **Longest Loss Streak** | 7 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $-46.09 / $+180.17 / $+525.84 |
| **Avg Max Drawdown** | $113.98 |


### Prop Firm Simulation — Apex 100K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+1,876.40 |
| **Max DD Used** | $177.25 |
| **Trading Days** | 292 |
| **Total Trades** | 762 |
| **Win Rate** | 48.6% |
| **Avg Win / Loss** | $29.09 / $15.03 |
| **Profit Factor** | 1.83 |
| **Avg Daily P&L** | $+6.43 |
| **Best / Worst Day** | $+435.66 / $-67.84 |
| **Longest Loss Streak** | 7 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $-56.32 / $+171.60 / $+549.65 |
| **Avg Max Drawdown** | $115.13 |


### Prop Firm Simulation — TopStep 50K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+1,876.40 |
| **Max DD Used** | $177.25 |
| **Trading Days** | 292 |
| **Total Trades** | 762 |
| **Win Rate** | 48.6% |
| **Avg Win / Loss** | $29.09 / $15.03 |
| **Profit Factor** | 1.83 |
| **Avg Daily P&L** | $+6.43 |
| **Best / Worst Day** | $+435.66 / $-67.84 |
| **Longest Loss Streak** | 7 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+59.52 / $+399.56 / $+869.31 |
| **Avg Max Drawdown** | $156.00 |


### Prop Firm Simulation — TopStep 100K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+1,876.40 |
| **Max DD Used** | $177.25 |
| **Trading Days** | 292 |
| **Total Trades** | 762 |
| **Win Rate** | 48.6% |
| **Avg Win / Loss** | $29.09 / $15.03 |
| **Profit Factor** | 1.83 |
| **Avg Daily P&L** | $+6.43 |
| **Best / Worst Day** | $+435.66 / $-67.84 |
| **Longest Loss Streak** | 7 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+71.28 / $+409.56 / $+868.67 |
| **Avg Max Drawdown** | $154.30 |


### Prop Firm Simulation — FTMO 50K ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+1,876.40 |
| **Max DD Used** | $7.99 |
| **Trading Days** | 292 |
| **Total Trades** | 762 |
| **Win Rate** | 48.6% |
| **Avg Win / Loss** | $29.09 / $15.03 |
| **Profit Factor** | 1.83 |
| **Avg Daily P&L** | $+6.43 |
| **Best / Worst Day** | $+435.66 / $-67.84 |
| **Longest Loss Streak** | 7 trades |
| **Consistency Rule** | 🚨 VIOLATED |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $-38.42 / $+191.91 / $+561.72 |
| **Avg Max Drawdown** | $54.23 |


### Prop Firm Simulation — Generic 50K (no constraints) ❌

#### Deterministic (Historical Sequence)
| Metric | Value |
| :--- | :--- |
| **Outcome** | ⏱ TIMED OUT |
| **Account Blown** | No |
| **Final P&L** | $+1,876.40 |
| **Max DD Used** | $177.25 |
| **Trading Days** | 292 |
| **Total Trades** | 762 |
| **Win Rate** | 48.6% |
| **Avg Win / Loss** | $29.09 / $15.03 |
| **Profit Factor** | 1.83 |
| **Avg Daily P&L** | $+6.43 |
| **Best / Worst Day** | $+435.66 / $-67.84 |
| **Longest Loss Streak** | 7 trades |
| **Consistency Rule** | OK |
| **Daily Loss Violations** | 0 days |
| **Trades Skipped (Daily Cap)** | 0 |

#### Monte Carlo (2,000 Permutations)
| Metric | Value |
| :--- | :--- |
| **Pass Rate** | **0.0%** (Grade: **F**) |
| **Blow-Up Rate** | 0.0% |
| **Timeout Rate** | 100.0% |
| **Avg Days to Pass** | N/A |
| **Median Days to Pass** | N/A |
| **P10 / P50 / P90 Equity** | $+59.84 / $+408.00 / $+873.28 |
| **Avg Max Drawdown** | $153.88 |



## 5. Bootstrap Confidence Intervals (Parity §2.6)

| Strategy | Mean/Session | CI Low | CI High | Verdict |
| :--- | :---: | :---: | :---: | :---: |
| BB_E14 | $2.24 | $-37.51 | $44.5 | NOISE |
| ST_S09 | $6.43 | $2.23 | $11.48 | EDGE |

## 6. Trade Structuring Recommendations

_(Auto-generated from excursion + trade-level analysis above)_

### BB_E14
- **Stop placement:** Median MAE = 0.61R, p75 = 1.14R. Stops at 1.0R catch 67% of trades before full-risk drawdown.
- **Target placement:** Median MFE = 0.70R, p75 = 2.57R, p90 = 5.87R. T1 at 0.7R captures 50% of runners; T2 at 2.6R captures the top quartile.
- **Risk in bps (ADR-023):** Median risk = 5.34 bps. Floor 2.0 bps, ceiling 15.0 bps. ✅ Within bracket.
- **Reach probability:** P(MFE≥1R) = 38%, P(MFE≥2R) = 33%. Warning: <50% reach 1R.

### ST_S09
- **Stop placement:** Median MAE = 1.38R, p75 = 2.24R. Stops at 1.0R catch 32% of trades before full-risk drawdown.
- **Target placement:** Median MFE = 1.00R, p75 = 1.74R, p90 = 2.75R. T1 at 1.0R captures 50% of runners; T2 at 1.7R captures the top quartile.
- **Risk in bps (ADR-023):** Median risk = 3.14 bps. Floor 2.0 bps, ceiling 15.0 bps. ✅ Within bracket.
- **Reach probability:** P(MFE≥1R) = 50%, P(MFE≥2R) = 19%. Warning: <50% reach 1R.


---

_Compliant with ADR-002 (price %), ADR-010 (7-layer pipeline), ADR-021 (PropFirmSimulator), ADR-023 (bps + excursion stats)._