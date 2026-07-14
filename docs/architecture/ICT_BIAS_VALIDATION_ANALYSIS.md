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

## 5. Reframing the Approach — Per-Session Candle Bias

### The Problem with the Current Approach

The current bias model computes one "daily bias" at 09:30 ET and measures whether the RTH close direction matches. This has fundamental issues:

1. **One bias for the whole day** — but the day is made up of multiple sessions (Asia, London, NY AM, Lunch, PM), each with its own dynamics. Asia might be bearish while NY AM is bullish. A single daily bias can't capture this.

2. **Day type is an outcome, not an input** — R1/R2/DWP/DNP classification is known AFTER the day closes. Using it as a filter for bias is look-ahead bias. It tells you what happened, not what will happen.

3. **Thresholds are position-based, not price-based** — "40% of PDH-PDL range" doesn't translate to actual price movement. It should be "price moved X% below the session open" or "price is X% away from the equilibrium."

### Session-as-Candle Model

Each session is a candle with its own OHLC:

| Session | Open (ET) | Close (ET) | "Candle" |
|---------|-----------|------------|----------|
| Asia | 18:00 | 02:00 | Open at 18:00, close at 02:00 |
| London | 02:00 | 08:30 | Open at 02:00, close at 08:30 |
| NY AM | 09:30 | 11:00 | Open at 09:30, close at 11:00 |
| NY Lunch | 11:00 | 13:30 | Open at 11:00, close at 13:30 |
| NY PM | 13:30 | 16:00 | Open at 13:30, close at 16:00 |

**Bullish session** = session close > session open (green candle)
**Bearish session** = session close < session open (red candle)

The bias should predict whether the NEXT session's candle will be bullish or bearish — not whether the whole day's RTH close will be up or down.

### Why Per-Session Matters

- ICT killzones are session-specific. The Asia KZ pivot (AS.H/AS.L) is relevant for London's bias. The London KZ pivot is relevant for NY AM's bias.
- Herman's sweep probabilities are session-specific (Pre-NY sweep → NY continuation).
- The Delivery Triad (I2E/E2I) changes between sessions — price may sweep liquidity in London (E2I) then fill FVGs in NY AM (I2E).
- A single daily bias loses all this session-level granularity.

### Revised Outcome Definition

Instead of one outcome (RTH close direction), we should measure per-session outcomes:

| Eval Time | Predicts | Outcome Window |
|-----------|----------|---------------|
| 18:00 | Asia session candle | 18:00 → 02:00 |
| 02:00 | London session candle | 02:00 → 08:30 |
| 08:30 | NY AM session candle | 09:30 → 11:00 |
| 09:30 | Full RTH candle | 09:30 → 16:00 |
| 11:00 | NY Lunch candle | 11:00 → 13:30 |
| 13:30 | NY PM candle | 13:30 → 16:00 |
| 16:00 | Overnight session candle | 16:00 → 18:00 (next day) |

Each outcome is: `session_close > session_open` → BULLISH, `session_close < session_open` → BEARISH.

### Price-Percentage Thresholds

Instead of "position within range at 40%/60%", thresholds should be expressed as actual price movement:

- "Price is 0.3% below the dealing range midpoint" → discount signal
- "Price moved 0.5% above the session open" → momentum signal
- "Price is 0.2% above the prior session close" → continuation signal

This makes the thresholds instrument-agnostic and regime-aware — 0.3% means the same thing for NQ at 10,000 or 30,000.

### VIX/VVIX Treatment

High-VIX events (CPI, FOMC, NFP weeks) are rare — a few weeks per year. These should be:
- Flagged in the parquet (high_VIX flag) for filtering
- Discounted as anomalies, not designed around
- Not used as adaptive threshold inputs (too infrequent to matter for the bulk of trading days)

---

## 6. Revised Next Steps

### Step 1: Reframe to Per-Session Candle Bias
- Change the outcome from "RTH close direction" to "session close vs session open" for each eval time
- Each eval time predicts its own next session, not the whole day
- Add session OHLC columns (session_open, session_close, session_high, session_low) to the parquet

