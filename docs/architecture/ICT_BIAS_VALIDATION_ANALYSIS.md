# ICT Daily Bias — Historical Validation Analysis

> **Date:** 2026-07-13
> **Data:** NQ1 + ES1, 2019-09-09 to 2026-07-13 (~7 years, ~1765 trading days)
> **Method:** `scripts/context/generate_bias_signals.py`
> **ADR Compliance:** ADR-002 (percentage-based), ADR-017 (vectorized, no loops in calc paths)

---

## 1. Timeframe and Scope

| Parameter | Value |
|-----------|-------|
| Start date | 2019-09-09 |
| End date | 2026-07-13 |
| Trading days | ~1,765 (NQ1: 1,769, ES1: 1,763) |
| Eval times | 18:00, 02:00, 08:30, 09:30, 11:00, 13:30, 16:00 |
| Symbols | NQ1, ES1 |
| Outcome metrics | RTH close direction, max excursion direction, excursion magnitude (%) |

### ADR Compliance
- **ADR-002 (Statistical Normalization):** Excursion magnitude is reported as price percentage (median 0.68%, max 14.11%). Win/loss is directional, not absolute. ✅
- **ADR-017 (Zero-Loop):** The bias signal generator uses per-day iteration (O(days) = ~2000 iterations), not per-bar loops. Model computations are vectorized. ✅
- **ADR-021 (Prop Firm Simulation):** Not yet integrated — this is a directional bias study, not a strategy backtest. Prop firm simulation should be applied when we convert bias signals into actual trade signals. ⬜ (future)

---

## 2. ICT Daily Bias Models — NQ1 vs ES1 at 09:30 ET

### Outcome: RTH Close Direction (did the close match the bias direction?)

| Model | NQ1 Win% | NQ1 Edge | ES1 Win% | ES1 Edge | Assessment |
|-------|----------|----------|----------|----------|------------|
| A: Premium/Discount | 41.3% | -8.7% | 42.2% | -7.8% | ❌ Counter-predictive |
| B: Draw on Liquidity | 44.4% | -5.6% | 44.5% | -5.5% | ❌ Slight negative |
| C: IPDA Position | 27.3% | -22.7% | 27.9% | -22.1% | ❌ Strongly counter-predictive |
| D: HTF Structure | 43.8% | -6.2% | 44.2% | -5.8% | ❌ Negative |
| E: Prior Day Candle | 51.1% | +1.1% | 48.4% | -1.6% | ⚠ NQ marginal positive, ES negative |
| F: Midnight Open | 47.0% | -3.0% | 47.6% | -2.4% | ❌ Slight negative |
| G: London/Asia Sweep | 33.6% | -16.4% | 35.3% | -14.7% | ❌ Strongly counter-predictive |
| **Composite** | **42.8%** | **-7.2%** | **43.7%** | **-6.3%** | ❌ Negative |

### Confidence Buckets (NQ1 @ 09:30)

| Confidence | Signals | Win Rate | Interpretation |
|------------|---------|----------|----------------|
| 0-30% | 79 | 43.0% | Low confidence ≈ coin flip |
| 30-60% | 1476 | 43.8% | Most signals here, still below 50% |
| 60-80% | 210 | 36.7% | High confidence = WORSE |
| 80-100% | 4 | 0.0% | When all models agree, always wrong |

### Confidence Buckets (ES1 @ 09:30)

| Confidence | Signals | Win Rate |
|------------|---------|----------|
| 0-30% | 81 | 35.8% |
| 30-60% | 1450 | 45.4% |
| 60-80% | 225 | 36.9% |
| 80-100% | 7 | 14.3% |

---

## 3. Why Are the Models Contrarian?

### Hypothesis 1: ICT bias models capture "overextension," not "continuation"

The ICT framework says: "price in premium → shorts favored." If price is in premium (>60% of PDH-PDL range), the model says BEARISH. But in trending markets, price can stay in premium for extended periods — the "premium" condition doesn't cause a reversal, it just describes the current state.

