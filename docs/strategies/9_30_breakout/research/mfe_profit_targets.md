# MFE Analysis: Optimal Profit Targets
## Based on 10-Year Backtest Data (2016-2025)

### Dataset
- **Total Trades Analyzed:** 2,761 (Threshold 0% strategy)
- **Sweet Spot Trades:** 1,727 (ranges 0.10-0.25%)
- **Winners:** 621 (36%)
- **Losers:** 1,106 (64%)

---

## Key MFE Statistics

### Winners Only (What You Should Aim For)
| Metric | MFE % |
|--------|-------|
| **Average** | 0.351% |
| **Median** | 0.322% |
| **75th Percentile** | 0.454% |
| **90th Percentile** | 0.566% |
| **Maximum** | 1.215% |

### Context: All Trades (Including Losers)
| Metric | MFE % |
|--------|-------|
| Average | 0.177% |
| Median | 0.116% |

**Key Insight:** Even losing trades move favorably by ~0.08% on average before reversing.

---

## Profit Target Recommendations (R-Multiples)

**Assumption:** Opening Range Height = 1R (Your Risk)

For a **typical 0.18% range** (sweet spot midpoint):

| Target | % Move | % of Winners That Reach It |
|--------|--------|----------------------------|
| **0.5R** | 0.090% | 98.6% ✓ |
| **1.0R** | 0.180% | 89.2% ✓ |
| **1.5R** | 0.270% | 74.6% ✓ |
| **2.0R** | 0.360% | 52.7% |
| **2.5R** | 0.390% | 34.3% |
| **3.0R** | 0.467% | 22.7% |

---

## Recommended Scaling Strategy

Based on the probability distribution, use a **3-tier exit approach**:

### **TP1: 1.5R (50% of position)**
- **Target:** ~0.27% move
- **Hit Rate:** 75% of winners
- **Logic:** Captures the median winner. Locks in profit early.

### **TP2: 2.5R (30% of position)**
- **Target:** ~0.39% move
- **Hit Rate:** 34% of winners
- **Logic:** Captures above-average moves. Lets winners breathe.

### **TP3: 4.0R+ (20% of position)**
- **Target:** ~0.54%+ move (or trail)
- **Hit Rate:** ~15-20% of winners
- **Logic:** Captures the "home runs" (90th percentile+). Use trailing stop.

---

## Example Trade Execution

**Scenario:** NQ at 20,000, Opening Range = 36 points (0.18%)

| Level | Price Target | R-Multiple | Exit Action |
|-------|--------------|------------|-------------|
| **Entry** | 20,036 (Long) | - | Full position |
| **Stop Loss** | 20,000 | -1R | Exit all if hit |
| **TP1** | 20,054 | +1.5R | Exit 50% |
| **TP2** | 20,070 | +2.5R | Exit 30% |
| **TP3** | 20,090+ | +4R+ | Trail remaining 20% |

**Risk:** 36 points
**Potential Reward:** 
- Minimum (all TP1): 54 points (1.5R)
- Blended (typical): ~70-80 points (2-2.2R)
- Maximum (runners): 100+ points (3R+)

---

## Key Takeaways

1. **1.5R is the "sweet spot"** - 75% of winners reach it
2. **2R is ambitious but achievable** - 53% hit rate
3. **3R+ requires patience** - Only 23% reach it, but these are the big wins
4. **Scaling out is optimal** - Balances consistency with upside capture

---

*Analysis Date: December 14, 2025*
*Data Source: Threshold_0Pct_2016_2025.csv (2,761 trades)*