### Step 2: Add Existing Models for Comparison
- Add ALN signal (LPEU/LPED/AEL → BULLISH/BEARISH/NEUTRAL)
- Add Herman Pre-NY sweep signal
- Add Candle Science directional prediction (P(C3 Bull) > P(C3 Bear) → BULLISH)
- Compare all models side-by-side at each eval time

### Step 3: Test Inverted ICT Models
- If models are counter-predictive, test the inverted signal
- If inverted win rate > 55%, the models are contrarian fade signals

### Step 4: Price-Percentage Thresholds
- Replace position-based thresholds (40%/60% of range) with price-movement thresholds (0.3% below midpoint)
- Test different price-percentage thresholds to find the optimal cutoff

### Step 5: Flag and Filter VIX Anomalies
- Add a `high_vix` flag to the parquet (VIX > 22 or CPI/FOMC/NFP day)
- Filter these days from the analysis as anomalies
- Report results with and without anomaly filtering

### Step 6: ADR-021 Prop Firm Simulation
- Once a working bias model is found, run it through PropFirmSimulator
- The ultimate test: can this bias generate trades that pass a prop firm evaluation?

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

---

## 8. Simple Models — 200 SMA and Market Structure

### 8.1 200-Day SMA (daily)

The simplest possible trend-following signal: price above 200-day average = bullish, below = bearish.

**NQ1 results (session_dir):**

| Eval Time | Win% | Edge | n |
|-----------|------|------|---|
| 02:00 | 52.8% | +2.8% | 1768 |
| 09:30 | 53.3% | +3.3% | 1765 |
| 11:00 | **55.7%** | **+5.7%** | 1765 |
| 13:30 | 53.7% | +3.7% | 1706 |

The 200 SMA beats every single ICT model at every eval time. It's positive edge everywhere, and gets better later in the day.

### 8.2 200 SMA on Intraday Timeframes

| Model | 09:30 session | 11:00 session | 13:30 session |
|-------|-------------|-------------|-------------|
| 200 SMA (1m) | 53.6% (+3.6%) | 52.9% (+2.9%) | 53.3% (+3.3%) |
| 200 SMA (5m) | 53.1% (+3.1%) | 53.0% (+3.0%) | 54.1% (+4.1%) |
| 200 SMA (15m) | 51.0% (+1.0%) | 53.5% (+3.5%) | **55.0% (+5.0%)** |
| 200 SMA (1h) | 50.2% (+0.2%) | 51.7% (+1.7%) | 53.6% (+3.6%) |
| 200 SMA (daily) | 53.3% (+3.3%) | **55.7% (+5.7%)** | 53.7% (+3.7%) |

Longer timeframes work better later in the day. Daily 200 SMA is best at 11:00 (55.7%). 15m 200 SMA is best at 13:30 (55.0%).

### 8.3 Market Structure (HH/HL vs LH/LL) — Multi-Timeframe

Market structure per timeframe: current bar made higher high AND higher low = bullish; lower high AND lower low = bearish; else neutral.

**NQ1 session_dir results:**

| Model | 02:00 | 08:30 | 09:30 | 11:00 | 13:30 |
|-------|-------|-------|-------|-------|-------|
| MS (5m) | 53.5% (+3.5%) | 68.3% (+18.3%) | 57.2% (+7.2%) | 57.8% (+7.8%) | 57.6% (+7.6%) |
| MS (15m) | 53.2% (+3.2%) | 71.4% (+21.4%) | 60.4% (+10.4%) | 62.0% (+12.0%) | 62.7% (+12.7%) |
| MS (1h) | **66.6% (+16.6%)** | 66.9% (+16.9%) | **71.7% (+21.7%)** | **73.9% (+23.9%)** | **70.4% (+20.4%)** |
| MS (4h) | **70.1% (+20.1%)** | **79.1% (+29.1%)** | 70.1% (+20.1%) | **84.8% (+34.8%)** | **88.1% (+38.1%)** |

MS on higher timeframes (1h, 4h) is massively predictive — 70-88% win rates. Lower timeframes (5m) are noisy (~57%).

### 8.4 Combinations — MS + 200 SMA Agree

When MS (1h) and 200 SMA (daily) both agree:

| Eval | Outcome | n | Win% | Edge |
|------|---------|---|------|------|
| 11:00 | session_dir | 762 | **77.0%** | **+27.0%** |
| 09:30 | session_dir | 718 | 74.7% | +24.7% |
| 13:30 | session_dir | 483 | 75.4% | +25.4% |

