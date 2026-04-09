# Macro Research Pipeline — Design Document

## Overview

A quantitative research framework for studying ICT macro window behavior across futures instruments (ES, NQ, YM, RTY, CL, GC). The system detects and classifies price action patterns within 20-minute macro windows, catalogs Fair Value Gaps, tracks post-macro outcomes, and provides an Edgeful-style conditional probability query interface.

**Core Research Question:** Within each ICT macro window, is there a statistically reliable two-phase structure (Judas sweep → Real Move), and can we identify the inflection point and optimal trade location using FVG, hourly open, and expansion midpoint as anchors?

---

## Architecture

### Data Sources (Inputs)

| Source | Format | Location | Description |
|--------|--------|----------|-------------|
| 1-minute OHLCV | Parquet | `data/{INST}_1m.parquet` | Raw price/volume data. Columns: `open`, `high`, `low`, `close`, `volume`, `time` (epoch), `timestamp` (naive UTC string). Instruments: ES1, NQ1, YM1, RTY1, CL1, GC1. Range: 2006-01-05 to 2026-01-23. |
| 5-minute OHLCV | Parquet | `data/{INST}_5m.parquet` | Aggregated price data. Available for optional 5-min FVG layer. |
| Daily Scenarios CSV | CSV → Parquet | Existing file | Session-level analysis: manipulation classification, pattern, gap info, session OHLC, level hit tracking, CBDR, P12, OTE levels. One row per day per instrument. |
| 9:30 Opening Bar | JSON → Parquet | Existing file | RTH first 1-minute candle: open, high, low, close, range_pts, range_pct. |
| VIX/VVIX Daily | Existing format | Existing location | Daily aggregation. Prior day close used for regime classification. |
| News/Events | SQLite (Prisma DB) | Existing DB | News and event data already stored. |

### Pipeline Outputs

| Table | Format | Description |
|-------|--------|-------------|
| `macro_records.parquet` | Parquet | One row per macro window per instrument per day. ~816K rows (24 macros × 3 Hydra × 252 days × 20 years × 6 instruments). |
| `fvg_detail.parquet` | Parquet | One row per FVG detected within a macro window. Linked to macro_records via `macro_id`. |
| `calendar.parquet` | Parquet | Generated reference table: OpEx, FOMC, CPI, NFP flags by date. |

### Query Engine

- **DuckDB** as the analytical query engine — reads parquet files natively, can attach SQLite (Prisma DB) directly for joins to news/event data
- **Prisma DB (SQLite)** for reference data, news/events, and any dashboard state
- **Next.js dashboard** for the interactive Edgeful-style interface

---

## Macro Window Definitions

### Standard Macros (hour-boundary windows, excluding 17:50)

Generated programmatically: every `XX:50` to `XX+1:10` ET, excluding the invalid `17:50-18:10` window.

```python
EXCLUDED_STANDARD_MACRO_START_HOURS = {17}

STANDARD_MACROS = [
    (f"Macro_{h:02d}50", h, 50, (h+1) % 24, 10)
    for h in range(24)
    if h not in EXCLUDED_STANDARD_MACRO_START_HOURS
]
```

### ICT-Named Aliases

| Generated Name | ICT Name | ET Window |
|---------------|----------|-----------|
| Macro_1850 | Asia_1 | 18:50–19:10 |
| Macro_1950 | Asia_2 | 19:50–20:10 |
| Macro_2050 | Asia_3 | 20:50–21:10 |
| Macro_0250 | London_1 | 02:50–03:10 |
| Macro_0450 | London_2 | 04:50–05:10 |
| Macro_0950 | NY_AM_1 | 09:50–10:10 |
| Macro_1050 | NY_AM_2 | 10:50–11:10 |
| Macro_1150 | NY_Lunch | 11:50–12:10 |
| Macro_1350 | NY_PM | 13:50–14:10 |
| Macro_1550 | NY_Close | 15:50–16:10 |

Non-ICT windows retain their generated names (e.g., `Macro_0150`, `Macro_1450`). The `ict_name` field is populated for known windows, null for others.

### Hydra Macros (3 windows)

| Name | ET Window |
|------|-----------|
| Hydra_1 | 08:20–08:40 |
| Hydra_2 | 09:20–09:40 |
| Hydra_3 | 10:20–10:40 |

### Mid-Anchor Open

- **Standard macros:** The hourly open (`:00` bar) that falls inside the window
- **Hydra macros:** The half-hour open (`:30` bar) that falls inside the window

---

## Phase 1: Macro Extraction & Classification

### Timestamp Handling

- Raw data is in naive UTC
- Convert to US/Eastern using `zoneinfo.ZoneInfo('US/Eastern')` — handles DST automatically
- **Trading date assignment:** Futures session runs 18:00 ET to 17:00 ET next day. Bars from 18:00 Sunday through 17:00 Monday = Monday's trading date. All overnight macros (Asia, London) are assigned to the next calendar day's trading date.

### Macro OHLC Extraction

For each trading day × each macro window × each instrument:
- Filter 1-minute bars within the window
- `macro_open` = open of the first bar
- `macro_high` = highest high across all bars
- `macro_low` = lowest low across all bars
- `macro_close` = close of the last bar
- `macro_mid` = (macro_high + macro_low) / 2
- `macro_volume` = sum of volume across all bars

### Judas Classification Rules

**Reference point:** The macro open price. Everything measured relative to it.

