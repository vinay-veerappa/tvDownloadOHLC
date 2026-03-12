# HTF EMA Analysis - Requirements & Technical Specification

## 1. Goal
Build a Pine Script v6 overlay indicator named **HTF EMA Analysis** that replicates complex probability chart metrics, centered on percentage-distance excursions from the weekly EMA(5). The indicator delivers comprehensive daily and weekly statistics, configurable EMA zones, probabilistic dashboards, and flawlessly renders cross-timeframe structural elements without encountering historical array limit crashes.

## 2. Environment & Scope
- **Platform:** TradingView Pine Script v6.
- **Type:** Intraday & Higher Timeframe (HTF) Overlay Indicator.
- **Primary Market Use:** Support/Resistance and Magnet Level detection using probability engines, specifically for instruments operating under futures or robust global sessions.

## 3. Core Definitions & Formulas

### 3.1 Base Percent Excursion Metric
All probability calculations define movement away from the *closing* Weekly EMA(5) of the **completed prior week**.

**Positive (Upward) Excursion:**
`dUp = math.max(0.0, ((High - prevWeeklyEma) / prevWeeklyEma) * 100)`

**Negative (Downward) Excursion:**
`dDn = math.max(0.0, ((prevWeeklyEma - Low) / prevWeeklyEma) * 100)`

**Requirement Note:**
- If the target high/low failed to move in the designated direction at all, the excursion is intrinsically considered `0.0`.
- This ensures adverse volatility does not artificially suppress the baseline metrics of the opposed direction.

### 3.2 Weekly Statistical Lookback Window
- **Default Range:** Exclusively evaluates the historical `52` fully completed weeks (Current week in progress is naturally excluded from the statistical index).
- **Core Outputs:** 
  1. `Mean` (Mathematical average)
  2. `Median` (Sorted midpoint)
  3. `Mode` (Binned highest frequency)

### 3.3 Target Analysis Zone
- A static probability analysis zone dynamically checking exactly **2% to 3%** distance from the Weekly EMA(5).
- Detects interaction overlap/touch logic. 

### 3.4 Binned Mode Logic (Tie-Breaking & Zero-Purge)
Instead of returning singular raw ticks, the distribution is clustered incrementally.
1. Data arrays are binned by `i_modeBinSize` (default: **0.5%**).
2. The zero bin (values `< 0.001%`) is aggressively excluded from the array analysis so tightly-ranged consolidation chop cannot overwhelm directional metrics.
3. If multiple frequency bins tie for maximum count, the framework employs a **Nearest-to-Mean** check, evaluating the absolute delta of each tied bin's center against the sequence's arithmetic `Mean`. The closest bin becomes the ultimate `Mode`.

### 3.5 Classification Logic (Thirds)
Performance rates explicitly populate in one of three fractional categories:
- **Good (Green):** $\ge 66.67\%$ Hit Rate
- **Fair (Yellow):** $\ge 33.33\%$ and $< 66.67\%$ Hit Rate
- **Rare (Red):** $< 33.33\%$ Hit Rate

## 4. Architectural Rules & Structural Features

### 4.1 Global Time Coordinates Protocol
To permit monthly/weekly architectural objects to exist effortlessly on 1m or 15m timeframes, TradingView's `bar_index` limit (~500 bar recursive limit) is completely bypassed. 
Every persistent drawing object strictly utilizes `xloc.bar_time` combined with raw `time` / `time_close` variables instead.
`time` geometrically guarantees lines/boxes reach identically scaled destinations regardless of the viewer's timeframe multiplier.

### 4.2 NFP & Holiday Anomalies
- The script dynamically detects Non-Farm Payroll anomalies by assessing the initial Friday of the month utilizing native logic (`dayofweek.friday` and `dayofmonth <= 7`).
- Records the highest high/lowest low directly achieved during the 6-hour NFP block preceding New York open.

### 4.3 Sunday & Tuesday Intraday Anchors
- **Sunday Anchor:** Triggers exactly at the first `18:00` candle hour.
- **Tuesday Anchor:** 
  - Timeframes `< 60m`: Identifies the exact `09:30` opening candle.
  - Timeframes $\ge 60m`: Targets the inclusive hour bar capturing `09:30`.
- Wraps the session high/low directly into targeted `color.new(val, 85)` transparent fill boxes trailing to the current close sequence.

## 5. UI Elements & Dashboards

### 5.1 Weekly Analysis Panel
- Presents a summary column of standard HTF states (`Mean`, `Median`, `Mode`).
- Details current zone entry hit-rate percentages alongside raw opening positions.
- Cross-references statistical days of the week rows corresponding to current price limits (`dUp` & `dDn` math).

### 5.2 All Levels Hit-Rate Dashboard
- Projects a granular step grid incrementing by `0.5%` continuously to 5.0%.
- Actively categorizes success rates across the Good/Fair/Rare metric matrix.
- Appends specialized `Mode` row summaries to identify the most potent predictive magnet levels mathematically proven by the algorithm.

### 5.3 Toggle Modularity
- Enormous feature flag support (Toggle visibility for EMA zones, Monthly High/Low/Mid, NFP filters, Prior Week 25%/50%/75% subdivisions, Statistical tables).
- Color customization for virtually every array line instantiated on the panel without polluting the main input index excessively.
