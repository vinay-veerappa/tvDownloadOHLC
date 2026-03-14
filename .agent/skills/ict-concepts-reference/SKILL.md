---
name: ICT Concepts Reference
description: Domain knowledge reference for ICT/SMC concepts, market structure, liquidity, sessions, and algorithmic detection rules used by trading indicator workflows.
---

# ICT Concepts Skill — Domain Knowledge Reference

> Comprehensive reference for Inner Circle Trader (ICT) / Smart Money Concepts (SMC)
> methodology. Covers market structure, liquidity, PD arrays, time-based concepts,
> bias determination, reference levels, and algorithmic detection rules.
>
> **Purpose**: Domain knowledge that informs WHAT to build.
> For HOW to build it in Pine Script / NinjaScript / Tradovate, see TRADING_INDICATOR_SKILL.md.
>
> **Instrument context**: Primarily NQ (Nasdaq futures), also ES, RTY, YM, GC, CL, forex futures.
> All times are Eastern Time (ET / America/New_York) unless noted.

---

## 1. FOUNDATIONAL FRAMEWORK

### 1.1 IPDA (Interbank Price Delivery Algorithm)

The core model: price moves for two reasons — to seek **liquidity** and to rebalance **imbalances**. The algorithm delivers price between institutional levels within specific data ranges.

### 1.2 IPDA Data Ranges (20/40/60)

Rolling lookback windows defining the algorithm's operating range:

| Range | Lookback | Scope |
|-------|----------|-------|
| IPDA 20 | Last 20 daily candles | Short-term dealing range |
| IPDA 40 | Last 40 daily candles | Intermediate institutional range |
| IPDA 60 | Last 60 daily candles | Full institutional cycle |

**Calculation** (Daily TF, excluding current bar):
```
high_N = ta.highest(high, N)[1]
low_N  = ta.lowest(low, N)[1]
equilibrium = (high_N + low_N) / 2
position_pct = ((close - low_N) / (high_N - low_N)) * 100
```

- Each range shifts daily. The algorithm seeks BOTH the highs AND lows of the previous 60 days.
- Premium = price above equilibrium. Discount = price below equilibrium.
- Display modes: Classic (1D only), Classic+LTF (any TF via `request.security`), LTF (adapts to chart).

---

## 2. MARKET STRUCTURE

### 2.1 Break of Structure (BOS)
**Continuation** signal. Price breaks a swing high in uptrend / swing low in downtrend, confirming the existing trend.

### 2.2 Market Structure Shift (MSS) / Change of Character (CHoCH)
**Reversal** signal. Price breaks a swing low in uptrend / swing high in downtrend. Based on **high/low** swing points.

### 2.3 CISD (Change in State of Delivery)
**Earliest** reversal signal — forms BEFORE MSS/CHoCH. Uses candle **open/close**, not high/low.

| Direction | Condition |
|-----------|-----------|
| Bullish CISD | Price closes ABOVE the opening of the bearish delivery sequence |
| Bearish CISD | Price closes BELOW the opening of the bullish delivery sequence |

Invalidation: price reclaims the swept high/low. Late CISD: confirmation after HTF candle closes. Continuation: bias persists if structure aligns without new sweep.

### 2.4 Swing Hierarchy

| Level | Abbreviation | Use |
|-------|-------------|-----|
| Short-Term | STH / STL | Internal structure, entry refinement |
| Intermediate-Term | ITH / ITL | Key swings within a trend leg |
| Long-Term | LTH / LTL | Major points defining the trend |

### 2.5 Multi-Timeframe Alignment
HTF sets bias. LTF refines entry. Bullish HTF + LTF discount entry = highest probability.

---

## 3. LIQUIDITY

### 3.1 Core Concepts

| Concept | Description |
|---------|-------------|
| BSL (Buyside Liquidity) | Stops/orders above swing highs, equal highs, resistance |
| SSL (Sellside Liquidity) | Stops/orders below swing lows, equal lows, support |
| EQH / EQL | Equal highs/lows — obvious liquidity pools |
| Liquidity Sweep | Price trades through a level then reverses (stop hunt) |
| External Liquidity | Swing highs/lows — targets |
| Internal Liquidity | FVGs, imbalances — entry zones |
| Inducement (IDM) | Minor liquidity to lure retail before true sweep |
| HRLR / LRLR | High/Low Resistance Liquidity Run — difficulty of price delivery |
| Turtle Soup | Fading breakouts above/below 20-day H/L |

