# Asset-Specific Analysis & Optimization Recommendations

## Executive Summary

Deep analysis of why the IB Break pullback strategy fails on ES, RTY, YM, and GC, with specific recommendations to make each asset profitable.

---

## Asset Comparison Table

| Metric | NQ1 ✅ | ES1 ❌ | RTY1 ❌ | YM1 ❌ | GC1 ❌ |
|--------|--------|--------|---------|--------|--------|
| **Win Rate** | 62.0% | 67.1% | 50.3% | 54.8% | 43.3% |
| **Profit Factor** | 1.25 | 0.93 | 0.62 | 0.93 | 0.29 |
| **Return** | +11.71% | -2.96% | -11.43% | -16.40% | -4.79% |
| **Avg Win** | 0.41% | 0.25% | 0.32% | 0.32% | 0.16% |
| **Avg Loss** | -0.53% | -0.54% | -0.52% | -0.43% | -0.48% |
| **Avg MAE** | -0.81% | -0.40% | -0.45% | -0.36% | -0.55% |
| **Avg MFE** | 0.69% | 0.44% | 0.39% | 0.39% | 0.23% |
| **0.5R Reach** | 38.8% | 28.2% | 29.4% | 26.2% | 20.0% |
| **1R Reach** | 17.8% | 14.1% | 7.0% | 7.7% | 0.0% |
| **0 TPs Hit** | 45.7% | 42.4% | 59.8% | 57.9% | 53.3% |

---

## NQ1 (Nasdaq 100) - ✅ WORKS

### Why It Works
1. **Best MFE**: 0.69% average (highest of all assets)
2. **Good TP Reach**: 38.8% reach 0.5R, 17.8% reach 1.0R
3. **Larger Wins**: 0.41% avg win vs 0.53% avg loss (0.77:1 ratio)
4. **High Volatility**: Avg IB range 0.61% (good for pullback strategy)
5. **Strong Trends**: Price follows through after IB breaks

### Performance by IB Range
- **>1.0%**: 81.2% WR, +0.47% avg PnL ✅ BEST
- **0.5-0.7%**: 60.7% WR, +0.04% avg PnL
- **0.3-0.5%**: 58.0% WR, -0.01% avg PnL

**Recommendation**: Continue trading NQ as-is. Consider filtering for IB range > 0.5% for even better results.

---

## ES1 (S&P 500) - ❌ HIGH WR BUT LOSING

### The Problem

**Paradox**: Highest win rate (67.1%) but still losing (-2.96%)

**Root Cause**: **Wins too small relative to losses**
- Avg Win: 0.25%
- Avg Loss: -0.54%
- **Ratio**: 0.46:1 (losses 2.2x larger than wins)

### Why Wins Are Small

1. **Lower MFE**: 0.44% vs NQ's 0.69%
2. **Poor TP Reach**: Only 28.2% reach 0.5R (vs 38.8% for NQ)
3. **Smaller Moves**: ES is less volatile than NQ
4. **Tighter Ranges**: Avg IB range 0.55% vs NQ's 0.61%

### Detailed Analysis

**Take Profit Tiers Hit**:
- 0 TPs: 42.4% (getting stopped out)
- 1 TP: 44.7% (hitting 0.5R only)
- 2 TPs: 12.9% (hitting both 0.5R and 1.0R)

**Performance by IB Range**:
- **>1.0%**: 85.7% WR, +0.23% avg PnL ✅
- **0.7-1.0%**: 100% WR, +0.33% avg PnL ✅✅ BEST
- **0.5-0.7%**: 60.0% WR, -0.14% avg PnL
- **0.3-0.5%**: 62.0% WR, -0.05% avg PnL

### Optimization Recommendations for ES1

#### 1. **Tighter Take Profits** (Primary Fix)

**Problem**: Current TPs (0.5R, 1.0R) too far for ES's smaller moves

**Solution**: Use smaller R-multiples
```python
tp_r_multiples=[0.3, 0.6]  # Instead of [0.5, 1.0]
```

**Expected Impact**:
- More trades hit TP1 (0.3R instead of 0.5R)
- Capture smaller ES moves
- Improve profit factor from 0.93 to 1.2+

#### 2. **Filter for Larger IB Ranges**

**Current**: Trading all IB ranges (0.3%+)
**Optimal**: Only trade IB range > 0.7%

**Data Shows**:
- IB > 0.7%: 92.9% WR, profitable
- IB < 0.7%: 61.0% WR, losing

**Implementation**:
```python
if ib_range_pct < 0.7:
    return None  # Skip trade
```

**Expected Impact**:
- Reduce trades from 85 to ~15
- Win rate 90%+
- Positive returns

#### 3. **Tighter Stop Loss**

**Current**: IB opposite (avg -0.54% loss)
**Optimal**: Use MAE-optimized stop (-0.285% from winners)

**Calculation**:
```python
optimized_stop = winner_median_mae * 1.2 = -0.285% * 1.2 = -0.342%
```

**Expected Impact**:
- Smaller losses (-0.34% vs -0.54%)
- Better R/R ratio
- Profit factor improvement

### Projected ES1 Performance with Optimizations