---

## 9. Full Timeframe Continuity (FTFC)

### 9.1 PineScript Reference: FTFC Vip3rr

The PineScript indicator "FTFC Vip3rr" implements Full Timeframe Continuity using **candle direction** (open vs close), NOT market structure (HH/HL):

```
For each timeframe (1h, Daily, Weekly, Monthly):
  - Bullish if open <= close (green candle)
  - Bearish if open >= close (red candle)
  - Change % = (close - open) * 100 / abs(open)
  - Opacity indicates strength: >2% = heavy, >1% = average, else light
```

FTFC = all timeframes showing green candles (bullish) or all showing red candles (bearish).

**Key difference from my MS test:** FTFC uses candle body direction (open vs close), while my test used bar structure (HH/HL vs LH/LL). These are different signals:
- **Candle direction**: Is the current bar's close above its open? (green/red candle)
- **Market structure**: Did the current bar make a higher high AND higher low than the prior bar? (HH/HL)

### 9.2 FTFC Results (Market Structure Approach — HH/HL across 5m/15m/1h/4h)

I tested the concept using market structure alignment across 4 intraday timeframes:

| Model | 08:30 | 09:30 | 11:00 | 13:30 |
|-------|-------|-------|-------|-------|
| 2/4 TFs agree | 74.7% (+24.7%) n=1023 | 65.7% (+15.7%) n=1482 | 72.1% (+22.1%) n=1550 | 66.0% (+16.0%) n=1157 |
| 3/4 TFs agree | 80.6% (+30.6%) n=453 | 72.8% (+22.8%) n=867 | 80.7% (+30.7%) n=892 | 74.1% (+24.1%) n=768 |
| **4/4 Full Continuity** | **86.0% (+36.0%) n=179** | **78.8% (+28.8%) n=236** | **91.1% (+41.1%) n=315** | **90.9% (+40.9%) n=406** |
| **4/4 + 200 SMA** | 81.2% (+31.2%) n=96 | 77.5% (+27.5%) n=142 | **92.4% (+42.4%) n=184** | **91.5% (+41.5%) n=235** |

**Day direction results (close vs eval_price):**

| Model | 08:30 | 09:30 | 11:00 | 13:30 |
|-------|-------|-------|-------|-------|
| 4/4 Full Continuity | 81.6% (+31.6%) | 78.8% (+28.8%) | **92.1% (+42.1%)** | **93.7% (+43.7%)** |
| 4/4 + 200 SMA | 84.4% (+34.4%) | 78.2% (+28.2%) | **94.0% (+44.0%)** | **94.1% (+44.1%)** |

### 9.3 Key FTFC Findings

1. **Full continuity (4/4 agree) at 11:00 = 91.1% win rate (+41.1% edge)** with 315 signals (~18% coverage). This is an exceptionally strong directional bias.

2. **Continuity gets stronger later in the day** — 08:30 is 86%, 11:00 is 91%, 13:30 is 91%. The trend establishes across timeframes and persists.

3. **The 200 SMA filter improves day outcome** (94.0% vs 92.1% at 11:00) but slightly reduces coverage. It mainly removes counter-trend continuity signals.

4. **Even 2/4 agreement is strong** — 72% win rate at 11:00. Partial alignment already gives meaningful edge.

5. **Coverage vs edge tradeoff:**
   - 2/4: ~55% coverage, ~22% edge
   - 3/4: ~32% coverage, ~31% edge
   - 4/4: ~18% coverage, ~41% edge
   - 4/4 + SMA: ~10% coverage, ~44% edge

6. **The progression is clean and monotonic** — more TFs agreeing = higher win rate, consistently.

### 9.4 Next: Test Candle-Direction FTFC

The PineScript FTFC uses candle direction (open vs close), not market structure (HH/HL). These should also be tested:
- **Candle FTFC**: all timeframes have green candles (close > open) = bullish
- **Compare**: which approach works better — candle direction or market structure?

### 9.5 Full Results — All Sessions (NQ1, session_dir)

#### Candle FTFC (candle direction: close > open across 5m/15m/1h/4h/Daily)