### 3.2 BSL/SSL Pivot Detection
```
Swing High: high[2] < high[1] > high[0]  (3-bar pivot)
Swing Low:  low[2] > low[1] < low[0]
Equal Highs: |pivot1 - pivot2| <= ATR margin
On sweep (high > level AND close < level): mark as swept
```

---

## 4. SMT DIVERGENCE (Smart Money Tool)

A "crack" in correlation between two markets that normally move together. One makes a new extreme; the other fails to confirm — signals institutional manipulation.

### 4.1 Correlated Instrument Groups (Futures)

| Group | Instruments | Correlation |
|-------|-------------|-------------|
| Equity Indices | NQ, ES, YM, RTY | Positive |
| Metals | GC, SI, HG | Positive |
| Energy | CL, NG | Positive |
| Forex Futures | 6E, 6B, 6J vs DX | Inverse (DX) |
| Crypto | BTC, ETH (CME) | Positive |

Primary triad for NQ: **NQ & ES & YM**

### 4.2 Detection

| Type | Condition |
|------|-----------|
| Bearish SMT | Asset HH, correlated asset LOWER high |
| Bullish SMT | Asset LL, correlated asset HIGHER low |
| Inverse | When vs DX: flip the comparison |

SMT requires confluence with key levels, killzones, PD arrays. Best at D/W/4H highs and lows.

---

## 5. BIAS DETERMINATION MODEL (HTF Sweep + LTF CISD)

| Step | Action |
|------|--------|
| 1 | HTF candle sweeps previous candle's H or L (or SMT divergence occurs) |
| 2 | LTF CISD confirms — close through the opposing delivery opening |
| 3 | Check confluence: BSL/SSL taken, FVG tap, key level tap, KZ H/L tap |
| 4 | Bias set: bearish = high swept + CISD down; bullish = low swept + CISD up |

Invalidation: price reclaims swept level. Continuation: prior bias persists without new sweep.
Pro Alert: Sweep/SMT + (BSL/SSL or FVG or Key Level or KZ tap) + CISD = high-confidence.
Multi-TF stacking: run across 5 pairs (1M/1D, 1W/4H, 1D/1H, 4H/15m, 1H/5m).

---

## 6. PD ARRAYS (Premium/Discount Arrays)

### 6.1 Fair Value Gap (FVG)
3-candle formation, wicks don't overlap. The gap = imbalance the algorithm returns to fill.

```
Bullish: low > high[2] AND close > high[2]  → zone = [high[2], low]
Bearish: high < low[2] AND close < low[2]   → zone = [high, low[2]]
```

### 6.2 Consequent Encroachment (CE)
50% midpoint of an FVG, IFVG, NWOG, or long wick: `CE = (top + bot) / 2`
The minimum level the algorithm must revisit. Price often reacts here without filling the entire gap.

### 6.3 Mean Threshold (MT)
50% midpoint of an Order Block or Breaker Block: `MT = (OB_high + OB_low) / 2`
CE applies to imbalances; MT applies to order-based structures.

### 6.4 Inverted FVG (IFVG)
An FVG that was **invalidated** (price broke through) — now acts as S/R from the **opposite side**.
Bullish IFVG = broken bearish FVG flipped to support. Bearish IFVG = broken bullish FVG flipped to resistance.

### 6.5 Balanced Price Range (BPR)
The **overlap zone** between a bullish FVG and a bearish FVG. Two opposing FVGs with vertical overlap.
High-probability entry zone. "Clean BPR" = no price interference between the two FVGs.
Detection: track all FVGs → check overlap between most recent opposing pair. Delay 1 bar for invalidation.

### 6.6 Volume Imbalance (VI)
Gap between consecutive candle bodies (open/close, not wicks). Smaller than FVG but still a rebalancing target.

### 6.7 Opening Range Gap (ORG)
Gap between previous session close (16:14 ET) and new session open (09:30 ET).

| Level | Calculation |
|-------|-------------|
| Open | Previous settlement |
| Close | New session open |
| C.E. | (Open + Close) / 2 |
| Quadrants | 1/4 and 3/4 of gap |

~70% probability price retraces ≥50% of ORG in first 30 minutes. First 1m FVG after 09:31 = key entry signal.

