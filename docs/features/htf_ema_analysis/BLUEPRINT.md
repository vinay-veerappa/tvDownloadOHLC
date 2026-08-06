# HTF Weekly EMA(5) Excursion Analysis — Master Domain Blueprint

> **Source**: NotebookLM Pack Transcripts, `docs/features/htf-ema-analysis/REQUIREMENTS.md`, & Pine Indicator (`random HF` by Mickey1984)
> **Purpose**: Technical and operational guide detailing how Matt Mickey uses Higher Timeframe (HTF) Weekly EMA(5) percentage excursions, 52-week statistical distributions, 2%-3% magnet zones, Sunday/Tuesday anchors, and NFP Friday anomalies.

---

## 1. Core Philosophy & Metrics

Matt Mickey uses percentage excursions away from the **completed prior Weekly EMA(5)** to determine whether price is overextended, extended into a high-probability reversal magnet, or in structural equilibrium.

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

---

## 3. The 2%–3% Analysis Magnet Zone

The **2% to 3% distance zone** from the Weekly EMA(5) is Mickey's primary **Magnet / Reversion Zone**:
- When price extends into $2.0\% - 3.0\%$ away from the Weekly EMA(5), historical hit-rate distributions indicate whether price typically exhausts or continues.
- If price reaches 2.5% excursion on Thursday/Friday, mean-reversion pullbacks toward the Weekly EMA(5) or P12 Midline become high-probability trades.

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

---

## 5. Software Verification Checklist

To verify our Python implementation (`scripts/wargaming/htf_ema_analysis.py`), the module must pass:

- [ ] **Weekly EMA(5) Continuity**: EMA(5) must be computed on completed weekly bars (Monday close to Friday close).
- [ ] **52-Week Lookback Index**: Excludes current week in progress; evaluates exactly 52 prior weeks.
- [ ] **Excursion Distribution**: Correctly bins in 0.5% increments and computes Mean, Median, and Mode.
- [ ] **NFP Friday Detection**: Correctly flags NFP Fridays and extracts 08:30 AM release candle boundaries.

---
*Document Location: `docs/features/htf_ema_analysis/BLUEPRINT.md`*