| Session | 5/5 FTFC | 4/5 | FTFC+SMA |
|---------|----------|-----|----------|
| **ASIA (18:00)** | N/A (no session data) | N/A | N/A |
| **LONDON (02:00)** | 60.3% (+10.3%) n=463 | 58.8% (+8.8%) n=987 | **60.7% (+10.7%) n=239** |
| **PRE-NY (08:30)** | **92.7% (+42.7%) n=603** | 86.6% (+36.6%) n=1173 | **93.7% (+43.7%) n=332** |
| **RTH OPEN (09:30)** | **90.9% (+40.9%) n=492** | 83.0% (+33.0%) n=1056 | 92.0% (+42.0%) n=289 |
| **LUNCH (11:00)** | 77.5% (+27.5%) n=457 | 70.5% (+20.5%) n=1050 | 78.8% (+28.8%) n=260 |
| **NY PM (13:30)** | 61.1% (+11.1%) n=542 | 49.3% (-0.7%) n=1208 | 64.0% (+14.0%) n=325 |

#### MS FTFC (market structure: HH/HL across 5m/15m/1h/4h/Daily)

| Session | 5/5 FTFC | 4/5 | FTFC+SMA |
|---------|----------|-----|----------|
| **ASIA (18:00)** | N/A | N/A | N/A |
| **LONDON (02:00)** | **80.0% (+30.0%) n=155** | 75.6% (+25.6%) n=409 | **81.1% (+31.1%) n=95** |
| **PRE-NY (08:30)** | 87.0% (+37.0%) n=92 | 85.5% (+35.5%) n=310 | 87.0% n=54 |
| **RTH OPEN (09:30)** | 84.1% (+34.1%) n=145 | 78.7% (+28.7%) n=536 | 80.9% n=89 |
| **LUNCH (11:00)** | 89.7% (+39.7%) n=174 | 84.8% (+34.8%) n=598 | **92.8% (+42.8%) n=111** |
| **NY PM (13:30)** | **92.4% (+42.4%) n=171** | **84.9% (+34.9%) n=548** | **90.7% (+40.7%) n=108** |

#### Combined FTFC (candle + MS both agree)

| Session | 5/5 | 4/5 | 5/5+SMA | 4/5+SMA |
|---------|-----|-----|---------|---------|
| **ASIA (18:00)** | N/A | N/A | N/A | N/A |
| **LONDON (02:00)** | **80.0% (+30.0%) n=110** | 75.6% (+25.6%) n=328 | 78.5% (+28.5%) n=65 | 75.4% n=179 |
| **PRE-NY (08:30)** | **92.4% (+42.4%) n=79** | 87.8% (+37.8%) n=286 | **93.5% (+43.5%) n=46** | 88.1% (+38.1%) n=159 |
| **RTH OPEN (09:30)** | 88.2% (+38.2%) n=85 | 85.6% (+35.6%) n=390 | 84.9% n=53 | 84.1% n=239 |
| **LUNCH (11:00)** | 87.5% (+37.5%) n=112 | 85.0% (+35.0%) n=448 | **90.8% (+40.8%) n=76** | 87.6% (+37.6%) n=283 |
| **NY PM (13:30)** | **89.4% (+39.4%) n=94** | 81.9% (+31.9%) n=370 | 85.9% n=64 | 86.0% (+36.0%) n=228 |

#### Day Direction (close vs eval_price) — Best Models

