# V7G Strategy Comprehensive Analysis
## Data Gathering & Performance Evaluation

**Date:** January 7, 2026  
**Period:** Jan 9, 2023 — Jan 6, 2026 (3 years)  
**Symbol:** MNQ1! (Micro Nasdaq Futures)  
**Initial Capital:** $3,000  
**TP1:** 0.15% (harmonized with V2)

---

## 📊 EXECUTIVE SUMMARY

| Metric | V7G Value | Grade | Notes |
|--------|-----------|-------|-------|
| **Net Profit** | $13,715.50 (457%) | A | Strong absolute returns |
| **Win Rate** | 42.3% | C | Below 50%, typical for trend systems |
| **Profit Factor** | 1.28 | C | Acceptable but needs improvement |
| **Sharpe Ratio** | 0.54 | C | Moderate risk-adjusted returns |
| **Sortino Ratio** | 2.26 | A | Excellent downside-adjusted returns |
| **SQN** | 2.82 | B+ | Good system quality |
| **Max Drawdown** | $3,073 (102%) | D | Exceeded initial capital |
| **EV per Trade** | $7.28 | C | Positive but small edge |

### Strategy Grade: **B-** (Good foundation, needs optimization)

---

## 🎯 KEY QUESTION: DO MORE ATTEMPTS HELP?

### V2 (15 attempts) vs V7G (5+1 attempts) Comparison

| Metric | V2 (15 attempts) | V7G (5+1) | Winner |
|--------|------------------|-----------|--------|
| Total Trades | 3,315 | 1,883 | V2 |
| Net Profit | $15,992 | $13,716 | V2 (+$2,277) |
| **Avg Trade** | **$4.82** | **$7.28** | **V7G (+51%)** |
| Win Rate | 39.1% | 42.3% | V7G |
| Profit Factor | 1.22 | 1.28 | V7G |
| Return/DD Ratio | 7.58x | 4.46x | V2 |

### The Math on Extra Attempts

```
V2's extra 1,432 trades generated: $2,276.50
Per extra trade average: $1.59

V7G's core trades average: $7.28
V2's all trades average: $4.82

⚠️ CONCLUSION: Extra attempts are DILUTING the edge, not enhancing it.
```

**The additional attempts (6-15) generate only $1.59/trade vs $7.28 for attempts 1-5.**

This makes sense because:
1. Later attempts happen after multiple failures on the same day
2. The market has already moved, reducing edge
3. Statistically, if 5 attempts failed, the 6th is unlikely to succeed

---

## 📈 PERFORMANCE BY ENTRY TYPE

### Judas vs Reversal Trades

| Entry Type | Trades | Win % | Total P&L | Avg P&L | Avg MFE | Avg MAE |
|------------|--------|-------|-----------|---------|---------|---------|
| **JUDAS** | 619 | 42.0% | $4,051 | $6.54 | $36.18 | -$29.47 |
| **REVERSAL** | 1,264 | 42.5% | $9,665 | $7.65 | $69.86 | -$44.85 |

**Insight:** Reversal trades have:
- 2x the MFE potential ($70 vs $36)
- But also 50% more heat ($45 vs $29 MAE)
- Slightly better per-trade profit

### Performance by Reversal Attempt Number

| Attempt | Trades | Win % | Total P&L | Avg P&L |
|---------|--------|-------|-----------|---------|
| REV 1 | 547 | 41.7% | $3,920 | $7.17 |
| REV 2 | 333 | **45.3%** | $3,824 | **$11.48** |
| REV 3 | 187 | 39.0% | $390 | $2.08 |
| REV 4 | 123 | 42.3% | $616 | $5.00 |
| REV 5 | 74 | 44.6% | $917 | $12.39 |

**Key Finding:** 
- **REV 2 is the sweet spot** — highest win rate (45.3%) and best avg P&L ($11.48)
- REV 3 is the weakest — only $2.08 avg
- REV 5 surprisingly good — but small sample (74 trades)

### Recommendation
Consider reducing max reversals from 5 to 3-4, or implementing adaptive logic:
- If REV 1 + REV 2 both fail → reduce size on REV 3+
- Or skip REV 3 entirely and wait for fresh setup

---

## 🎰 EXIT SIGNAL ANALYSIS

### Exit Distribution

| Exit Type | Count | Total P&L | Avg P&L | Avg MAE | Avg MFE |
|-----------|-------|-----------|---------|---------|---------|
| **T1** | 744 | +$35,105 | +$47.18 | -$20.44 | $55.42 |
| **MAE Exit** | 949 | -$36,246 | -$38.19 | -$49.67 | $24.77 |
| **EOD Exit** | 117 | +$21,690 | **+$185.38** | -$48.69 | $306.95 |
| **SL** | 48 | -$5,207 | -$108.48 | -$108.48 | $115.06 |
| **DP1** | 20 | -$1,541 | -$77.03 | -$77.03 | $121.38 |
| **DP2/DP3** | 5 | -$86 | -$17.10 | - | - |

### Analysis

**✅ What's Working:**
1. **T1 Exits** (+$35K) — Core profit engine, clean 0.15% targets
2. **EOD Runners** (+$21.7K) — These are the gold! 117 trades captured big moves

