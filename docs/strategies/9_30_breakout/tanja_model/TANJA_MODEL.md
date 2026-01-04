# Tanja 9:30 Model - Trading Strategy Research

**Source**: Model_930_Tanja.pdf  
**Last Updated**: January 4, 2026  
**Status**: Research/Validation (Not Production Ready)

---

## Executive Summary

The Tanja 9:30 Model is a Judas-based reversal strategy for trading the first 15 minutes of the NY session. The core insight is that **87-90% of the time, the first move after 9:30 reverses**.

> **Key Finding**: If the high forms before the low (first move UP), the session ends BEARISH 87% of the time. If the low forms before the high (first move DOWN), the session ends BULLISH 90% of the time.

### Backtest Results Summary (2023-2024)

| Metric | Basic ORB | Tanja (No SL) | Tanja (With SL) |
|--------|-----------|---------------|-----------------|
| Trades | 511 | 516 | 516 |
| Win Rate | 51.3% | 48.8% | 42.8% |
| Total P&L | -64 pts | -254 pts | -475 pts |
| Status | Baseline | ❌ Underperforms | ❌ Worse |

**Conclusion**: The Judas reversal concept is statistically valid (87-90% reversal rate), but the trading implementation needs refinement. Entry timing and stop-loss placement are suboptimal.

---

## The Core Concepts

### 1. Pre-Market Zones

| Zone | Time (ET) | Purpose |
|------|-----------|---------|
| 8:50-9:10 Macro | 8:50-9:10 | Consolidation/liquidity zone |
| Pre-Open Range | 9:20-9:29 | Judas detection window |
| Opening Range | 9:30-9:31 | Entry trigger zone |
| Trade Window | 9:30-9:44 | Execution and exit |

### 2. The Judas Concept

**Judas Move** = A false move that traps traders before the real direction is revealed.

- 88% of trading days have a Judas move in the first 15 minutes
- The Judas sweeps liquidity (stops) before reversing
- Pre-market clues help identify where Judas will form

### 3. Entry Models (Three Types)

The strategy has three entry models based on pre-market price action:

---

## Entry Model 1: Breaker Sequence + Pre-Fill

![Breaker Sequence + Pre-Fill](tanja_model_img1.png)

### Description
When at 9:30 we have this type of sequence and we had a recent snap where we left some inefficiencies behind in the SNAP leg, then we can go ahead with a **pre-fill model** and believe that judas was already created during 9:20 - 9:29.

### Key Elements
- **850-910 macro** acts as support/resistance
- **Snap** with inefficiencies left behind
- **Higher high** pattern forming pre-9:30
- Judas is **already completed** in pre-open
- Entry: Look for gap-fill or continuation

### When to Use
- Clear directional snap before 9:30
- Inefficiencies (gaps) left in the snap leg
- 9:20-9:29 shows clear directional bias

---

## Entry Model 2: Breaker Sequence + Gap Chaser

![Breaker Sequence + Gap Chaser](tanja_model_img2.png)

### Description
When at 9:30 we have an aggressive snap after having created an HH (higher high), then we can anticipate that a breaker sequence is being created and anticipate that the judas has been created and we will have a **gap-chaser**.

### Key Elements
- Aggressive snap after HH formation
- Breaker sequence forming
- Judas already created
- Entry: Chase the gap/inefficiency

### When to Use
- Aggressive move post-HH
- Clear breaker level
- Gap or inefficiency to chase

---

## Entry Model 3: Breaker Sequence + Macro Soup

![Breaker Sequence + Macro Soup](tanja_model_img3.png)

### Description
When during 9:20 - 9:29 we don't have great price action (consolidation), then we can anticipate a judas at 9:30. If 9:30 shows a violent movement until one of the macro high/low (8:50 - 9:10), we can anticipate a **macro soup**.

### Key Elements
- 9:20-9:29 is **consolidation** (no clear direction)
- Judas is **at 9:30** (not pre-open)
- Violent move to 8:50-9:10 macro level
- Reversal from macro soup

### When to Use
- No clear direction in 9:20-9:29
- Wait for 9:30 violence toward macro
- Trade the reversal from macro level

---

## Entry Model 4: Failure Swing Sequence + Macro Soup