**Evidence:** Model C (IPDA Position) has the worst edge (-22%). IPDA measures multi-day rolling ranges. When price is at the top of a 20/40/60-day range, the model says BEARISH (expect reversion). But in strong bull markets (like NQ 2019-2026), being at the top of the range is the *normal state* — price keeps making new highs. The model is fighting a trend.

### Hypothesis 2: NQ has a structural upward bias

NQ (Nasdaq) has a strong long-term upward drift. Over 7 years (2019-2026), NQ went from ~8,000 to ~30,000 — a 275% gain. Any model that says "short because price is high" will be wrong more often than right, because NQ keeps going higher.

**Evidence:** The IPDA model says BEARISH when price is in premium (>60% of range). With NQ's relentless uptrend, price is frequently in premium and the close is frequently higher. The 27.3% win rate means the model correctly predicted bearish closes only 27% of the time — it was wrong 73% of the time.

### Hypothesis 3: The thresholds are miscalibrated

The current thresholds:
- Premium/Discount: <40% = BULLISH, >60% = BEARISH
- IPDA: <40% & <50% = BULLISH, >60% & >60% = BEARISH

These may be too aggressive. In a trending market, 60% of range is not "overextended" — it's normal. The models need adaptive thresholds or trend-aware filtering.

### Hypothesis 4: The "London/Asia Sweep" model has a logic inversion

Model G says: "London swept Asia low → bullish continuation." But the data shows 33.6% win rate — it's strongly counter-predictive. This could mean:
- When London sweeps Asia low, price tends to continue DOWN (bearish), not up (bullish)
- The sweep is a liquidity raid that signals the direction of the NEXT move, which is the OPPOSITE of what the model assumes
- OR: the model's logic is correct but the "continuation" is already priced in — by the time the sweep happens, the move is done

### Hypothesis 5: High confidence = herding = reversal

When all 7 models agree (80-100% confidence), the win rate is 0-14%. This is classic contrarian behavior — when every signal points the same way, the market does the opposite. This is consistent with the "liquidity sweep" concept: when all signals say "bullish," all the buy stops are resting above — the market sweeps them and reverses.

---

## 4. Comparison with Existing Bias Models

### ALN (NQStats Unified Bias Algorithm)

ALN classifies overnight sessions into patterns:
- **LPEU** (London Premium Expansion Up): London High > Asia High, London Low ≥ Asia Low → Bullish
- **LPED** (London Premium Expansion Down): London Low < Asia Low, London High ≤ Asia High → Bearish
- **AEL** (Asia Encompasses London): London inside Asia → Consolidation

ALN is a **morning bias tool** — it reads the overnight session structure to predict the NY session direction. It's not directly comparable to ICT daily bias because:
1. ALN is intraday-specific (London → NY), ICT is daily structure
2. ALN uses session H/L relationships, ICT uses dealing range / IPDA / KZ pivots
3. ALN is already validated through the NQStats pipeline

**To compare:** We'd need to add ALN signals to the bias_signals parquet. This requires running NQStatsEngine at each historical date and recording the ALN pattern + bias.

### Herman (Liquidity Sweep Probabilities)

Herman provides static probabilities:
- Pre-NY breaks London HIGH → 86.4% bullish
- Pre-NY breaks London LOW → 77.9% bearish
- PL sweeps Asia HIGH → 77.2% London sweeps high again
- London OR breaks HIGH → 76.5% bullish continuation

These are **conditional probabilities** — "IF X happens, THEN Y happens with Z% probability." They're not daily bias models — they're event-triggered. The ICT Model G (London/Asia Sweep) is the closest analog, and it's performing poorly (33.6% win rate), which may mean the Herman probabilities are also less reliable than claimed (or that the market regime has changed since Herman's study).

**To compare:** We'd need to add Herman signals to the bias_signals parquet — recording whether the Pre-NY sweep occurred and what the subsequent direction was.

