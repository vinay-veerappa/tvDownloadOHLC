# Pine Script v6 Development Skill

> Comprehensive Pine Script v6 coding skill for building TradingView indicators and strategies.
> Tailored for ICT-methodology trading tools, overlay indicators, and statistical dashboards.

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

### FVG Detection Between HTF Candles
```pine
// Bearish FVG: candle1.low > candle3.high (gap down, no overlap)
if c1.l > c3.h
    box.new(c1.endIdx, c1.l, c3.startIdx, c3.h, bgcolor=fvgColor)

// Bullish FVG: candle1.high < candle3.low (gap up, no overlap)
if c1.h < c3.l
    box.new(c1.endIdx, c3.l, c3.startIdx, c1.h, bgcolor=fvgColor)
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