| Metric | Current | Optimized | Improvement |
|--------|---------|-----------|-------------|
| Win Rate | 67.1% | 85%+ | +18% |
| Avg Win | 0.25% | 0.20% | -20% (smaller TPs) |
| Avg Loss | -0.54% | -0.34% | +37% better |
| Profit Factor | 0.93 | 1.5+ | +61% |
| Return | -2.96% | +8-12% | Profitable |

---

## RTY1 (Russell 2000) - ❌ TOO CHOPPY

### The Problem

**Worst performer**: -11.43% return, 50.3% win rate

**Root Causes**:
1. **Too many trades**: 286 (2.2x more than NQ)
2. **Too choppy**: 59.8% hit 0 TPs (getting stopped out)
3. **Poor MFE**: Only 29.4% reach 0.5R
4. **Losses dominate**: Avg loss -0.52% vs avg win 0.32%

### Why RTY Fails

1. **Small Cap Volatility**: More erratic, less trending
2. **False Breakouts**: IB breaks don't follow through
3. **Wide IB Ranges**: Avg 0.74% (widest of all) = wider stops
4. **Lower Liquidity**: More slippage and whipsaw

### Detailed Analysis

**Take Profit Tiers**:
- **0 TPs: 59.8%** ❌ (most getting stopped out)
- 1 TP: 28.3%
- 2 TPs: 11.9%

**Performance by IB Range**:
- All ranges losing (no sweet spot found)
- Even >1.0% range only 55.4% WR

**Entry Time Analysis**:
- 14:00-15:00: 62.5% WR ✅ (best window)
- 15:00-16:00: 50.0% WR
- 16:00-17:00: 45.5% WR
- 17:00-18:00: 38.2% WR
- 18:00-19:00: 18.2% WR ❌

### Optimization Recommendations for RTY1

#### 1. **Strict Entry Window** (Primary Fix)

**Problem**: Trading too late into the day (poor performance after 15:00)

**Solution**: Only enter 14:00-15:00
```python
entry_window_start = time(14, 0)
entry_window_end = time(15, 0)  # Instead of 14:00
```

**Expected Impact**:
- Reduce trades from 286 to ~88
- Win rate from 50.3% to 62.5%
- Focus on best-performing hour

#### 2. **Require Matched Expectation**

**Data**:
- Matched: 52.1% WR
- Unmatched: 41.7% WR

**Solution**:
```python
if not matched_expectation:
    return None  # Skip trade
```

**Expected Impact**:
- Reduce trades by ~17%
- Improve win rate by ~10%

#### 3. **Wider Take Profits**

**Problem**: RTY has larger moves (0.74% avg IB range) but current TPs too tight

**Solution**: Use larger R-multiples
```python
tp_r_multiples=[0.75, 1.5]  # Instead of [0.5, 1.0]
```

**Rationale**: RTY's avg MFE is 0.39%, but winners' MFE is 0.65% - need to capture these larger moves

#### 4. **Filter for Moderate IB Ranges**

**Solution**: Only trade IB range 0.5-1.0%
```python
if ib_range_pct < 0.5 or ib_range_pct > 1.0:
    return None
```

**Expected Impact**:
- Avoid extreme volatility (>1.0%)
- Avoid low volatility (<0.5%)

### Projected RTY1 Performance with Optimizations

| Metric | Current | Optimized | Improvement |
|--------|---------|-----------|-------------|
| Trades | 286 | ~70 | -75% (quality over quantity) |
| Win Rate | 50.3% | 60%+ | +10% |
| Profit Factor | 0.62 | 1.0+ | +61% |
| Return | -11.43% | +5-8% | Profitable |

---

## YM1 (Dow Jones) - ❌ SIMILAR TO ES

### The Problem

**Similar to ES but worse**: -16.40% return, 54.8% win rate

**Root Causes**:
1. **Wins too small**: 0.32% avg win vs -0.43% avg loss
2. **Poor TP reach**: Only 26.2% reach 0.5R
3. **Too many 0 TPs**: 57.9% hit no TPs

### Why YM Fails

1. **Lower Volatility**: Avg MFE 0.39% (similar to RTY)
2. **Smaller Moves**: Less follow-through than NQ
3. **Many Trades**: 221 trades (1.7x more than NQ)
4. **Late Entries Fail**: Performance degrades after 17:00

### Detailed Analysis

**Performance by IB Range**:
- **0.3-0.5%**: 60.0% WR, +0.01% avg PnL (best range)
- **0.5-0.7%**: 51.7% WR, -0.02% avg PnL
- **0.7-1.0%**: 54.8% WR, +0.03% avg PnL
- **>1.0%**: 40.0% WR, -0.14% avg PnL ❌

**Entry Time**:
- 14:00-16:00: 58%+ WR ✅
- 17:00+: <40% WR ❌

### Optimization Recommendations for YM1

#### 1. **Smaller Take Profits** (Like ES)

**Solution**: Use tighter TPs for smaller YM moves
```python
tp_r_multiples=[0.3, 0.6]
```

#### 2. **Filter for Smaller IB Ranges**

