# HTF Weekly EMA(5) Excursion Analysis — Master Domain Blueprint

> **Source**: NotebookLM Pack Transcripts, `docs/features/htf-ema-analysis/REQUIREMENTS.md`, & Pine Indicator (`random HF` by Mickey1984)
> **Purpose**: Technical and operational guide detailing how Matt Mickey uses Higher Timeframe (HTF) Weekly EMA(5) percentage excursions, 52-week statistical distributions, 2%-3% magnet zones, Sunday/Tuesday anchors, and NFP Friday anomalies.
> **Verified 2026-09-01**: Cross-checked against NotebookLM `Pack Trading - Live Wargaming YouTube Transcripts` (68 sources) and `Pack Oct Bootcamp` (72 sources). Sections 1.5, 2.5, 3.5, 4.5, 6, 7 carry transcript-verified refinements that supersede the original blueprint text.

---

## 1. Core Philosophy & Metrics

Matt Mickey uses percentage excursions away from the **completed prior Weekly EMA(5)** to determine whether price is overextended, extended into a high-probability reversal magnet, or in structural equilibrium.

### 1.5 The "Blue Line" — Why Weekly EMA(5) (VERIFIED)
Mickey is explicit that the indicator has no magic:
> *"is there anything specific or special about a weekly 5 EMA? Absolutely not... but it's close enough to live price and the local volatility and the local market environment that we can put probabilities on it."*

Its role is a **live mean**: a fixed constant that moves with the market. A static mean fails because *"the market goes up into the right"* — the EMA is *"live with the market, but stable enough that it doesn't capture every wiggle."* All excursion probabilities are measured as percentages off this line, never points.

### Excursion Formulas
For any daily/intraday bar:
- **Upward Excursion ($dUp$)**:
  $$dUp = \max\left(0.0, \frac{\text{High} - \text{WeeklyEMA}_5}{\text{WeeklyEMA}_5} \times 100\right)$$
- **Downward Excursion ($dDn$)**:
  $$dDn = \max\left(0.0, \frac{\text{WeeklyEMA}_5 - \text{Low}}{\text{WeeklyEMA}_5} \times 100\right)$$

If price fails to move in the designated direction beyond the EMA, the excursion is $0.0$.

---

## 2. 52-Week Statistical Lookback & Binned Mode Logic

The statistical lookback window strictly evaluates the **prior 52 fully completed weeks** (excluding the current in-progress week):

1. **Metrics Calculated**:
   - **Mean**: Arithmetic average excursion %.
   - **Median**: Sorted 50th percentile midpoint.
   - **Mode**: Binned highest frequency excursion zone.
2. **Binning & Zero-Purge**:
   - Data is binned in **0.5% increments** (e.g. 0.0%–0.5%, 0.5%–1.0%, 1.0%–1.5%, 2.0%–2.5%).
   - The zero bin ($<0.001\%$) is purged so consolidation chop does not distort directional metrics.
   - **Tie-Breaking**: If multiple bins tie for highest frequency, the bin center closest to the arithmetic Mean is selected as the Mode.
3. **Hit-Rate Classification**:
   - **Good (Green)**: $\ge 66.67\%$ Hit Rate
   - **Fair (Yellow)**: $\ge 33.33\%$ and $< 66.67\%$ Hit Rate
   - **Rare (Red)**: $< 33.33\%$ Hit Rate

### 2.5 The Hit-Rate Ladder — His Actual Dashboard (VERIFIED)
The dashboard is a **cumulative per-level hit-rate ladder** ("% of weeks whose excursion reached each level"), not a distribution summary. From Mickey's 52-week sample (bootcamp image data):

| Level | dUp Hit Rate | dDn Hit Rate |
|---|---|---|
| 0.5% | 86.5% | 53.8% |
| 1.0% | 80.8% | 42.3% |
| 1.5% | 75.0% | 42.3% |
| 2.0% | 69.2% | 36.5% |
| 2.5% | 59.6% | 32.7% |
| 3.0% | 51.9% | 21.2% |
| 3.5% | 36.5% | 21.2% |
| 4.0% | 21.2% | 19.2% |
| 4.5% / 5.0% | 13.5% | 19.2% |

