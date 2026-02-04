# Mission Control - Calculation Specifications

**Version:** 1.0.0
**Last Updated:** 2026-02-03

---

## Purpose

This document provides **platform-agnostic calculation specifications** for all Mission Control components. Each specification includes:

1. **Algorithm Description**: What the calculation does and why.
2. **Inputs**: Required data inputs with types and formats.
3. **Outputs**: Expected outputs with types and formats.
4. **Pseudocode**: Step-by-step logic implementable in any language.
5. **Edge Cases**: Handling of missing data, holidays, etc.
6. **Implementation Notes**: Platform-specific considerations.

These specifications enable implementation in:
- **Python** (primary dashboard backend)
- **PineScript** (TradingView indicators/strategies)
- **NinjaTrader** (NinjaScript indicators/strategies)
- **Any other platform**

---

## Table of Contents

1. [EMA Zone Probability Analysis](#1-ema-zone-probability-analysis)
2. [Premium/Discount Multi-Timeframe](#2-premiumdiscount-multi-timeframe)
3. [Session Fuel/Distribution](#3-session-fueldistribution)
4. [Regime Streak Analysis](#4-regime-streak-analysis)
5. [Candle Science C3 Projection](#5-candle-science-c3-projection)
6. [Daily HOD/LOD Timing](#6-daily-hodlod-timing)
7. [Session Status (Long/Short TRUE/FALSE)](#7-session-status-longshort-truefalse)

---

## 1. EMA Zone Probability Analysis

### 1.1 Algorithm Description

Calculate the probability that price will reach certain percentage distances from the Daily 5 EMA. Used to identify high-probability support/resistance zones.

### 1.2 Inputs

| Input | Type | Description |
| :--- | :--- | :--- |
| `close_prices` | Array[float] | Daily close prices (adjusted or unadjusted) |
| `high_prices` | Array[float] | Daily high prices |
| `low_prices` | Array[float] | Daily low prices |
| `ema_period` | int | EMA period (default: 5) |
| `zone_levels` | Array[float] | Percentage levels to analyze (e.g., [0.5, 1, 1.5, 2, 2.5, 3]) |
| `lookback_weeks` | int | Number of weeks to analyze (default: 52) |

### 1.3 Outputs

| Output | Type | Description |
| :--- | :--- | :--- |
| `current_ema` | float | Current EMA value |
| `current_distance_pct` | float | Current price distance from EMA as % |
| `zone_levels` | Array[ZoneLevel] | Array of zone statistics |

```typescript
interface ZoneLevel {
  level_pct: number;      // e.g., 2.0 for 2%
  price_above: number;    // EMA + (EMA * level_pct / 100)
  price_below: number;    // EMA - (EMA * level_pct / 100)
  hit_rate_up: number;    // % of weeks price touched this level going UP
  hit_rate_down: number;  // % of weeks price touched this level going DOWN
  status: 'Good' | 'Fair' | 'Fail';
}
```

### 1.4 Pseudocode

```
FUNCTION calculate_ema_zones(close, high, low, ema_period, zone_levels, lookback_weeks):
    
    # Step 1: Calculate EMA
    ema = EMA(close, ema_period)
    
    # Step 2: Define weekly periods
    weeks = group_data_by_week(close, high, low, ema)
    weeks = weeks[-lookback_weeks:]  # Last N weeks
    
    # Step 3: For each week, calculate distance extremes
    FOR each week IN weeks:
        week.max_distance_up = MAX((week.high - week.ema_at_start) / week.ema_at_start * 100)
        week.max_distance_down = MAX((week.ema_at_start - week.low) / week.ema_at_start * 100)
    
    # Step 4: Calculate hit rates for each zone level
    results = []
    FOR each level IN zone_levels:
        weeks_hit_up = COUNT(weeks WHERE max_distance_up >= level)
        weeks_hit_down = COUNT(weeks WHERE max_distance_down >= level)
        
        hit_rate_up = weeks_hit_up / LEN(weeks) * 100
        hit_rate_down = weeks_hit_down / LEN(weeks) * 100
        
        # Determine status based on hit rate
        IF hit_rate_up >= 60 OR hit_rate_down >= 40:
            status = 'Good'
        ELSE IF hit_rate_up >= 40 OR hit_rate_down >= 25:
            status = 'Fair'
        ELSE:
            status = 'Fail'
        
        results.append({
            level_pct: level,
            price_above: current_ema * (1 + level/100),
            price_below: current_ema * (1 - level/100),
            hit_rate_up: hit_rate_up,
            hit_rate_down: hit_rate_down,
            status: status
        })
    
    RETURN {
        current_ema: ema[-1],
        current_distance_pct: (close[-1] - ema[-1]) / ema[-1] * 100,
        zone_levels: results
    }
```

### 1.5 Edge Cases

| Edge Case | Handling |
| :--- | :--- |
| Insufficient data | Return null; require minimum `ema_period + lookback_weeks * 5` bars |
| Week with no trading (holiday) | Skip week in analysis |
| EMA crosses through zero | Not applicable for futures prices |

### 1.6 Implementation Notes

**PineScript:**
```pinescript
ema5 = ta.ema(close, 5)
distance_pct = (close - ema5) / ema5 * 100
// Weekly aggregation requires request.security() with weekly timeframe
```

**NinjaScript:**
```csharp
EMA ema5 = EMA(Close, 5);
double distancePct = (Close[0] - ema5[0]) / ema5[0] * 100;
```

---

## 2. Premium/Discount Multi-Timeframe

### 2.1 Algorithm Description

Determine if current price is in the Premium (upper 50%) or Discount (lower 50%) zone of a range across multiple timeframes.

### 2.2 Inputs

| Input | Type | Description |
| :--- | :--- | :--- |
| `current_price` | float | Current price |
| `timeframes` | Array[string] | Timeframes to analyze (e.g., ['1W', '1D', '4H', '1H', '15m']) |
| `range_type` | string | 'previous_bar' or 'swing' |

### 2.3 Outputs

| Output | Type | Description |
| :--- | :--- | :--- |
| `analysis` | Array[TFAnalysis] | Array of per-timeframe analysis |

```typescript
interface TFAnalysis {
  timeframe: string;
  range_high: number;
  range_low: number;
  equilibrium: number;     // (high + low) / 2
  current_price: number;
  zone: 'PREMIUM' | 'DISCOUNT' | 'EQUILIBRIUM';
  position_pct: number;    // 0% = low, 50% = EQ, 100% = high
}
```

### 2.4 Pseudocode

```
FUNCTION calculate_premium_discount(current_price, timeframes):
    
    results = []
    
    FOR each tf IN timeframes:
        
        # Step 1: Get range for this timeframe
        IF range_type == 'previous_bar':
            range_high = previous_bar(tf).high
            range_low = previous_bar(tf).low
        ELSE IF range_type == 'swing':
            range_high = recent_swing_high(tf)
            range_low = recent_swing_low(tf)
        
        # Step 2: Calculate equilibrium (50% level)
        equilibrium = (range_high + range_low) / 2
        
        # Step 3: Calculate position percentage
        # 0% = at low, 100% = at high
        range_size = range_high - range_low
        IF range_size > 0:
            position_pct = (current_price - range_low) / range_size * 100
        ELSE:
            position_pct = 50  # No range = at equilibrium
        
        # Step 4: Determine zone
        IF position_pct > 55:
            zone = 'PREMIUM'
        ELSE IF position_pct < 45:
            zone = 'DISCOUNT'
        ELSE:
            zone = 'EQUILIBRIUM'  # Within 5% of 50%
        
        results.append({
            timeframe: tf,
            range_high: range_high,
            range_low: range_low,
            equilibrium: equilibrium,
            current_price: current_price,
            zone: zone,
            position_pct: position_pct
        })
    
    RETURN results
```

### 2.5 Edge Cases

| Edge Case | Handling |
| :--- | :--- |
| Range is zero (doji) | Return 50% position, EQUILIBRIUM zone |
| Price outside range | Cap position_pct at 0% or 100%, mark as "EXTENDED_PREMIUM" or "EXTENDED_DISCOUNT" |
| Missing timeframe data | Skip timeframe, return partial results |

### 2.6 Implementation Notes

**PineScript:**
```pinescript
// Weekly range
[w_high, w_low] = request.security(syminfo.tickerid, "W", [high[1], low[1]])
w_eq = (w_high + w_low) / 2
w_pos_pct = (close - w_low) / (w_high - w_low) * 100
w_zone = w_pos_pct > 55 ? "PREMIUM" : w_pos_pct < 45 ? "DISCOUNT" : "EQUILIBRIUM"
```

**Drawing Boxes in PineScript:**
```pinescript
// Premium zone (upper 50%)
box.new(bar_index - 100, range_high, bar_index, equilibrium, 
        bgcolor=color.new(color.green, 80), border_color=color.green)
// Discount zone (lower 50%)
box.new(bar_index - 100, equilibrium, bar_index, range_low, 
        bgcolor=color.new(color.red, 80), border_color=color.red)
```

---

## 3. Session Fuel/Distribution

### 3.1 Algorithm Description

Calculate the median range for each session type by day of week, then compare today's realized range to determine "fuel consumed" or remaining expansion potential.

### 3.2 Inputs

| Input | Type | Description |
| :--- | :--- | :--- |
| `session_data` | Array[SessionBar] | Historical session OHLC data |
| `current_session` | SessionBar | Current session data |
| `lookback_days` | int | Days to look back (e.g., 10 or configurable 5) |
| `session_type` | string | 'ASIA', 'LONDON', 'NY1', 'NY2' |
| `day_of_week` | int | 0=Sunday, 1=Monday, ..., 5=Friday |

```typescript
interface SessionBar {
  date: Date;
  session: string;
  day_of_week: int;
  high: number;
  low: number;
  open: number;
  close: number;
  range: number;  // high - low
}
```

### 3.3 Outputs

| Output | Type | Description |
| :--- | :--- | :--- |
| `median_range` | float | Median range for this session+DOW combo |
| `current_range` | float | Today's current range |
| `fuel_pct` | float | current_range / median_range * 100 |
| `interpretation` | string | 'LOW_FUEL', 'NORMAL', 'HIGH_FUEL' |

### 3.4 Pseudocode

```
FUNCTION calculate_session_fuel(session_data, current_session, lookback_days, session_type, day_of_week):
    
    # Step 1: Filter historical data for matching session and DOW
    matching_sessions = FILTER session_data WHERE:
        session == session_type AND
        day_of_week == day_of_week AND
        date >= (today - lookback_days trading days)
    
    # Step 2: Calculate median range
    ranges = [s.range for s in matching_sessions]
    median_range = MEDIAN(ranges)
    
    # Step 3: Calculate current session range
    current_range = current_session.high - current_session.low
    
    # Step 4: Calculate fuel percentage
    IF median_range > 0:
        fuel_pct = (current_range / median_range) * 100
    ELSE:
        fuel_pct = 0
    
    # Step 5: Interpretation
    IF fuel_pct < 50:
        interpretation = 'LOW_FUEL'      # Expect expansion
    ELSE IF fuel_pct < 120:
        interpretation = 'NORMAL'
    ELSE:
        interpretation = 'HIGH_FUEL'     # May be exhausted
    
    RETURN {
        median_range: median_range,
        current_range: current_range,
        fuel_pct: fuel_pct,
        interpretation: interpretation
    }
```

### 3.5 Session Time Definitions

| Session | Start (NY Time) | End (NY Time) | Notes |
| :--- | :--- | :--- | :--- |
| ASIA | 18:00 | 02:00 | Previous day's evening session |
| LONDON | 02:00 | 08:00 | Pre-market Europe |
| NY1 | 09:30 | 12:00 | Morning session (RTH) |
| NY2 | 12:00 | 16:00 | Afternoon session (RTH) |
| 09:30-10:00 | 09:30 | 10:00 | First 30 minutes |

### 3.6 Edge Cases

| Edge Case | Handling |
| :--- | :--- |
| Holiday (no data) | Skip day in lookback |
| Incomplete session | Use partial range but flag as "IN_PROGRESS" |
| Zero median (rare) | Return 0% fuel, flag as "INSUFFICIENT_DATA" |

### 3.7 Display Format (Dashboard)

```
| Session | Today | MON | TUE | WED | THU | FRI |
|---------|-------|-----|-----|-----|-----|-----|
| ASN     | -     | 98.50 (2.05%) [4] | 80.75 (1.65%) [4] | ... |
| LDN     | -     | 22.75 (0.47%) [4] | 28.50 (0.58%) [4] | ... |
| NY1     | -     | 49.75 (1.03%) [4] | 57.25 (1.18%) [4] | ... |
| NY2     | -     | 66.00 (1.34%) [4] | 80.75 (1.63%) [4] | ... |
```

Format: `<median_range> (<range_pct>) [<sample_count>]`

---

## 4. Regime Streak Analysis

### 4.1 Algorithm Description

Track the TRUE/FALSE state of each session over time to identify streaks and predict regime flips.

### 4.2 Definitions

| Term | Definition |
| :--- | :--- |
| **Long TRUE** | Session broke above previous session high AND closed in upper half |
| **Long FALSE** | Session broke above previous session high BUT closed in lower half |
| **Short TRUE** | Session broke below previous session low AND closed in lower half |
| **Short FALSE** | Session broke below previous session low BUT closed in upper half |
| **Neutral** | Neither breakout condition met |

### 4.3 Inputs

| Input | Type | Description |
| :--- | :--- | :--- |
| `session_history` | Array[SessionResult] | Historical session results |
| `lookback_days` | int | Days to analyze (e.g., 73) |

```typescript
interface SessionResult {
  date: Date;
  session: string;
  prev_high: number;
  prev_low: number;
  session_high: number;
  session_low: number;
  session_close: number;
  status: 'LONG_TRUE' | 'LONG_FALSE' | 'SHORT_TRUE' | 'SHORT_FALSE' | 'NEUTRAL';
}
```

### 4.4 Outputs

```typescript
interface RegimeAnalysis {
  days_in_history: number;
  current_state: 'TRUE_ACTIVE' | 'FALSE_ACTIVE';
  bo_direction: 'LONG' | 'SHORT';
  
  true_pct: number;
  false_pct: number;
  
  max_streak_true: number;
  max_streak_false: number;
  current_streak: number;
  current_streak_type: 'TRUE' | 'FALSE';
  
  days_with_false: number;
  days_without_false: number;
  
  // MFE/MAE percentiles
  hist_bo_mfe_p50: number;
  hist_bo_mfe_p70: number;
  hist_bo_mfe_max: number;
  hist_bo_mae_p50: number;
  hist_bo_mae_p70: number;
  hist_bo_mae_max: number;
  hist_bo_mae_min: number;
  
  // Today's comparison
  today_bo_mfe: number;
  today_bo_mae: number;
  today_false_mfe: number | null;
  today_false_mae: number | null;
  
  range_size: number;  // % of price
}
```

### 4.5 Pseudocode

```
FUNCTION calculate_regime_analysis(session_history, lookback_days):
    
    # Step 1: Filter to lookback period
    history = session_history[-lookback_days:]
    
    # Step 2: Calculate TRUE/FALSE counts
    true_days = COUNT(history WHERE status IN ['LONG_TRUE', 'SHORT_TRUE'])
    false_days = COUNT(history WHERE status IN ['LONG_FALSE', 'SHORT_FALSE'])
    total = true_days + false_days
    
    true_pct = (true_days / total) * 100
    false_pct = (false_days / total) * 100
    
    # Step 3: Calculate streaks
    streaks = []
    current_streak = 0
    current_type = null
    
    FOR each day IN history:
        day_type = 'TRUE' IF day.status CONTAINS 'TRUE' ELSE 'FALSE'
        
        IF day_type == current_type:
            current_streak += 1
        ELSE:
            IF current_streak > 0:
                streaks.append({ type: current_type, length: current_streak })
            current_streak = 1
            current_type = day_type
    
    # Finalize last streak
    streaks.append({ type: current_type, length: current_streak })
    
    max_streak_true = MAX(s.length FOR s IN streaks WHERE s.type == 'TRUE')
    max_streak_false = MAX(s.length FOR s IN streaks WHERE s.type == 'FALSE')
    
    # Step 4: Calculate MFE/MAE percentiles
    true_days_data = FILTER history WHERE status CONTAINS 'TRUE'
    mfe_values = [calculate_mfe(day) FOR day IN true_days_data]
    mae_values = [calculate_mae(day) FOR day IN true_days_data]
    
    RETURN {
        days_in_history: LEN(history),
        current_state: current_type + '_ACTIVE',
        # ... (fill in all fields)
    }

FUNCTION calculate_mfe(session):
    # Maximum Favorable Excursion
    IF session.status CONTAINS 'LONG':
        RETURN (session.session_high - session.entry_price) / session.entry_price * 100
    ELSE:
        RETURN (session.entry_price - session.session_low) / session.entry_price * 100

FUNCTION calculate_mae(session):
    # Maximum Adverse Excursion
    IF session.status CONTAINS 'LONG':
        RETURN (session.entry_price - session.session_low) / session.entry_price * 100
    ELSE:
        RETURN (session.session_high - session.entry_price) / session.entry_price * 100
```

### 4.6 Edge Cases

| Edge Case | Handling |
| :--- | :--- |
| No breakout (neutral) | Skip in streak calculation |
| Holiday gap | Continue streak across gap |
| Partial session | Use available data, flag as incomplete |

---

## 5. Candle Science C3 Projection

### 5.1 Algorithm Description

Given the C1 (two days ago) and C2 (yesterday) candle patterns, calculate the probability distribution for C3 (today).

### 5.2 Candle Classification

Each candle is classified by comparing its components:

| Position | Bullish | Bearish |
| :--- | :--- | :--- |
| Open vs Close | Close > Open | Close < Open |
| Close vs High | Close near High | Close far from High |
| Open vs Low | Open near Low | Open far from Low |

Full classification uses 8 binary comparisons, yielding 256 possible patterns.

### 5.3 Inputs

| Input | Type | Description |
| :--- | :--- | :--- |
| `c1` | Candle | Two days ago candle |
| `c2` | Candle | Yesterday's candle |
| `historical_data` | Array[CandleTriple] | Historical C1-C2-C3 sequences |

### 5.4 Outputs

```typescript
interface C3Projection {
  bullish_pct: number;
  bearish_pct: number;
  sample_size: number;
  
  // Position probabilities
  c3_close_above_c2_close: number;
  c3_close_above_c2_high: number;
  c3_low_below_c2_low: number;
  c3_high_above_c2_high: number;
}
```

### 5.5 Pseudocode

```
FUNCTION calculate_c3_projection(c1, c2, historical_data):
    
    # Step 1: Classify C1 and C2
    c1_pattern = classify_candle(c1)
    c2_pattern = classify_candle(c2)
    
    # Step 2: Find matching historical sequences
    matches = FILTER historical_data WHERE:
        classify_candle(triple.c1) == c1_pattern AND
        classify_candle(triple.c2) == c2_pattern
    
    IF LEN(matches) < 10:
        RETURN { insufficient_data: true }
    
    # Step 3: Calculate C3 outcomes from matches
    bullish_count = COUNT(matches WHERE triple.c3.close > triple.c3.open)
    bearish_count = COUNT(matches WHERE triple.c3.close < triple.c3.open)
    
    bullish_pct = bullish_count / LEN(matches) * 100
    bearish_pct = bearish_count / LEN(matches) * 100
    
    # Step 4: Calculate position probabilities
    close_above_c2_close = COUNT(matches WHERE triple.c3.close > triple.c2.close) / LEN(matches) * 100
    close_above_c2_high = COUNT(matches WHERE triple.c3.close > triple.c2.high) / LEN(matches) * 100
    # ... etc
    
    RETURN {
        bullish_pct: bullish_pct,
        bearish_pct: bearish_pct,
        sample_size: LEN(matches),
        # ... position probabilities
    }

FUNCTION classify_candle(candle):
    # Returns 8-bit pattern based on candle structure
    pattern = 0
    
    IF candle.close > candle.open:
        pattern |= 0b00000001  # Bullish body
    IF candle.close > (candle.open + candle.close) / 2:
        pattern |= 0b00000010  # Close in upper half
    # ... continue for all 8 comparisons
    
    RETURN pattern
```

### 5.6 Implementation Notes

**PineScript Consideration:**
TradingView limits historical bar access. Pre-compute pattern statistics offline and embed as lookup table.

---

## 6. Daily HOD/LOD Timing

### 6.1 Algorithm Description

Calculate the statistical mode and median times for when the High of Day (HOD) and Low of Day (LOD) occur.

### 6.2 Inputs

| Input | Type | Description |
| :--- | :--- | :--- |
| `daily_data` | Array[DailyBar] | Daily OHLC with intraday high/low times |
| `lookback_days` | int | Days to analyze |

### 6.3 Outputs

```typescript
interface HODLODAnalysis {
  hod_mode_time: string;      // Most common HOD time (30m bucket)
  hod_median_time: string;    // Median HOD time
  lod_mode_time: string;      // Most common LOD time
  lod_median_time: string;    // Median LOD time
  
  hod_distribution: Record<string, number>;  // Time bucket -> count
  lod_distribution: Record<string, number>;
}
```

### 6.4 Pseudocode

```
FUNCTION calculate_hod_lod_timing(daily_data, lookback_days):
    
    data = daily_data[-lookback_days:]
    
    # Step 1: Bucket times into 30-minute intervals
    hod_buckets = {}
    lod_buckets = {}
    
    FOR each day IN data:
        hod_bucket = floor_to_30m(day.hod_time)
        lod_bucket = floor_to_30m(day.lod_time)
        
        hod_buckets[hod_bucket] = (hod_buckets[hod_bucket] OR 0) + 1
        lod_buckets[lod_bucket] = (lod_buckets[lod_bucket] OR 0) + 1
    
    # Step 2: Find mode (most common)
    hod_mode = KEY_WITH_MAX_VALUE(hod_buckets)
    lod_mode = KEY_WITH_MAX_VALUE(lod_buckets)
    
    # Step 3: Find median
    hod_times_sorted = SORT([day.hod_time FOR day IN data])
    lod_times_sorted = SORT([day.lod_time FOR day IN data])
    
    hod_median = hod_times_sorted[LEN(hod_times_sorted) / 2]
    lod_median = lod_times_sorted[LEN(lod_times_sorted) / 2]
    
    RETURN {
        hod_mode_time: hod_mode,
        hod_median_time: hod_median,
        lod_mode_time: lod_mode,
        lod_median_time: lod_median,
        hod_distribution: hod_buckets,
        lod_distribution: lod_buckets
    }

FUNCTION floor_to_30m(time):
    # Round down to nearest 30-minute bucket
    minutes = time.hour * 60 + time.minute
    bucket_minutes = FLOOR(minutes / 30) * 30
    RETURN format_time(bucket_minutes)
```

---

## 7. Session Status (Long/Short TRUE/FALSE)

### 7.1 Algorithm Description

Determine the status of a session based on whether price broke above/below the previous session's range and where it closed.

### 7.2 Status Definitions

```
LONG_TRUE:
  - Price broke ABOVE previous session high
  - AND closed in UPPER 50% of session range
  - Interpretation: Bullish breakout confirmed

LONG_FALSE:
  - Price broke ABOVE previous session high
  - BUT closed in LOWER 50% of session range
  - Interpretation: Failed breakout (bull trap)

SHORT_TRUE:
  - Price broke BELOW previous session low
  - AND closed in LOWER 50% of session range
  - Interpretation: Bearish breakout confirmed

SHORT_FALSE:
  - Price broke BELOW previous session low
  - BUT closed in UPPER 50% of session range
  - Interpretation: Failed breakdown (bear trap)

NEUTRAL:
  - No breakout of previous session range
  - Interpretation: Inside day / consolidation
```

### 7.3 Pseudocode

```
FUNCTION calculate_session_status(prev_session, current_session):
    
    prev_high = prev_session.high
    prev_low = prev_session.low
    
    curr_high = current_session.high
    curr_low = current_session.low
    curr_close = current_session.close
    
    # Calculate session midpoint
    curr_midpoint = (curr_high + curr_low) / 2
    
    # Determine breakout direction
    broke_above = curr_high > prev_high
    broke_below = curr_low < prev_low
    
    # Determine close position
    closed_upper = curr_close >= curr_midpoint
    closed_lower = curr_close < curr_midpoint
    
    # Determine status
    IF broke_above AND closed_upper:
        RETURN 'LONG_TRUE'
    ELSE IF broke_above AND closed_lower:
        RETURN 'LONG_FALSE'
    ELSE IF broke_below AND closed_lower:
        RETURN 'SHORT_TRUE'
    ELSE IF broke_below AND closed_upper:
        RETURN 'SHORT_FALSE'
    ELSE:
        RETURN 'NEUTRAL'
```

### 7.4 Implementation Notes

**PineScript:**
```pinescript
// Previous session values
prev_high = request.security(syminfo.tickerid, "60", high[1])
prev_low = request.security(syminfo.tickerid, "60", low[1])

// Current session
curr_mid = (high + low) / 2

// Status calculation
broke_above = high > prev_high
broke_below = low < prev_low
closed_upper = close >= curr_mid

status = broke_above and closed_upper ? "LONG_TRUE" :
         broke_above and not closed_upper ? "LONG_FALSE" :
         broke_below and not closed_upper ? "SHORT_TRUE" :
         broke_below and closed_upper ? "SHORT_FALSE" : "NEUTRAL"
```

---

## Derived Data Files

| Calculation | Data Source | Logic |
| :--- | :--- | :--- |
| EMA Zones | JSON Chunks (1D) | Real-time via `MissionControlService` |
| Premium/Discount | JSON Chunks (All TFs) | Real-time via `MissionControlService` |
| Session Fuel | JSON Chunks (1m) | Real-time via `MissionControlService` |
| Regime Streaks | JSON Chunks (1m) | Real-time via `MissionControlService` (In Progress) |
| Candle Science | JSON Chunks (1D) | Real-time via `MissionControlService` |
| HOD/LOD Timing | `{ticker}_daily_hod_lod.json` | Pre-computed via existing script |
| Session Status | `public/data/` | Derived from 1m JSON chunks |

---

## Script Index

| Script | Purpose | Inputs | Outputs |
| :--- | :--- | :--- | :--- |
| `scripts/analysis/ema_zone_analysis.py` | Calculate EMA zone hit rates | 1D parquet | `_ema_zones.json` |
| `scripts/analysis/premium_discount.py` | Multi-TF P/D analysis | Multi-TF parquets | `_premium_discount.json` |
| `scripts/analysis/regime_analysis.py` | Streak and regime analysis | Profiler data | `_regime_streaks.json` |
| `scripts/analysis/session_fuel.py` | Session range statistics | Profiler data | `_session_fuel.json` |

---

## Version History

| Version | Date | Changes |
| :--- | :--- | :--- |
| 1.0.0 | 2026-02-03 | Initial specification |