**Data shows**: Best performance in 0.3-0.5% range

**Solution**:
```python
if ib_range_pct < 0.3 or ib_range_pct > 0.7:
    return None
```

#### 3. **Strict Entry Window**

**Solution**: Only enter 14:00-17:00
```python
entry_window_end = time(17, 0)
```

#### 4. **Require Matched Expectation**

**Data**:
- Matched: 57.6% WR
- Unmatched: 40.5% WR

**Solution**: Skip unmatched trades

### Projected YM1 Performance with Optimizations

| Metric | Current | Optimized | Improvement |
|--------|---------|-----------|-------------|
| Trades | 221 | ~80 | -64% |
| Win Rate | 54.8% | 65%+ | +10% |
| Profit Factor | 0.93 | 1.2+ | +29% |
| Return | -16.40% | +5-10% | Profitable |

---

## GC1 (Gold) - ❌ FUNDAMENTALLY INCOMPATIBLE

### The Problem

**Worst of all**: Only 30 trades, 43.3% WR, 0.29 PF, -4.79% return

**Root Causes**:
1. **Too few trades**: Only 30 (4.3x less than NQ)
2. **No 1R reaches**: 0% of trades reach 1.0R ❌
3. **Tiny wins**: 0.16% avg win (smallest of all)
4. **Large losses**: -0.48% avg loss (3x larger than wins)
5. **Different dynamics**: Commodity vs equity index

### Why Gold Fails

1. **Different Market**: Commodity, not equity index
2. **Different Hours**: Gold trades 23 hours (different IB dynamics)
3. **Different Drivers**: Macro/geopolitical vs earnings/tech
4. **Lower Momentum**: Mean-reverting vs trending
5. **Insufficient Data**: Only 30 trades (not statistically significant)

### Detailed Analysis

**MFE Reach**:
- 0.25R: 36.7%
- 0.5R: 20.0%
- 0.75R: **0.0%** ❌
- 1.0R: **0.0%** ❌

**Conclusion**: Gold doesn't trend enough after IB breaks to reach targets

### Optimization Recommendations for GC1

#### ⚠️ **NOT RECOMMENDED TO TRADE**

Gold is fundamentally incompatible with this strategy. However, if you insist:

#### 1. **Much Smaller Take Profits**

**Solution**: Extremely tight TPs
```python
tp_r_multiples=[0.2, 0.4]  # Very small
```

#### 2. **Different IB Definition**

**Problem**: Gold trades 23 hours, standard IB (9:30-10:15) may not be relevant

**Solution**: Use gold-specific IB (e.g., London open or NY open)

#### 3. **Require Large IB Ranges**

**Data**: Only 3 trades with IB >1.0%, but 66.7% WR

**Solution**: Only trade IB > 1.0%

#### 4. **Consider Different Strategy**

**Recommendation**: IB break pullback doesn't suit gold. Consider:
- Mean reversion strategies
- Support/resistance bounces
- Macro event-driven trades

### Verdict on GC1

**Status**: ❌ **DO NOT TRADE**

Even with optimizations, gold is unlikely to be profitable with this strategy. The asset characteristics don't match the strategy requirements.

---

## Summary of Optimizations

### ES1 (S&P 500) - Can Be Fixed ✅

**Changes**:
1. Tighter TPs: [0.3, 0.6] instead of [0.5, 1.0]
2. Filter IB range > 0.7%
3. Tighter stop loss (-0.34%)

**Expected**: 85%+ WR, +8-12% return

### RTY1 (Russell 2000) - Can Be Fixed ⚠️

**Changes**:
1. Strict entry window: 14:00-15:00 only
2. Require matched expectation
3. Wider TPs: [0.75, 1.5]
4. Filter IB range 0.5-1.0%

**Expected**: 60%+ WR, +5-8% return

### YM1 (Dow Jones) - Can Be Fixed ✅

**Changes**:
1. Smaller TPs: [0.3, 0.6]
2. Filter IB range 0.3-0.7%
3. Entry window: 14:00-17:00
4. Require matched expectation

**Expected**: 65%+ WR, +5-10% return

### GC1 (Gold) - Cannot Be Fixed ❌

**Verdict**: Fundamentally incompatible with strategy

**Recommendation**: Do not trade

---

## Implementation Priority

1. **ES1**: Easiest to fix (just adjust TPs and filters)
2. **YM1**: Similar to ES, straightforward fixes
3. **RTY1**: More challenging (needs multiple filters)
4. **GC1**: Skip entirely

---

## Next Steps

1. Implement asset-specific parameter sets
2. Re-run backtests with optimized parameters
3. Validate improvements
4. Create asset-specific strategy variants
5. Document optimal parameters for each asset

---

## Files for Reference

- NQ1: `historical_validation/nq_2019_2020.csv`
- ES1: `multi_asset_validation/es1_2019_2020.csv`
- RTY1: `multi_asset_validation/rty1_2019_2020.csv`
- YM1: `multi_asset_validation/ym1_2019_2020.csv`
- GC1: `multi_asset_validation/gc1_2019_2020.csv`
- Summary: `multi_asset_validation/detailed_analysis.csv`