**Bullish Judas (fake up, real down):**
- Macro high is above macro open (at least one bar's wick exceeds the open)
- Macro close is below macro open
- Judas extreme = macro high (the wick, not the close)
- Judas magnitude = macro_high − macro_open
- Real move magnitude = macro_open − macro_close

**Bearish Judas (fake down, real up):**
- Macro low is below macro open
- Macro close is above macro open
- Judas extreme = macro low (the wick)
- Judas magnitude = macro_open − macro_low
- Real move magnitude = macro_close − macro_open

**Trend-through up:**
- Macro low never goes below macro open (no wick below)
- Macro close is above macro open

**Trend-through down:**
- Macro high never goes above macro open (no wick above)
- Macro close is below macro open

There is no neutral category. Every macro is directionally classified.

**Key design decision:** The Judas side is determined by the **outcome** (where the macro closes relative to the open), not by the sequence of moves. If price dips 2 ticks below the open, rallies 15 ticks above, then crashes 10 ticks below, the rally above is the Judas because the macro closes below the open.

**Edge case — price never crosses the open on the Judas side:** In a bullish Judas, the macro high must be above the open. In the case where all bars traded below the open and close is below the open, this is `trend_down`, not a Judas.

**Edge case — small range / noise:** Captured via `macro_range_pct`. Analysis-time filtering by range percentile rather than a hardcoded threshold.

### Indicator Classification (Pine Script Replication)

Replicates the `f_classify()` function from the ICT Macros + Hydra indicator. Uses **pivot highs/lows** (not prior macro levels) as reference.

**Pivot detection:** Replicates TradingView's `ta.pivothigh()` / `ta.pivotlow()` with `length=13` (configurable). A pivot high at bar `i` requires `high[i]` to be the highest high in the range `[i-13, i+13]`. Confirmed 13 bars after occurrence. Forward-filled to provide the most recent confirmed pivot at any point.

**Classification logic:**

```
Inputs: macro_high, macro_low, macro_open, macro_close, macro_mid, pivot_high, pivot_low

If no prior pivot exists, default to current macro high/low (first macro of session).

broke_high = macro_high > pivot_high
broke_low  = macro_low < pivot_low
range      = macro_high - macro_low
q1_upper   = macro_low + range * 0.25
q4_lower   = macro_high - range * 0.25

full_displacement = (open < q1_upper AND close > q4_lower) OR (open > q4_lower AND close < q1_upper)
crossed_mid       = (open > macro_mid AND close < macro_mid) OR (open < macro_mid AND close > macro_mid)

Case 1: broke_high AND broke_low
  → full_displacement ? "Expansion" : "Manip"

Case 2: broke_high OR broke_low (not both)
  → crossed_mid ? "Accum" : "Expansion"

Case 3: neither broken
  → full_displacement ? "Expansion" : "Accum"
```

**Three output labels:** Accumulation, Expansion, Manipulation

**Relationship to Judas classification:** These are independent dimensions. Indicator class describes the macro's relationship to prior market structure. Judas class describes the macro's internal structure relative to its own open. Both stored, both used as conditioning variables.

### All Measurements as Price Percentage

Every magnitude/distance field is stored as a percentage of the macro open price:

```
value_pct = (value - reference) / macro_open * 100
```

Raw price levels are stored for the anchor points (macro_open, macro_high, etc.). Derived measurements use percentage. This enables cross-instrument and cross-time comparability.

---

## Phase 2: FVG Detection & Cataloging

### FVG Definition (Standard Three-Candle)

**Bullish FVG (gap up):**
- Bar 1 high < Bar 3 low
- Gap zone = [Bar 1 high, Bar 3 low]

**Bearish FVG (gap down):**
- Bar 1 low > Bar 3 high
- Gap zone = [Bar 3 high, Bar 1 low]

Applied on 1-minute bars within each macro window. The FVG is considered "completed" on Bar 3.

### FVG Tags (Boolean Flags, Not Mutually Exclusive)

| Tag | Definition |
|-----|-----------|
| `is_first_macro_fvg` | First FVG formed after macro opens, any direction |
| `is_first_presented` | First FVG after the Judas inflection, in the real move direction |
| `is_first_hour_fvg` | First FVG formed after the mid_anchor_open timestamp |
| `is_silver_bullet` | FVG falls within Silver Bullet time windows (10:00–11:00 or 14:00–15:00 ET) |

A single FVG can carry multiple tags simultaneously.

### FVG Phase Classification

Using the Judas inflection timing from Phase 1:
- **judas_phase:** FVG formed before the inflection bar
- **transition:** FVG formed on or near the inflection bar
- **real_move_phase:** FVG formed after the inflection bar

### FVG Direction Pattern

Stored on the macro record as a string encoding: e.g., `"B-B-S-S"` for bullish, bullish, bearish, bearish. Used to derive inter-FVG patterns during analysis:
- **Opposing FVGs:** FVGs on both sides of a swing point → reversal signal
- **Consecutive same-direction:** Two+ FVGs in same direction → continuation signal

These patterns are **derived at analysis time**, not precomputed, to keep the schema lean.

### FVG Lookforward Window

- **Standard macros:** Track until the next standard macro starts (~40 minutes post-macro)
- **Hydra macros:** Track for 1 hour from FVG formation
- Outcomes split into **intra-macro** and **full lookforward** segments

### FVG Outcome Tracking

For each FVG:
- Was it tested (price returned to the gap zone)
- Fill depth (0% = touched edge, 50% = CE, 100% = fully filled)
- Held (respected and continued) vs. failed (price closed through)
- Inversion (failed, then acted as opposite zone on retest)
- MAE/MFE from FVG test as hypothetical entry (percentage-based, not R-multiples)

### Macro-Level FVG Summary Fields

- `has_fvg` — boolean, did any FVG form
- `fvg_count` — total FVGs in macro
- `fvg_direction_pattern` — encoded sequence

### Optional: 5-Minute FVG Layer

Deferred to post-Sprint 2. Run separately on 5-minute parquet data and join back. Evaluate whether 1-minute FVGs that coincide with 5-minute FVGs perform better before adding complexity.

---

## Phase 3: Post-Macro Outcome (Continuation vs. Reversion)

### Measurement Window

Same as FVG lookforward: from macro end until next standard macro starts (standard macros), or 1 hour (Hydra).

### Continuous Measurements (Not Binary Classification)

| Field | Description |
|-------|-------------|
| post_macro_high | Highest price in lookforward window |
| post_macro_low | Lowest price in lookforward window |
| post_macro_close | Price at lookforward cutoff |
| post_macro_continuation_pct | Max move in real move direction from macro close, as % |
| post_macro_reversion_pct | Max move against real move direction from macro close, as % |
| post_macro_net_pct | Net price change to lookforward cutoff, signed, as % |

Classification thresholds (continuation / reversion / stall) are defined at **analysis time**, not baked into the data.

### Macro Mid Retracement Tracking

| Field | Description |
|-------|-------------|
| post_macro_retested_mid | Did price return to macro_mid after macro end |
| mid_retest_time | Minutes after macro end |
| mid_retest_mfe_pct | MFE after mid retest |
| mid_retest_mae_pct | MAE after mid retest |
| mid_retest_held | Did price respect the mid |

### Inter-Macro Sequencing

| Field | Description |
|-------|-------------|
| prior_macro_name | Which macro preceded this one |
| prior_macro_high / low / mid / open | Price levels of prior macro |
| prior_macro_classification | Prior Judas class |
| prior_macro_indicator_class | Prior Accum/Expansion/Manip |
| prior_macro_real_direction | Up or down |
| same_direction_as_prior | Boolean |
| macro_streak | Consecutive macros with same real move direction |

**Prior macro level interaction** (swept prior high, swept prior low, close relative to prior range) is **derived at analysis time** from the stored price levels.

### Macro-Level MAE/MFE

| Field | Description |
|-------|-------------|
| macro_mfe_pct | Max favorable move from macro open through lookforward |
| macro_mae_pct | Max adverse move from macro open through lookforward |
| macro_mfe_bar | Minutes after macro open when MFE reached |
| macro_mae_bar | Minutes after macro open when MAE reached |

---

## Context Fields

### Time-Based Anchors

| Field | Source |
|-------|--------|
| mid_anchor_open | Hourly open (standard) or half-hour open (Hydra) inside window |
| midnight_open | 00:00 ET bar open |
| globex_open | 18:00 ET prior day bar open |
| daily_open | 09:30 ET bar open (null if pre-RTH) |

### RTH Opening Bar (from 9:30 JSON data)

| Field | Description |
|-------|-------------|
| rth_bar_open | 9:30 candle open |
| rth_bar_high | 9:30 candle high |
| rth_bar_low | 9:30 candle low |
| rth_bar_close | 9:30 candle close |
| rth_bar_mid | (high + low) / 2 |
| rth_bar_range_pct | Already computed in source |
| macro_open_vs_rth_bar | above / below / inside the 9:30 bar range |
| macro_open_vs_rth_bar_mid | above / below |

Null for pre-RTH macros (Asia, London, Hydra_1).

### Previous Hour Context

| Field | Description |
|-------|-------------|
| prev_hour_high | High of the full hour before macro start |
| prev_hour_low | Low of the full hour before macro start |
| prev_hour_mid | (high + low) / 2 |

### Session Levels (Developing, as of Macro Start)

| Session | Fields |
|---------|--------|
| Asia | asia_high, asia_low, asia_mid |
| London | london_high, london_low, london_mid |
| Overnight | overnight_high, overnight_low, overnight_mid |
| NY AM | ny_am_high, ny_am_low, ny_am_mid |
| Developing Day | developing_day_high, developing_day_low, developing_day_mid |

These are **developing** values computed from bars prior to macro start. Null when the session hasn't started yet.

### Prior Day Levels

| Field | Description |
|-------|-------------|
| prior_day_high | Previous trading day's high |
| prior_day_low | Previous trading day's low |
| prior_day_mid | (high + low) / 2 |

### Pivot Reference

| Field | Description |
|-------|-------------|
| pivot_high | Most recent confirmed pivot high (length=13) as of macro start |
| pivot_low | Most recent confirmed pivot low (length=13) as of macro start |
| pivot_high_bar_age | Bars since pivot high, relative to macro start |
| pivot_low_bar_age | Bars since pivot low, relative to macro start |

### Volume Context

| Field | Description |
|-------|-------------|
| macro_volume | Total volume during macro window |
| judas_phase_volume | Volume from macro open to inflection bar |
| real_move_phase_volume | Volume from inflection bar to macro close |
| volume_ratio | real_move_volume / judas_volume |
| volume_vs_avg | Macro volume relative to rolling average for that window |
| pre_macro_volume | Volume in 10 minutes before macro started |

### Volatility Regime (from VIX/VVIX daily)

| Field | Description |
|-------|-------------|
| vix_at_macro | Prior day VIX close |
| vvix_at_macro | Prior day VVIX close |
| vix_regime | Categorical: low / medium / high / extreme (percentile-based) |
| atr_20d | 20-day ATR as of that date |

### Calendar / Event Flags

| Field | Description |
|-------|-------------|
| is_monthly_opex | Third Friday of month |
| is_triple_witching | Third Friday of Mar/Jun/Sep/Dec |
| is_opex_week | Full week leading up to monthly opex |
| is_opex_minus_1 | Thursday before opex |
| days_to_monthly_opex | Numeric countdown |
| has_major_event_today | Boolean |
| event_type | FOMC/CPI/NFP/PPI/etc., null if none |
| minutes_to_event | Distance from macro to event time |
| minutes_since_event | Distance after event, null if before |
| is_pre_event_macro | Last macro before the event |
| is_post_event_macro | First macro after the event |

### Candle Structure

| Field | Description |
|-------|-------------|
| macro_body_pct | abs(open - close) / range as percentage |
| upper_wick_pct | Upper wick as % of range |
| lower_wick_pct | Lower wick as % of range |
| macro_candle_type | Derived: marubozu / doji / hammer / shooting_star / etc. |

### Relative Position Flags

| Field | Values |
|-------|--------|
| open_vs_midnight | above / below |
| open_vs_daily_open | above / below |
| open_vs_globex_open | above / below |
| open_vs_prior_day_mid | above / below |
| open_vs_overnight_mid | above / below |
| open_vs_asia_mid | above / below (null if pre-Asia) |
| open_vs_london_mid | above / below (null if pre-London) |

### Time Context

| Field | Description |
|-------|-------------|
| minutes_since_rth_open | How far into RTH session |
| minutes_to_rth_close | How much session time remains |
| is_first_rth_macro | First standard macro after 9:30 |
| is_last_rth_macro | The close macro |
| day_of_month | Numeric |
| week_of_month | 1–4 |
| is_monday / is_friday | Boolean |
| is_first_trading_day_of_week | Boolean |
| is_last_trading_day_of_week | Boolean |
| is_month_end | Last 2 trading days |
| is_quarter_end | Boolean |

---

## Complete Schema Reference

### Table 1: macro_records (one row per macro window per instrument per day)

**Identifiers**
- `date` — trading date
- `day_of_week` — integer (0=Mon–4=Fri) + string
- `instrument` — ES, NQ, YM, RTY, CL, GC
- `macro_name` — generated name: Macro_0050 through Macro_2350, Hydra_1/2/3
- `ict_name` — ICT alias (Asia_1, NY_AM_1, etc.) or null
- `macro_start` — timestamp of window start
- `macro_id` — unique identifier (date + instrument + macro_name)

**Macro Price Action**
- `macro_open`, `macro_high`, `macro_low`, `macro_close`, `macro_mid`
- `macro_volume`

**Macro Timing**
- `macro_high_bar`, `macro_low_bar` — minute into macro
- `extreme_spread` — abs difference
- `judas_first` — boolean

**Macro Internals (% of macro_open)**
- `macro_range_pct`, `excursion_above_pct`, `excursion_below_pct`
- `close_vs_open_pct` — signed
- `bars_above_open`, `bars_below_open`

**Candle Structure**
- `macro_body_pct`, `upper_wick_pct`, `lower_wick_pct`, `macro_candle_type`
- `open_quartile`, `close_quartile` — 1–4 within macro range

**Judas Classification**
- `classification` — bullish_judas / bearish_judas / trend_up / trend_down
- `judas_extreme` — price level
- `judas_magnitude_pct`, `real_move_magnitude_pct`, `judas_to_real_ratio`

**Inflection Timing Fields**
- `judas_inflection_m` — minute of the Judas-side extreme (bullish_judas -> high_offset_m, bearish_judas -> low_offset_m)
- `real_move_extreme_m` — minute of the real-move extreme (bullish_judas -> low_offset_m, bearish_judas -> high_offset_m)

**Indicator Classification**
- `indicator_class` — Accum / Expansion / Manip
- `broke_prior_pivot_high`, `broke_prior_pivot_low` — booleans

**Pivot Reference**
- `pivot_high`, `pivot_low` — price levels
- `pivot_high_bar_age`, `pivot_low_bar_age`

**Volume Context**
- `macro_volume`, `judas_phase_volume`, `real_move_phase_volume`
- `volume_ratio`, `volume_vs_avg`, `pre_macro_volume`

**Time-Based Anchors**
- `mid_anchor_open`, `midnight_open`, `globex_open`, `daily_open`

**RTH Opening Bar**
- `rth_bar_open`, `rth_bar_high`, `rth_bar_low`, `rth_bar_close`, `rth_bar_mid`, `rth_bar_range_pct`
- `macro_open_vs_rth_bar`, `macro_open_vs_rth_bar_mid`

**Previous Hour Context**
- `prev_hour_high`, `prev_hour_low`, `prev_hour_mid`

**Session Levels (developing)**
- `asia_high`, `asia_low`, `asia_mid`
- `london_high`, `london_low`, `london_mid`
- `overnight_high`, `overnight_low`, `overnight_mid`
- `ny_am_high`, `ny_am_low`, `ny_am_mid`
- `developing_day_high`, `developing_day_low`, `developing_day_mid`

**Prior Day Levels**
- `prior_day_high`, `prior_day_low`, `prior_day_mid`

**Prior Macro Context**
- `prior_macro_name`, `prior_macro_high`, `prior_macro_low`, `prior_macro_mid`, `prior_macro_open`
- `prior_macro_classification`, `prior_macro_indicator_class`, `prior_macro_real_direction`
- `same_direction_as_prior`, `macro_streak`

**Relative Position Flags**
- `open_vs_midnight`, `open_vs_daily_open`, `open_vs_globex_open`
- `open_vs_prior_day_mid`, `open_vs_overnight_mid`
- `open_vs_asia_mid`, `open_vs_london_mid`

**Volatility Regime**
- `vix_at_macro`, `vvix_at_macro`, `vix_regime`, `atr_20d`

**Calendar/Event Flags**
- `is_monthly_opex`, `is_triple_witching`, `is_opex_week`, `is_opex_minus_1`, `days_to_monthly_opex`
- `has_major_event_today`, `event_type`, `minutes_to_event`, `minutes_since_event`
- `is_pre_event_macro`, `is_post_event_macro`

**Time Context**
- `minutes_since_rth_open`, `minutes_to_rth_close`
- `is_first_rth_macro`, `is_last_rth_macro`
- `day_of_month`, `week_of_month`
- `is_monday`, `is_friday`, `is_first_trading_day_of_week`, `is_last_trading_day_of_week`
- `is_month_end`, `is_quarter_end`

**FVG Summary (from Phase 2)**
- `has_fvg`, `fvg_count`, `fvg_direction_pattern`

**Post-Macro Outcome (Phase 3)**
- `post_macro_high`, `post_macro_low`, `post_macro_close`
- `post_macro_continuation_pct`, `post_macro_reversion_pct`, `post_macro_net_pct`
- `close_vs_macro_mid_pct`, `close_vs_mid_anchor_pct`
- `post_macro_retested_mid`, `mid_retest_time`, `mid_retest_mfe_pct`, `mid_retest_mae_pct`, `mid_retest_held`

**Macro-Level MAE/MFE**
- `macro_mfe_pct`, `macro_mae_pct`, `macro_mfe_bar`, `macro_mae_bar`

### Table 2: fvg_detail (one row per FVG detected within a macro)

**Identifiers**
- `fvg_id` — unique identifier
- `macro_id` — links to macro_records

**FVG Properties**
- `fvg_type` — bullish / bearish
- `fvg_high`, `fvg_low`, `fvg_mid`
- `fvg_size_pct` — as % of macro_open
- `bar_index` — minute into macro when completed
- `sequence_in_macro` — 1st, 2nd, 3rd etc.
- `phase` — judas_phase / transition / real_move_phase

**Tags (boolean flags)**
- `is_first_macro_fvg`, `is_first_presented`, `is_first_hour_fvg`, `is_silver_bullet`

**Intra-Macro Outcome**
- `tested_intra`, `fill_depth_intra_pct`, `held_intra`

**Full Lookforward Outcome**
- `was_tested`, `test_time`, `fill_depth_pct`, `held`, `failed`

**Inversion**
- `inverted`, `inversion_test_time`, `inversion_held`

**MAE/MFE (from FVG test as hypothetical entry)**
- `mfe_pct`, `mae_pct`, `mfe_time`, `mae_time`

### Table 3: calendar (generated reference, one row per trading date)

- `date`, `is_monthly_opex`, `is_triple_witching`, `is_opex_week`, `is_opex_minus_1`
- `days_to_monthly_opex`
- `has_fomc`, `has_cpi`, `has_nfp`, `has_ppi`, `event_type`, `event_time`

---

## Trade Strategies

### Strategy 1: Intra-Macro FVG Entry

**Setup:**
- Macro window active
- Judas swing identified (price traded on one side of macro open, crossed back through)
- First presented FVG forms in real move direction after inflection

**Entry:** Price retraces to first presented FVG (or FVG consequent encroachment / 50% level)

**Stop:** Behind the Judas extreme (wick high for bullish Judas, wick low for bearish Judas)

**Target:** Driven by continuation/reversion probability model:
- Continuation → next session level in real move direction
- Reversion → tighter target, opposing end of macro range or next macro's range

**Time management:** Data-driven decision on whether to cancel at macro end or hold. Statistics on post-macro FVG entries will inform this.

### Strategy 2: Post-Macro Mid Retracement Entry

**Setup:**
- Macro completed
- Classification determined
- Probability model assigns continuation or reversion with sufficient confidence

**Entry:** Price retraces to macro mid (50% of completed macro range)

**Direction:** Based on probability model prediction

**Stop:**
- Continuation trades → beyond the Judas extreme
- Reversion trades → beyond the macro close

**Target:**
- Continuation → next significant level in real move direction
- Reversion → macro open, mid_anchor_open, or prior macro mid (statistically determined)

### Strategy 3: Macro-to-Macro Sequencing

**Logic:** Use the outcome of one macro to bias the next macro's expected Judas direction. The current macro's classification, indicator class, and post-macro behavior inform the next macro's setup.

### Key Filters (All Strategies)

- Minimum macro range filter (percentile-based)
- VIX regime filter
- Event day filter (exclude or use separate parameters)
- Day of week filter
- Indicator class filter (Manip macros may be untradeable)
- Confidence threshold on continuation/reversion prediction
- Sample size minimum for any probability estimate

### Trade Outcome Measurement

All measured as **price percentage**, not R-multiples:
- MFE (maximum favorable excursion) from entry
- MAE (maximum adverse excursion) from entry
- At various MFE thresholds, probability of retracing to entry ("cover the queen" analysis)
- Distribution of outcomes drives stop/target selection

### FVG-Based Trade Management Signals

- Opposing FVG forms during the trade → tighten stop or take partial profits (reversal warning)
- Consecutive same-direction FVGs → confirms trade direction (continuation signal)

---

## Implementation Plan

### Sprint 1: Macro Extraction & Classification

**Goal:** Produce preliminary `macro_records.parquet` with identifiers, OHLC, volume, timing, Judas classification, and indicator classification.

**Module structure:**
```
ROOT/scripts/edgeful/
├── __init__.py
├── config.py          # Macro windows, session times, parameters
├── data_loader.py     # Load parquet, normalize, UTC→ET
├── macro_extractor.py # Extract macro windows, compute OHLCV
├── classifiers.py     # Judas + indicator classification
├── pivots.py          # ta.pivothigh/low replication (length=13)
├── pipeline.py        # Orchestrates everything, produces output
└── validate.py        # Validation checks against TradingView
```

**Build order:**
1. data_loader — load, normalize, convert timezone
2. macro_extractor — extract windows, compute basic OHLCV and timing
3. pivots — replicate pivot high/low detection
4. classifiers — Judas + indicator classification
5. pipeline — orchestrate and output
6. validate — spot-check 10–15 instances against TradingView

**Sprint 1 scope boundary:** Sprint 1 output includes ONLY: identifiers, macro OHLC, volume, timing fields, Judas classification, indicator classification, pivot reference, candle structure, and basic derived percentages. Do NOT implement FVG detection, context level joins, post-macro tracking, session levels, daily scenario joins, inter-macro sequencing, calendar/event flags, VIX regime, or any Phase 2/3 fields in Sprint 1.

#### Sprint 1 Implementation Clarifications & Gotchas

**1. Trading Date Assignment (CRITICAL)**

Futures session runs 18:00 ET to 17:00 ET next day. Any bar with ET timestamp >= 18:00 belongs to the NEXT calendar day's trading date.

```python
def get_trading_date(et_timestamp: pd.Timestamp) -> date:
    """
    18:00 ET Monday → Tuesday's trading date
    09:30 ET Tuesday → Tuesday's trading date
    17:00 ET Tuesday → Tuesday's trading date (last bar of session)
    18:00 ET Friday → Monday's trading date (skip weekend)
    18:00 ET Sunday → Monday's trading date
    """
    if et_timestamp.hour >= 18:
        next_day = et_timestamp.date() + timedelta(days=1)
        # Skip weekends
        if next_day.weekday() == 5:  # Saturday
            next_day += timedelta(days=2)
        elif next_day.weekday() == 6:  # Sunday
            next_day += timedelta(days=1)
        return next_day
    else:
        return et_timestamp.date()
```

All Asia macros (18:50, 19:50, 20:50 ET) belong to the NEXT day's trading date. This is essential — getting it wrong breaks all session level joins and inter-macro sequencing.

**2. Macro Windows Crossing Midnight**

The Macro_2350 window (23:50–00:10) crosses midnight. The start and end are on different calendar dates but the same trading date. Bar filtering CANNOT use simple `hour >= start AND hour <= end` when end_hour < start_hour.

```python
def get_macro_bars(day_df, start_hour, start_min, end_hour, end_min):
    """
    Handle both same-day and cross-midnight windows.
    """
    start_time = time(start_hour, start_min)
    end_time = time(end_hour, end_min)
    
    if end_time > start_time:
        # Normal case: e.g., 09:50 to 10:10
        mask = (day_df.index.time >= start_time) & (day_df.index.time < end_time)
    else:
        # Cross-midnight: e.g., 23:50 to 00:10
        mask = (day_df.index.time >= start_time) | (day_df.index.time < end_time)
    
    return day_df[mask]
```

**3. Timestamp Handling**

The raw data `timestamp` column contains naive UTC strings like `"2025-01-01 23:00:00"`. The `time` column is epoch milliseconds. Use the `timestamp` string column:

```python
df['datetime'] = pd.to_datetime(df['timestamp'])
df['datetime'] = df['datetime'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
df = df.set_index('datetime').sort_index()
```

CRITICAL: Do NOT treat the naive timestamp as ET. It is UTC. The conversion to US/Eastern handles DST automatically via `zoneinfo`/`pytz`.

**4. DST Transitions**

When clocks spring forward (March): 2:00 AM ET jumps to 3:00 AM. Macro windows during the missing hour (e.g., Macro_0250 = 02:50–03:10) will have fewer bars or no bars. Handle gracefully — if fewer than N bars exist in a window, mark the macro as `incomplete` or skip it. Do NOT crash.

When clocks fall back (November): 1:00 AM ET occurs twice. The `tz_convert` function handles this with fold disambiguation, but verify that bar filtering doesn't double-count bars during the ambiguous hour.

Implementation: After converting to ET, check for any duplicate timestamps and resolve them. Use `ambiguous='NaT'` or `ambiguous='infer'` as appropriate.

**5. Percentage Calculations — Sign Conventions**

```python
# ALWAYS positive (or zero):
excursion_above_pct = (macro_high - macro_open) / macro_open * 100
excursion_below_pct = (macro_open - macro_low) / macro_open * 100
macro_range_pct     = (macro_high - macro_low) / macro_open * 100
judas_magnitude_pct = abs(judas_extreme - macro_open) / macro_open * 100
real_move_magnitude_pct = abs(macro_close - macro_open) / macro_open * 100

# SIGNED (positive = close above open, negative = close below):
close_vs_open_pct = (macro_close - macro_open) / macro_open * 100
```

Do NOT use absolute values on `close_vs_open_pct` — the sign carries directional information.

**6. Judas Classification — Both Sides Can Have Excursion**

The most common case is that macro_high > macro_open AND macro_low < macro_open (price went both directions). Classification is determined SOLELY by where the close is relative to the open:

```python
def classify_judas(macro_open, macro_high, macro_low, macro_close):
    has_excursion_above = macro_high > macro_open
    has_excursion_below = macro_low < macro_open
    close_above = macro_close >= macro_open
    close_below = macro_close < macro_open

    if close_below and has_excursion_above:
        return "bullish_judas"    # Fake up, real down
    elif close_above and has_excursion_below:
        return "bearish_judas"    # Fake down, real up
    elif close_above and not has_excursion_below:
        return "trend_up"         # No fake, just went up
    elif close_below and not has_excursion_above:
        return "trend_down"       # No fake, just went down
    return "trend_up"             # Exact flat edge case (open==high==low==close)
```

Do NOT add logic requiring the Judas side to have "more" excursion than the real side. A 2-tick wick above the open with a close 15 ticks below is still a bullish Judas.

Note on `has_excursion_above`: Use strict inequality `macro_high > macro_open`, not `>=`. If the high exactly equals the open (no wick above at all), there is no Judas upward move.

**7. Indicator Classification — Exact Quartile Logic**

The Pine Script uses STRICT inequality (`<` and `>`, not `<=` and `>=`). Replicate exactly:

```python
rng = macro_high - macro_low
q1_upper = macro_low + rng * 0.25
q4_lower = macro_high - rng * 0.25

# Strict inequalities — matching Pine Script
open_in_bottom_q = macro_open < q1_upper    # strict <
open_in_top_q    = macro_open > q4_lower    # strict >
close_in_bottom_q = macro_close < q1_upper  # strict <
close_in_top_q    = macro_close > q4_lower  # strict >

full_displacement = (open_in_bottom_q and close_in_top_q) or \
                    (open_in_top_q and close_in_bottom_q)

crossed_mid = (macro_open > macro_mid and macro_close < macro_mid) or \
              (macro_open < macro_mid and macro_close > macro_mid)
```

**8. Pivot Detection — Forward-Fill and Fallback**

After computing pivots on the full 1-minute series:
- Forward-fill the most recent confirmed pivot high and pivot low so that at any bar, `pivot_high` and `pivot_low` have values.
- At the start of the dataset (before any pivot is confirmed, which takes at least `PIVOT_LENGTH * 2 + 1 = 27` bars), pivot values will be NaN.
- For the indicator classification, if pivot_high is NaN, fall back to the current macro's own high. If pivot_low is NaN, fall back to the current macro's own low. This replicates Pine Script's `nz()` behavior:

```python
piv_h = pivot_high if not pd.isna(pivot_high) else macro_high
piv_l = pivot_low if not pd.isna(pivot_low) else macro_low
```

Do NOT leave NaN values flowing into the classification function.

**9. `macro_high_bar` / `macro_low_bar` — Last Occurrence**

If multiple bars print the same extreme (e.g., three bars all hit the same high), use the LAST one:

```python
# Get the minute index of the LAST bar that hit the macro high
macro_bars = day_df[macro_mask]
high_bars = macro_bars[macro_bars['high'] == macro_high]
macro_high_bar = (high_bars.index[-1] - macro_start).total_seconds() / 60  # last occurrence

low_bars = macro_bars[macro_bars['low'] == macro_low]
macro_low_bar = (low_bars.index[-1] - macro_start).total_seconds() / 60   # last occurrence
```

Using pandas `.idxmax()` gives the FIRST occurrence by default. Either use `.iloc[-1]` on filtered bars or reverse the search.

**10. Open Quartile / Close Quartile Computation**

Quartiles divide the macro range into four equal parts:
- Q1: macro_low to macro_low + 25% of range (bottom quarter)
- Q2: 25% to 50%
- Q3: 50% to 75%
- Q4: 75% to macro_high (top quarter)

```python
rng = macro_high - macro_low
if rng == 0:
    open_quartile = 2  # midpoint default for zero-range
    close_quartile = 2
else:
    open_pct = (macro_open - macro_low) / rng  # 0.0 to 1.0
    open_quartile = min(int(open_pct * 4) + 1, 4)  # 1 to 4
    
    close_pct = (macro_close - macro_low) / rng
    close_quartile = min(int(close_pct * 4) + 1, 4)
```

**11. Candle Type Classification**

```python
rng = macro_high - macro_low
if rng == 0:
    candle_type = "doji"
else:
    body = abs(macro_close - macro_open)
    body_pct = body / rng * 100
    upper_wick = macro_high - max(macro_open, macro_close)
    lower_wick = min(macro_open, macro_close) - macro_low
    upper_wick_pct = upper_wick / rng * 100
    lower_wick_pct = lower_wick / rng * 100
    
    if body_pct > 80:
        candle_type = "marubozu"
    elif body_pct < 20:
        candle_type = "doji"
    elif lower_wick_pct > 60 and upper_wick_pct < 20:
        candle_type = "hammer" if macro_close > macro_open else "hanging_man"
    elif upper_wick_pct > 60 and lower_wick_pct < 20:
        candle_type = "shooting_star" if macro_close < macro_open else "inverted_hammer"
    else:
        candle_type = "standard"
```

**12. Volume Fields in Sprint 1**

Sprint 1 captures `macro_volume` (sum of all bars in the window). The phase-split volume fields (`judas_phase_volume`, `real_move_phase_volume`, `volume_ratio`) require the inflection bar timing, which is available in Sprint 1. Include these if straightforward, otherwise defer to Sprint 2.

`volume_vs_avg` (relative to rolling average for that window) and `pre_macro_volume` (10 min before macro) can be deferred to Sprint 2 as they require cross-day aggregation.

**13. Holidays and Missing Data**

Some trading days are shortened (half days before holidays) or missing entirely. If a macro window has zero bars, skip it entirely — do not create a record. If a macro window has fewer bars than expected (e.g., 15 bars instead of 20 due to a half day or data gap), create the record but add a flag:

```python
expected_bars = 20  # for standard macros
actual_bars = len(macro_bars)
is_complete = actual_bars >= expected_bars - 1  # allow 1 bar tolerance
```

Store `bar_count` and `is_complete` on each record so analysis can filter out incomplete macros.

**14. `judas_first` Derivation**

```python
if classification in ("bullish_judas",):
    # Judas extreme is the high, real move extreme is the low
    judas_first = macro_high_bar < macro_low_bar
elif classification in ("bearish_judas",):
    # Judas extreme is the low, real move extreme is the high
    judas_first = macro_low_bar < macro_high_bar
else:
    judas_first = None  # Not applicable for trend_up/trend_down
```

**15. `judas_to_real_ratio` — Division by Zero**

If `real_move_magnitude_pct` is zero, the ratio is undefined. Set to `None`/`NaN`:

```python
if real_move_magnitude_pct > 0:
    judas_to_real_ratio = judas_magnitude_pct / real_move_magnitude_pct
else:
    judas_to_real_ratio = None
```

### Sprint 2: Context Joins & FVG Detection

**Goal:** Add all context fields (session levels, daily scenarios join, VIX, calendar, 9:30 bar) and FVG detection/tracking.

**Build order:**
1. Context level computation (session levels, previous hour, prior day)
2. Join to daily scenarios CSV
3. Join to 9:30 bar JSON
4. Join to VIX/VVIX daily
5. Generate and join calendar table (OpEx, events)
6. FVG detection within macros
7. FVG tagging and outcome tracking
8. Post-macro outcome computation
9. Inter-macro sequencing fields
10. Output final parquet files

**Sprint 2 scope:** All context fields from the schema, FVG detail table, post-macro outcome fields, inter-macro sequencing, MAE/MFE. After Sprint 2, both output parquet files (macro_records, fvg_detail) are complete.

#### Sprint 2 Implementation Clarifications & Gotchas

**1. Session Level Computation — "Developing" Values**

Session levels must be computed as of macro start time, not end-of-day values. For the 10:50 macro, `ny_am_high` is the highest high from 09:30 to 10:49, NOT the full NY AM session high. This means session levels grow throughout the day — the 9:50 macro's `ny_am_high` only includes 20 minutes of NY AM data, while the 11:50 macro's includes over 2 hours.

Implementation: For each macro, filter the 1-minute data from session start to macro start (exclusive), then compute high/low/mid.

```python
def get_developing_session_level(df, session_start_time, macro_start_time):
    """
    Compute high/low/mid from session_start up to (but not including) macro_start.
    Returns None if session hasn't started yet.
    """
    mask = (df.index >= session_start_time) & (df.index < macro_start_time)
    session_bars = df[mask]
    if len(session_bars) == 0:
        return None, None, None
    return session_bars['high'].max(), session_bars['low'].min(), \
           (session_bars['high'].max() + session_bars['low'].min()) / 2
```

**2. Session Boundaries and Null Handling**

For macros that occur before a session starts, the session levels are null:
- Asia macros → `london_high/low/mid` = null, `ny_am_high/low/mid` = null
- London macros → `ny_am_high/low/mid` = null
- Hydra_1 (08:20) → `ny_am_high/low/mid` = null (RTH hasn't started)

Do NOT fill these with zeros or defaults. They must be null/NaN so analysis correctly handles them.

**3. Prior Day Levels — Trading Day, Not Calendar Day**

`prior_day_high/low/mid` refers to the previous TRADING day's full session (18:00 to 17:00 ET). For Monday's macros, the prior day is Friday (skip weekend). Use the same `get_trading_date()` function to group bars by trading day, then look up the prior trading day's aggregates.

**4. Previous Hour Context**

`prev_hour_high/low/mid` is the full 60-minute hour BEFORE the macro starts. For the 9:50 macro, this is 08:50–09:49 (the full 60 minutes immediately before). NOT the 09:00 hour — it's a rolling 60-minute lookback.

Wait — clarification needed: in our design discussion, we defined this as "the hour containing the bars before macro start." Re-reading the conversation, the intent was the full clock hour before the macro. For the 9:50 macro, that's the 9:00–9:59 hour. But only bars from 9:00 to 9:49 are available since the macro starts at 9:50.

Implementation: Use the clock hour before the macro starts. For Macro_0950, prev_hour = bars from 09:00 to 09:49. For Macro_1050, prev_hour = bars from 10:00 to 10:49.

```python
prev_hour_start = macro_start.replace(minute=0, second=0)
prev_hour_bars = df[(df.index >= prev_hour_start) & (df.index < macro_start)]
```

**5. Daily Scenarios CSV Join**

The daily scenarios CSV (in `ROOT\docs\research\ict\data\`) has one row per trading date. Join on `date` column. Verify the date format matches between the macro pipeline output and the CSV. The CSV dates look like `"2006-01-09"` — ensure the macro pipeline's `date` field is the same format.

Not all fields from the CSV need to be duplicated into the macro table. The join can happen at query time in DuckDB. Only pull in fields that are needed for per-macro computation (e.g., session levels if they differ from our computed developing values).

**6. 9:30 Opening Bar JSON Join**

The JSON has one record per trading date with the RTH opening candle. Join on date. All fields (`rth_bar_open/high/low/close/mid/range_pct`) go onto every macro for that date. Pre-RTH macros (Asia, London, Hydra_1) still get the values (from the previous day's 9:30 bar? Or null?).

Decision: For pre-RTH macros on the current trading date, the current day's 9:30 bar hasn't happened yet. Set these to null. The `macro_open_vs_rth_bar` position fields are also null for pre-RTH macros.

**7. FVG Detection — Bar Indexing Within Macros**

FVGs require three consecutive bars (Bar 1, Bar 2, Bar 3). The FVG "completes" on Bar 3. The `bar_index` field should record Bar 3's minute into the macro.

For a 20-minute macro (20 bars at 1-minute), the first possible FVG completes on minute 2 (bars 0, 1, 2) and the last on minute 19 (bars 17, 18, 19). Verify the bar indexing is zero-based or one-based and be consistent.

```python
def detect_fvgs(macro_bars: pd.DataFrame) -> list[dict]:
    """
    Scan consecutive triplets of 1-minute bars within a macro.
    
    Bullish FVG: bars[i].high < bars[i+2].low
    Bearish FVG: bars[i].low > bars[i+2].high
    
    Returns list of FVG dicts with properties.
    """
    fvgs = []
    bars = macro_bars.reset_index()
    for i in range(len(bars) - 2):
        bar1_high = bars.iloc[i]['high']
        bar1_low = bars.iloc[i]['low']
        bar3_high = bars.iloc[i+2]['high']
        bar3_low = bars.iloc[i+2]['low']
        
        if bar1_high < bar3_low:  # Bullish FVG
            fvgs.append({
                'fvg_type': 'bullish',
                'fvg_high': bar3_low,    # top of gap
                'fvg_low': bar1_high,    # bottom of gap
                'bar_index': i + 2,      # Bar 3 position
            })
        elif bar1_low > bar3_high:  # Bearish FVG
            fvgs.append({
                'fvg_type': 'bearish',
                'fvg_high': bar1_low,    # top of gap
                'fvg_low': bar3_high,    # bottom of gap
                'bar_index': i + 2,
            })
    return fvgs
```

**8. FVG Phase Tagging**

The `phase` tag requires the Judas inflection bar from Phase 1. Define "transition" as the inflection bar ± 1 minute:

```python
inflection_bar = macro_high_bar if classification == 'bullish_judas' else macro_low_bar

if fvg_bar_index < inflection_bar - 1:
    phase = 'judas_phase'
elif fvg_bar_index <= inflection_bar + 1:
    phase = 'transition'
else:
    phase = 'real_move_phase'
```

For trend_up/trend_down classifications, all FVGs are tagged as `real_move_phase` since there's no Judas inflection.

**9. `is_first_presented` Tag**

This is the first FVG that meets ALL of these criteria:
- Formed AFTER the inflection bar
- Direction matches the real move (bearish FVG for bullish_judas, bullish FVG for bearish_judas)

Only one FVG per macro can have this flag set to True.

```python
first_presented_found = False
for fvg in sorted(fvgs, key=lambda x: x['bar_index']):
    if not first_presented_found and fvg['bar_index'] > inflection_bar:
        if (classification == 'bullish_judas' and fvg['fvg_type'] == 'bearish') or \
           (classification == 'bearish_judas' and fvg['fvg_type'] == 'bullish'):
            fvg['is_first_presented'] = True
            first_presented_found = True
```

**10. `is_silver_bullet` Tag**

Silver Bullet windows are 10:00–11:00 ET and 14:00–15:00 ET. Convert the FVG's absolute timestamp (not just bar_index) to check:

```python
fvg_time = macro_start + timedelta(minutes=fvg['bar_index'])
fvg_hour = fvg_time.hour
is_silver_bullet = (10 <= fvg_hour < 11) or (14 <= fvg_hour < 15)
```

**11. FVG Lookforward Outcome Tracking**

The lookforward window extends beyond the macro. You need access to bars AFTER the macro ends. The pipeline should pre-load a buffer of bars beyond each macro window:

```python
# For standard macros: lookforward until next standard macro starts (~40 min)
# For Hydra: lookforward for 60 minutes from macro end
lookforward_end = next_standard_macro_start  # or macro_end + 60min for Hydra

post_bars = df[(df.index >= macro_end) & (df.index < lookforward_end)]
```

For `was_tested`: check if any bar in the lookforward window has a low <= fvg_high (for bullish FVG) or high >= fvg_low (for bearish FVG).

For `fill_depth_pct`: measure how deep into the FVG zone price penetrated:
```python
if fvg_type == 'bullish':
    deepest_fill = post_bars['low'].min()
    fill_depth = (fvg_high - max(deepest_fill, fvg_low)) / (fvg_high - fvg_low) * 100
elif fvg_type == 'bearish':
    deepest_fill = post_bars['high'].max()
    fill_depth = (min(deepest_fill, fvg_high) - fvg_low) / (fvg_high - fvg_low) * 100
```

**12. FVG Inversion Detection**

An inversion requires a sequence: (1) FVG fails (price closes through it entirely), then (2) price returns to the zone from the other side, and (3) the zone holds as the new support/resistance.

```python
# Step 1: Detect failure
if fvg_type == 'bullish':
    failed = any(post_bars['close'] < fvg_low)  # closed below the entire gap
    # Step 2: After failure, did price come back up to the FVG zone?
    failure_bar = post_bars[post_bars['close'] < fvg_low].index[0]
    post_failure = post_bars[post_bars.index > failure_bar]
    retested = any(post_failure['high'] >= fvg_low)  # came back to zone
    # Step 3: Did the zone hold as resistance?
    if retested:
        retest_bar = post_failure[post_failure['high'] >= fvg_low].index[0]
        post_retest = post_failure[post_failure.index > retest_bar]
        inversion_held = not any(post_retest['close'] > fvg_high)
```

This is complex — if it adds too much Sprint 2 time, defer inversion detection to Sprint 2.5 or Sprint 3.

**13. Inter-Macro Sequencing — Ordering**

Macros must be sorted chronologically within each trading day per instrument before computing prior macro fields. The sort order is Asia macros → London macros → Hydra macros → NY macros. Since we generate 24 standard macros + 3 Hydra, interleaving them correctly matters.

Sort by `macro_start` timestamp, not by `macro_name` alphabetically.

**14. `macro_streak` Computation**

Count consecutive macros with the same real move direction. Reset the streak when direction changes:

```python
# Within a single day's macros for one instrument, sorted by macro_start
streak = 1
for i in range(1, len(day_macros)):
    if day_macros[i].real_direction == day_macros[i-1].real_direction:
        streak += 1
    else:
        streak = 1
    day_macros[i].macro_streak = streak
```

The streak does NOT carry across trading days — reset at each new trading date.

**15. Post-Macro Continuation/Reversion Direction**

The "continuation direction" is the direction of the real move. For a bullish_judas (real move is DOWN), continuation means price continues DOWN after the macro, reversion means price goes back UP.

```python
if classification in ('bullish_judas', 'trend_down'):
    real_direction = 'down'
    continuation_pct = (macro_close - post_macro_low) / macro_open * 100   # positive = continued down
    reversion_pct = (post_macro_high - macro_close) / macro_open * 100     # positive = reverted up
elif classification in ('bearish_judas', 'trend_up'):
    real_direction = 'up'
    continuation_pct = (post_macro_high - macro_close) / macro_open * 100  # positive = continued up
    reversion_pct = (macro_close - post_macro_low) / macro_open * 100      # positive = reverted down
```

Both `continuation_pct` and `reversion_pct` should be positive values representing the magnitude of the move in each direction. `post_macro_net_pct` is signed.

### Sprint 3: Interactive Dashboard MVP

**Goal:** Edgeful-style web interface with basic filtering and probability display.

**Features:**
- 5–6 key filter variables (macro window, classification, indicator class, VIX regime, day of week, event flag)
- Probability distributions update as filters change
- Sample size displayed for every query
- Distribution charts (inflection timing, MFE/MAE, continuation/reversion)
- Drill-down to individual macro instances

**Tech stack:** Next.js (existing), DuckDB for analytical queries, Prisma DB for reference data.

### Sprint 4+: Enhancements

- 5-minute FVG layer
- Additional scenario integration from daily CSV
- Pine Script translation of winning rules
- GEX/DEX overlay integration
- More dashboard features (side-by-side comparison, custom scenario builder, etc.)

---

## Parameters & Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| PIVOT_LENGTH | 13 | Lookback/lookforward for pivot detection |
| EXCLUDED_STANDARD_MACRO_START_HOURS | {17} | Excludes invalid 17:50 standard macro |
| STANDARD_MACRO_DURATION | 20 min | XX:50 to XX+1:10 |
| HYDRA_MACRO_DURATION | 20 min | XX:20 to XX:40 |
| LOOKFORWARD_STANDARD | Until next standard macro start | ~40 min post-macro |
| LOOKFORWARD_HYDRA | 60 min | From FVG/macro formation |

All parameters stored in `config.py` and recorded in `metadata.json` alongside output parquet files for reproducibility.

---

## File Locations & Data Paths

### Input Data Locations

| Data | Path | Format |
|------|------|--------|
| 1-minute OHLCV | `C:\Users\vinay\tvDownloadOHLC\data\{INST}_1m.parquet` | Parquet |
| 5-minute OHLCV | `C:\Users\vinay\tvDownloadOHLC\data\{INST}_5m.parquet` | Parquet |
| 9:30 Opening Bar | `C:\Users\vinay\tvDownloadOHLC\data\` (JSON) | JSON |
| Daily Scenarios CSV | `ROOT\docs\research\ict\data\` | CSV |
| VIX/VVIX Daily | `C:\Users\vinay\tvDownloadOHLC\data\` | Existing format |
| News/Events | Prisma DB (SQLite) | SQLite |

### Pipeline Code Location

```
ROOT\scripts\edgeful\
├── __init__.py
├── config.py
├── data_loader.py
├── macro_extractor.py
├── classifiers.py
├── pivots.py
├── pipeline.py
└── validate.py
```

### Pipeline Output Location

Output parquet files written to a location TBD within the existing project structure (to be decided during implementation to avoid data duplication).

### config.py Path Constants

```python
import os
from pathlib import Path

# Adjust ROOT as needed for your project structure
OHLCV_DATA_DIR = Path(r"C:\Users\vinay\tvDownloadOHLC\data")
ICT_RESEARCH_DIR = Path(os.environ.get("PROJECT_ROOT", ".")) / "docs" / "research" / "ict" / "data"

# Input files
def get_1m_path(instrument: str) -> Path:
    return OHLCV_DATA_DIR / f"{instrument}_1m.parquet"

def get_5m_path(instrument: str) -> Path:
    return OHLCV_DATA_DIR / f"{instrument}_5m.parquet"

# Instruments available
INSTRUMENTS = {
    "ES1": "ES",
    "NQ1": "NQ",
    "YM1": "YM",
    "RTY1": "RTY",
    "CL1": "CL",
    "GC1": "GC",
}
```