| Session | Best Model | Day Win% | Day n |
|---------|-----------|----------|-------|
| **ASIA (18:00)** | (all negative — Asia FTFC doesn't predict RTH close) | — | — |
| **LONDON (02:00)** | Combined FTFC+SMA | **96.9% (+46.9%)** | 65 |
| **LONDON (02:00)** | Candle FTFC+SMA | **96.2% (+46.2%)** | 240 |
| **PRE-NY (08:30)** | Candle FTFC+SMA | 92.8% (+42.8%) | 333 |
| **RTH OPEN (09:30)** | Candle FTFC+SMA | 91.4% (+41.4%) | 290 |
| **LUNCH (11:00)** | Combined FTFC+SMA | **98.7% (+48.7%)** | 76 |
| **NY PM (13:30)** | MS FTFC+SMA | **95.4% (+45.4%)** | 109 |

### 9.6 Session-Specific Findings

**ASIA (18:00):** FTFC does NOT work for predicting the RTH day direction. All models show negative edge (-7% to -18%). The overnight Asia session's timeframe alignment doesn't predict the next RTH session — the market regime shifts between overnight and RTH. **Do not use FTFC for Asia session bias.**

**LONDON (02:00):** Both candle and MS FTFC work well for predicting the RTH day direction:
- Candle FTFC+SMA: **96.2% day win rate** with 240 signals (14% coverage)
- Combined FTFC+SMA: **96.9% day win rate** with 65 signals (4% coverage)
- MS FTFC: **91.6% day win rate** with 155 signals
- For session direction (London candle): MS FTFC = 80%, Candle FTFC = 60%

**PRE-NY (08:30):** Candle FTFC is strongest here — 92.7% session, 93.7% with SMA filter. This is the morning sweet spot: the overnight candles have formed, the daily candle is establishing, and alignment across all TFs is highly predictive.

**RTH OPEN (09:30):** Candle FTFC+SMA = 92.0% session / 91.4% day with 289 signals. Good coverage and strong edge.

**LUNCH (11:00):** Combined FTFC+SMA = **98.7% day win rate** (76 signals). The highest conviction signal in the entire study. When candle direction, market structure, AND 200 SMA all agree at lunch, the day closes in that direction 98.7% of the time.

**NY PM (13:30):** MS FTFC dominates — candle FTFC degrades (49-61%) while MS FTFC stays strong (92.4%). The MS FTFC+SMA = 95.4% day win rate with 109 signals. By PM, candle direction is unreliable (the daily candle may have reversed) but market structure captures the persistent trend.

### 9.7 The Winning Bias Model — Session-Adaptive

```
Session-specific bias model:

ASIA (18:00):    DO NOT USE FTFC — negative edge. Use other signals.
LONDON (02:00):  Candle FTFC + 200 SMA = 96.2% day, 240 signals
                 Combined FTFC + SMA = 96.9% day, 65 signals (highest conviction)
PRE-NY (08:30):  Candle FTFC + 200 SMA = 93.7% session, 332 signals (best coverage)
RTH (09:30):     Candle FTFC + 200 SMA = 92.0% session / 91.4% day, 289 signals
LUNCH (11:00):    Combined FTFC + 200 SMA = 98.7% day, 76 signals (highest conviction)
NY PM (13:30):   MS FTFC + 200 SMA = 95.4% day, 109 signals

Pattern:
  Morning -> Candle FTFC (captures forming candle momentum)
  Lunch   -> Combined FTFC (highest conviction when both agree)
  PM      -> MS FTFC (captures persistent structural trend)

ICT concepts (FVG, OB, KZ pivots, gaps) for entry timing, NOT directional bias.
```

### 9.8 Why Asia Session FTFC is Negative — Root Cause Analysis

At 18:00 ET (Asia session start), the FTFC model fails because:

**1. Daily candle is incomplete.** The trading date rolls at 18:00 ET. At 18:00, "today's" daily candle has just 1 bar (the 18:00 open). The daily candle direction (open vs close) is based on a single 1-minute bar — essentially random.

**2. Even using the prior day's candle doesn't help.** Tested with prior day's complete daily candle:
- Prior day candle_D vs RTH close: 46.4% (-3.6% edge)
- Prior day ms_D vs RTH close: 47.9% (-2.1% edge)

The prior day's direction doesn't predict the next RTH because the overnight session introduces new information.

**3. Intraday TFs are in regime transition.** At 18:00:
- 4h bar covers 16:00-20:00 — spans RTH close AND Asia open, mixing two regimes
- 1h bar covers 18:00-19:00 — just the first hour of Asia
- 5m/15m bars show the transition noise, not established structure

**4. The market regime shifts between overnight and RTH.** The Asia/London session has its own dynamics (sweeps, consolidations, reversals) that may differ from the prior RTH day. By the time NY AM starts (09:30), the London session has established a new structure that IS predictive — which is why the 08:30 and 09:30 eval times work so well.

**Conclusion:** FTFC requires timeframes to show **meaningful, established** structure. At 18:00 ET, the structure is in transition. The model works from 02:00 onward (London established) through 13:30 (PM established), but not at 18:00 (regime transition).