### 6.8 NDOG / NWOG
NDOG = gap between today's midnight open and yesterday's close. NWOG = gap between Sunday open and Friday close.
Both act as magnets. CE of NWOG is especially significant.

### 6.9 Order Block (OB)
Last opposing candle before displacement. Bullish OB = last down candle before up move. Bearish OB = last up candle before down move.

### 6.10 Breaker Block (BB)
A broken OB that flips to opposing S/R. Failed bullish OB → bearish breaker (resistance).

### 6.11 Propulsion Block
An OB that forms where price interacts with a **preceding OB**. Signals the original OB is being "reloaded" with institutional orders. Detection: track OB zones → detect new OB forming within existing OB zone.

### 6.12 PD Array Priority Matrix
**Premium (sell)**: Bearish OB → BB → FVG → Mitigation Block → Old High
**Discount (buy)**: Bullish OB → BB → FVG → Mitigation Block → Old Low
Algorithm skips absent arrays.

---

## 7. PREMIUM & DISCOUNT

### 7.1 Equilibrium
50% level of any range. The dividing line between premium and discount.

### 7.2 OTE (Optimal Trade Entry)
61.8%–78.6% Fibonacci retracement zone of a displacement leg. Highest-probability entry zone.

### 7.3 Multi-TF Nesting
Discount entry on LTF within HTF discount = "double discount" = highest probability long.
Premium entry on LTF within HTF premium = "double premium" = highest probability short.

### 7.4 IPDA Standard Deviations (Fractal SD Projections)
Projects deviation multiples from swing H/L within IPDA time windows.
- "0" = anchor (preceding swing low/high). "1" = the swing point itself.
- `target = anchor + (range × deviation)`. Common: 0, 1, -1, -1.5, -2, -2.5, -4.
- Fractal windows: Monthly (D TF), Weekly (4H-8H), Daily (15m-1H), Intraday (1m-5m).
- 3-bar pivot swing detection. Invalidation when price trades through anchor.

---

## 8. TIME-BASED CONCEPTS

### 8.1 Sessions & Killzones (all ET)

| Session | Time | Notes |
|---------|------|-------|
| Asian Session | 20:00-00:00 | Consolidation, sets up London |
| London Killzone | 02:00-05:00 | High-probability reversal window |
| NY AM Killzone | 09:30-11:00 | Primary day trading session |
| NY Lunch | 12:00-13:00 | Low volume, manipulation — avoid |
| NY PM / London Close | 13:30-16:00 | Second high-probability window |

### 8.2 Killzone Pivot Tracking
After each KZ, its H/L become pivot levels (AS.H, LO.H, NYAM.H, etc.). Extend until mitigated. Midpoint (50% of KZ range) = separate level. Track range vs N-period average for expansion/compression.

### 8.3 ICT Macros

| Time (ET) | Name |
|-----------|------|
| 09:50-10:10 | NY Morning Macro |
| 10:50-11:10 | NY Mid-Morning Macro |
| 13:10-13:40 | NY Lunch Macro |
| 15:15-15:45 | NY Last Hour Macro |
| 02:33-03:00 | London Macro |
| 04:03-04:30 | London Macro 2 |

### 8.4 Silver Bullet Windows

| Time (ET) | Name |
|-----------|------|
| 10:00-11:00 | NY AM Silver Bullet |
| 14:00-15:00 | NY PM Silver Bullet |
| 03:00-04:00 | London Silver Bullet |

Rules: HTF bias → liquidity sweep → displacement → FVG entry. One trade per window.

### 8.5 CBDR, Asia Range & FLOUT

| Range | Time (ET) | SD Increments | Ideal Size (forex) |
|-------|-----------|---------------|-------------------|
| CBDR | 16:00-20:00 | 1, 2, 3, 4 | 15-40 pips |
| Asia | 20:00-00:00 | 1, 2, 3, 4 | 20-40 pips |
| FLOUT | 16:00-00:00 | 0.5, 1, 1.5, 2 | Fallback |

Auto select: CBDR if 15-40p → else Asia if 20-40p → else FLOUT.
For futures: thresholds measured in points/ticks, not pips.

### 8.6 ICT Opening Range (30-Minute Range)

