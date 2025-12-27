# Win Rate Optimization Analysis
## Target & Range Filter Impact Comparison

### Complete Results Matrix (500 trades each)

| Range Filter | Target | Win Rate | PnL | Avg PnL |
|--------------|--------|----------|-----|---------|
| **NONE** | 0.5R | **50.2%** | 1,002 | 2.00 |
| **NONE** | 1R | 47.0% | **1,273** | 2.55 |
| **NONE** | 1.5R | 41.8% | 1,122 | 2.24 |
| **NONE** | 2R | 38.2% | 907 | 1.81 |
| **NONE** | 3R | 34.2% | 509 | 1.02 |
| 0.25% | 0.5R | **50.6%** | 1,016 | 2.03 |
| 0.25% | 1R | 47.0% | 1,254 | 2.51 |
| 0.25% | 1.5R | 41.6% | 1,091 | 2.18 |
| 0.25% | 2R | 38.8% | 924 | 1.85 |
| 0.25% | 3R | 34.2% | 522 | 1.04 |
| **0.18%** | 0.5R | **51.4%** | 892 | 1.78 |
| 0.18% | 1R | 45.8% | 980 | 1.96 |
| 0.18% | 1.5R | 41.6% | 931 | 1.86 |
| 0.18% | 2R | 38.8% | 847 | 1.69 |
| 0.18% | 3R | 34.0% | 403 | 0.81 |
| 0.15% | 0.5R | 49.6% | 746 | 1.49 |
| 0.15% | 1R | 45.0% | 913 | 1.83 |
| 0.15% | 1.5R | 40.6% | 874 | 1.75 |
| 0.15% | 2R | 38.0% | 806 | 1.61 |
| 0.15% | 3R | 33.2% | 372 | 0.74 |

---

### Key Findings

**1. Target is the primary win rate driver, not range filter**
- 0.5R → ~50% win rate (all filters)
- 1.0R → ~46% win rate
- 2.0R → ~38% win rate
- 3.0R → ~34% win rate

**2. Range filter has minimal win rate impact**
At 2R target across all filters: WR varies only 38.0% - 38.8% (negligible)

**3. Optimal configurations:**
- **Max Win Rate:** 0.5R + 0.18% filter → **51.4%** (but lower PnL)
- **Max PnL:** 1R + No filter → **1,273 pts** (47% WR)
- **Best Balance:** 1R + 0.25% filter → **1,254 pts** (47% WR, filtered risk)

---

### Recommendation

| Goal | Configuration | Win Rate | PnL |
|------|---------------|----------|-----|
| **Max Win Rate** | 0.5R + 0.18% | 51.4% | 892 |
| **Best Balance** | 1R + 0.25% | 47.0% | 1,254 |
| **Max Profit** | 1R + No filter | 47.0% | 1,273 |