**❌ What's NOT Working:**
1. **MAE Exits** (-$36K) — Necessary evil, but losing 949 trades at $38 avg hurts
2. **SL Hits** (-$5.2K) — Only 48 trades but $108 avg loss is too high
3. **Dump Pouch Trails** (-$1.6K) — DP1/DP2/DP3 exits are all negative

---

## 🏃 RUNNER ANALYSIS

### Runner Performance (Post-TP1 Exits)

| Metric | Value |
|--------|-------|
| Trades that became runners | 142 (7.5% of all trades) |
| Profitable runners | 93/142 (65.5%) |
| Total runner P&L | $20,064 |
| Avg runner P&L | $141.29 |
| Avg runner MFE | $284.71 |

### Was Holding Runners Worth It?

```
If runners had exited at T1: ~$6,700
Actual runner P&L: $20,064
VALUE ADDED BY HOLDING: +$13,363 (2x return!)
```

**✅ HOLDING RUNNERS IS ESSENTIAL** — It added $13K to the strategy.

### Big Winners (P&L > $200)

| Metric | Value |
|--------|-------|
| Count | 36 trades |
| Total P&L | $17,494 |
| % of gross profit | 28% |
| **All 36 from** | **EOD Exit** |

**Every single big winner came from holding to end of day!**

---

## 📉 DRAWDOWN & LOSS ANALYSIS

### Consecutive Losses

| Metric | Value |
|--------|-------|
| Max Consecutive Wins | 9 |
| Max Consecutive Losses | **11** |
| Avg Win Streak | 1.91 |
| Avg Loss Streak | 2.23 |
| Expected Max Loss Streak (formula) | 11.0 |

### Loss Streak Distribution

| Streak Length | Occurrences |
|---------------|-------------|
| 1 loss | 185 |
| 2 losses | 121 |
| 3 losses | 40 |
| 4 losses | 36 |
| 5 losses | 19 |
| 6+ losses | 24 |
| **11 losses** | **2** |

**You hit an 11-loss streak TWICE** in 1,883 trades.

At $225 risk/trade, that's **$2,475 drawdown** from a single streak.

### Drawdown Periods

| Metric | Value |
|--------|-------|
| Max Drawdown | $3,073 (102% of initial capital) |
| Avg Drawdown | $742 |
| Significant DD periods (>$1000) | 2 |
| Longest DD period | 1,422 trades |

**⚠️ WARNING:** The strategy exceeded initial capital in drawdown. This would blow a $3K account.

---

## 🎲 RISK OF RUIN ANALYSIS

### Core Risk Metrics

| Metric | Value |
|--------|-------|
| Win Rate | 42.33% |
| Loss Rate | 50.35% |
| Avg Win | $78.29 |
| Avg Loss | $51.35 |
| EV per Trade | $7.28 |
| Profit Factor | 1.28 |
| Normalized EV (EV/Risk) | 0.032 |
| Combined Edge | 0.041 |

### Risk of Ruin by Account Type

Assuming $225 risk per trade:

| Account | Max DD Allowed | Bankroll (Losses) | Risk of Ruin |
|---------|----------------|-------------------|--------------|
| $50K Apex (EOD Trail $2,500) | $2,500 | 11.1 | **39.75%** ⚠️ |
| $100K TopStep (EOD Trail $3K) | $3,000 | 13.3 | **33.05%** ⚠️ |
| $150K Apex (EOD Trail $5K) | $5,000 | 22.2 | **15.80%** |
| $3K Personal | $3,000 | 13.3 | **33.05%** ⚠️ |

**⚠️ CRITICAL:** With current parameters, there's a **33-40% chance of blowing** most prop accounts.

### Why Risk of Ruin is High

1. **Combined Edge (0.041) is too small** — Need 0.10+ for safety
2. **Max loss streak (11) × $225 = $2,475** — Close to most DD limits
3. **Win rate (42.3%)** too low to survive long losing streaks

---

## 📊 MFE/MAE ANALYSIS

### Overall Statistics

| Metric | Value |
|--------|-------|
| Avg MFE (all trades) | $58.79 |
| Avg MAE (all trades) | -$39.79 |
| **MFE/MAE Ratio** | **1.48** |
| Max MFE | $3,269 |
| Max MAE (worst) | -$362.50 |

### Winner Efficiency

| Metric | Value |
|--------|-------|
| Avg MFE on winners | $92.87 |
| Avg captured (Net P&L) | $78.29 |
| **Capture Rate** | **84.3%** ✅ |

**Good!** We're capturing 84% of available profit on winning trades.

### Loser Analysis

| Metric | Value |
|--------|-------|
| Avg MAE on losers | -$62.22 |
| Avg actual loss | -$51.35 |
| Loss/MAE Ratio | 0.83 |
| **Avg MFE on losers** | **$37.21** |

**Problem identified:** Losers see $37 MFE on average before failing. Some of these could have been winners with better exit timing.

### Big Movers (MFE > $200)

