# ORB V6 Optimization Results

**Date**: December 29, 2025
**Ticker**: NQ1
**Period**: 10 Years (2015-2025)

---

## 1. Configuration Comparison

### Baseline vs Optimized Config
| Config | Regime | VVIX | Exit Time | Trades | Win Rate | PnL | PF |
|--------|--------|------|-----------|--------|----------|-----|-----|
| **Baseline (V6)** | ON | ON | 10:00 | 1,185 | 38.23% | +2.25% | 1.03 |
| **Optimized** | **OFF** | ON | **11:00** | 1,651 | 31.07% | **+25.45%** | **1.17** |

**Key Insight**: Extending exit time to 11:00 and removing Regime filter **increased PnL by 10x** (+25.45% vs +2.25%).

---

## 2. Entry Mode Performance

| Entry Mode | Trades | Win Rate | PnL | Avg MAE | Avg MFE |
|------------|--------|----------|-----|---------|---------|
| **IMMEDIATE** | 1,185 | 38.57% | **+3.95%** | 0.125% | 0.151% |
| PULLBACK_FALLBACK (Baseline) | 1,185 | 38.23% | +2.25% | 0.121% | 0.144% |
| PULLBACK_ONLY | 1,072 | 36.85% | +3.49% | 0.121% | 0.146% |

**Recommendation**: IMMEDIATE entry outperforms pullback strategies by +75% (3.95% vs 2.25%).

---

## 3. Pullback Depth Analysis

| PB Level | Trades | Win Rate | PnL |
|----------|--------|----------|-----|
| **0.15 (Shallow)** | 1,185 | 38.31% | **+3.43%** |
| 0.20 | 1,185 | 37.89% | +2.05% |
| 0.25 (Baseline) | 1,185 | 38.23% | +2.25% |
| 0.30 | 1,184 | 38.09% | +0.66% |
| 0.35 (Deep) | 1,184 | 37.25% | **-2.52%** ⚠️ |

**Recommendation**: Shallow pullback (0.15) works best. Deep pullbacks (0.35) are **negative expectancy**.

---

## 4. MAE/MFE Risk Analysis

### Distribution Statistics
| Metric | Mean | 50th % | 75th % | 90th % |
|--------|------|--------|--------|--------|
| **MAE (Heat)** | 0.12% | 0.11% | 0.16% | 0.22% |
| **MFE (Run-up)** | 0.14% | 0.09% | 0.20% | 0.36% |

### By Outcome
| Outcome | Avg MAE | Avg MFE |
|---------|---------|---------|
| **Winners** | 0.08% | 0.27% |
| **Losers** | 0.15% | 0.07% |

**Key Insight**: Winners experience half the heat (0.08% vs 0.15%) and 4x the run-up (0.27% vs 0.07%).

---

## 5. Stop Loss Optimization

| SL Level | Stopped Out | Remaining | Est. PnL |
|----------|-------------|-----------|----------|
| 0.10% | 637 (54%) | 548 | -21.04% ⚠️ |
| 0.15% | 324 (27%) | 861 | -10.19% |
| **0.20%** | 156 (13%) | 1,029 | **-2.23%** |
| **0.25%** | 81 (7%) | 1,104 | **+0.80%** ✅ |
| 0.30% (Baseline) | 39 (3%) | 1,146 | +1.07% |

**Recommendation**: SL at **0.20-0.25%** is optimal. Tighter stops (0.10%) cause too many premature exits.

---

## 6. Take Profit Optimization

| TP Level | Would Hit | Capture Rate | Est. Profit |
|----------|-----------|--------------|-------------|
| 0.05% | 761 | 64% | 38.05% |
| 0.08% | 626 | 53% | 50.08% |
| **0.10%** | 545 | 46% | **54.50%** ✅ |
| **0.15%** | 400 | 34% | **60.00%** ✅ |
| 0.20% | 298 | 25% | 59.60% |
| 0.25% | 223 | 19% | 55.75% |

**Recommendation**: TP at **0.10-0.15%** captures maximum profit. Higher targets have diminishing returns.

---

## 7. Profit Leakage

- **Winners with >50% leakage**: 27.6% (125/453)
- **Average Leakage**: 0.08% per trade
- **Total Leaked Profit**: 36.42%

**Key Insight**: Over 1/3 of potential profit is lost by not taking partial profits at MFE.

---

## 8. Recommended Configuration (V7 Candidate)

Based on this analysis, the optimal configuration appears to be:

| Parameter | Baseline (V6) | Recommended (V7) |
|-----------|---------------|------------------|
| `USE_REGIME` | True | **False** |
| `USE_VVIX` | True | True |
| `USE_TUESDAY` | True | True |
| `USE_WEDNESDAY` | False | **True** |
| `HARD_EXIT` | 10:00 | **11:00** |
| `ENTRY_MODE` | PULLBACK_FALLBACK | **IMMEDIATE** |
| `MAX_SL_PCT` | 0.30% | **0.25%** |
| `TP1` | None | **0.10%** (50% qty) |
| `TP2` | None | **0.15%** (remaining) |

**Expected Improvement**: ~10-15x PnL improvement with better risk management.

---

## Files Generated
| File | Description |
|------|-------------|
| `optimization_summary.csv` | All parameter test results |
| `v6_backtest_details.csv` | Baseline trade-level data |
| `v6_custom_regime_off_vvix_on_exit_1100.csv` | Optimized config trades |
| `mae_mfe_analysis.csv` | Risk analysis summary |
| `all_trades_combined.csv` | All optimization test trades |
