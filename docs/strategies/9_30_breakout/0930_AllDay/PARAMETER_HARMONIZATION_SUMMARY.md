# Parameter Harmonization Summary: V2 vs V7F vs V7G

## Purpose
Ensure fair backtesting comparison across all strategy versions by aligning key parameters.

---

## Harmonized Parameters

| Parameter | V2 (Baseline) | V7F (Updated) | V7G (Updated) |
|-----------|---------------|---------------|---------------|
| `initial_capital` | 100,000 | ✅ 100,000 | ✅ 100,000 |
| `margin_long/short` | 0 | ✅ 0 | ✅ 0 |
| `calc_on_every_tick` | false | ✅ false | ✅ false |
| `riskPercent` | 1.0% | ✅ 1.0% | ✅ 1.0% |
| `maxReversalTrades` | 5 | ✅ 5 | ✅ 5 |
| `fixedSLPct` | 0.20% | 0.20% | ✅ 0.20% |

---

## Dynamic Position Sizing (Key Feature)

All strategies now use the same position sizing formula from V2:

```pinescript
rSize = orFormed ? orHigh - orLow : na

calcBaseQty() =>
    math.max(1, math.floor((strategy.equity * riskPercent / 100) / (rSize * syminfo.pointvalue)))

reversalContracts = orFormed ? calcBaseQty() : na
```

### How it works:
1. **Calculate dollar risk**: `strategy.equity * riskPercent / 100`
   - With $100K capital and 1% risk = $1,000 per trade
   
2. **Calculate risk per contract**: `rSize * syminfo.pointvalue`
   - For MNQ: pointvalue = $2
   - If OR range = 50 points → $100 risk per contract
   
3. **Calculate contracts**: `$1,000 / $100 = 10 contracts`

### Benefits:
- Consistent risk across different OR ranges
- Smaller position on wide-range days (higher volatility)
- Larger position on tight-range days
- Apples-to-apples P&L comparison across strategies

---

## Parameters That SHOULD Differ (Strategy-Specific)

These parameters define each strategy's unique approach and should NOT be harmonized:

| Parameter | V2 | V7F | V7G |
|-----------|-----|-----|-----|
| MAE Filter | ❌ Not in V2 | ❌ No | ✅ Yes (0.15%) |
| Dump Pouch | ❌ No | ✅ Yes | ✅ Yes |
| Judas Bias | ❌ No | ✅ Yes | ✅ Yes |

---

## Changed Files

1. **orb_v7f_dump_pouch_harmonized.pine**
   - Updated `initial_capital` from 10,000 → 100,000
   - Added `riskPercent` input (1.0% default)
   - Added dynamic `calcBaseQty()` function
   - Removed fixed `reversalContracts` input
   - Updated `maxReversalTrades` from 3 → 5

2. **orb_v7g_hybrid_harmonized.pine**
   - Updated `initial_capital` from 10,000 → 100,000
   - Added `riskPercent` input (1.0% default)
   - Added dynamic `calcBaseQty()` function
   - Removed fixed `reversalContracts` input
   - Updated `maxReversalTrades` from 3 → 5
   - Updated `fixedSLPct` from 0.25% → 0.20%

---

## Backtesting Instructions

For fair comparison, run all three strategies on:
- **Symbol**: MNQ1! (or specific contract)
- **Timeframe**: 1-minute
- **Date Range**: Same period for all (e.g., 2023-01-01 to 2025-12-31)
- **Settings**: Use default inputs (all harmonized)

### Expected Comparison Metrics:
- Net Profit
- Win Rate
- Profit Factor
- Max Drawdown
- Avg Trade
- Sharpe Ratio

---

## Quick Verification

Run this in TradingView Strategy Tester to verify parameters match:

```
V2:  initial_capital=100000, riskPercent=1.0%, maxReversalTrades=5
V7F: initial_capital=100000, riskPercent=1.0%, maxReversalTrades=5
V7G: initial_capital=100000, riskPercent=1.0%, maxReversalTrades=5
```

All should show similar position sizes for the same OR range.