| Metric | Value |
|--------|-------|
| Trades with MFE > $200 | 73 |
| Total P&L from big movers | $18,546 |
| Avg capture | $254.05 |
| Avg MFE | $471.86 |
| **Capture Rate on Big Movers** | **53.8%** ⚠️ |

**We're only capturing 54% of big moves** — There's $18K+ left on the table.

---

## 📋 SQN (System Quality Number)

| Metric | Value |
|--------|-------|
| Mean R-Multiple | 0.032 |
| StdDev R-Multiple | 0.498 |
| N Trades | 1,883 |
| **SQN** | **2.82** |

### SQN Interpretation
- < 1.6: Poor
- 1.6-2.0: Average
- **2.0-3.0: Good** ← V7G is here
- \> 3.0: Excellent

**V7G has a "Good" quality score** — the system is valid but not excellent.

---

## ✅ WHAT V7G IS DOING WELL

1. **Runner Capture (+$13K added value)**
   - EOD exits are generating 28% of gross profit
   - All 36 big winners came from holding runners

2. **MAE Filter Working**
   - Limiting losses to $38 avg vs potentially $100+
   - Cutting losers early before full stop hit

3. **Judas Bias Improving Entries**
   - 42.3% win rate vs V2's 39.1%
   - Better entry timing

4. **Efficient Capital Use**
   - $7.28/trade vs V2's $4.82
   - 51% more efficient

5. **Good System Quality**
   - SQN of 2.82 validates the edge
   - Sortino ratio of 2.26 shows good downside management

---

## ❌ WHAT V7G IS DOING POORLY

1. **Risk of Ruin Too High (33-40%)**
   - Combined Edge of 0.041 is too small
   - 11-loss streaks are account killers

2. **Dump Pouch Trail Not Working**
   - DP1/DP2/DP3 exits are all negative (-$1,626)
   - Only EOD exits are profitable

3. **Big Move Capture Rate Low (54%)**
   - Leaving $18K+ on the table
   - Exits too early on winners

4. **Max Drawdown Excessive (102%)**
   - Would blow a $3K account
   - Need more capital cushion

5. **REV 3 Underperforming**
   - Only $2.08 avg vs $11.48 for REV 2
   - Consider skipping or reducing

---

## 🔧 IMPROVEMENT RECOMMENDATIONS

### Immediate Fixes (High Impact)

1. **Reduce Risk Per Trade**
   - Current: ~$225 (7.5% of $3K)
   - Recommended: $100-150 (3-5% of $3K)
   - This will halve Risk of Ruin

2. **Remove/Simplify Dump Pouch**
   - DP1/DP2/DP3 exits are losing money
   - Switch to: After TP1, either BE stop OR hold to EOD
   - No middle levels

3. **Reduce Max Reversals to 3**
   - REV 3+ has diminishing returns
   - Save capital for tomorrow's fresh setups

### Medium-Term Optimizations

4. **Improve MAE Exit Logic**
   - Current: -$38 avg loss
   - Target: -$30 avg loss
   - Test tighter MAE threshold (0.08% instead of 0.10%)

5. **Implement "Protect the Runner" Rule**
   - When MFE hits 0.50%, move stop to lock 25% profit
   - Don't let big winners reverse to losses

6. **Add Time-Based Exit**
   - If trade not at TP1 by 14:00, exit
   - Avoid end-of-day volatility on mediocre setups

### Strategic Changes

7. **Use Larger Account for Prop**
   - $50K Apex with $2,500 trail has 40% RoR
   - $150K Apex with $5,000 trail has 16% RoR
   - Bigger buffer = higher survival

8. **Implement Scaling**
   - Win 2 in a row → increase size by 25%
   - Lose 3 in a row → reduce size by 50%
   - Reduces impact of losing streaks

---

## 📊 TARGET METRICS (After Optimization)

| Metric | Current | Target | How to Achieve |
|--------|---------|--------|----------------|
| Win Rate | 42.3% | 45%+ | Better entry filters |
| Profit Factor | 1.28 | 1.50+ | Reduce avg loss, hold winners |
| Combined Edge | 0.041 | 0.10+ | Improve PF and EV |
| Risk of Ruin | 33% | <10% | Reduce risk/trade |
| Max DD | 102% | <50% | Smaller position size |
| Capture Rate (big moves) | 54% | 70%+ | Better runner management |

---

## 🎯 SUMMARY

**V7G is a VALID strategy with a real edge, but it's not yet TRADEABLE on prop accounts due to high Risk of Ruin.**

### The Good
- Real positive expectancy (+$7.28/trade)
- Excellent runner capture (+$13K value)
- Good system quality (SQN 2.82)
- More efficient than V2

### The Bad
- 33-40% chance of blowing prop accounts
- Max drawdown exceeded initial capital
- Dump Pouch trail is net negative
- Too many reversal attempts dilute edge

### The Fix
1. **Cut risk in half** (from $225 to $100-125)
2. **Simplify exits** (remove DP levels, just T1 + EOD)
3. **Reduce reversals** (cap at 3)
4. **Use larger account buffer** ($150K Apex minimum)

**With these changes, V7G could become a consistent, lower-risk earner suitable for prop firm trading.**