> ⚠️ **Ticker-specific, not universal**: the ladder above is **NQ's** ladder. The philosophy (live EMA mean, percentage excursions, 0.5% ladder, variance multiplier, spent-target state) is identical for every instrument, but **each ticker's hit-rate values must be recomputed from its own weekly history** — e.g. ES's distribution differs (our ES1 sample: dUp mean ~2.21%, dDn mean ~1.02%; shallower tails than NQ). Volatile/linear instruments (CL) will show much deeper tails. The Python engine computes per-ticker ladders; never reuse NQ's percentages on another symbol.

- **Live-cited sample sizes**: 50bps hit 53/56 weeks; 1% hit 51/56 weeks.

---

## 3. The 2%–3% Analysis Magnet Zone

The **2% to 3% distance zone** from the Weekly EMA(5) is Mickey's primary **Magnet / Reversion Zone**:
- When price extends into $2.0\% - 3.0\%$ away from the Weekly EMA(5), historical hit-rate distributions indicate whether price typically exhausts or continues.
- If price reaches 2.5% excursion on Thursday/Friday, mean-reversion pullbacks toward the Weekly EMA(5) or P12 Midline become high-probability trades.

### 3.5 Zone Asymmetry + Variance Multiplier (VERIFIED)
- **Asymmetric zones**: the 2–3% red box is **upside-only** in his chart config (weekly highs form there 50–68% of the time — median 3.08%, mode 3.0–3.5%). The downside green box is **0.5–1.0%** (matches dDn median 0.86% and optimal level 1.0%). Our original 2–3%-both-directions reading was a simplification.
- **Overextension ≠ blind fade**: at 2%+ he says *"we're getting kind of overextended"*, but he **never fades blindly** — the stretch is context; execution requires the intraday **Four-Step Reversal Checklist** to confirm the snap.
- **The Variance Multiplier ("statistic of the statistic")**: the 1% upside level went unhit two weeks in a row **zero times in 56 weeks**; the 50bps level once. Singles misses are common (1% missed 5 of 56 weeks) but consecutive misses are the extreme tail:
  > *"Not only do we have a 91% probability every single week of hitting that 1%, but now we have a multiplier that we can put on there because we usually don't not hit it two times in a row."*
- **Anomaly weeks**: 4%+ excursion = second standard deviation (8% of 198 weeks; 3 of 101 weeks) — headline-driven outlier weeks where he anticipates the eventual violent snap back toward the EMA.

---

## 4. Key Intraday Anchors & NFP Macro Anomalies

### 1. Sunday Anchor Box (18:00 ET)
- Triggers at the Globex Sunday opening candle (18:00 ET). Sets the initial weekly range anchor.

### 2. Tuesday Anchor Box (09:30 AM ET)
- Triggers at Tuesday 09:30 AM RTH open. Mickey observes that Tuesday 09:30–10:30 frequently locks in either the Weekly High or Weekly Low for trend continuation days.

### 3. NFP (Non-Farm Payroll) Friday Anomalies
- Dynamically detected on the **first Friday of the month** (`dayofweek == Friday` and `dayofmonth <= 7`).
- Records the highest high and lowest low of the pre-market 08:30 AM EST NFP release candle.
- Price action after 09:30 AM RTH open is evaluated relative to this 08:30 NFP range box.

### 4.5 Spent-Target State Machine (VERIFIED)
Weekly EMA targets operate as a **sequential spent-target checklist**:
1. Levels are attacked **from the near side**: open above the prior-week EMA → top-down (50bps → 1% → 1.5%); open below → bottom-up.
2. When touched, a level is **deleted as spent** — *"we hit our 1% to the downside, so there goes the other one."*
3. When all of 50bps/1%/1.5%/2% are spent: *"all the high probability targets have already been hit for the week"* → weekly edge collapses to a **50/50 coin flip**; Friday becomes a **weekly doji / lock-in-the-range** day, not an expansion day:
   > *"we've hit all of our weekly probability levels... the next one to the upside is 46%, the next one to the downside is 40%... from this weekly approach we know there's no edge right there, right? It's a 50/50 coin flip."*

## 5. The Macro Regime Gate: NFP Friday Close + Previous Month 50% + Current Month 30% (VERIFIED)

These three monthly levels form the **directional regime gate** that sits above the weekly EMA targets.