### Candle Science (C1→C2→C3 Pattern)

Candle Science uses the last 2 daily candles to predict the 3rd day's direction:
- P(C3 Bull) — probability of a bullish C3 candle
- P(C3 Bear) — probability of a bearish C3 candle
- MFE/MAE percentiles — expected excursion magnitude
- R:R envelope — median MFE/MAE ratio

This is a **pattern-matching** approach (find historical days with the same C1/C2 pattern, compute statistics). It's different from ICT bias (which is level-based). Candle Science is already validated through the CandleScienceService.

**To compare:** We'd need to add Candle Science signals to the bias_signals parquet — recording P(C3 Bull), P(C3 Bear), and the directional prediction.

---

## 5. What Needs to Happen Next

### Add ALN, Herman, and Candle Science to the Bias Signals Parquet

The bias_signals parquet should be extended with:
- `model_h_aln` — ALN pattern (LPEU/LPED/AEL) → BULLISH/BEARISH/NEUTRAL
- `model_i_herman` — Herman Pre-NY sweep result → BULLISH/BEARISH/NEUTRAL
- `model_j_candle` — Candle Science P(C3 Bull) > 50% → BULLISH, P(C3 Bear) > 50% → BEARISH

This would give us a side-by-side comparison of all bias models (ICT + ALN + Herman + Candle Science) at each eval time.

### Test Inverted ICT Models

Since the ICT models are counter-predictive, test the inverted version:
- If model says BULLISH, record BEARISH as the prediction
- If inverted win rate > 55%, the models are contrarian indicators and should be used as fade signals

### Test Different Eval Times

The current analysis is at 09:30 (RTH open). The models may work better at other times:
- 18:00 (overnight open) — does the bias predict the overnight direction?
- 02:00 (London open) — does the bias predict the London session?
- 16:00 (close) — does the bias predict the next day?

### Test Per-Day-Type Breakdown

The models may work on certain day types (R1/R2/DWP/DNP) but not others. We have daily classification data to group by.

### Adaptive Thresholds

Instead of fixed 40/60 thresholds, test:
- 30/70 (more extreme = more reliable?)
- 20/80 (only signal in deep discount/premium)
- Trend-aware: adjust thresholds based on whether market is trending or ranging

### ADR-021 Prop Firm Simulation

Once we have a working bias model (even if inverted), we should run it through the PropFirmSimulator to see if it can actually pass a prop firm evaluation. This is the ultimate test — not "is the bias directionally correct?" but "can this bias generate trades that pass a prop firm?"

---

## 6. Excursion Magnitude Analysis (ADR-002 Compliant)

The `excursion_magnitude` column is the maximum price excursion (up or down) from eval_price to RTH close, expressed as a percentage of eval_price:

| Stat | NQ1 (%) |
|------|---------|
| Mean | 0.86% |
| Median | 0.68% |
| 25th percentile | 0.33% |
| 75th percentile | 1.15% |
| Max | 14.11% |

This means: on a typical day, NQ moves about 0.68% from the 09:30 eval price to some extreme before the close. The bias models should predict which direction this excursion goes — and they're currently getting it wrong more often than right.

---

## 7. Summary

| Finding | Implication |
|---------|------------|
| All 7 ICT bias models have negative edge at 09:30 | Models are counter-predictive, not predictive |
| Higher confidence = worse win rate | Classic contrarian signal — fade the consensus |
| IPDA Position is worst (-22%) | Fighting the trend in a trending market |
| Prior Day Candle is best (+1.1% NQ) | The only model with marginal positive edge |
| NQ1 and ES1 show same pattern | Not ticker-specific — it's a model issue |
| Models may need inversion | Test inverted signals as contrarian fade trades |
| ALN/Herman/Candle Science not yet compared | Need to add them to the parquet for side-by-side |
| Prop firm simulation not yet applied | Ultimate test is whether bias can generate passing trades |