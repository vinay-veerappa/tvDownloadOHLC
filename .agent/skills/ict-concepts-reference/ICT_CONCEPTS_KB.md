# ICT Concepts — Knowledge Base

> Comprehensive technical reference for Inner Circle Trader (ICT) / Smart Money Concepts (SMC).
> Covers all concepts, detection logic (Python + Pine Script), session timing, bias determination,
> risk management, and quantitative data from backtests.
>
> **Instrument context**: Primarily NQ (Nasdaq futures), also ES, RTY, YM, GC, CL, forex futures.
> All times are Eastern Time (ET / America/New_York) unless noted.

---

## Table of Contents

1. [Foundational Framework (IPDA)](#1-foundational-framework-ipda)
2. [Market Structure](#2-market-structure)
3. [Liquidity](#3-liquidity)
4. [SMT Divergence](#4-smt-divergence)
5. [Bias Determination](#5-bias-determination)
6. [PD Arrays — Imbalances & Gaps](#6-pd-arrays--imbalances--gaps)
7. [PD Arrays — Order Blocks](#7-pd-arrays--order-blocks)
8. [Premium & Discount](#8-premium--discount)
9. [Time-Based Concepts](#9-time-based-concepts)
10. [Standard Deviation Projections](#10-standard-deviation-projections)
11. [Reference Levels & Key Prices](#11-reference-levels--key-prices)
12. [Trading Models](#12-trading-models)
13. [Intraday Bias Determination (Expanded)](#13-intraday-bias-determination)
14. [News Guidance](#14-news-guidance)
15. [Execution Playbook](#15-execution-playbook)
16. [Risk Management](#16-risk-management)
17. [Failure Swings](#17-failure-swings)
18. [Weekly Profiles](#18-weekly-profiles)
19. [Quantitative Data](#19-quantitative-data)
20. [Glossary](#20-glossary)

---

## 1. Foundational Framework (IPDA)

### 1.1 Interbank Price Delivery Algorithm

The core model: price moves for two reasons — to seek **liquidity** (stops, pending orders) and to rebalance **imbalances** (FVGs, voids). The algorithm delivers price between institutional levels within specific data ranges.

### 1.2 IPDA Data Ranges (20/40/60)

Rolling lookback windows defining the algorithm's operating range:

| Range | Lookback | Scope |
|-------|----------|-------|
| IPDA 20 | Last 20 daily candles | Short-term dealing range |
| IPDA 40 | Last 40 daily candles | Intermediate institutional range |
| IPDA 60 | Last 60 daily candles | Full institutional cycle |

**Calculation** (excludes current bar):

```python
# Python
high_20 = df['high'].rolling(20).max().shift(1)
low_20  = df['low'].rolling(20).min().shift(1)
equilibrium = (high_20 + low_20) / 2
position_pct = ((df['close'] - low_20) / (high_20 - low_20)) * 100
```

```pine
// Pine Script
high20 = ta.highest(high, 20)[1]
low20  = ta.lowest(low, 20)[1]
eq     = (high20 + low20) / 2
pct    = ((close - low20) / (high20 - low20)) * 100
```

**Key properties:**
- Each range shifts daily. The algorithm seeks BOTH the highs AND lows of the previous 60 days.
- **Premium** = price above equilibrium (>50%). **Discount** = price below equilibrium (<50%).
- When price creates new 20-day extremes → watch for liquidity sweep / false breakout.
- PD Arrays within IPDA ranges determine which levels the algorithm targets next.
- Display modes: Classic (1D only), Classic+LTF (any TF via `request.security`), LTF (adapts to chart).

---

## 2. Market Structure

### 2.1 Break of Structure (BOS)
**Continuation** signal. Price breaks a swing high in an uptrend (or swing low in a downtrend), confirming the existing trend.

### 2.2 Market Structure Shift (MSS) / Change of Character (CHoCH)
**Reversal** signal. Price breaks a swing low in an uptrend (or swing high in a downtrend). Based on **high/low** swing points. Must be accompanied by **displacement** (large-bodied candles) for high probability.

### 2.3 CISD (Change in State of Delivery)
The **earliest** reversal signal — forms BEFORE MSS/CHoCH. Uses candle **open/close**, not high/low.

| Direction | Condition |
|-----------|-----------|
| Bullish CISD | Price closes ABOVE the opening of the bearish delivery sequence |
| Bearish CISD | Price closes BELOW the opening of the bullish delivery sequence |

**CISD vs MSS**: CISD is more sensitive (fires earlier) but produces more false signals. MSS waits for swing point breaks — more reliable but later entry. Both are used as confirmation at HTF PD arrays.

**Detection algorithm** (from cd_bias_profile indicator):
1. Track LTF candle direction (+1=bull, -1=bear) in arrays per HTF period
2. After HTF sweep: find the swing H bar within LTF candles → walk forward to first bull→bear transition
3. Mark that candle's **open** as the CISD level
4. If any close < CISD level → bearish CISD confirmed
5. **Invalidation**: price reclaims the swept high/low → reset CISD
6. **Late CISD**: confirmation arrives after the initial HTF candle closes
7. **Continuation**: bias persists if prior structure aligns without a new sweep

### 2.4 Swing Hierarchy

| Level | Abbreviation | Use |
|-------|-------------|-----|
| Short-Term | STH / STL | Internal structure, entry refinement |
| Intermediate-Term | ITH / ITL | Key swings within a trend leg |
| Long-Term | LTH / LTL | Major points defining the trend |

Internal structure = moves within a swing leg (entry refinement). Swing structure = the swing legs themselves (bias determination). Fractal structure = hierarchy nests across timeframes.

### 2.5 Multi-Timeframe Alignment
HTF sets bias. LTF refines entry. Bullish HTF trend + LTF discount entry = highest probability. Bias is highest when Daily, 4H, and 1H structures are in sync.

---

## 3. Liquidity

### 3.1 Core Concepts

| Concept | Description |
|---------|-------------|
| **BSL** (Buyside Liquidity) | Stops/orders above swing highs, equal highs, resistance |
| **SSL** (Sellside Liquidity) | Stops/orders below swing lows, equal lows, support |
| **EQH / EQL** | Equal highs/lows — obvious liquidity pools the algorithm targets |
| **Liquidity Sweep** | Price trades through a level then reverses (stop hunt / raid) |
| **External Liquidity** | Swing highs/lows — these are **targets** |
| **Internal Liquidity** | FVGs, imbalances — these are **entry zones** |
| **Inducement (IDM)** | Minor liquidity to lure retail before the true sweep |
| **HRLR** | High Resistance Liquidity Run — price struggles, many obstacles |
| **LRLR** | Low Resistance Liquidity Run — price flows freely, few obstacles |
| **Turtle Soup** | Fading breakouts above/below 20-day H/L (Larry Williams adapted by ICT) |

**Key principle**: The market alternates between seeking liquidity and rebalancing imbalances. If price just swept liquidity → next draw is an imbalance. If it just filled an imbalance → next draw is liquidity.

### 3.2 BSL/SSL Pivot Detection

```python
# Python — 3-bar pivot detection
df['swing_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
df['swing_low']  = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))

# Equal highs/lows within tolerance
tolerance = df['high'].rolling(20).apply(lambda x: x.max() - x.min()).mean() * 0.1
```

```pine
// Pine Script
bool swingHigh = high[2] < high[1] and high[1] > high[0]
bool swingLow  = low[2] > low[1] and low[1] < low[0]
// On sweep: high > level AND close < level → mark as swept
```

---

## 4. SMT Divergence

A "crack" in correlation between two markets that normally move together. One makes a new extreme; the other fails to confirm — signals institutional manipulation.

### 4.1 Correlated Instrument Groups (Futures)

| Group | Instruments | Correlation |
|-------|-------------|-------------|
| Equity Indices | NQ, ES, YM, RTY | Positive |
| Metals | GC, SI, HG | Positive |
| Energy | CL, NG | Positive |
| Forex Futures | 6E, 6B, 6J vs DX | Inverse (DX) |
| Crypto | BTC, ETH (CME) | Positive |

**Primary triad for NQ trading**: NQ & ES & YM

### 4.2 Detection Rules

| Type | Condition |
|------|-----------|
| Bearish SMT | Asset makes HH, correlated asset makes **lower** high (fails to confirm) |
| Bullish SMT | Asset makes LL, correlated asset makes **higher** low (fails to confirm) |
| Inverse (DX) | Flip the comparison — DX high = correlated asset low |

SMT is NOT a standalone signal. Requires confluence with key levels, killzones, PD arrays. Best at weekly/daily/4H highs and lows.

**SMT + CISD** = high-probability bias model (as implemented in cd_bias_profile indicator).

---

## 5. Bias Determination

### 5.1 HTF Sweep + LTF CISD Model

The core systematic model for establishing directional bias:

| Step | Action |
|------|--------|
| 1 | HTF candle sweeps previous candle's H or L (or SMT divergence occurs) |
| 2 | LTF CISD confirms — close through the opposing delivery opening |
| 3 | Check confluence: BSL/SSL taken, FVG tap, key level tap, KZ H/L tap |
| 4 | Bias set: bearish = high swept + CISD down; bullish = low swept + CISD up |

**Invalidation**: price reclaims the swept level.
**Continuation**: prior bias persists without new sweep if structure aligns.
**Pro Alert**: Sweep/SMT + (BSL/SSL or FVG or Key Level or KZ tap) + CISD = high-confidence.
**Multi-TF stacking**: run across 5 pairs (1M/1D, 1W/4H, 1D/1H, 4H/15m, 1H/5m).

### 5.2 Previous Day Candle Analysis

- **Bullish**: Close above PDH signals strength. Sweeping PDL and closing back above signals reversal.
- **Bearish**: Close below PDL signals weakness. Sweeping PDH and closing back below signals reversal.
- **Inside Bar**: Refer to previous candle's direction for likely target.

### 5.3 Midnight to London Range

Mark the range between 00:00 (Midnight Open) and 03:00 (London Open).
- **Judas Swing**: Move above/below the Midnight Open during London/Pre-Market that sweeps the range then reverses toward daily bias.
- If range hasn't been swept by 08:30 → wait for NY Open to sweep one side, then enter on displacement.

### 5.4 London Session Confirmation

- **Bullish**: London takes Asia Low (SSL) → NY continuation.
- **Bearish**: London takes Asia High (BSL) → NY continuation.
- **Range**: If London consolidates, NY will sweep that range.

### 5.5 Draw on Liquidity (DOL) Assessment

The market always moves from an imbalance to liquidity, or liquidity to an imbalance:
1. Where is the nearest liquidity pool (PDH/PDL/EQH/EQL)?
2. Where is the nearest imbalance (FVG)?

If price just swept liquidity → next draw is an imbalance. If it just filled an imbalance → next draw is liquidity.

### 5.6 Displacement Requirement

A valid bias MUST be supported by **displacement** (large-bodied candles). Without displacement/MSS, any move is likely just a hunt for liquidity (Judas Swing) rather than a trend change.

---

## 6. PD Arrays — Imbalances & Gaps

PD Arrays are zones where institutional orders concentrate. The algorithm delivers price to these zones for order fills.

### 6.1 Fair Value Gap (FVG)

3-candle formation where the wicks of candle 1 and candle 3 don't overlap, leaving a gap.

```python
# Python
gap_bull = df['low'].iloc[i] - df['high'].iloc[i-2]
if gap_bull > min_threshold:
    fvg = {'top': df['low'].iloc[i], 'bottom': df['high'].iloc[i-2], 'dir': 'bull'}

gap_bear = df['low'].iloc[i-2] - df['high'].iloc[i]
if gap_bear > min_threshold:
    fvg = {'top': df['low'].iloc[i-2], 'bottom': df['high'].iloc[i], 'dir': 'bear'}
```

```pine
// Pine Script
bool bullFVG = low > high[2] and close > high[2]
float fvgTop = low, fvgBot = high[2]

bool bearFVG = high < low[2] and close < low[2]
float fvgTop = low[2], fvgBot = high
```

**Mitigation**: price enters the FVG zone. Track by shrinking box to remaining unfilled portion. Full fill = price closes through entire gap.

### 6.2 Consequent Encroachment (CE)

The **50% midpoint** of an imbalance structure (FVG, IFVG, NWOG, or long wick).

```
CE = (FVG_top + FVG_bot) / 2
```

The minimum level the algorithm must revisit when rebalancing. Price often reacts at CE without filling the entire gap. After HTF CE is reached → drop to LTF for MSS/CHoCH entry confirmation.

**CE also applies to long wicks**: 50% of a wick range = reversal/target zone.

### 6.3 Mean Threshold (MT)

The **50% midpoint** of an order-based structure (Order Block, Breaker Block).

```
MT = (OB_high + OB_low) / 2
```

**CE vs MT**: CE applies to imbalances (FVGs, gaps, wicks). MT applies to order blocks and breaker blocks. Both represent equilibrium within their respective structures.

### 6.4 Inverted FVG (IFVG)

An FVG that was **invalidated** (price broke through) — now acts as S/R from the **opposite side**.

| Type | Formation |
|------|-----------|
| Bullish IFVG | Bearish FVG broken (price closes above) → flips to bullish support |
| Bearish IFVG | Bullish FVG broken (price closes below) → flips to bearish resistance |

Trade: wait for retest from the new side, enter on rejection. Invalidation: price trades back through in original direction.

### 6.5 Balanced Price Range (BPR)

The **overlap zone** between a bullish FVG and a bearish FVG. Price reacts strongly because it combines two opposing imbalances.

**Detection**: track all FVGs → check vertical overlap between most recent opposing pair.
**Clean BPR**: no price interference between the two FVGs before formation.
Delay signals by 1 bar to allow invalidation. Invalidation: price closes through full BPR range.

```pine
// Track last bull/bear FVG boundaries
// overlap_top = math.min(bull_top, bear_top)
// overlap_bot = math.max(bull_bot, bear_bot)
// if overlap_top > overlap_bot → BPR exists
```

### 6.6 Volume Imbalance (VI)

Gap between consecutive candle **bodies** (open/close, not wicks). Smaller than FVG but still a rebalancing target.

### 6.7 Opening Range Gap (ORG)

Gap between previous session close/settlement and new session open.

**For index futures**: 16:14 ET close → 09:30 ET open

| Level | Calculation |
|-------|-------------|
| Open | Previous settlement price |
| Close | New session open price |
| C.E. | (Open + Close) / 2 |
| Quadrants | 1/4 and 3/4 of gap |

~70% probability price retraces ≥50% of ORG within first 30 minutes.

**First 1-minute FVG** after 09:31 ET is a key entry signal — acts as focal point/magnet for the day. Monday's first FVG extends through the entire week.

### 6.8 NDOG / NWOG

| Gap | Definition |
|-----|------------|
| NDOG | Gap between today's midnight open and yesterday's close |
| NWOG | Gap between Sunday open and Friday close |

Both act as magnets. CE of NWOG is especially significant.

### 6.9 First Presented FVG (2022 Concept)

The very first Fair Value Gap on the 1-minute chart at **09:31 ET or later**.

- **Magnet**: Price often returns to this gap later in the session
- **Reversal Point**: If price trades into it and rejects, confirms direction
- **Extend to 15:45 ET** — observe how often price returns
- Can evolve into an **IFVG** if broken
- Monday's 1st FVG extends through the entire week
- Must be used with bias context

---

## 7. PD Arrays — Order Blocks

### 7.1 Order Block (OB)

The last opposite-direction candle before a displacement move.

| Type | Definition |
|------|------------|
| Bullish OB | Last bearish (down) candle before a strong up move (demand zone) |
| Bearish OB | Last bullish (up) candle before a strong down move (supply zone) |

```python
# Displacement = candle body > 2x average body size
avg_body = df['body'].rolling(20).mean()
is_displacement = df['body'] > (avg_body * 2.0)

# Find last opposite-color candle before displacement
if is_bullish_displacement:
    OB = last_bearish_candle_before_displacement
```

**Mitigation**: Bullish OB mitigated when price trades below OB low. Bearish OB mitigated when price trades above OB high.

### 7.2 Breaker Block (BB)

A **broken OB** that flips to act as S/R on the opposite side. A bullish OB that fails and gets broken → bearish breaker (resistance).

### 7.3 Propulsion Block

An OB that forms where price interacts with a **preceding OB**. NOT just an OB inside an FVG — specifically an OB that forms AT a prior OB level, signaling the original is being "reloaded."

| Type | Formation |
|------|-----------|
| Bullish Propulsion | Bearish OB forms → price returns to zone → bullish OB forms inside it |
| Bearish Propulsion | Bullish OB forms → price returns to zone → bearish OB forms inside it |

Detection: track OB zones → detect new OB forming within existing OB zone. When mitigated, both propulsion block AND associated OB are removed.

### 7.4 Other Block Types

| Block | Description |
|-------|-------------|
| Mitigation Block | Previously mitigated OB that failed, now opposing zone |
| Rejection Block | OB with long wick, price rejected from within |
| Vacuum Block | OB near a liquidity void |
| Reclaimed Block | OB that was broken then reclaimed |

### 7.5 PD Array Priority Matrix

**Premium (sell setups)**: Bearish OB → Bearish BB → Bearish FVG → Mitigation Block → Old High
**Discount (buy setups)**: Bullish OB → Bullish BB → Bullish FVG → Mitigation Block → Old Low

Algorithm skips absent arrays and proceeds to next in priority.

---

## 8. Premium & Discount

### 8.1 Equilibrium
50% level of any range — the dividing line between premium and discount.

### 8.2 OTE (Optimal Trade Entry)
61.8%–78.6% Fibonacci retracement zone of a displacement leg. Highest-probability entry zone within premium or discount.

### 8.3 Multi-TF Nesting
- **Double Discount**: LTF discount entry within HTF discount = highest probability long
- **Double Premium**: LTF premium entry within HTF premium = highest probability short

---

## 9. Time-Based Concepts

### 9.1 Sessions & Killzones (all ET)

| Session | Time | Notes |
|---------|------|-------|
| Asian Session | 20:00-00:00 | Consolidation range, sets up London |
| London Killzone | 02:00-05:00 | High-probability reversal window |
| NY AM Killzone | 09:30-11:00 | Primary day trading session |
| NY Lunch | 12:00-13:00 | Low volume, manipulation — avoid new entries |
| NY PM / London Close | 13:30-16:00 | Second high-probability window |

### 9.2 Killzone Pivot Tracking

After each KZ session ends, its H and L become **pivot levels**:
AS.H/AS.L, LO.H/LO.L, NYAM.H/NYAM.L, NYL.H/NYL.L, NYPM.H/NYPM.L

Pivots extend **until mitigated**. **Midpoint** (50% of KZ range) = separate level. Track range vs N-period historical average for expansion/compression.

### 9.3 ICT Macros

| Time (ET) | Name |
|-----------|------|
| 09:50-10:10 | NY Morning Macro |
| 10:50-11:10 | NY Mid-Morning Macro |
| 13:10-13:40 | NY Lunch Macro |
| 15:15-15:45 | NY Last Hour Macro |
| 02:33-03:00 | London Macro |
| 04:03-04:30 | London Macro 2 |

20-30 minute windows when institutional algorithms are most active. High probability for liquidity sweeps, FVG formations, and displacement.

### 9.4 Silver Bullet Windows

| Time (ET) | Name |
|-----------|------|
| 10:00-11:00 | NY AM Silver Bullet |
| 14:00-15:00 | NY PM Silver Bullet |
| 03:00-04:00 | London Silver Bullet |

Rules: HTF bias → liquidity sweep → displacement → FVG entry. One trade per window.

### 9.5 CBDR, Asia Range & FLOUT (Standard Deviation Ranges)

| Range | Time (ET) | SD Increments | Ideal Size (forex) |
|-------|-----------|---------------|-------------------|
| CBDR (Central Bank Dealers Range) | 16:00-20:00 | 1, 2, 3, 4 | 15-40 pips |
| Asia Range | 20:00-00:00 | 1, 2, 3, 4 | 20-40 pips |
| FLOUT (Full Range Out) | 16:00-00:00 | 0.5, 1, 1.5, 2 | Fallback |

**Auto SD Selection**: If CBDR is 15-40p → use CBDR. Else if Asia is 20-40p → use Asia. Else → FLOUT.

For futures (NQ/ES): range measured in points/ticks, not pips — thresholds differ.

### 9.6 ICT Opening Range (30-Minute Range)

The H/L range of the first 30 minutes of each session. The algorithm establishes key price levels during this window.

**Canonical Sessions** (from ICT Mentorship Core Content):

| Session | Time (ET) | Source |
|---------|-----------|--------|
| Midnight | 00:00-00:30 | Month 08 — Defining the Daily Range |
| London | 01:30-02:00 | Opening Range precedes London KZ |
| NY AM KZ | 07:00-07:30 | Opening Range Theory / 1st Presented FVG Logic |
| NY AM | 09:30-10:00 | Primary — equities open |
| NY PM | 13:30-14:00 | Afternoon session |
| Asia | 20:00-20:30 | Month 08 — Defining the Daily Range |

**Key levels within each Opening Range:**

| Level | Description |
|-------|-------------|
| Opening Price | Open of first 1m candle (static) |
| Range High / Low | Absolute H/L or swing-based |
| C.E. | Midpoint = (H + L) / 2 |
| Quadrants | 25% and 75% — premium/discount within range |

**SD Projections**: 0.5 SD increments from H and L. Dynamic (appear as price crosses) or Fixed (all at once).

**Statistic**: ~73% of the time (ES 2022), the daily H or L is made within the first hour.

### 9.7 PO3 / AMD / TGIF

**PO3 (Power of 3) / AMD**: Accumulation → Manipulation (Judas Swing) → Distribution.

**TGIF (Thank God It's Friday)**: Friday retracement toward 20-30% or 70-80% of weekly range.

| Zone | Condition | Expect |
|------|-----------|--------|
| Upper (70-80%) | Weekly H made on Friday | Retracement down |
| Lower (20-30%) | Weekly L made on Friday | Retracement up |

Detection: `dayofweek(weekly_high_time) == friday` → activate upper zone.

---

## 10. Standard Deviation Projections

### 10.1 Type 1: ADR-Based Standard Deviations

Projects levels from a reference point (Midnight Open, 08:30 Open) using Average Daily Range.

```
ADR = Average of (High - Low) over N days (typically 5 or 20)
SD_Unit = ADR / 2

Levels from Reference:
  +2.5 SD = Reference + (2.5 × SD_Unit)
  +2.0 SD = Reference + (2.0 × SD_Unit)
  ...
  Reference (0) = Midnight Open or 08:30 Open
  -1.0 SD = Reference - (1.0 × SD_Unit)
  ...
```

### 10.2 Type 2: Swing-Based / Failure Swing Projections

Projects levels from a key swing using the swing range as the unit. **Fractal** — works on any timeframe.

```
Swing_Range = Swing_High - Swing_Low

+4.5 = Anchor + (4.5 × Swing_Range)
+1.0 = Anchor + (1.0 × Swing_Range)  ← 100% extension
Anchor (0) = Failure swing point / Key level
-1.0 = Anchor - (1.0 × Swing_Range)
-2.5 = Anchor - (2.5 × Swing_Range)
```

### 10.3 Type 3: IPDA Fractal Standard Deviations

Projects deviation multiples from swing H/L within IPDA time windows.

- "0" = anchor (preceding swing low/high). "1" = the swing itself.
- `target = anchor + (range × deviation)`. Common: 0, 1, -1, -1.5, -2, -2.5, -4.
- Fractal windows: Monthly (D TF), Weekly (4H-8H), Daily (15m-1H), Intraday (1m-5m).
- 3-bar pivot swing detection. Invalidation when price trades through anchor.

### 10.4 Type 4: Opening Range SD Projections

Projects from the 30-minute Opening Range H/L in 0.5 SD increments.

- **Dynamic**: next level only appears when price crosses previous extreme
- **Fixed**: all levels plotted at session close
- `level = range_high + (N × 0.5 × range_size)` for upside
- `level = range_low - (N × 0.5 × range_size)` for downside

### 10.5 SD Projection Implementation

```python
def project_sd_levels(anchor, swing_range, direction='down',
                      levels=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]):
    result = []
    for sd in levels:
        if direction == 'down':
            result.append(anchor - (sd * swing_range))
        else:
            result.append(anchor + (sd * swing_range))
    return result
```

---

## 11. Reference Levels & Key Prices

### 11.1 Session Opening Prices (ET)

| Level | Time |
|-------|------|
| Midnight Open (NMO) | 00:00 |
| London Open | 03:00 |
| NY Open | 08:30 |
| Equities Open | 09:30 |
| Afternoon Open | 13:30 |

### 11.2 HTF Open, High, Low, Mid

**Always track all four** per period:

| Period | Open | Prev High | Prev Low | Mid = (H+L)/2 |
|--------|------|-----------|----------|----------------|
| Daily | D Open | PDH | PDL | PDM |
| Weekly | W Open | PWH | PWL | PWM |
| Monthly | M Open | PMH | PML | PMM |

Also track **current period developing** H/L/Mid.

**Mid = equilibrium** = key S/R level. Price above mid = premium, below = discount relative to that period. Mids of previous day/week/month are high-probability reaction points.

```python
# Python implementation
pdh = df.resample('D')['high'].max().shift(1)
pdl = df.resample('D')['low'].min().shift(1)
pdm = (pdh + pdl) / 2

pwh = df.resample('W-FRI')['high'].max().shift(1)
pwl = df.resample('W-FRI')['low'].min().shift(1)
pwm = (pwh + pwl) / 2

pmh = df.resample('ME')['high'].max().shift(1)
pml = df.resample('ME')['low'].min().shift(1)
pmm = (pmh + pml) / 2
```

### 11.3 ADR & Hourly Stats
- **ADR**: Average Daily Range in points/ticks
- **Hourly stats**: Mean/median range by hour for the instrument

---

## 12. Trading Models

### 12.1 ICT 2022 Model (Core Day Trading)

| Step | Action |
|------|--------|
| 1 | Determine daily bias (HTF structure + key levels) |
| 2 | Mark previous day/session H and L |
| 3 | Wait for liquidity sweep of range H or L |
| 4 | MSS with displacement on LTF (5m/3m/1m) |
| 5 | Mark PD array (FVG/OB) in premium/discount |
| 6 | Wait for retrace to PD array |
| 7 | Enter, stop beyond sweep, target opposing liquidity |

### 12.2 Silver Bullet
Time window (10-11, 14-15, or 03-04 ET) → bias → sweep → displacement → FVG entry. One trade per window.

### 12.3 Unicorn Model
OB + FVG overlap (propulsion block within FVG). Both align at same price zone.

### 12.4 One Shot One Kill (OSOK)
Single high-probability entry per day using IPDA + PD arrays.

### 12.5 Market Maker Models
- **MMBM (Buy)**: Accumulation → Spring/SSL sweep → Markup → Distribution
- **MMSM (Sell)**: Distribution → Upthrust/BSL sweep → Markdown → Accumulation

---

## 13. Intraday Bias Determination

### Full Method Checklist

| # | Method | Key Signal |
|---|--------|-----------|
| 1 | Previous Day Candle | Close vs PDH/PDL, sweep + reversal |
| 2 | Midnight-London Range | Judas swing, range sweep |
| 3 | London Confirmation | Asia H/L sweep → NY continuation |
| 4 | Daily MSS | Structural displacement on daily chart |
| 5 | Premium/Discount | Position relative to D/W range equilibrium |
| 6 | TF Alignment | D/4H/1H structures in sync |
| 7 | Draw on Liquidity | Nearest liquidity pool vs nearest imbalance |
| 8 | Displacement | No displacement = no trade |
| 9 | HTF Sweep + LTF CISD | The systematic model (Section 5.1) |

---

## 14. News Guidance

### High-Impact News Weeks (CPI, FOMC, NFP)

| Period | Recommendation |
|--------|----------------|
| Monday-Tuesday of NFP/FOMC week | Tradeable with caution |
| Wednesday-Thursday pre-news | Reduce size or sit out |
| Day of CPI/NFP (before 08:30) | Avoid intraday. Consolidation profile. |
| FOMC Wednesday (entire day) | **NO TRADING** |
| During News Release | **NEVER TRADE** |
| 15-60 min after release | Wait for recovery setup (MSS/CISD on LTF) |
| Day after FOMC/NFP | Often cleaner directional setups |

### "Seek and Destroy" Profile
Neutral/low-probability profile common during major news weeks. Aggressive hunting of liquidity on both sides with no clear directional bias. Common in summer months (July/August).

### Practical Rules
- **Manipulation Window**: 08:35-09:20 ET often manipulative after 08:30 release. Wait for valid setup after 09:20.
- **Recovery**: 80% of the time, recovery setup occurs 20-60 minutes post-release.
- 8:30 AM releases can override technical levels. Wait 15 minutes for algorithmic patterns to resume.

---

## 15. Execution Playbook

### Phase 1: Pre-Market (08:30-09:30 ET)

- [ ] Check Economic Calendar — is it a "No Trade" week?
- [ ] Establish confluence — does statistical data align with daily classification?
- [ ] Mark liquidity magnets: Midnight Open, London Range H/L, PDH/PDL
- [ ] Analyze sweeps: Has London already swept Asia? If yes → NY continuation. If no → expect NY sweep.

### Phase 2: The Open (09:30-10:10 ET)

- [ ] 09:30 Opening Range — observe initial impulse vs Midnight Open
- [ ] Wait for Judas Swing — 80% of setups occur after initial London range sweep
- [ ] **Macro Window (09:50-10:10)** — prime time for MSS. Look for displacement + FVG.
- [ ] **Silver Bullet (10:00-11:00)** — entries at FVGs in direction of confirmed bias

### Phase 3: AM Execution (10:10-12:00 ET)

- [ ] Target 80% confidence levels
- [ ] Use London Mid or Midnight Open as trailing stop reference
- [ ] PDH/PDL sweep → watch for reversal closure or full expansion
- [ ] **NY Lunch** — begin flattening by 12:00. Choppy, mean-reverting action.

### Hard Rules

1. **Bias Conflict**: If stats say Bullish but classification says Bearish → low conviction or wait for 10:00 sweep
2. **Missing Displacement**: No displacement = no trade
3. **News Release**: Never trade during release. Wait 15-60 min for recovery.
4. **Range Bound London**: If London stayed inside Asia → expect volatile NY expansion

---

## 16. Risk Management

| Rule | Detail |
|------|--------|
| Max risk | 1-2% per trade |
| Stop placement | Beyond the sweep H/L |
| Partials | At 1:1, 2:1; runner to target |
| Break-even | Move stop after first partial |
| Trade count | One per day mentality |
| Min R:R | 3R+ asymmetric |
| Sit out | No bias, macro news, Friday PM |

---

## 17. Failure Swings

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
1. Price makes swing high (H1)
2. Pulls back to swing low (L1)
3. Rallies but **fails to exceed H1** → lower high (H2)
4. H2 is the failure swing → bearish signal

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
1. Price makes swing low (L1)
2. Rallies to swing high (H1)
3. Retraces but **fails to exceed L1** → higher low (L2)
4. L2 is the failure swing → bullish signal

### Detection Algorithm
```python
def find_failure_swings(df, lookback=20):
    swings = []
    df['is_swing_high'] = (df['high'] == df['high'].rolling(5, center=True).max())
    df['is_swing_low']  = (df['low'] == df['low'].rolling(5, center=True).min())

    swing_highs = df[df['is_swing_high']].index.tolist()
    swing_lows  = df[df['is_swing_low']].index.tolist()

    # Check for lower high (bearish failure)
    for i in range(1, len(swing_highs)):
        curr_high = df.loc[swing_highs[i], 'high']
        prev_high = df.loc[swing_highs[i-1], 'high']
        if curr_high < prev_high:
            between_low = df.loc[swing_highs[i-1]:swing_highs[i], 'low'].min()
            swing_range = prev_high - between_low
            swings.append({
                'type': 'BEARISH_FAILURE',
                'datetime': swing_highs[i],
                'anchor': curr_high,
                'swing_range': swing_range
            })
    # Mirror for bullish failure (higher low)...
    return swings[-5:]
```

---

## 18. Weekly Profiles

### High/Low of Week Timing

| Bullish Week | Bearish Week |
|-------------|-------------|
| Low: Monday/Tuesday | High: Monday/Tuesday |
| High: Thursday/Friday | Low: Thursday/Friday |

---

## 19. Quantitative Data

### 19.1 FP Zone Strategy
NQ TP22/SL66 ticks, 58% WR. S/R both directions. Best hours (ET): 02, 04, 06, 07, 09-12, 15.

### 19.2 Historical Data
48,732 session samples (10 years). Session combo patterns (APEX/LINE classification). Candle Science Engine pattern matching. Hourly range mean/median for NQ. Bullish bias % by hour. BISI/SIBI effectiveness by hour.

---

## 20. Glossary

| Abbr | Meaning |
|------|---------|
| ADR | Average Daily Range |
| AMD | Accumulation Manipulation Distribution |
| BB | Breaker Block |
| BOS | Break of Structure |
| BPR | Balanced Price Range |
| BSL | Buyside Liquidity |
| CE | Consequent Encroachment |
| CHoCH | Change of Character |
| CISD | Change in State of Delivery |
| DOL | Draw on Liquidity |
| EQH/EQL | Equal Highs / Equal Lows |
| FVG | Fair Value Gap |
| HRLR | High Resistance Liquidity Run |
| HTF/LTF | Higher / Lower Time Frame |
| IDM | Inducement |
| IFVG | Inverted Fair Value Gap |
| IPDA | Interbank Price Delivery Algorithm |
| ITH/ITL | Intermediate Term High / Low |
| LRLR | Low Resistance Liquidity Run |
| MMBM/MMSM | Market Maker Buy / Sell Model |
| MSS | Market Structure Shift |
| MT | Mean Threshold |
| NDOG | New Day Opening Gap |
| NMO | NY Midnight Open |
| NWOG | New Week Opening Gap |
| OB | Order Block |
| ORG | Opening Range Gap |
| OSOK | One Shot One Kill |
| OTE | Optimal Trade Entry |
| PDH/PDL | Previous Day High / Low |
| PDM | Previous Day Midpoint |
| PMH/PML | Previous Month High / Low |
| PO3 | Power of 3 |
| PWH/PWL | Previous Week High / Low |
| PWM | Previous Week Midpoint |
| SMC | Smart Money Concepts |
| SMT | Smart Money Tool (Divergence) |
| SSL | Sellside Liquidity |
| STH/STL | Short Term High / Low |
| TGIF | Thank God It's Friday |
| VI | Volume Imbalance |
