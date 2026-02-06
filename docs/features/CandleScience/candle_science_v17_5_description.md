# Candle Science Engine v17.5

## What It Does

The Candle Science Engine predicts the probable behavior of the next candle (C3) based on the structural relationship between the two preceding candles (C1 and C2). It scans all available chart history, finds every instance where C1→C2 formed the same pattern as the current pair, and computes statistical distributions of what C3 did in those historical matches.

The result: probability-based projections for C3's direction, high, low, and close — rendered as a projected candle with probability zones directly on your chart.

---

## How It Works

**Pattern Matching**
The engine characterizes each C1→C2 pair across up to 16 structural dimensions — candle direction, higher-highs/lower-lows, close vs open relationships, and where C3 opened relative to C2. It then searches history for triplets where the C1→C2 relationship matched the current pattern, and analyzes what C3 did in each case.

**Auto-Detect Mode**
Select a pattern preset (Minimal, Standard, Detailed, Full, or Custom) to control how many dimensions define the pattern match. Fewer dimensions = more historical matches but less specificity. More dimensions = fewer matches but tighter pattern definition.

- **Minimal (2d):** C1 and C2 direction only
- **Standard (5d):** + HH/HL/LH/LL structure + C3 open position
- **Detailed (9d):** + close and open cross-level relationships
- **Full (16d):** Every structural dimension
- **Custom:** Pick exactly which dimensions to match

**Manual Mode**
Alternatively, manually specify exact filter criteria (Bull/Bear/Any, Above/Below/Any) for full control over pattern definition.

---

## Statistics Table

The main statistics table shows:

- **Direction:** Probability of C3 being bullish vs bearish
- **C3H vs C2H:** Probability of C3 high breaking above C2 high, with MFE or MAE median
- **C3L vs C2L:** Probability of C3 low breaking below C2 low, with MFE or MAE median
- **C3 Close:** Where C3 close typically lands relative to all four C2 levels (C2H, C2O, C2C, C2L), plus median C3 close position relative to C2 close
- **Body:** Median body size as percentage of C2 close

---

## MFE / MAE Distributions

The engine measures excursions from all four C2 OHLC reference levels:

| Reference | Favorable (MFE) | Adverse (MAE) |
|-----------|-----------------|---------------|
| C2 High | C3H above C2H (upside breakout) | C3L below C2H (drawdown from high) |
| C2 Low | C3L below C2L (downside breakout) | C3H above C2L (rally from low) |
| C2 Close | C3H above C2C / C3L below C2C | — |
| C2 Open | C3H above C2O / C3L below C2O | — |

Each distribution shows:
- Dynamic bucketed histogram with bar charts
- Sample count and percentage per bucket
- Auto-zone detection highlighting the tightest range containing your configured threshold of samples
- Median value

Toggle any combination of the 8 distributions on/off via the Distribution Toggles settings.

---

## Probability-Adaptive Projections

The projected candle and probability zones automatically adapt based on whether a breakout or containment scenario is more likely:

- **When P(C3H > C2H) is high →** Uses MFE: projects how far above C2H the high typically extends
- **When P(C3H > C2H) is low →** Switches to MAE: projects where C3 high typically lands when it stays below C2H
- Same logic applies to the low side with C2L

You can override this with manual controls: Always MFE, Always MAE, or Auto (probability-based switching at a configurable threshold).

The projected candle close is anchored to the median C3 close position relative to C2 close, giving a statistically grounded close projection rather than a simple body-size estimate.

---

## Visual Elements

- **Projected Candle:** Body shows open-to-projected-close, wicks show projected high/low range
- **Probability Zones:** Shaded areas showing the auto-detected concentration zone for upside and downside excursions
- **Median Lines:** Solid lines at median MFE/MAE levels
- **Reference Lines:** Dotted lines at C2 High, Low, Open, Close (individually toggleable)
- **Distribution Table:** Bucketed histograms with bar charts and auto-zone highlighting

All visual elements have configurable size, position, color, and offset.

---

## Key Settings

| Setting | Purpose |
|---------|---------|
| Analysis Mode | Real-time (C3 forming) or Historical (C3 not yet open) |
| Pattern Preset | Controls pattern specificity (Minimal → Full) |
| Minimum Samples | Minimum matches required to display statistics |
| Projection Mode | Auto / MFE / MAE for high and low separately |
| Auto-Zone Threshold | What percentage of samples the auto-zone must capture |
| Trim Percentile | Outlier trimming for distribution buckets |
| Number of Buckets | Distribution granularity (3–8) |

---

## Notes

- Works on any instrument and timeframe
- More history = more matches = more reliable statistics
- The "Standard" preset with 5 dimensions is a good starting point for most instruments
- Watch the sample count (n=) — higher counts give more statistically reliable probabilities
- All probabilities update in real-time as the current candle develops
