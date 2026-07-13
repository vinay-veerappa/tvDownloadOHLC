# ICT Daily Bias: Modular Models & Algorithms

## 1. Overview
The `ict_engine` implements Daily Bias as a modular, testable component. Rather than a single "hardcoded" bias, the engine treats Bias as a **Hypothesis** that can be verified through historical data.

The goal is to provide multiple "Bias Strategies" that can be plugged into backtests to determine which interpretation yields the highest win rate for a specific ticker (e.g., NQ vs. ES).
## Implementation Status

**7 models implemented** in `scripts/trader/signals/ict_data_loader.py:compute_ict_daily_bias()`:

| # | Model | Status | What it measures |
|---|-------|--------|-----------------|
| A | Premium/Discount | ✅ Implemented | Price position in PDH/PDL dealing range |
| B | Draw on Liquidity | ✅ Implemented | Proximity to BSL (untaken highs) vs SSL (untaken lows) |
| C | IPDA Position | ✅ Implemented | 20/40/60-day rolling range position |
| D | HTF Structure | ✅ Implemented | Price vs PWH/PWL |
| E | Prior Day Candle | ✅ Implemented | Close vs PDH/PDL |
| F | Midnight Open | ✅ Implemented | Price above/below midnight open |
| G | London/Asia Sweep | ✅ Implemented | London swept Asia H/L = continuation |
| H | Daily MSS/BOS | ⬜ Phase 2 | Break of structure on daily chart |
| I | Delivery Triad | ⬜ Phase 2 | I2E vs E2I cycle detection |
| J | SMT Divergence | ⬜ Phase 2 | NQ vs ES divergence at key levels |
| K | Judas Swing | ⬜ Phase 2 | Midnight Open sweep during London |
| L | DOL Enhanced | ⬜ Phase 2 | Magnet strength + sweep tracking |

**Phase 2 plan:** See [ICT_PHASE2_PLAN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/ICT_PHASE2_PLAN.md)
**Historical validation:** `scripts/context/validate_ict_bias.py` (Phase 2B — planned)
---

## 2. Models of Bias

### 2.1 Model A: Institutional Order Flow (IOF)
**Focus**: Pure structural sequence on the Daily (D1) or Weekly (W1) chart.
- **Bullish**: Daily Swing Low followed by a Break of Daily Swing High (BOS).
- **Bearish**: Daily Swing High followed by a Break of Daily Swing Low (BOS).
- **Neutral**: Inside Day or Consolidation.
- **Logic**: Traditional "Trend Following" but using ICT Swing definitions.

### 2.2 Model B: The Draw on Liquidity (DOL) Proximity
**Focus**: Proximity to major liquidity pools (BSL/SSL).
- **Bullish**: Price is closer to a major untaken High (e.g., PWH or Old D1 High) than a major Low.
- **Bearish**: Price is closer to a major untaken Low (e.g., PWL or Old D1 Low) than a major High.
- **Stat Metric**: "Magnet Strength" (Percent distance to target).

### 2.3 Model C: Market Delivery Triad (E2I / I2E)
**Focus**: The cycle of market delivery.
- **Internal to External (I2E)**: If price just filled/rebalanced a Daily FVG -> Bias is toward the next External Liquidity high/low.
- **External to Internal (E2I)**: If price just swept External Liquidity (PDH/PDL) -> Bias is toward the next Internal FVG/Imbalance.
- **Logic**: This is a "Counter-Trend" or "Reversion" model when liquidity is swept.

### 2.4 Model D: Premium vs. Discount (P/D)
**Focus**: Mathematical Equilibrium of the current Dealing Range.
- **Bullish**: Price < 50% Equilibrium of the current Daily leg (Looking for Buy).
- **Bearish**: Price > 50% Equilibrium of the current Daily leg (Looking for Sell).
- **Integration**: Best used as a filter for other models.

---

## 3. Modular Implementation Plan

### 3.1 Function Signature
Each bias function should adhere to a standard interface for easy swapping in backtests:

```python
def detect_bias_iof(ohlc_daily, ohlc_weekly): -> BiasResult
def detect_bias_dol(ohlc_daily, liquidity_pools): -> BiasResult
def detect_bias_delivery_triad(ohlc_daily, fvgs, liquidity): -> BiasResult
```

### 3.2 Bias Confidence Scoring
A "Signal Stacker" will combine these into a unified score:
- **Bias Score**: -100 (Bearish) to +100 (Bullish).
- **Confidence**: Based on how many models agree.

---

## 4. Statistical Verification
To validate a bias model, we measure:
1. **Bias Alignment**: Did price expand further in the expected direction?
2. **Opening Price Proximity**: Did price stay above/below the Midnight Open consistent with bias?
3. **MDR (Modern Delivery Ratio)**: Efficiency of the move toward DOL.