| Session | Time (ET) | Source |
|---------|-----------|--------|
| Midnight | 00:00-00:30 | ICT Month 08 |
| London | 01:30-02:00 | Precedes London KZ |
| NY AM KZ | 07:00-07:30 | Opening Range Theory |
| NY AM | 09:30-10:00 | Primary |
| NY PM | 13:30-14:00 | Afternoon |
| Asia | 20:00-20:30 | ICT Month 08 |

**Levels**: Opening Price (static), Range H/L, C.E. (midpoint), Quadrants (25%/75%).
**SD Projections**: 0.5 SD increments from H/L. Dynamic (appear as price crosses) or Fixed (all at once).
**Statistic**: ~73% of time, daily H or L made within first hour (ES 2022).

**First Presented FVG (1st FVG)**: First FVG on 1m chart at 09:31+ ET. Focal point for the day. Extend to 15:45. Monday's extends through the week.

### 8.7 Weekly/Daily Profiles

**PO3 (Power of 3) / AMD**: Accumulation → Manipulation (Judas Swing) → Distribution.

**TGIF**: Friday retracement to 20-30% or 70-80% of weekly range.

| Zone | Condition | Expect |
|------|-----------|--------|
| Upper (70-80%) | Weekly H made on Friday | Retracement down |
| Lower (20-30%) | Weekly L made on Friday | Retracement up |

---

## 9. TRADING MODELS

### 9.1 ICT 2022 Model

| Step | Action |
|------|--------|
| 1 | Determine daily bias (HTF structure + key levels) |
| 2 | Mark previous day/session H and L |
| 3 | Wait for liquidity sweep of range H or L |
| 4 | MSS with displacement on LTF (5m/3m/1m) |
| 5 | Mark PD array (FVG/OB) in premium/discount |
| 6 | Wait for retrace to PD array |
| 7 | Enter, stop beyond sweep, target opposing liquidity |

### 9.2 Silver Bullet
Time window → bias → sweep → displacement → FVG entry. One trade per window.

### 9.3 Unicorn Model
OB + FVG overlap (propulsion block within FVG). Both align at same price zone.

### 9.4 One Shot One Kill (OSOK)
Single high-probability entry per day using IPDA + PD arrays.

### 9.5 Market Maker Models
MMBM (Buy): Accumulation → Spring/SSL sweep → Markup → Distribution.
MMSM (Sell): Distribution → Upthrust/BSL sweep → Markdown → Accumulation.

---

## 10. REFERENCE LEVELS

### 10.1 Session Opening Prices (ET)
Midnight (00:00), London (03:00), NY (08:30), Equities (09:30), Afternoon (13:30).

### 10.2 HTF Open, High, Low, Mid
**Always track all four** per period:

| Period | Open | Prev High | Prev Low | Mid = (H+L)/2 |
|--------|------|-----------|----------|----------------|
| Daily | D Open | PDH | PDL | D Mid |
| Weekly | W Open | PWH | PWL | W Mid |
| Monthly | M Open | PMH | PML | M Mid |

Also track current developing H/L/Mid. Mid = equilibrium = key S/R. Above mid = premium, below = discount.

### 10.3 ADR & Hourly Stats
ADR = Average Daily Range in points/ticks. Hourly mean/median ranges by instrument.

---

## 11. RISK MANAGEMENT

| Rule | Detail |
|------|--------|
| Max risk | 1-2% per trade |
| Stop | Beyond the sweep H/L |
| Partials | At 1:1, 2:1; runner to target |
| Break-even | After first partial |
| Trade count | One per day mentality |
| Min R:R | 3R+ asymmetric |
| Sit out | No bias, macro news, Friday PM |

---

## 12. GLOSSARY

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
| OTE | Optimal Trade Entry |
| PDH/PDL | Previous Day High / Low |
| PO3 | Power of 3 |
| PWH/PWL | Previous Week High / Low |
| PMH/PML | Previous Month High / Low |
| SMC | Smart Money Concepts |
| SMT | Smart Money Tool (Divergence) |
| SSL | Sellside Liquidity |
| STH/STL | Short Term High / Low |
| TGIF | Thank God It's Friday |
| VI | Volume Imbalance |

---

## 13. QUANTITATIVE DATA

### 13.1 FP Zone Strategy
NQ TP22/SL66 ticks, 58% WR. S/R both directions. Best hours: 02, 04, 06, 07, 09-12, 15 ET.

