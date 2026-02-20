# Trading Indicator Development Skill

> Comprehensive skill for building trading indicators across TradingView (Pine Script v6),
> NinjaTrader 8 (NinjaScript/C#), and Tradovate (JavaScript).
> Tailored for ICT-methodology trading tools, overlay indicators, and statistical dashboards.
> Includes cross-platform conversion mappings.

---

## 1. Script Structure (Mandatory Order)

Always organize Pine Script files in this order. Never deviate.

```
<license>              // MPL 2.0 + author
<version>              // //@version=6
<declaration>          // indicator() or strategy()
<imports>              // import statements if using libraries
<UDT_definitions>      // type declarations (User Defined Types)
<constants>            // SNAKE_CASE const values
<inputs>               // All input.* calls, grouped by feature
<helper_functions>     // Pure utility functions (no global deps)
<global_functions>     // Functions that depend on global state
<calculations>         // Core logic, HTF detection, state machines
<strategy_calls>       // strategy.entry/exit (strategies only)
<visuals>              // Drawing code (boxes, lines, labels, tables)
<alerts>               // alertcondition() calls at the very end
```

---

## 2. Version & Declaration

```pine
//@version=6
indicator("Indicator Name v1.0", overlay=true, 
  max_boxes_count=500, max_lines_count=500, max_labels_count=500,
  max_bars_back=5000)
```

- Always use `//@version=6`
- Always set `max_boxes_count`, `max_lines_count`, `max_labels_count` to 500 for overlay indicators
- Add `max_bars_back=5000` when using historical bar references beyond 500 bars
- For strategies, include: `pyramiding`, `default_qty_type`, `initial_capital`, `commission_type`, `commission_value`

---

## 3. Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Constants | `SNAKE_CASE` | `MAX_LOOKBACK`, `BULL_COLOR` |
| Inputs | `i_` prefix + camelCase | `i_htfTF`, `i_candleWidth`, `i_showTable` |
| Input groups | `GRP_` prefix or descriptive string | `"HTF Settings"`, `"OHLC Traces"` |
| Functions | `f_` prefix + camelCase | `f_lineStyle()`, `f_colors()`, `f_formatTime()` |
| UDT types | PascalCase | `HTFCandle`, `SessionData`, `TradeEntry` |
| UDT fields | camelCase | `startIdx`, `wickUp`, `traceO` |
| Methods on UDTs | PascalCase verb | `Monitor()`, `Update()`, `Reorder()` |
| Local variables | camelCase | `bodyTop`, `wickBar`, `isBull` |
| `var` state variables | camelCase | `var float liveO = na` |
| Drawing references | `lv` prefix for live | `lvBody`, `lvWickUp`, `lvTraceO` |
| Alert variables | descriptive | `completedBull`, `alertPrevH` |

---

## 4. User Defined Types (UDTs)

**Always use UDTs when an entity has 3+ related fields.** UDTs bundle data and drawings together, preventing parallel array sync bugs.

### Pattern: Entity UDT with Drawings

```pine
type HTFCandle
    float   o
    float   h
    float   l
    float   c
    int     startTime
    int     startIdx
    int     endIdx
    int     hIdx
    int     lIdx
    bool    isBull
    // Drawings — owned by this entity
    box     body
    line    wickUp
    line    wickDn
    line    traceO
    line    traceH
    label   rangeLabel
    label   timeLabel
```

### Pattern: Settings UDT

```pine
type CandleSettings
    bool    show
    string  htf
    int     maxDisplay
```

### Benefits
- **Single array** holds all entities: `var array<HTFCandle> candles = array.new<HTFCandle>()`
- **Clean deletion**: One function deletes all drawings for an entity
- **No parallel array sync issues**: Everything travels together
- **Easy history management**: `array.push(candles, c)` / `array.shift(candles)`

### Cleanup Pattern
```pine
while array.size(candles) > maxCount
    HTFCandle del = array.shift(candles)
    box.delete(del.body)
    line.delete(del.wickUp)
    line.delete(del.wickDn)
    line.delete(del.traceO)
    // ... delete all drawing fields
```

---

## 5. Input Organization

### Group inputs by feature, not by type

```pine
// ── HTF Settings ──
i_htfTF       = input.timeframe("60",  "HTF Timeframe",                    group="HTF Settings")
i_candleCount = input.int(50,          "Max Candles",  minval=1, maxval=200, group="HTF Settings")

// ── Bullish Colors ──
i_bullBody    = input.color(color.new(#26a69a, 20), "Body Fill",           group="Bullish Colors")
i_bullBorder  = input.color(color.new(#26a69a, 0),  "Border",             group="Bullish Colors")
i_bullWick    = input.color(color.new(#26a69a, 0),  "Wick",               group="Bullish Colors")
```

### MANDATORY: Configurable table/text sizing and position

Every indicator with tables MUST include:

```pine
i_tablePos    = input.string("Top Right", "Table Position", 
  options=["Top Left","Top Right","Bottom Left","Bottom Right","Middle Left","Middle Right"],
  group="Info Table")
i_tableSize   = input.string("normal", "Table Text Size", 
  options=["tiny","small","normal","large"], group="Info Table")
```

Default text/table size: **normal** (not small, not tiny).

### MANDATORY: Colors must work on light backgrounds

- Never use `color.white` as a default text color
- Use dark defaults or provide theme-aware inputs
- Test against TradingView's "Light Pro" theme mentally

### Use inline for related inputs

```pine
i_sess1 = input.bool(true, "18-21", inline="s1", group="Sessions")
i_sess2 = input.bool(true, "21-00", inline="s1", group="Sessions")
```

### Use tooltips for non-obvious settings

```pine
i_showOTE = input.bool(false, "Show OTE Zone (62-79%)", group="Fib", 
  tooltip="ICT Optimal Trade Entry zone drawn as a shaded box")
```

---

## 6. Drawing Management

### CRITICAL: Never delete historical drawings

**Preserve all boxes/lines/labels** so users can scroll through history. Only delete:
- Live/updating drawings that get recreated each bar
- Drawings that exceed `max_*_count` limits (use array trimming)

### Pattern: Update-in-Place for Live Drawings

Instead of delete-and-recreate every bar (expensive), use set methods:

```pine
var box lvBody = na

if not na(liveO)
    if na(lvBody)
        lvBody := box.new(bL, bTop, bR, bBot, border_color=col, bgcolor=fill)
    else
        box.set_top(lvBody, bTop)
        box.set_bottom(lvBody, bBot)
        box.set_left(lvBody, bL)
        box.set_right(lvBody, bR)
        box.set_bgcolor(lvBody, fill)
        box.set_border_color(lvBody, col)
```

This is significantly more efficient than:
```pine
// BAD — creates drawing object churn
box.delete(lvBody)
lvBody := box.new(...)
```

**Exception**: Labels with changing text are cheaper to delete/recreate since `label.set_text()` + `label.set_xy()` is roughly equivalent.

### Pattern: Reset Live Drawings on Period Change

```pine
if isNewPeriod
    box.delete(lvBody),     lvBody    := na
    line.delete(lvWickUp),  lvWickUp  := na
    label.delete(lvLabel),  lvLabel   := na
```

### Pattern: Array-Based Cleanup with While Loops

```pine
// CORRECT — safe drain
while array.size(boxes) > maxCount
    box.delete(array.shift(boxes))

// WRONG — index shifts cause out-of-bounds
for i = 0 to array.size(boxes) - 1
    box.delete(array.get(boxes, i))  // WILL CRASH
```

### Pattern: barstate.islast for Retained/Dynamic Drawings

Drawings that span from history to current bar (retained levels, etc.) should be redrawn on `barstate.islast`:

```pine
if barstate.islast
    // Clear and redraw retained level lines
    while array.size(retainLines) > 0
        line.delete(array.shift(retainLines))
    // Redraw fresh...
```

---

## 7. HTF Data & Candle Tracking

### NEVER rely on `request.security()` for live candle OHLC

`request.security()` with `[1]` offset is unreliable for the bar where a new HTF period starts. Instead, track OHLC bar-by-bar:

```pine
var float liveO = na, var float liveH = na
var float liveL = na, var float liveC = na

if isNewHTF
    // SAVE completed candle BEFORE resetting
    completedO := liveO
    completedH := liveH
    completedL := liveL  
    completedC := liveC
    // THEN reset for new period
    liveO := open
    liveH := high
    liveL := low
    liveC := close
else
    liveH := math.max(nz(liveH, high), high)
    liveL := math.min(nz(liveL, low), low)
    liveC := close
```

**Critical**: Save BEFORE reset. The order matters.

### HTF Period Detection

```pine
isNewHTF = ta.change(time(i_htfTF)) != 0
```

### Custom Daily Open (ICT Methodology)

```pine
if i_customDailyOpen and i_htfTF == "1D"
    if i_customDailyTime == "Midnight"
        isNewHTF := dayofweek(time, "America/New_York") != dayofweek(time[1], "America/New_York")
    else if i_customDailyTime == "8:30"
        isNewHTF := not na(time(timeframe.period, "0830-0831:123456", "America/New_York")) and 
          na(time(timeframe.period, "0830-0831:123456", "America/New_York")[1])
    else if i_customDailyTime == "9:30"
        isNewHTF := not na(time(timeframe.period, "0930-0931:123456", "America/New_York")) and 
          na(time(timeframe.period, "0930-0931:123456", "America/New_York")[1])
```

### Use `request.security()` only for confirmed historical data

```pine
[htfO, htfH, htfL, htfC] = request.security(syminfo.tickerid, i_htfTF, 
  [open, high, low, close], lookahead=barmerge.lookahead_off)
```

---

## 8. Time & Session Handling

### Always use explicit timezone

```pine
// GOOD
hour(time, "America/New_York")
str.format_time(timestamp, "H:mm", syminfo.timezone)

// BAD — uses exchange timezone implicitly, can surprise
hour(time)
```

### Use `str.format_time()` for time labels

```pine
f_formatTime(int t) =>
    str.format_time(t, "H:mm", syminfo.timezone)
```

### Remaining Time Calculation

```pine
f_remainingTime(string htf) =>
    int tClose    = time_close(htf)
    int remaining = math.max(0, tClose - timenow)
    int totalSec  = math.floor(remaining / 1000)
    int hrs = math.floor(totalSec / 3600)
    int mins = math.floor((totalSec % 3600) / 60)
    int secs = totalSec % 60
    // Format...
```

Note: `timenow` only works in realtime. Show "n/a" on replay:
```pine
string timeRem = barstate.isrealtime ? f_remainingTime(i_htfTF) : "n/a"
```

### Session Detection Pattern

```pine
inSession = not na(time(timeframe.period, "0930-1600:23456", "America/New_York"))
```

---

## 9. Helper Function Patterns

### Size/Style Converters

```pine
f_lineStyle(string s) =>
    switch s
        "Solid"  => line.style_solid
        "Dashed" => line.style_dashed
        => line.style_dotted

f_labelSize(string s) =>
    switch s
        "tiny"   => size.tiny
        "small"  => size.small
        "normal" => size.normal
        => size.large

f_tablePos(string s) =>
    switch s
        "Top Left"     => position.top_left
        "Top Right"    => position.top_right
        "Bottom Left"  => position.bottom_left
        "Bottom Right" => position.bottom_right
        "Middle Left"  => position.middle_left
        => position.middle_right
```

### Color Selection Function

```pine
f_colors(float _o, float _c) =>
    bool _isDoji = _c == _o
    bool _isBull = _c > _o
    _body   = _isDoji ? i_dojiBody : _isBull ? i_bullBody : i_bearBody
    _border = _isDoji ? i_dojiBorder : _isBull ? i_bullBorder : i_bearBorder
    _wick   = _isDoji ? i_dojiWick : _isBull ? i_bullWick : i_bearWick
    [_body, _border, _wick, _isBull, _isDoji]
```

---

## 10. Performance Optimization

### Do NOT use `var` for constants
```pine
// GOOD — optimized by runtime
int MS_IN_DAY = 86400000

// BAD — var incurs maintenance overhead on every bar
var int MS_IN_DAY = 86400000
```

### Minimize `request.security()` calls
Each call adds overhead. Bundle multiple values in a single call using tuples:
```pine
// GOOD — one call
[htfO, htfH, htfL, htfC] = request.security(sym, tf, [open, high, low, close])

// BAD — four calls
htfO = request.security(sym, tf, open)
htfH = request.security(sym, tf, high)
htfL = request.security(sym, tf, low)
htfC = request.security(sym, tf, close)
```

### Use update-in-place over delete/create
See Section 6 above. This reduces drawing object allocation and GC pressure.

### Gate expensive operations with `barstate.islast`
```pine
if barstate.islast
    // Table rendering, retained level redraw, etc.
```

### Avoid string concatenation in hot loops
Pre-build strings where possible. `str.tostring()` is fine but don't call it unnecessarily.

---

## 11. ICT-Specific Patterns

> **Domain knowledge reference**: See `ICT_CONCEPTS_SKILL.md` for definitions of all ICT concepts
> (IPDA, CISD, SMT, BPR, CE/MT, killzones, opening ranges, TGIF, etc.) and their
> algorithmic detection rules in pseudocode (Section 14). This section covers Pine Script
> implementation patterns for the most common ICT features.

### FVG Detection — Complete Patterns

FVGs are 3-candle formations where the wicks of candle 1 and candle 3 don't overlap, leaving a gap (the "void") at candle 2. There are multiple ways to detect and render them depending on context.

#### Pattern A: Same-Timeframe FVG (Chart TF)

The simplest form — detect on the chart's own timeframe using bar history:

```pine
// Bullish FVG: candle 3's low > candle 1's high (gap up)
bool bullFVG = low > high[2] and close > high[2]
float fvgTop = low        // candle 3 low = top of gap
float fvgBot = high[2]    // candle 1 high = bottom of gap

// Bearish FVG: candle 3's high < candle 1's low (gap down)
bool bearFVG = high < low[2] and close < low[2]
float fvgTop = low[2]     // candle 1 low = top of gap
float fvgBot = high       // candle 3 high = bottom of gap

// The close confirmation (close > high[2] for bull) ensures displacement
// Without it, you get more FVGs but lower quality
```

#### Pattern B: FVG Between Pre-Built HTF Candles (Overlay)

When you have an array of HTF candle objects (from bar-by-bar tracking):

```pine
// Requires 3 consecutive candles from the array
if array.size(candles) >= 3
    for i = 0 to array.size(candles) - 3
        HTFCandle c1 = array.get(candles, i)
        HTFCandle c3 = array.get(candles, i + 2)
        // Bearish FVG
        if c1.l > c3.h
            box.new(c1.startIdx + candleWidth, c1.l, c3.startIdx, c3.h, bgcolor=fvgColor)
        // Bullish FVG
        if c1.h < c3.l
            box.new(c1.startIdx + candleWidth, c3.l, c3.startIdx, c1.h, bgcolor=fvgColor)
```

#### Pattern C: Multi-Timeframe FVG Detection (LTF FVG on any chart)

Detect FVGs on a specific lower timeframe using `request.security`, render on the current chart regardless of chart TF. This is the most versatile pattern — used by the "Every Hour 1st FVG" indicator:

```pine
// Bundle all needed data in a single security call
getFVGData() =>
    [time, close, high, low, open, high[1], low[1], close[1], open[1], high[2], low[2], close[2], open[2]]

[mtfTime, mtfClose, mtfHigh, mtfLow, mtfOpen, 
 mtfHigh1, mtfLow1, mtfClose1, mtfOpen1, 
 mtfHigh2, mtfLow2, mtfClose2, mtfOpen2] = 
    request.security(syminfo.tickerid, ltfResolution, getFVGData(), 
      lookahead=barmerge.lookahead_on)

// Bullish FVG: current candle's low > 2-bars-ago candle's high
bool bullFVG = mtfLow > mtfHigh2 and mtfClose > mtfHigh2

// Bearish FVG: current candle's high < 2-bars-ago candle's low
bool bearFVG = mtfHigh < mtfLow2 and mtfClose < mtfLow2

if bullFVG
    fvgTop := mtfLow      // The gap's upper bound = candle 3's low
    fvgBot := mtfHigh2     // The gap's lower bound = candle 1's high

if bearFVG
    fvgTop := mtfLow2     // The gap's upper bound = candle 1's low
    fvgBot := mtfHigh      // The gap's lower bound = candle 3's high
```

**Key design notes for MTF FVG:**
- Use `xloc.bar_time` for boxes so they render correctly regardless of chart TF
- Bundle all 3 candles' OHLC in a single `request.security()` call via tuple
- The close confirmation (`mtfClose > mtfHigh2`) filters for displacement-quality FVGs
- Track "first FVG per hour" with a `var bool` flag that resets on hour change
- Right edge of FVG box = hour end time (`hourStart + 3600000`) or next session boundary

#### Pattern D: Inverted FVG (IFVG)

An IFVG is a **previously invalidated FVG** that now acts as S/R from the opposite side.
When price breaks through a bearish FVG (closes above it), the zone flips to bullish support (Bullish IFVG).
When price breaks through a bullish FVG (closes below it), the zone flips to bearish resistance (Bearish IFVG).

Detection: track all FVGs → when price closes through one, convert it to an IFVG with flipped direction.
See `ICT_CONCEPTS_SKILL.md` Section 6.4 for full rules.

**Note**: Some implementations also detect "Implied FVG" where candle bodies don't overlap but wicks do — this is a separate, lower-probability pattern:

```pine
// Implied FVG: bodies don't overlap but wicks do
float c1BodyTop = math.max(open[2], close[2])
float c3BodyBot = math.min(open, close)

if c3BodyBot > c1BodyTop  // Bullish implied FVG
    float ifvgTop = c3BodyBot
    float ifvgBot = c1BodyTop
```

### Volume Imbalance (Body Gap)
```pine
float c1Top = math.max(c1.o, c1.c)
float c1Bot = math.min(c1.o, c1.c)
float c2Top = math.max(c2.o, c2.c)
float c2Bot = math.min(c2.o, c2.c)

if c1Bot > c2Top  // Bearish VI
    box.new(...)
if c1Top < c2Bot  // Bullish VI
    box.new(...)
```

### OTE Zone (62-79% Retracement)
```pine
float range_ = candle.h - candle.l
if candle.isBull
    oteTop := candle.h - range_ * 0.62  // Discount
    oteBot := candle.h - range_ * 0.79
else
    oteBot := candle.l + range_ * 0.62  // Premium
    oteTop := candle.l + range_ * 0.79
```

### Previous H/L Takeout Detection
```pine
if currentH > prevCandle.h
    label.new(bar, currentH, "▲", textcolor=takeoutColor)
if currentL < prevCandle.l
    label.new(bar, currentL, "▼", textcolor=takeoutColor)
```

### Order Block Detection (Swing-Based)
```pine
// Bearish OB: last bullish candle before a bearish swing high
// Bullish OB: last bearish candle before a bullish swing low
// Requires swing detection (N-bar pivot) + lookback for the opposing candle

int swingLen = 5
bool swingHigh = ta.pivothigh(high, swingLen, swingLen)
bool swingLow  = ta.pivotlow(low, swingLen, swingLen)

if swingHigh
    // Walk back from the swing high to find last bullish candle
    for i = swingLen to swingLen + 10
        if close[i] > open[i]  // bullish candle = bearish OB
            obTop := high[i]
            obBot := low[i]
            break

if swingLow
    // Walk back from the swing low to find last bearish candle
    for i = swingLen to swingLen + 10
        if close[i] < open[i]  // bearish candle = bullish OB
            obTop := high[i]
            obBot := low[i]
            break
```

### BPR Detection (Balanced Price Range)
```pine
// Track recent bullish and bearish FVGs
// BPR = vertical overlap between opposing FVGs
var float lastBullTop = na, var float lastBullBot = na
var float lastBearTop = na, var float lastBearBot = na

if bullFVG
    lastBullTop := fvgTop
    lastBullBot := fvgBot
    // Check overlap with most recent bearish FVG
    float overlapTop = math.min(lastBullTop, lastBearTop)
    float overlapBot = math.max(lastBullBot, lastBearBot)
    if overlapTop > overlapBot and not na(lastBearTop)
        // BPR exists — draw at [overlapBot, overlapTop]
        box.new(bar_index[2], overlapTop, bar_index, overlapBot, bgcolor=bprColor)

// Mirror logic for bearFVG checking against lastBullTop/Bot
// Delay confirmation by 1 bar to allow invalidation
```

### CE / MT Midpoint Line
```pine
// CE for any FVG/IFVG/NWOG zone:
float ce = (zoneTop + zoneBot) / 2
line.new(x1, ce, x2, ce, style=line.style_dotted, color=ceColor)

// MT for any OB/BB zone:
float mt = (obTop + obBot) / 2
line.new(x1, mt, x2, mt, style=line.style_dotted, color=mtColor)

// CE/MT are the 50% equilibrium — highest probability reaction level within the zone
```

---

## 12. Table Pattern

```pine
var table infoTable = na

if i_showTable and barstate.islast
    if not na(infoTable)
        table.delete(infoTable)
    
    infoTable := table.new(f_tablePos(i_tablePos), columns, rows, 
      border_color=borderCol, border_width=1, bgcolor=bgCol)
    
    tSz = f_labelSize(i_tableSize)
    table.cell(infoTable, 0, 0, "Label", text_color=textCol, text_size=tSz)
    table.cell(infoTable, 1, 0, value,   text_color=valCol,  text_size=tSz)
```

---

## 13. Alert Conditions

Place at the very end. Use descriptive titles and messages with `{{interval}}` placeholder:

```pine
alertcondition(condition, "HTF Candle Closed Bullish", "HTF {{interval}} candle closed bullish")
alertcondition(takeoutH, "Previous HTF High Taken Out", "Price took out previous HTF high")
```

---

## 14. Common Pine v6 Gotchas

| Issue | Solution |
|---|---|
| `label.style` is not a type | Don't declare `label.style x = ...`. Use the value directly. |
| Array out of bounds in for loop | Use `while array.size() > 0` + `array.shift()` to drain arrays |
| `request.security` live bar data stale | Track OHLC bar-by-bar with `var` variables instead |
| `var` on constants = slower | Don't use `var` for values that never change |
| Integer division truncation (v5) | v6 supports fractional division natively |
| `timenow` returns na on replay | Guard with `barstate.isrealtime` |
| Drawing limits exceeded | Use array-based cleanup with `while` loops |
| Strings can't use `+=` in older Pine | v6 supports `+=` for string concatenation |
| `time()` returns na outside session | Check `not na(time(...))` for session detection |
| Line/label stacking on realtime | Use update-in-place pattern, not create-every-tick |

---

## 15. Documentation Standards

### Header Block
```pine
// This Pine Script® code is subject to the terms of the Mozilla Public License 2.0
// © Author
// Indicator Name vX.Y
// Brief description of what the indicator does.
```

### Strategy Documentation Block
For strategies, include a comprehensive documentation section explaining:
- **PURPOSE**: What the strategy discovers/trades
- **METHODOLOGY**: Step-by-step logic
- **ENTRY RULES**: Specific conditions
- **EXIT RULES**: TP/SL/timed exit logic
- **DATA COLLECTED**: What metrics are tracked

### Section Headers
Use clear visual separators:
```pine
// ══════════════════════════════════════════════
// ══ SECTION NAME
// ══════════════════════════════════════════════
```

Or for sub-sections:
```pine
// ── Sub-section Name ──
```

---

## 16. Visual Style Preferences

- **Table defaults**: Size = normal, Position = configurable (9 positions)
- **Colors**: Must work on both dark and light chart backgrounds
- **Historical drawings**: NEVER delete old boxes/lines — preserve for scroll history
- **Boxes**: Use transparent fills with visible borders for zones
- **Labels**: Use `label.style_none` for clean floating text
- **Lines**: Provide style options (Solid/Dashed/Dotted) via input
- **Candle colors**: Always provide separate Bull/Bear/Doji color groups with fill + border + wick

---

## 17. File Naming Convention

```
indicator_name_v{major}.pine          # e.g., htf_candle_overlay_v3.pine
indicator_name_v{major}_{minor}.pine  # e.g., fp_zone_v6_2.pine
```

---

## 18. Checklist Before Delivery

- [ ] `//@version=6` is present
- [ ] All inputs have `group=` parameter
- [ ] Table size and position are configurable with sensible defaults
- [ ] Colors work on light backgrounds (no white-on-white)
- [ ] Historical drawings are preserved (not deleted on new periods)
- [ ] Live drawings use update-in-place where possible
- [ ] No `request.security()` for live candle data — use bar-by-bar tracking
- [ ] Array cleanup uses `while` loops, not `for` loops with deletion
- [ ] Alert conditions are at the bottom of the script
- [ ] Section headers are clear and consistent
- [ ] UDTs are used for entities with 3+ fields
- [ ] Helper functions have `f_` prefix and no global dependencies where possible
- [ ] Tooltips on non-obvious inputs
- [ ] `barstate.isrealtime` guard on `timenow` usage

---

## 19. LuxAlgo-Inspired Design Patterns

LuxAlgo indicators (ICT Concepts, Pure Price Action Tools, Smart Money Concepts, Midnight Open Retracement, HTF Candle Projections) are considered best-in-class for visual design on TradingView. These patterns are extracted from their open-source indicators.

### Present vs Historical Mode

LuxAlgo uses a "Mode" toggle between `Present` (latest 500 bars only) and `Historical` (full chart). This reduces clutter and drawing count:

```pine
i_mode = input.string("Present", "Mode", options=["Present", "Historical"], group="Settings")

// In Present mode, only show last N structures
if i_mode == "Present"
    while array.size(structures) > maxVisible
        deleteStructure(array.shift(structures))
```

### "Show Last N" Pattern for Zone Visibility

Instead of showing all detected zones, cap visible count per type:

```pine
i_showLastBullOB = input.int(5, "Show Last Bullish OB", minval=1, maxval=50, group="Order Blocks")
i_showLastBearOB = input.int(5, "Show Last Bearish OB", minval=1, maxval=50, group="Order Blocks")
```

This is better than a single "max zones" input — it gives independent control per direction.

### Zone Mitigation Tracking

LuxAlgo tracks whether a zone (OB, FVG, etc.) has been "mitigated" (price returned to it). Mitigated zones change color:

```pine
type Zone
    float   top
    float   bottom
    int     startBar
    int     endBar
    bool    isBull
    bool    mitigated
    box     visual

// On each bar, check if price has entered any active zone
if not zone.mitigated
    if zone.isBull and low <= zone.top and low >= zone.bottom
        zone.mitigated := true
        box.set_bgcolor(zone.visual, mitigatedColor)
    if not zone.isBull and high >= zone.bottom and high <= zone.top
        zone.mitigated := true
        box.set_bgcolor(zone.visual, mitigatedColor)
```

### Dynamic Box Extension

LuxAlgo extends zone boxes to the right until they're mitigated or a new one replaces them:

```pine
// Extend unmitigated zones to current bar
if not zone.mitigated
    box.set_right(zone.visual, bar_index + 5)
```

### Gradient Fills for Zones

Use `color.from_gradient()` for heat-map style zone visualization:

```pine
// Gradient based on zone strength (e.g., number of times tested)
zoneStrength = math.min(zone.touchCount / maxTouches, 1.0)
zoneColor = color.from_gradient(zoneStrength, 0, 1, weakColor, strongColor)
box.set_bgcolor(zone.visual, zoneColor)
```

### Multi-Line Structure Labels (MSS/BOS)

LuxAlgo draws structure labels with a connecting line from the broken swing point to the break candle:

```pine
// Draw line from swing point to break point
line.new(swingBar, swingPrice, breakBar, swingPrice, 
  color=mssColor, style=line.style_dashed, width=1)

// Label at midpoint
int midBar = math.round((swingBar + breakBar) / 2)
label.new(midBar, swingPrice, isBull ? "MSS" : "MSS", 
  style=isBull ? label.style_label_up : label.style_label_down,
  color=color.new(mssColor, 80), textcolor=mssColor, size=size.tiny)
```

### Liquidity Level Visualization

Equal highs/lows as liquidity levels with margin tolerance (ATR-based):

```pine
// Two swing highs are "equal" if within ATR margin
float margin = ta.atr(10) / (10.0 / marginInput)
bool equalHighs = math.abs(swingH1 - swingH2) < margin

if equalHighs
    // Draw box spanning both highs
    box.new(bar1, math.max(swingH1, swingH2), bar2, math.min(swingH1, swingH2),
      border_color=liqColor, bgcolor=color.new(liqColor, 90))
```

### Displacement Detection

Successive same-direction candles with large bodies and short wicks:

```pine
f_isDisplacement(int lookback) =>
    bool allSameDir = true
    bool allLargeBody = true
    for i = 0 to lookback - 1
        bool isBull = close[i] > open[i]
        bool prevBull = close[i+1] > open[i+1]
        if isBull != prevBull
            allSameDir := false
        float bodyRatio = math.abs(close[i] - open[i]) / (high[i] - low[i])
        if bodyRatio < 0.6
            allLargeBody := false
    allSameDir and allLargeBody
```

### Killzone Session Boxes

Time-based colored boxes for specific trading sessions:

```pine
type Killzone
    string name
    string session     // "0700-0900:23456"
    color  col

// Array of killzones
var array<Killzone> killzones = array.from(
    Killzone.new("NY KZ",     "0700-0900:23456", color.new(#ff9800, 85)),
    Killzone.new("London",    "0200-0500:23456", color.new(#2196f3, 85)),
    Killzone.new("Lon Close", "1000-1200:23456", color.new(#9c27b0, 85)),
    Killzone.new("Asia",      "2000-0000:23456", color.new(#4caf50, 85))
)
```

### NWOG/NDOG (New Week/Day Opening Gap)

```pine
// Track opening gap between previous session close and new session open
var float prevWeekClose = na
var float newWeekOpen = na

if isNewWeek
    prevWeekClose := close[1]
    newWeekOpen   := open
    if not na(prevWeekClose)
        // Draw gap box
        box.new(bar_index, math.max(prevWeekClose, newWeekOpen), 
          bar_index + gapExtension, math.min(prevWeekClose, newWeekOpen),
          bgcolor=nwogColor, border_color=color.new(nwogColor, 50))
```

### Fibonacci Auto-Connect Between Features

LuxAlgo draws fib levels between the two most recent features of the same type:

```pine
// Connect two most recent OBs with fib levels
if array.size(bullOBs) >= 2
    Zone ob1 = array.get(bullOBs, array.size(bullOBs) - 1)
    Zone ob2 = array.get(bullOBs, array.size(bullOBs) - 2)
    float range_ = ob1.top - ob2.bottom
    float[] fibLevels = array.from(0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
    for i = 0 to array.size(fibLevels) - 1
        float level = ob2.bottom + range_ * array.get(fibLevels, i)
        line.new(ob2.startBar, level, ob1.endBar, level, 
          color=fibColor, style=line.style_dotted, width=1)
```

### Dashboard with Probability Stats (Midnight Open Retracement style)

LuxAlgo's Midnight Open indicator shows retracement probability — design pattern for stat dashboards:

```pine
// Track historical hit rate
var int totalDays = 0
var int retraceDays = 0

if isNewDay
    totalDays += 1
    if priceRetracedToMidnight
        retraceDays += 1

float hitRate = totalDays > 0 ? (retraceDays / totalDays) * 100 : 0

// Display in table
table.cell(dash, 0, 1, "Retracement %", text_color=textCol, text_size=tSz)
table.cell(dash, 1, 1, str.tostring(hitRate, "#.0") + "%", 
  text_color=hitRate > 60 ? bullCol : bearCol, text_size=tSz)
```

### Input Group Naming Convention (LuxAlgo Style)

LuxAlgo uses consistent emoji-prefixed descriptive names in their docs, and clean grouped inputs:

```pine
// Feature toggle + color on same inline
i_showOB    = input.bool(true,  "Order Blocks", inline="ob", group="Order Blocks")
i_obBullCol = input.color(#2157f3, "", inline="ob", group="Order Blocks")
i_obBearCol = input.color(#f7827c, "", inline="ob", group="Order Blocks")

// "Show Last N" on same line
i_obShowLast = input.int(5, "Show Last", inline="ob2", group="Order Blocks")
```

### chart.bg_color for Theme Awareness

```pine
// Detect if chart background is dark or light
bool isDarkTheme = color.r(chart.bg_color) < 128

// Auto-select text colors
color autoTextCol = isDarkTheme ? color.white : color.black
color autoLabelBg = isDarkTheme ? color.new(#1e222d, 10) : color.new(#f0f0f0, 10)
```

---

## 20. Advanced Visual Techniques

### Stacked Transparency for Depth

Layer multiple boxes with decreasing transparency to create a "glow" effect:

```pine
for i = 0 to 3
    float expand = i * atrVal * 0.1
    int transp = 85 + i * 4  // 85, 89, 93, 97
    box.new(left, top + expand, right, bottom - expand,
      bgcolor=color.new(baseColor, transp), border_color=color.new(baseColor, 100))
```

### Candle Body vs Full Range Zones

LuxAlgo lets users choose between candle body and full range for OB zones:

```pine
i_useBody = input.bool(false, "Use Candle Body", group="Order Blocks")

float zoneTop = i_useBody ? math.max(open, close) : high
float zoneBot = i_useBody ? math.min(open, close) : low
```

### Line Style Shorthand Input (LuxAlgo Pattern)

```pine
i_obStyle = input.string("⎯⎯⎯", "Line Style", 
  options=["⎯⎯⎯", "----", "····"], group="Style")

f_styleFromStr(string s) =>
    switch s
        "----" => line.style_dashed
        "····" => line.style_dotted
        => line.style_solid
```

### Polyline for Complex Shapes (Pine v6)

v6 supports `polyline.new()` for irregular shapes like wedges, channels, and patterns:

```pine
var array<chart.point> pts = array.new<chart.point>()
array.push(pts, chart.point.from_index(bar_index - 10, high[10]))
array.push(pts, chart.point.from_index(bar_index, high))
array.push(pts, chart.point.from_index(bar_index, low))
array.push(pts, chart.point.from_index(bar_index - 10, low[10]))
polyline.new(pts, closed=true, fill_color=color.new(color.blue, 90))
```

---

# PART II: NinjaScript (NinjaTrader 8) Development

---

## 21. NinjaScript Structure (Mandatory Order)

```csharp
// <using_statements>
// <namespace>
//   <class_declaration>  (extends Indicator or Strategy)
//     <private_variables>
//     <OnStateChange>     (lifecycle — SetDefaults, Configure, DataLoaded, Terminated)
//     <OnBarUpdate>       (core logic — runs every bar/tick)
//     <helper_methods>
//     <properties>        (#region Properties — user-facing parameters)
//   </class>
// </namespace>
```

---

## 22. NinjaScript Indicator Template

```csharp
#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class MyIndicator : Indicator
    {
        // ── Private Variables ──
        private double myValue;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description         = "My custom indicator";
                Name                = "MyIndicator";
                IsOverlay           = true;
                IsSuspendedWhileInactive = true;
                Calculate           = Calculate.OnBarClose;
                // Default property values
                Period              = 14;
                // Plots
                AddPlot(Brushes.DodgerBlue, "MainPlot");
            }
            else if (State == State.Configure)
            {
                // Add secondary data series, configure here
            }
            else if (State == State.DataLoaded)
            {
                // Initialize Series<T> objects here
            }
        }

        protected override void OnBarUpdate()
        {
            // CRITICAL: Always guard against insufficient bars
            if (CurrentBar < Period) return;

            // Core logic here
            Value[0] = Close[0]; // Example
        }

        #region Properties
        [Range(1, int.MaxValue), NinjaScriptProperty]
        [Display(Name = "Period", GroupName = "Parameters", Order = 0)]
        public int Period { get; set; }
        #endregion
    }
}
```

---

## 23. NinjaScript Key Patterns

### Lifecycle States

| State | Use For |
|---|---|
| `SetDefaults` | Name, description, default property values, AddPlot() |
| `Configure` | AddDataSeries(), secondary bars configuration |
| `DataLoaded` | Initialize Series<double>, custom objects that need bar data |
| `Historical` | Processing historical data (runs before real-time) |
| `Realtime` | Switched to real-time processing |
| `Terminated` | Cleanup resources, dispose objects |

### Bar History Guard (Critical)

```csharp
// ALWAYS check CurrentBar before accessing historical data
protected override void OnBarUpdate()
{
    if (CurrentBar < requiredBars) return;
    
    // Safe to access Close[requiredBars] now
    double value = Close[requiredBars];
}
```

### Drawing Objects

```csharp
// Rectangle (like Pine's box.new)
Draw.Rectangle(this, "zone_" + CurrentBar, false, 
    startBar, topPrice, endBar, bottomPrice, 
    Brushes.Transparent, Brushes.DodgerBlue, 20);

// Line (like Pine's line.new)
Draw.Line(this, "line_" + CurrentBar, false, 
    startBar, startPrice, endBar, endPrice, 
    Brushes.Gray, DashStyleHelper.Dash, 1);

// Text (like Pine's label.new)
Draw.Text(this, "label_" + CurrentBar, "MSS", 
    barsAgo, price, Brushes.White);
```

### Session Detection

```csharp
// First bar of session (like Pine's ta.change(time("D")))
if (Bars.IsFirstBarOfSession)
{
    sessionOpen = Open[0];
    sessionHigh = High[0];
    sessionLow = Low[0];
}

// Time-based session (like Pine's time() session filter)
bool isNYSession = ToTime(Time[0]) >= 93000 && ToTime(Time[0]) <= 160000;
```

### Property Attributes

```csharp
// User-visible parameter with validation
[Range(1, 200), NinjaScriptProperty]
[Display(Name = "Lookback Period", GroupName = "Parameters", Order = 0)]
public int Period { get; set; }

// Color property
[XmlIgnore]
[Display(Name = "Bull Color", GroupName = "Visual", Order = 10)]
public Brush BullBrush { get; set; }

[Browsable(false)]
public string BullBrushSerialize
{
    get { return Serialize.BrushToString(BullBrush); }
    set { BullBrush = Serialize.StringToBrush(value); }
}

// Boolean toggle
[NinjaScriptProperty]
[Display(Name = "Show Zones", GroupName = "Visual", Order = 11)]
public bool ShowZones { get; set; }
```

### Multi-Timeframe Data

```csharp
// In OnStateChange → Configure
AddDataSeries(BarsPeriodType.Minute, 60); // Add 60-minute series

// In OnBarUpdate
if (BarsInProgress == 0) // Primary series
{
    // LTF logic
}
else if (BarsInProgress == 1) // 60-min series
{
    // HTF logic
    htfClose = Closes[1][0];
}
```

### Order Management (Strategies)

```csharp
// Entry
EnterLong(1, "LongEntry");
EnterShort(1, "ShortEntry");

// Stop Loss & Take Profit
SetStopLoss("LongEntry", CalculationMode.Ticks, stopTicks, false);
SetProfitTarget("LongEntry", CalculationMode.Ticks, targetTicks);

// Trailing stop
SetTrailStop("LongEntry", CalculationMode.Ticks, trailTicks, false);

// CRITICAL: Set stops BEFORE entry, not after
// Stops set after entry may not apply until the next bar
```

### Common NinjaScript Gotchas

| Issue | Solution |
|---|---|
| `IndexOutOfRangeException` | Check `if (CurrentBar < N) return;` before `Close[N]` |
| `NullReferenceException` on Series | Initialize in `State.DataLoaded`, not `SetDefaults` |
| Stops not triggering on entry bar | Set `SetStopLoss()` before `EnterLong()` |
| Drawing objects piling up | Use unique tag names or `RemoveDrawObject()` |
| Strategy fills at wrong price | Check `Calculate = Calculate.OnBarClose` vs `OnEachTick` |
| Multi-series bar sync | Always check `BarsInProgress` in `OnBarUpdate()` |

---

# PART III: Tradovate (JavaScript) Development

---

## 24. Tradovate Indicator Structure

```javascript
const predef = require("./tools/predef");
const SMA = require("./tools/SMA");
const EMA = require("./tools/EMA");

class MyIndicator {
    init() {
        // Initialize state, helper functions, series
        this.sma = SMA(this.props.period);
        this.prevClose = null;
    }

    map(d, i, history) {
        // Core logic — called for every bar
        // d = current bar data, i = bar index, history = all bars

        const close = d.close();
        const open = d.open();
        const high = d.high();
        const low = d.low();
        const volume = d.volume();

        // Access previous bars
        const prior = history.prior();
        if (prior) {
            const prevClose = prior.close();
        }

        // Return plot values
        return {
            value: this.sma(close),
            color: close > open ? "green" : "red"
        };
    }

    filter(d, i) {
        // Optional: filter which bars to process
        return i > this.props.period;
    }
}

module.exports = {
    name: "MyIndicator",
    description: "My custom indicator",
    calculator: MyIndicator,
    params: {
        period: predef.paramSpecs.period(14)
    },
    tags: ["Custom"],
    plots: {
        value: { title: "Value" }
    },
    schemaVersion: 2
};
```

---

## 25. Tradovate Key Patterns

### Session Detection

```javascript
map(d, i, history) {
    const tradeDate = d.tradeDate();
    
    if (this.lastDate !== tradeDate) {
        // New session detected
        this.sessionOpen = d.open();
        this.sessionHigh = d.high();
        this.sessionLow = d.low();
        this.lastDate = tradeDate;
    }
    
    // Update session H/L
    this.sessionHigh = Math.max(this.sessionHigh, d.high());
    this.sessionLow = Math.min(this.sessionLow, d.low());
}
```

### History Access

```javascript
// Access N bars back
const prior = history.prior();           // 1 bar back
const twoBarsAgo = history.back(2);      // 2 bars back

// CRITICAL: Always null-check history access
if (prior && prior.close) {
    const prevClose = prior.close();
}
```

### Helper Function Initialization

```javascript
init() {
    this.sma = SMA(this.props.period);
    this.ema = EMA(this.props.fastPeriod);
    this.atr = require("./tools/ATR")(this.props.atrPeriod);
}
```

### Module Exports with Parameters

```javascript
module.exports = {
    name: "ICT_SessionVWAP",
    description: "Session VWAP with SD bands",
    calculator: ICTSessionVWAP,
    params: {
        period:    predef.paramSpecs.period(20),
        sdMult:    predef.paramSpecs.number(2.0, 0.1, 0.5, 5.0),
        showBands: predef.paramSpecs.bool(true),
        session:   predef.paramSpecs.enum("NY", ["NY", "London", "Asia", "All"])
    },
    tags: ["ICT", "VWAP", "Session"],
    plots: {
        vwap:      { title: "VWAP" },
        upperBand: { title: "Upper Band" },
        lowerBand: { title: "Lower Band" }
    },
    schemaVersion: 2
};
```

### Common Tradovate Gotchas

| Issue | Solution |
|---|---|
| `undefined is not a function` | Null-check `history.prior()` before accessing methods |
| Indicator not loading | Verify `module.exports` has all required fields |
| Wrong bar data on first bars | Use `filter()` to skip insufficient history |
| NaN in calculations | Guard division by zero, check for null/undefined |
| Session boundaries wrong | Use `d.tradeDate()` not clock time for session changes |

---

# PART IV: Cross-Platform Conversion

---

## 26. Concept Mapping Table

| Concept | Pine Script v6 | NinjaScript (C#) | Tradovate (JS) |
|---|---|---|---|
| **Close price** | `close` | `Close[0]` | `d.close()` |
| **Previous close** | `close[1]` | `Close[1]` | `history.prior().close()` |
| **Open/High/Low** | `open`, `high`, `low` | `Open[0]`, `High[0]`, `Low[0]` | `d.open()`, `d.high()`, `d.low()` |
| **Volume** | `volume` | `Volume[0]` | `d.volume()` |
| **Bar index** | `bar_index` | `CurrentBar` | `i` (map parameter) |
| **SMA** | `ta.sma(src, len)` | `SMA(src, len)[0]` | `SMA(len)(value)` |
| **EMA** | `ta.ema(src, len)` | `EMA(src, len)[0]` | `EMA(len)(value)` |
| **ATR** | `ta.atr(len)` | `ATR(len)[0]` | `ATR(len)(d)` |
| **RSI** | `ta.rsi(src, len)` | `RSI(src, len)[0]` | Custom implementation |
| **Crossover** | `ta.crossover(a, b)` | `CrossAbove(a, b, 1)` | `prev < thresh && curr >= thresh` |
| **Crossunder** | `ta.crossunder(a, b)` | `CrossBelow(a, b, 1)` | `prev > thresh && curr <= thresh` |
| **New session** | `ta.change(time("D"))` | `Bars.IsFirstBarOfSession` | `d.tradeDate() !== lastDate` |
| **Time of day** | `hour(time, tz)` | `ToTime(Time[0])` (HHMMSS int) | `d.timestamp()` |
| **Persistent var** | `var float x = na` | Class-level field | `this.x` in class |
| **User input (int)** | `input.int(14, "Period")` | `[NinjaScriptProperty] int Period` | `predef.paramSpecs.period(14)` |
| **User input (bool)** | `input.bool(true, "Show")` | `[NinjaScriptProperty] bool Show` | `predef.paramSpecs.bool(true)` |
| **User input (color)** | `input.color(#ff0000, "Color")` | `Brush property + Serialize` | Not natively supported |
| **Draw box** | `box.new(l, t, r, b)` | `Draw.Rectangle(this, tag, ...)` | Not natively supported |
| **Draw line** | `line.new(x1,y1,x2,y2)` | `Draw.Line(this, tag, ...)` | Not natively supported |
| **Draw label** | `label.new(x, y, text)` | `Draw.Text(this, tag, ...)` | Not natively supported |
| **Alert** | `alertcondition(cond)` | `Alert("msg", Priority.High)` | Not natively supported |
| **Overlay on chart** | `overlay=true` | `IsOverlay = true` | Plot on price chart |
| **Max drawing objects** | `max_boxes_count=500` | No hard limit (memory-based) | N/A |
| **Calc on close** | Default behavior | `Calculate = Calculate.OnBarClose` | Default behavior |
| **Calc on each tick** | `calc_on_every_tick=true` | `Calculate = Calculate.OnEachTick` | N/A |

---

## 27. Conversion Workflow

When converting a Pine Script indicator to NinjaScript or Tradovate:

1. **Map the data model**: Pine's series-based `close[1]` becomes `Close[1]` (Ninja) or `history.prior().close()` (Tradovate)
2. **Map inputs to properties**: Pine's `input.*()` becomes `[NinjaScriptProperty]` attributes (Ninja) or `params` in module.exports (Tradovate)
3. **Map drawings**: Pine's `box.new`/`line.new`/`label.new` becomes `Draw.Rectangle`/`Draw.Line`/`Draw.Text` (Ninja). Tradovate has limited drawing support.
4. **Map session handling**: Pine's `time()` session filters become `ToTime()` comparisons (Ninja) or `d.tradeDate()` checks (Tradovate)
5. **Map state**: Pine's `var` keyword becomes class-level fields in both Ninja and Tradovate
6. **Guard bar access**: Pine handles `na` gracefully; Ninja throws `IndexOutOfRange`; Tradovate returns `undefined`. Always add explicit guards.

### NinjaScript-Specific Conversion Notes

- NinjaScript uses 0-based bar indexing from current bar (`Close[0]` = current), same as Pine
- `AddDataSeries()` replaces Pine's `request.security()` for MTF data
- Colors use `System.Windows.Media.Brushes`, not hex codes
- Strategy orders (`EnterLong`/`SetStopLoss`) must be set in correct sequence
- Drawing object tags must be unique strings — use `"tag_" + CurrentBar` pattern

### Tradovate-Specific Conversion Notes

- No native drawing API — calculations only, plots via `module.exports.plots`
- All state must live on `this` — no global variables
- `init()` = setup, `map()` = per-bar logic, `filter()` = bar filtering
- Limited built-in indicators — may need to implement custom (e.g., RSI, Stochastic)
- Use `require("./tools/predef")` for parameter specifications

---

## 28. NinjaScript Debugging Cheat Sheet

| Error | Cause | Fix |
|---|---|---|
| `Index was outside the bounds` | `Close[N]` when `CurrentBar < N` | Add `if (CurrentBar < N) return;` |
| `Object reference not set` | Series not initialized | Move `new Series<double>(this)` to `State.DataLoaded` |
| `Strategy not filling orders` | `Calculate.OnBarClose` with intra-bar logic | Switch to `OnEachTick` or adjust entry logic |
| `Indicator values all zero` | Plot not assigned | Ensure `Value[0] = result;` in `OnBarUpdate` |
| `Drawing objects disappearing` | Duplicate tag names | Use unique tags per drawing |
| `Multi-series out of sync` | Missing `BarsInProgress` check | Always check which series triggered `OnBarUpdate` |

---

## 29. File Naming Conventions (All Platforms)

```
Pine Script:    indicator_name_v{major}.pine          # htf_candle_overlay_v3.pine
NinjaScript:    IndicatorName.cs                       # HTFCandleOverlay.cs  
Tradovate:      indicator-name.js                      # htf-candle-overlay.js
```
