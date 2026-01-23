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
| `scripts/analysis/analyze_weekly_profile.py` | Weekly High/Low timing |
| `scripts/utils/fused_data_loader.py` | Data loading from Live + Historical |

---

## Intraday Bias Determination (NY Session)

Establishing a clear intraday bias before the 09:30 AM ET open is critical. ICT uses a multi-method approach to determine if the daily draw is likely higher or lower.

### 1. Previous Day Candle Analysis
Look at the current daily candle relative to PVH/PDL.
- **Bullish**: Close above PDH signals strength. Sweeping PDL (Sellside) and closing back above signals a reversal.
- **Bearish**: Close below PDL signals weakness. Sweeping PDH (Buyside) and closing back below signals a reversal.
- **Inside Bar**: Refer to the previous candle's direction for the likely target.

### 2. Midnight to London Range (2022 Mentorship)
Mark the range between **00:00 (Midnight Open)** and **03:00 (London Open)**.
- **Judas Swing**: A move above/below the Midnight Open during London or Pre-Market that sweeps the range then reverses towards the daily bias.
- **Setup**: If Midnight-to-London range hasn't been swept by 08:30, wait for NY Open to sweep one side then enter on displacement (MSS/FVG).

### 3. London Session Confirmation
If London moves with the higher-timeframe (daily) trend, expect NY to continue.
- **Bullish**: London takes Asia Low (Sellside) → NY Continuation.
- **Bearish**: London takes Asia High (Buyside) → NY Continuation.
- **Range**: If London consolidates, NY will likely sweep that range.

### 4. Daily Market Structure Shift (MSS)
Analyze the Daily chart for the most recent structural displacement.
- **Bullish MSS**: High probability for bullish intraday bias.
- **Bearish MSS**: High probability for bearish intraday bias.

### 5. Equilibrium (Premium vs. Discount)
Mark the 50% midpoint of the daily/weekly range.
- **Premium (Above 50%)**: Look for shorts towards the next discount liquidity pool.
- **Discount (Below 50%)**: Look for longs towards the next premium liquidity pool.

### 6. Timeframe Alignment (D/H4/H1)
Bias is highest probability when the Daily, 4-Hour, and 1-Hour structures are in sync. If Daily is bearish but H1 is bullish, expect a **bullish retracement** into a premium PD Array before the bearish continuation.

### 7. Draw on Liquidity (DOL) Assessment
The market is always moving from an **Imbalance (FVG/Gaps)** to **Liquidity (Highs/Lows)**.
1. Where is the nearest pool of liquidity (PDH/PDL/Equal H/L)?
2. Where is the nearest imbalance (FVG)?
If price just swept liquidity, its next draws is an imbalance. If it just filled an imbalance, its next draw is liquidity.

### 8. Displacement & FVG Direction
A valid bias MUST be supported by **displacement** (energetic move). Without displacement/MSS, any move is likely just a hunt for liquidity (Judas Swing) rather than a trend change.

---

---

## ICT News Guidance

### High-Impact News Weeks (CPI, FOMC, NFP)

ICT emphasizes that trading major economic releases like CPI, FOMC, and NFP is high-risk and akin to gambling for developing traders. The primary strategy is to **don't trade the news itself—trade the aftermath once proper structure forms.**

#### 📅 News Management Table

| Period | Recommendation |
|--------|----------------|
| **Monday-Tuesday of NFP/FOMC week** | Generally tradeable with caution. |
| **Wednesday-Thursday pre-news** | Reduce size or sit out. Consolidation likely. |
| **Day of CPI/NFP (before 08:30 AM)** | Avoid intraday trading. Consolidation profile with lack of follow through. |
| **FOMC Wednesday (entire day)** | **NO TRADING**. Forges discipline and protects capital. |
| **During News Release** | **NEVER TRADE**. High volatility hunts liquidity on both ends. |
| **15-60 minutes after release** | Wait for 2022 recovery setup (MSS/CISD on LTF). |
| **Day after FOMC/NFP** | Often provides cleaner directional setups. |

