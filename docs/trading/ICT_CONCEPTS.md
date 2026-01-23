# ICT Concepts Reference

This document serves as a technical reference for Inner Circle Trader (ICT) concepts implemented in this project.

---

## Table of Contents
1. [Key Price Levels](#key-price-levels)
2. [Order Blocks (OB)](#order-blocks)
3. [Fair Value Gaps (FVG)](#fair-value-gaps)
4. [Standard Deviation Projections](#standard-deviation-projections)
5. [Failure Swings](#failure-swings)
6. [Weekly Profiles](#weekly-profiles)

---

## Key Price Levels

### Prior Day High/Low (PDH/PDL)
- **Definition**: The high and low of the previous trading day
- **Significance**: Major liquidity pools; price often sweeps these levels
- **Implementation**: `retrieve_ict_context.py`

### Prior Week High/Low (PWH/PWL)
- **Definition**: The high and low of the previous trading week
- **Significance**: Higher timeframe liquidity; weekly draw on liquidity
- **Implementation**: Resampled from 1H data with `W-FRI` anchor

### Prior Month High/Low (PMH/PML)
- **Definition**: The high and low of the previous calendar month
- **Significance**: Institutional time frame; major liquidity zones
- **Implementation**: Resampled from 1H data with `ME` (month-end) anchor

### Midpoints
- **PDM**: (PDH + PDL) / 2 - Prior Day Midpoint
- **PWM**: (PWH + PWL) / 2 - Prior Week Midpoint
- **PMM**: (PMH + PML) / 2 - Prior Month Midpoint

---

## Order Blocks

### Definition
An Order Block is the last *opposite-direction* candle before a strong displacement move.

- **Bullish OB**: Last bearish candle before a bullish displacement (demand zone)
- **Bearish OB**: Last bullish candle before a bearish displacement (supply zone)

### Detection Logic
```python
# Displacement = candle body > 2x average body size
avg_body = df['body'].rolling(20).mean()
is_displacement = df['body'] > (avg_body * 2.0)

# Find the last opposite-color candle before displacement
if is_bullish_displacement:
    OB = last_bearish_candle_before_displacement
```

### Mitigation
An OB is considered **mitigated** (invalid) when:
- Bullish OB: Price trades below the OB low
- Bearish OB: Price trades above the OB high

**Implementation**: `filter_mitigated_obs()` in `generate_ict_chart.py`

---

## Fair Value Gaps

### Definition
An FVG is an imbalance/gap between candle wicks, representing inefficiency in price delivery.

- **Bullish FVG**: Gap between candle[i-2].high and candle[i].low (price gapped up)
- **Bearish FVG**: Gap between candle[i-2].low and candle[i].high (price gapped down)

### Detection Logic
```python
# Bullish FVG
gap = df['low'].iloc[i] - df['high'].iloc[i-2]
if gap > min_threshold:
    fvg = {'top': df['low'].iloc[i], 'bottom': df['high'].iloc[i-2]}

# Bearish FVG
gap = df['low'].iloc[i-2] - df['high'].iloc[i]
if gap > min_threshold:
    fvg = {'top': df['low'].iloc[i-2], 'bottom': df['high'].iloc[i]}
```

### Mitigation (Fill)
An FVG is considered **filled** when:
- Bullish FVG: Price trades into/below the gap bottom
- Bearish FVG: Price trades into/above the gap top

**Implementation**: `filter_mitigated_fvgs()` in `generate_ict_chart.py`

---

## Standard Deviation Projections

### Type 1: ADR-Based Standard Deviations
Projects levels from a reference point (Midnight Open, 08:30 Open) using Average Daily Range as the unit.

**Calculation:**
```
ADR = Average of (High - Low) over N days (typically 5 or 20)
SD_Unit = ADR / 2

Levels from Reference:
  +2.5 SD = Reference + (2.5 × SD_Unit)
  +2.0 SD = Reference + (2.0 × SD_Unit)
  +1.5 SD = Reference + (1.5 × SD_Unit)
  +1.0 SD = Reference + (1.0 × SD_Unit)
  +0.5 SD = Reference + (0.5 × SD_Unit)
  Reference (0) = Midnight Open or 08:30 Open
  -0.5 SD = Reference - (0.5 × SD_Unit)
  -1.0 SD = Reference - (1.0 × SD_Unit)
  ... etc
```

**Use Case**: Daily range projections, intraday targets

**Status**: 📋 Planned (task #131)

---

### Type 2: Swing-Based Standard Deviations (Failure Swing Projections)
Projects levels from a key swing using the swing range as the unit. This is **fractal** - works on any timeframe.

**Calculation:**
```
Swing_Range = Swing_High - Swing_Low

Levels from Swing:
  +4.5 = Anchor + (4.5 × Swing_Range)
  +4.0 = Anchor + (4.0 × Swing_Range)
  +3.5 = Anchor + (3.5 × Swing_Range)
  +3.0 = Anchor + (3.0 × Swing_Range)
  +2.5 = Anchor + (2.5 × Swing_Range)
  +2.0 = Anchor + (2.0 × Swing_Range)
  +1.5 = Anchor + (1.5 × Swing_Range)
  +1.0 = Anchor + (1.0 × Swing_Range)  ← 100% extension
  Anchor (0) = Failure swing point / Key level
  -0.5 = Anchor - (0.5 × Swing_Range)
  -1.0 = Anchor - (1.0 × Swing_Range)
  -2.0 = Anchor - (2.0 × Swing_Range)
  -2.5 = Anchor - (2.5 × Swing_Range)
  -3.0 = Anchor - (3.0 × Swing_Range)
  ... etc
```

#### Multi-Timeframe Application

| Timeframe | Swing Source | Use Case |
|-----------|--------------|----------|
| **1H (Weekly Context)** | HOTW/LOTW (High/Low of Week) | Daily bias, swing targets |
| **5M (Intraday)** | Session swing (London/NY) | Execution targets, entries |

#### Example 1: Weekly Profile SD (1H Chart)
![Weekly SD Example](examples/sd_weekly_profile_1h.png)

**Key observations:**
- **Week 1 (Left)**: Monday made LOTW ("Monday Low Zone"), Tuesday made HOTW ("Tuesday HOTW")
- Range measured from Monday Low → Tuesday High
- SD levels: -4, -3.5, -2.5, 0, 1, 1.5, 2, 2.5
- Price reversed from the 2.5 SD extension

**Week 2 (Right)**: Wednesday made LOTW with SD projections upward

---

#### Example 2: Failure Swing SD (5M Chart)
![Failure Swing SD Example](examples/sd_failure_swing_5m.png)

**Key observations:**
- Anchor on a failure swing (lower high)
- Range measured from the failure point
- SD levels extended: -3, -2.5, -1, 0, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 7.05
- Labels show "Prev Week High", "Prev Month Close", etc. for confluence

---

#### Example 3: Intraday SD (5M Chart)
![Intraday SD Example](examples/sd_intraday_5m.png)

**Key observations:**
- Overnight swing low (00:30-06:00) as anchor
- SD levels: -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.176, 2.5, 3.5, 4.5
- Blue zones = FVGs, Pink zones = OBs (confluence with SD levels)
- Price found support at 1.5 SD and resistance at 2.5/3.5 SD

---

**Status**: 📋 Planned - Add to 1H Daily Bias chart + 5M intraday chart

---

## Failure Swings

### Definition
A **Failure Swing** occurs when price fails to take out a previous swing high/low, signaling potential reversal.

### Bearish Failure Swing (Lower High)
```
    H1 (Previous High)
   /\
  /  \      H2 (Failure - Lower High)
 /    \    /\
/      \  /  \
        \/    \
        L1     \  ← Continuation down
                \
```
1. Price makes a swing high (H1)
2. Price pulls back to a swing low (L1)
3. Price rallies but **fails to exceed H1**, making a lower high (H2)
4. H2 is the **failure swing** → bearish signal

### Bullish Failure Swing (Higher Low)
```
        /
       /  ← Continuation up
      /
     /\
    /  \     L2 (Failure - Higher Low)
   /    \   /
  /      \ /
 /        \/
H1        L1 (Previous Low)
```
1. Price makes a swing low (L1)
2. Price rallies to a swing high (H1)
3. Price retraces but **fails to exceed L1**, making a higher low (L2)
4. L2 is the **failure swing** → bullish signal

### Detection Algorithm (Proposed)
```python
def find_failure_swings(df, lookback=20):
    """
    Detect failure swings (lower highs / higher lows).
    
    Returns list of failure swing points with:
    - type: 'BEARISH_FAILURE' or 'BULLISH_FAILURE'
    - anchor: The failure swing price level
    - swing_range: The range to use for SD projections
    """
    swings = []
    
    # 1. Find local swing highs and lows (using rolling window)
    df['is_swing_high'] = (df['high'] == df['high'].rolling(5, center=True).max())
    df['is_swing_low'] = (df['low'] == df['low'].rolling(5, center=True).min())
    
    # 2. Iterate through swings to find failures
    swing_highs = df[df['is_swing_high']].index.tolist()
    swing_lows = df[df['is_swing_low']].index.tolist()
    
    # 3. Check for lower high (bearish failure)
    for i in range(1, len(swing_highs)):
        curr_high = df.loc[swing_highs[i], 'high']
        prev_high = df.loc[swing_highs[i-1], 'high']
        
        if curr_high < prev_high:
            # Find the low between these highs
            between_low = df.loc[swing_highs[i-1]:swing_highs[i], 'low'].min()
            swing_range = prev_high - between_low
            
            swings.append({
                'type': 'BEARISH_FAILURE',
                'datetime': swing_highs[i],
                'anchor': curr_high,
                'swing_range': swing_range,
                'prev_high': prev_high,
                'between_low': between_low
            })
    
    # 4. Check for higher low (bullish failure)
    # Similar logic for swing_lows...
    
    return swings[-5:]  # Return most recent failures
```

### SD Projection from Failure Swing
Once a failure swing is detected:
```python
def project_sd_levels(anchor, swing_range, direction='down'):
    levels = []
    for sd in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]:
        if direction == 'down':
            levels.append(anchor - (sd * swing_range))
        else:
            levels.append(anchor + (sd * swing_range))
    return levels
```

---

## Weekly Profiles

### High/Low of Week Timing
ICT observes that the weekly high/low often forms on specific days:

| Bullish Week | Bearish Week |
|--------------|--------------|
| Low: Monday/Tuesday | High: Monday/Tuesday |
| High: Thursday/Friday | Low: Thursday/Friday |

### Implementation
`analyze_weekly_profile.py` calculates:
- Week-to-Date High/Low
- Which day the WTD High/Low formed
- Heuristic analysis (e.g., "Tuesday Low in effect")

---

## File Reference

| File | Concepts |
|------|----------|
| `scripts/trader/retrieve_ict_context.py` | PDH/PDL, PWH/PWL, PMH/PML, Midnight Open |
| `scripts/analysis/generate_ict_chart.py` | Order Blocks, FVGs, HTF Levels |
| `scripts/analysis/analyze_weekly_profile.py` | Weekly High/Low timing |
| `scripts/utils/fused_data_loader.py` | Data loading from Live + Historical |

---

## Roadmap

- [x] Key Price Levels (PDH/PDL/PWH/PWL/PMH/PML)
- [x] Order Blocks (detection + mitigation filtering)
- [x] Fair Value Gaps (multi-timeframe + mitigation filtering)
- [ ] ADR Standard Deviations
- [ ] Swing-Based Standard Deviations (Failure Swing Projections)
- [ ] Failure Swing Auto-Detection