### 13.2 Historical
48,732 session samples (10yr). Session combo patterns (APEX/LINE). Candle Science Engine data.
Hourly range mean/median for NQ. Bullish bias % by hour. BISI/SIBI effectiveness by hour.

---

## 14. ALGORITHMIC DETECTION RULES

This section bridges the ICT Concepts Skill and the Trading Indicator Skill.

### 14.1 FVG Detection
```
Bullish: low > high[2] AND close > high[2] → zone [high[2], low]
Bearish: high < low[2] AND close < low[2]  → zone [high, low[2]]
CE = (top + bot) / 2
```

### 14.2 HTF FVG Between Candle Objects
```
if c1.low > c3.high  → bullish FVG between candles 1 and 3
if c3.low > c1.high  → bearish FVG between candles 1 and 3
```

### 14.3 Multi-TF FVG (request.security bundle)
```
getFVGData() => [time, close, high, low, open, high[1], low[1], ..., high[2], low[2], ...]
[data...] = request.security(syminfo.tickerid, ltfRes, getFVGData(), lookahead=on)
```

### 14.4 CISD Detection
```
1. Track LTF candle tips (+1=bull, -1=bear) in arrays per HTF period
2. After HTF sweep: find swing H bar in LTF → walk forward to first bull→bear transition
3. Mark that candle's open as CISD level
4. If any close < CISD level → bearish CISD confirmed
5. Invalidation: current high > HTF swing high → reset
6. Late CISD: LTF later closes through level after HTF period ends
```

### 14.5 SMT Detection
```
Fetch OHLC of 2-3 correlated instruments via request.security
Bearish SMT: asset_H1 >= asset_H2 AND corr_H1 < corr_H2
Bullish SMT: asset_L1 <= asset_L2 AND corr_L1 > corr_L2
Inverse (DX): flip the high/low comparison
```

### 14.6 HTF FVG with Mitigation
```
1. Detect FVG → create box
2. Each bar: extend box right
3. Price enters gap → shrink box to remaining unfilled portion
4. Price closes through → invalidate (gray, stop extending)
5. Delete FVGs older than parent HTF period
```

### 14.7 Killzone Pivot Management
```
UDT: kz type with arrays of boxes, lines, labels, validity bools, range store
kz_helper wraps kz with session string and colors
On session start: create drawings. During: update H/L. After: extend pivots.
Mitigation: hi_valid=false when price breaks through
Range avg: array.unshift(store, range) + store.avg()
```

### 14.8 IPDA Data Range
```
high20 = ta.highest(high, 20)[1]  // Daily TF, or via request.security
low20  = ta.lowest(low, 20)[1]
eq = (high20 + low20) / 2
pct = ((close - low20) / (high20 - low20)) * 100
```

### 14.9 Opening Range Gap
```
Session: time("1", "1614-0930", "America/New_York")
ORG open = close at session start, ORG close = open at session end
CE = (open + close) / 2. Quadrants = gap/4.
First 1m FVG: request.security_lower_tf, body bounds, valid 09:31-12:00
```

### 14.10 Opening Range (30-Min)
```
Range: running min/max during 30-min window
Quadrants: 25%, 50% (CE), 75%
SD projections (dynamic):
  while low <= dynamicLow → plot next -0.5 SD, update dynamicLow
  while high >= dynamicHigh → plot next +0.5 SD, update dynamicHigh
SD projections (fixed): loop 1 to max_sd/0.5, plot both directions
```

### 14.11 TGIF
```
Track weekly H/L and time of occurrence
If dayofweek(weekly_high_time) == friday → upper zone (70-80% of range)
If dayofweek(weekly_low_time) == friday → lower zone (20-30% of range)
```

### 14.12 BPR
```
Track all bullish/bearish FVGs
For each new FVG: check vertical overlap with most recent opposing FVG
overlap_top = min(bull_top, bear_top), overlap_bot = max(bull_bot, bear_bot)
If overlap_top > overlap_bot → BPR. Delay 1 bar. Invalidate on close through.
```

### 14.13 IPDA Standard Deviations
```
3-bar pivot swing detection per time window
Bearish: range = swing_high - preceding_swing_low
  For each dev: price = preceding_swing_low + (range × dev)
Bullish: range = preceding_swing_high - swing_low
  For each dev: price = preceding_swing_high - (range × dev)
Invalidation: price through anchor → delete SD lines
```