![Failure Swing Sequence](tanja_model_img4.png)

### Description
**NEED MORE RESEARCH** - This model involves a failure swing pattern combined with macro soup. The failure swing forms post-9:30 when price fails to make a new high/low.

### Key Elements
- Higher high pre-9:30
- High forms post-9:30 (lower than pre-9:30 high)
- Failure swing pattern
- Macro soup as target

---

## Real Chart Example

![Chart Example](tanja_model_img5.png)

### Narrative from Example (January 2024)
1. The 8:50 to 9:10 macro was used as a **reversal point**
2. With time clusters we can see where Judas stopped (7:30 - 8:28)
3. During 9:20 - 9:29 the price did not have a marked trend → anticipate Judas at 9:30
4. After Judas is created, wait for signs of change in state of delivery: **9:28 candle being broken** and snap in market structure
5. Entry model in this case was **Macro Soup**

---

## The 9:28 / 9:32 Candle Relationship

### Theory
The 9:28 candle is the **directional candle** for 9:30 to 9:59.

| Pattern | Description | Meaning |
|---------|-------------|---------|
| **ON_TOP** | 9:32 is above 9:28 (not touching) | Bullish confirmation ✓ |
| **KISS** | 9:28 and 9:32 touch but don't engulf | Direction confirmed |
| **ENGULF** | 9:32 swallows 9:28 | Judas still forming ⚠️ |

### Validation Results (2023-2024)

| Pattern | Days | Alignment Rate |
|---------|------|----------------|
| ON_TOP | 60 | 48.3% |
| BELOW | 61 | 42.6% |
| **ENGULF** | 107 | **46.7%** ⚠️ |
| GAP_UP | 156 | 50.6% |
| GAP_DOWN | 131 | **56.5%** |

**Key Finding**: 
- ENGULF pattern has **4.4% lower alignment** than non-ENGULF
- GAP patterns (UP/DOWN) are the most predictive
- **9:28 BULLISH + ON_TOP = 57.1% aligned** (best confirmation)

---

## Backtest Details

### Strategy Parameters Tested

| Parameter | Basic ORB | Tanja Model |
|-----------|-----------|-------------|
| Entry Time | On OR break | 9:36 |
| Direction | Breakout direction | Opposite of first move |
| Stop-Loss | None | OR extreme |
| Exit | 9:44 | 9:44 |

### Why Tanja Underperformed

1. **Entry too late** - By 9:36, the reversal may have already started
2. **Stop too tight** - OR extreme is the Judas target, gets hit often
3. **Fixed exit** - 9:44 may not capture full move

### Possible Improvements (For Future Research)

1. **Earlier entry** - 9:33 instead of 9:36
2. **Wider stop** - OR extreme + 10-point buffer
3. **Later exit** - 9:59 instead of 9:44
4. **Pattern filter** - Only trade when 9:28+9:32 confirm (ON_TOP/GAP)

---

## Scripts Created

| Script | Purpose |
|--------|---------|
| `scripts/research/ml_price_curves/analyze_928_932_candles.py` | 9:28/9:32 relationship analysis |
| `scripts/research/ml_price_curves/validate_tanja_model.py` | Full model validation |
| `scripts/research/ml_price_curves/backtest_tanja_vs_orb.py` | Backtest comparison |

### Data Files

| File | Content |
|------|---------|
| `output/candle_928_932_results.csv` | 9:28/9:32 pattern results |
| `output/tanja_model_results.csv` | Judas detection results |
| `output/backtest_tanja.csv` | Tanja trade log |
| `output/backtest_orb.csv` | ORB trade log |

---

## Quick Resume Prompt

To continue this research later:

> "I'm working on the Tanja 9:30 Model documented in `docs/strategies/9_30_breakout/TANJA_MODEL.md`.
>
> Key findings so far:
> - 87-90% reversal rate after first move
> - BUT trading implementation underperforms (48.8% win rate)
> - Entry timing and stop-loss need optimization
>
> I want to [test earlier entry / test wider stops / add pattern filters]."

---

## References

- Source PDF: `Model_930_Tanja.pdf`
- Entry model images: `tanja_model_img1-5.png`
- Validation scripts: `scripts/research/ml_price_curves/`

---

*Document created January 4, 2026*