### 5.1 NFP Friday Close — The 70/30 vs 50/50 Regime Switch
The **close (and range) of the first Friday of the month** is marked as a macro boundary for the whole monthly candle:
- **Above NFP Friday range AND above Previous Month 50%** → **70% green days / 30% red days** (statistic cited since 1956 SPX / 1962–63). On those 70%-green days the **low of day locks in early** — 18:00–19:00, 03:00–04:00, or 09:30–10:30 — and the close finishes high into the afternoon.
- **Below either component, or stuck inside the NFP range** → reverts to **50/50 green/red**, with sharp volatile snapbacks (even bear markets do not exceed 50% red).
- > *"statistics tells us if we close above NFP Friday while we're above previous month 50% we can expect 70% green days and 30% red days meaning we expect to see the low of the day between 1800, 03, or 9:30 and 10:30"*
- Even when the government skips the release, the **first-Friday calendar slot still counts** as the NFP Friday level.

### 5.2 Previous Month 50% — Pullback Taxonomy
The exact midpoint of the prior month's high-to-low range diagnoses pullback depth:
1. **Monthly Slowdown** — shallow pause; price stays above both NFP Friday and Prev Month 50%.
2. **Quarterly Pullback** — closes below Prev Month 50% **and** below NFP Friday → downside targets = **"quarterly lows"** (count ~60 days back; often align with previous month lows):
   > *"the moment we close below this NFP Friday and previous month 50% statistically I expect quarterly lows."*
3. **Yearly Change of Character** — if price cannot rotate back above both levels **within the first week of the new month** → multi-quarter/yearly trend-shift threat.
- Between NFP Friday and Prev Month 50% = **"la la land"** — no HTF directional edge; rely on intraday session models only.

### 5.3 Current Month 30% — Red-Month Retracement Rule
A line at **30% of the current active monthly range** (low + 0.30 × range):
- **Green months**: expand and close near highs — *"green candles like to close at the high, there's no real edge"*.
- **Red months**: historically *"suck back into the range"* — statistically **close back above the 30% mark** of the monthly range, leaving a bottom wick:
  > *"what this means is by the 29th to 30th we should be above this 30%... on a red month we typically suck back into the range at least 30%."*
- Late-month red months approaching month-end with price below the 30% line → expect short-covering / dip-buying snap toward it.

### 5.4 How They Combine with the Weekly EMA Targets
- **70/30 regime active**: weekly candles distribute upward into Thu/Fri → use upside EMA brackets as aggressive trend targets (0.5% @ ~86–98%, 1.0% @ ~80–90%, 1.5% @ ~75%).
- **50/50 regime**: market hunts quarterly lows; EMA downside stretches of 1.87–2.38%+ enter the 13–19% frequency "anomaly zone". If the stretch coincides with days 29–30, the **Current Month 30% line becomes the mean-reversion anchor**.
- **Stacking principle**: *"we have two stack probabilities... these are two separate probabilities, right? So that's a great clue that the market's giving us."* — regime gate + EMA ladder must align before he treats a target as high conviction.

---

## 6. Software Verification Checklist

To verify our Python implementation (`scripts/wargaming/htf_ema_analysis.py`), the module must pass:

- [ ] **Weekly EMA(5) Continuity**: EMA(5) must be computed on completed weekly bars (Monday close to Friday close).
- [ ] **52-Week Lookback Index**: Excludes current week in progress; evaluates exactly 52 prior weeks.
- [ ] **Excursion Distribution**: Correctly bins in 0.5% increments and computes Mean, Median, and Mode.
- [ ] **Hit-Rate Ladder**: Cumulative "% of weeks reaching each 0.5% level" for both directions, per ticker.
- [ ] **Variance / Miss-Streak**: Per-level consecutive-miss tracking against the current week (the multiplier rule).
- [ ] **Spent-Target State**: Which 0.5% levels the current week has already touched (from either direction), computed from the current week's high/low vs the prior-week EMA.
- [ ] **NFP Friday Close Level**: First Friday's close + range captured as the monthly regime gate.
- [ ] **Regime Gate**: 70/30 vs 50/50 classification from NFP Friday close + Previous Month 50% position.
- [ ] **Previous Month 50%**: Midpoint of prior month's range; pullback taxonomy (Monthly Slowdown / Quarterly Pullback / Yearly CoC).
- [ ] **Current Month 30%**: 30% of current month range; red-month retracement rule with days-29-30 expectation.
- [ ] **NFP Friday Detection**: Correctly flags NFP Fridays and extracts 08:30 AM release candle boundaries.

---
*Document Location: `docs/features/htf_ema_analysis/BLUEPRINT.md`*