#### 🌪️ The "Seek and Destroy" Weekly Profile
A neutral to low-probability profile common during weeks with major news events (NFP, Rate announcements).
- **Behavior**: Aggressive hunting of liquidity on both ends with no clear directional bias.
- **Pattern**: Market consolidates from Monday to Thursday or makes irregular higher highs/lower lows waiting for the release.
- **Timing**: Often occurs in summer months (July/August).

#### 🛠️ Practical Rules
- **Manipulation Window**: Price movements between **08:35 and 09:20 AM ET** are often manipulative. Wait for a valid setup after 09:20 AM.
- **Recovery Setup**: 80% of the time, a recovery setup occurs 20-60 minutes post-release. Look for ICT MSS (Market Structure Shift) or CISD (Change in State of Delivery) after price trades back into the initial range.
- **Patience**: 8:30 AM releases can override technical levels. Wait 15 minutes for algorithmic patterns to resume.

---

## Roadmap

- [x] ICT News Guidance (Rules for CPI, FOMC, NFP)
- [x] ICT Intraday Bias (Methods 1-9)
- [x] Daytrader Execution Playbook
- [ ] ADR Standard Deviations
- [ ] Swing-Based Standard Deviations (Failure Swing Projections)
- [ ] Failure Swing Auto-Detection

---

## Daytrader's Intraday Execution Playbook

This checklist synthesizes all system data into a practical timeline for the NY session.

### 🕒 Phase 1: Pre-Market (08:30 - 09:30 AM ET)
- [ ] **Check Economic Calendar**: Filter for US news. Is it a "No Trade" week (FOMC/NFP)?
- [ ] **Establish Confluence**: Does NQStats (ALN) align with Daily Classification? (e.g., LPEU + R2 = High Conviction Bullish).
- [ ] **Mark Liquidity Magnets**:
    - Midnight Open (00:00)
    - London Session Range (High/Low)
    - PDH/PDL (Daily Draw)
- [ ] **Analyze Sweeps**: Has London already swept Asia? If yes, expect NY continuation. If no, expect NY to sweep any remaining liquidity.

### 🕒 Phase 2: The Open (09:30 - 10:10 AM ET)
- [ ] **09:30 Opening Range**: Observe where the initial impulse goes. Is it a move *away* from or *towards* the Midnight Open?
- [ ] **Wait for Judas Swing**: 80% of successful setups occur after an initial sweep of the London range (Methods 2 & 3).
- [ ] **Macro Window (09:50 - 10:10)**: This is the prime time for a Market Structure Shift (MSS). Look for displacement with an FVG.
- [ ] **Silver Bullet (10:00 - 11:00)**: Look for entries at FVGs in the direction of the confirmed daily bias.

### 🕒 Phase 3: AM Execution (10:10 - 12:00 PM ET)
- [ ] **Baseline Targets**: Aim for the 80% Confidence Targets provided in the newsletter.
- [ ] **Pivot Support**: Use London Mid or Midnight Open as a trailing stop reference.
- [ ] **PDH/PDL Sweep**: If price hits PDH/PDL early, watch for a reversal closure (Method 1) or full expansion.
- [ ] **NY Lunch**: Begin flattening positions by 12:00 PM. High risk of choppy, mean-reverting price action.

### 🛠️ Execution "Hard Rules"
1. **Bias Conflict**: If NQStats says Bullish but Classification says Bearish, trade with **Low Conviction** or wait for the 10:00 AM sweep.
2. **Missing Displacement**: No displacement = No trade. A slow move into a level is often a hunt, not a trend.
3. **News Release**: Never trade during the actual release. Wait 15-60 minutes for the recovery setup.
4. **Range Bound London**: If London stayed inside Asia (AEL), expect a volatile expansion day in NY.

---
