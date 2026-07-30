# IB Confluence Indicator — Architecture Brainstorm

> **Date**: 2026-07-30 (Session 12)
> **Status**: Design phase — brainstorming
> **Goal**: Extract IB confluence computation + visualization from `IBStrategyBase` into a standalone reusable NT8 Indicator, with a clean HUD table and chart drawing.

---

## 1. Problem Statement

The IB strategies (`IBBreakoutBot`, `IBRetestBot`, `IBFadeBot`) currently embed all confluence computation (IB range, FVG, AVWAP, EMA, depth, VCP, OPEX, calendar filters) inside `IBStrategyBase.cs` — a strategy base class. This causes:

1. **No visual verification** — the computation is invisible on the chart unless you add the strategy. You can't just "add an indicator" to see the IB confluence state for a given day.
2. **Duplicated logic** — the Python parity harness re-implements the same confluence logic. Any change requires updating both sides.
3. **Messy HUD** — the current `DrawHUD()` uses `Draw.Text` (price-anchored, moves with bars) with no alignment. It should be a fixed-position table with monospace columns.
4. **No reuse** — other strategies (ORB, London session, Asia session) can't leverage the IB confluence stack.
5. **Strategy = execution + computation** — the strategy should be thin (read confluence, execute trades). Computation + drawing should live in an indicator.

---

## 2. Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  IBConfluenceIndicator (NT8 Indicator, IsOverlay=true)              │
│                                                                     │
│  ═══ Computation (every bar in OnBarUpdate) ═══                     │
│    • IB range (configurable start/duration):                         │
│        high, low, mid, range, open, close, closePosition             │
│    • First break direction + time + break-vs-AVWAP                   │
│    • 09:30-anchored AVWAP (cumTPV / cumVol)                         │
│    • Daily EMA 20/50 (on session-window close, matching Python)      │
│    • IB-window FVG (5-min resampled 3-bar pattern)                   │
│        → biasFvg, fvgTop, fvgBottom, fvgFinalizedTime                │
│    • Retest depth (maxExcursionPastMid / range)                      │
│        → depthRatio, depthTier, depthSizeMult                        │
│    • VCP 3-day contracting                                           │
│    • OPEX week / Quarterly OPEX                                      │
│    • Calendar filters (skip Mon/Feb/May/Oct per play)                │
│    • Confluence pass/fail + fail reason string                       │
│                                                                     │
│  ═══ Drawing (on chart) ═══                                          │
│    • IB boundaries: high/low (blue dashed), mid (orange dotted)      │
│    • Quarter levels: 25%/75% (gray dotted)                          │
│    • IB box shading (light blue rectangle, 30% opacity)              │
│    • FVG box (green=bull / red=bear rectangle at gap price band)     │
│    • AVWAP line (purple, updated each bar from 09:30 anchor)         │
│    • Depth shade (green tint past mid in break direction)            │
│    • HUD table (Draw.TextFixed, TopRight, Consolas monospace)        │
│                                                                     │
│  ═══ Public Properties (read by strategies) ═══                      │
│    IBHigh, IBLow, IBMid, IBRange, IBComplete, IBOpen, IBClose        │
│    FirstBreakDir, FirstBreakTime, BreakVsAvwap                       │
│    BiasFvg, FvgTop, FvgBottom, FvgAligned                            │
│    TrendMisaligned, EMA20, EMA50                                     │
│    DepthRatio, DepthTier, DepthSizeMult                              │
│    Vcp3Day, IsOpexWeek, IsQuarterlyOpex                              │
│    CalendarSkip (bool — day skipped by calendar filter)              │
│    ConfluencePass (bool — all active filters pass)                   │
│    ConfluenceFailReason (string — which filter blocked, or "")       │
│    AvwapPrice (double — current 09:30-anchored AVWAP)                │
│                                                                     │
│  ═══ NinjaScriptProperties (user-configurable) ═══                   │
│    RangeStartHour, RangeStartMinute, RangeDurationMin                │
│    DrawVisuals (bool), DrawHUD (bool), DrawFVG (bool)                │
│    DrawAVWAP (bool), DrawIBBox (bool), DrawQuarters (bool)           │
│    Play2FvgBiasFilter, DepthWeakThreshold, DepthStrongThreshold      │
│    DepthWeakSizeMult, DepthModerateSizeMult, Play2DepthSizeOverlay   │
│    SkipMondayPlay2, SkipFebruaryPlay2, SkipMayPlay1, SkipOctoberPlay3│
│    ConfluenceFilterEnabled                                           │
│    [Color properties for each line/box — like PAX30OpeningRange]     │
└─────────────────────────────────────────────────────────────────────┘
           │
           │ Strategy adds via AddChartIndicator()
           │ and reads properties each bar
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  IBRetestBot / IBBreakoutBot / IBFadeBot (thin strategies)          │
│                                                                     │
│  SetStrategyDefaults:                                                │
│    ActivePlay = 2  (or 1 or 3)                                      │
│    TargetLvl, StopRMult, risk params                                 │
│                                                                     │
│  ConfigureStrategy:                                                  │
│    AddChartIndicator(IBConfluenceIndicator())                       │
│                                                                     │
│  CheckForEntry:                                                      │
│    var ib = IBConfluenceIndicator1;  // auto-created by AddChartInd  │
│    if (!ib.IBComplete) return 0;                                    │
│    if (!ib.ConfluencePass) return 0;                                │
│    if (ib.FirstBreakDir == 1 && retest condition)                   │
│        EnterWithRangeStop(1, ib.IBMid, ib.IBLow, target, qty)       │
│                                                                     │
│  // No computation, no drawing — all delegated to indicator          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Reusable Components Survey

### 3a. Existing code to extract (from `IBStrategyBase.cs`)

| Method | Lines | What it does | Action |
|---|---|---|---|
| `UpdateConfluenceIndicators()` | ~620-700 | AVWAP + EMA + break + depth computation | Extract to indicator `OnBarUpdate` |
| `Update5mFvgAccumulator()` + `Finalize5mBar()` | ~710-790 | 5-min FVG detection from 1-min bars | Extract directly |
| `DrawIBBoundaries()` | ~492-532 | IB high/low/mid/quarters box drawing | Extract, use `Draw.Line`/`Draw.Rectangle` |
| `DrawFVG()` | ~540-558 | FVG box drawing | Extract directly |
| `DrawHUD()` | ~566-610 | HUD text (currently messy) | **Rewrite** using `Draw.TextFixed` + monospace |
| `DepthSizeMultiplier()` | ~445-456 | Depth tier → size multiplier | Extract as public property |
| `ConfluenceFilter()` | ~820-880 | Per-play filter stack (P1/P2/P3) | Extract, expose `ConfluencePass` + `FailReason` |
| Calendar rules | ~200-210 | Skip Mon/Feb/May/Oct | Extract as `CalendarSkip` property |
| VCP/OPEX properties | ~712-740 | `Vcp3DayContracting`, `IsOpexWeek`, `IsQuarterlyOpex` | Extract directly |
| `TrackFirstBreak()` | ~430 | First break direction detection | Already in `UpdateConfluenceIndicators` — extract |

### 3b. Existing indicators as templates

| File | Class | Why it's useful |
|---|---|---|
| `docs/strategies/9_30_breakout/ninjatrader/PAX30OpeningRange.cs` | `PAX30OpeningRange : Indicator` | **Best indicator scaffold** — `[NinjaScriptProperty]` color/line/label properties, `IsOverlay=true`, multi-day level management, `Draw.Line`/`Draw.Text` patterns. Use as structural template. |
| `docs/strategies/9_30_breakout/ninjatrader/ORB_V7_Indicator.cs` | `ORB_V7_Indicator : Indicator` | `IsOverlay`/`DrawOnPricePanel` setup, triangle markers for signals |
| `docs/strategies/9_30_breakout/0930_AllDay/.../ORB_AllDay_MultiTP.cs` | `DrawDashboard()` (L1133-1190) | **Best HUD template** — `Draw.TextFixed` with `Consolas` monospace, `TextPosition.TopRight`, aligned columns, section separators |

### 3c. HUD design — clean table format

Using `Draw.TextFixed` with `TextPosition.TopRight` and `SimpleFont("Consolas", 10)`:

```
╔════════════════════════════════════════╗
║   IB CONFLUENCE — Play 2 Retest        ║
╠════════════════════════════════════════╣
║ Time      │ 10:15 ET    │ 2025-01-10   ║
║ IB High   │ 22109.25    │              ║
║ IB Low    │ 21922.00    │              ║
║ IB Mid    │ 22015.62    │              ║
║ IB Range  │ 187.25      │              ║
║ Q25 / Q75 │ 21968.81 / 22062.44       ║
╠════════════════════════════════════════╣
║ BREAK     │ DOWN        │ 10:05        ║
║ AVWAP     │ below       │ 22025.50     ║
║ EMA 20/50 │ 22050 / 21980│ misaligned   ║
║ FVG       │ bear        │ NOT aligned  ║
║ Depth     │ 1.22        │ strong ×1.00 ║
╠════════════════════════════════════════╣
║ Filter    │ PASS        │              ║
║ Calendar  │ SkipMon SkipFeb            ║
║ VCP 3-day │ n/a         │              ║
║ OPEX      │ n/a         │              ║
║ Trades    │ 0 / 2       │              ║
╚════════════════════════════════════════╝
```

Properties for HUD control:
- `DrawHUD` (bool, default true) — toggle the table
- `HUDPosition` (enum: TopRight, TopLeft, BottomRight, BottomLeft) — where to anchor
- `HUDFont` (string, default "Consolas") — monospace for alignment
- `HUDFontSize` (int, default 10)

### 3d. Built-in NT8 indicators to consider integrating

A full survey of `C:\Users\vinay\Documents\NinjaTrader 8\bin\Custom\Indicators\` found **~170 installed indicators**. Here are the most relevant for IB Confluence:

#### Tier 1 — Direct templates / reuse

| Indicator | File | Why it's directly useful |
|---|---|---|
| **ORB_0930_1min_Indicator** | `ORB_0930_1min_Indicator.cs` (28KB) | 🥇 **Closest template**. `DrawOrbLines()` = complete ORB line+box+label+HUD pattern. Has `Draw.TextFixed` dashboard, `Draw.Rectangle` range box, `Draw.Line` for high/low/mid, bar coloring for ORB period, buffer lines. Entry mode logic (Breakout/Retest/Shallow/Midpoint) mirrors IB plays. |
| **PAX30OpeningRange** | `PAX30OpeningRange.cs` (51KB) | 🥈 **Multi-day persistence template**. `Dictionary<DateTime, OrbData>` for multi-day levels. `DrawOrbForDay()` draws all lines+labels. Dynamic level expansion on breakout. Symbol-specific level factors (`GetMarketLevelFactor()`). `CleanupOldData()` for memory management. |
| **OpenRangeIndicator** | `OpenRangeIndicator.cs` (20KB) | 🥉 **Simplest clean ORB drawing**. `Draw.Line` with daily tags, configurable start/end time, color/dash/width properties per line. Direct copy for IB high/low/mid. |
| **FairValueGapICT** | `FairValueGapICT.cs` (37KB) | **Best FVG indicator**. Time-window filtering (exactly what IB needs — restrict to 09:30-10:00). `FVGList` public accessor. Fill tracking (close-through vs pierce-through). CE (consequent encroachment) line. 30+ config params. Can be added via `AddChartIndicator` for visual FVG boxes. |
| **RedTailAutoVWAP** | `MyCustomIndicator.cs` (147KB) | **Already has IB features!** `RangeData` class for `dayInitialBalance` / `nyOpeningRange`. VWAP with bands (±stdDev). Multi-anchor VWAP system. Most feature-complete — investigate `RangeData` class for IB range computation patterns. |

#### Tier 2 — Programmatic value readers

| Indicator | File | What to read |
|---|---|---|
| **FairValueGap** | `FairValueGap.cs` (5KB) | `LastUpGap()`, `LastUpGapPrice()`, `LastDownGap()`, `LastDownGapPrice()` — simple FVG API for filter logic |
| **Swing** | `@Swing.cs` (13KB) | `SwingHighBar(barsAgo, instance, lookBack)`, `SwingLowBar(...)` — for BoS/MSS structure detection after IB break |
| **CurrentDayOHL** | `@CurrentDayOHL.cs` (6KB) | `CurrentOpen[0]`, `CurrentHigh[0]`, `CurrentLow[0]` — session O/H/L for HOD/LOD tracking |
| **PriorDayOHLC** | `@PriorDayOHLC.cs` (7KB) | `PriorHigh[0]`, `PriorLow[0]`, `PriorClose[0]` — ICT daily bias models |
| **Pivots** | `@Pivots.cs` (22KB) | `Pp[0]`, `R1[0]`, `S1[0]`, etc. — floor pivot confluence levels |
| **CamarillaPivots** | `@CamarillaPivots.cs` (22KB) | `R1[0]`-`R4[0]`, `S1[0]`-`S4[0]` — Camarilla confluence (R3/S3 = reversal zones) |
| **NinjaPriceAction** | `NinjaPriceAction.cs` (10KB) | HH/HL/LH/LL/DT/DB labels — structure confirmation after IB breakout |
| **VWAP8** | `VWAP8.cs` (3KB) | `PlotVWAP[0]` — session VWAP (not 09:30-anchored, but useful as reference) |

#### Tier 3 — Drawing / HUD patterns

| Indicator | File | Pattern |
|---|---|---|
| **NetChangeDisplay** | `@NetChangeDisplay.cs` (9KB) | `Draw.TextFixed` with position enum + transparent background — clean HUD pattern |
| **BarTimer** | `@BarTimer.cs` (8KB) | `Draw.TextFixedFine` + `DispatcherTimer` — for IB countdown timer ("IB closes in 4:32") |
| **SampleCustomRender** | `@SampleCustomRender.cs` (19KB) | SharpDX `OnRender` reference — if `Draw.*` calls become too slow for many levels |
| **ToolBarClock** | `ToolBarClock.cs` (15KB) | WPF toolbar label pattern — for adding IB Confluence toggle buttons to chart toolbar |

#### Tier 4 — Conceptual reference

| Indicator | File | Concept |
|---|---|---|
| **ActiveGeoKingV1006** | `ActiveGeoKingV1006.cs` (400KB) | Confluence zones (BuyZoneNear/Far, SellZoneNear/Far), toolbar buttons. Too massive to extract code. |
| **amaRangeProjectionsDaily** | `amaRangeProjectionsDaily.cs` (104KB) | Daily range projections, ADN (Average Daily Noise) bands — could be IB confluence targets |
| **ActiveSwing** | `ActiveSwing.cs` (7KB) | `LowBar()`/`HighBar()` — simpler swing API than built-in `Swing` |

### Integration approach for the IB Confluence Indicator

The indicator should **compose** existing indicators rather than reimplementing:

```
IBConfluenceIndicator
├── IB range computation          ← extract from IBStrategyBase (09:30-09:59)
├── IB boundary drawing           ← template from OpenRangeIndicator / ORB_0930
├── FVG detection + drawing       ← AddChartIndicator(FairValueGapICT) with time window = IB
│   OR custom 5-min detection     ← extract from IBStrategyBase (parity-verified)
├── AVWAP computation             ← extract from IBStrategyBase (09:30-anchored)
├── EMA 20/50 on daily close      ← extract from IBStrategyBase
├── Depth tracking                ← extract from IBStrategyBase
├── BoS/MSS (future)              ← read from Swing indicator (SwingHighBar/SwingLowBar)
├── Prior day levels (future)     ← read from PriorDayOHLC (PriorHigh/PriorLow/PriorClose)
├── Floor pivots (future)         ← read from Pivots (Pp/R1/S1)
├── HUD table                     ← Draw.TextFixed template from NetChangeDisplay / ORB_0930
└── Confluence pass/fail          ← internal filter stack (extracted from IBStrategyBase)
```

---

## 4. Design Decisions to Make

### 4a. Scope: IB-only or generic range-window?

**Option A: IB-only** (`IBConfluenceIndicator`)
- Hardcoded 09:30-09:59 IB window (configurable start/duration)
- FVG detection tuned for IB window
- Calendar filters per play (Mon/Feb/May/Oct)
- Simpler, faster to build, matches current parity standard

**Option B: Generic range-window** (`RangeConfluenceIndicator`)
- Configurable range window (IB, ORB, London, Asia)
- FVG detection for any window
- Reusable across all range-bounded strategies
- More work, but higher reuse value

**Recommendation**: Start with **Option A** (IB-only) to validate the architecture. The indicator can be generalized later by making the range window configurable — the computation logic is already window-agnostic in `IntradayStrategyBase`.

### 4b. FVG: custom detection or built-in?

**Option A: Custom 5-min FVG** (current `IBStrategyBase` logic)
- Full control, matches Python parity standard exactly
- Detects only IB-window FVGs (first finalized)
- Stores `fvgTop`/`fvgBottom` for drawing
- Already tested and parity-verified

**Option B: Built-in `FVGICT`**
- Pre-built visual boxes (nicer drawing)
- 30+ config params (flexible)
- May not match Python parity (different detection algorithm)
- Would need to read its internal state for the filter

**Option C: Both** (custom for filter + built-in for drawing)
- Custom detection drives `ConfluencePass`
- Built-in `FVGICT` draws the boxes
- Property: `UseBuiltInFVGDrawing` (bool)

**Recommendation**: **Option A** (custom) for the initial build. We can add `FVGICT` as an optional visual layer later via a `UseBuiltInFVGDrawing` property.

### 4c. Strategy refactoring: one pass or incremental?

**Option A: One pass** — build indicator + refactor all 3 strategies simultaneously
- Cleaner end state
- Higher risk (all strategies change at once)
- Need to re-verify parity after

**Option B: Incremental** — build indicator, refactor IBRetestBot first, verify parity, then refactor the other two
- Lower risk
- IBRetestBot is the priority (Play 2 is the winner)
- Other bots can follow once the pattern is proven

**Recommendation**: **Option B** (incremental). Build the indicator, refactor `IBRetestBot` first, run parity check against the existing backtest JSON, then roll out to `IBBreakoutBot` and `IBFadeBot`.

### 4d. AVWAP and EMA drawing

Currently AVWAP and EMA are computed but only shown in HUD text. The indicator should draw them:

| Element | Drawing approach | Color |
|---|---|---|
| AVWAP line | `Draw.Line` from 09:30 to current bar, updated each bar | Purple, solid, width 2 |
| EMA 20 | `AddPlot` + `Value[0]` series (daily-close EMA, step function) | Blue, solid, width 1 |
| EMA 50 | `AddPlot` + `Value[0]` series (daily-close EMA, step function) | Red, solid, width 1 |
| Depth shade | `Draw.Rectangle` from mid to max excursion point | Green, 8% opacity |

Note: EMA on daily close is a **step function** (one value per day, flat intraday). Drawing it as a `AddPlot` series would show horizontal lines that step at each session close. Alternatively, draw it as a `Draw.Line` from session open to session close at the EMA value.

---

## 5. File Structure

```
scripts/strategies/nt8/
├── indicators/
│   └── IBConfluenceIndicator.cs      ← NEW: standalone indicator
├── base/
│   ├── RiskManagerBase.cs            (unchanged)
│   └── IntradayStrategyBase.cs       (simplified — range window only, no confluence)
├── ib_breakout/
│   ├── IBStrategyBase.cs             (simplified — just play-specific entry logic + calendar)
│   ├── IBBreakoutBot.cs              (thin — reads indicator properties)
│   ├── IBRetestBot.cs                (thin — reads indicator properties)
│   └── IBFadeBot.cs                  (thin — reads indicator properties)
```

The indicator lives in `indicators/` so it can be used independently of the strategies. The sync script (`sync_nt8_strategies.py`) needs to be updated to also sync the `indicators/` folder to NT8's `Indicators/Vinay/` directory.

---

## 6. Migration Plan

### Phase 1: Build the indicator (no strategy changes)
1. Create `IBConfluenceIndicator.cs` — extract all computation + drawing from `IBStrategyBase`
2. Add `[NinjaScriptProperty]` for all configurable params (colors, toggles, thresholds)
3. Implement clean HUD table using `Draw.TextFixed` + `Consolas`
4. Draw IB boundaries, quarters, FVG box, AVWAP line, depth shade
5. Expose all public properties for strategies to read
6. Compile and test standalone on a chart (no strategy attached)

### Phase 2: Refactor IBRetestBot (incremental)
1. Add `AddChartIndicator(IBConfluenceIndicator())` in `IBRetestBot.ConfigureStrategy`
2. Replace internal confluence computation with reads from `IBConfluenceIndicator1`
3. Remove `DrawIBBoundaries`/`DrawFVG`/`DrawHUD` from `IBStrategyBase` (indicator handles drawing)
4. Run NT8 backtest → compare to existing `scratch/nt8_ib_retest_fvg_sep26_full.json`
5. Verify: same 65 trades, same P&L, same WR/PF → parity preserved

### Phase 3: Refactor remaining bots
1. `IBBreakoutBot` — same pattern as IBRetestBot
2. `IBFadeBot` — same pattern
3. Verify each against existing backtest JSONs

### Phase 4: Enhancements
1. Add optional built-in `FVGICT` integration (`UseBuiltInFVGDrawing` property)
2. Add BoS (Break of Structure) via `ZigZag` to confluence stack
3. Generalize to `RangeConfluenceIndicator` (configurable window for ORB/London/Asia)
4. Add multi-day IB level persistence (like `PAX30OpeningRange` shows last N days)

---

## 7. Open Questions (updated post-survey)

1. ~~**Which built-in NT8 indicators do you already have installed?**~~ — **ANSWERED**: ~170 indicators surveyed. Key finds: `FairValueGapICT` (full ICT FVG with time windows), `ORB_0930_1min_Indicator` (closest ORB template), `PAX30OpeningRange` (multi-day persistence), `RedTailAutoVWAP` (already has IB range!), `Swing` (for BoS), `PriorDayOHLC` + `Pivots` + `CamarillaPivots` (confluence levels).
2. **FVG approach**: Use `FairValueGapICT` via `AddChartIndicator` (pre-built boxes, time-windowed) OR keep the custom 5-min detection from `IBStrategyBase` (parity-verified)? Or both (`UseBuiltInFVG` toggle)?
3. **RedTailAutoVWAP**: It already computes `dayInitialBalance` — should we investigate its `RangeData` class and potentially extend it rather than building from scratch?
4. **BoS/MSS**: Should the indicator include Break of Structure via `Swing` indicator in Phase 1, or defer to Phase 4?
5. **Confluence levels**: Should we add `PriorDayOHLC` (prior H/L/C) and `Pivots` (floor pivots) as confluence factors in Phase 1?
6. **HUD position**: TopRight (like ORB_0930) or TopLeft?
7. **Multi-day IB display**: Should the indicator show prior days' IB levels (like `PAX30OpeningRange` shows 8 days)? Useful for IB range persistence patterns.
8. **Custom rendering vs Draw.***: Start with `Draw.*` calls (simpler, proven) and switch to SharpDX `OnRender` (like `SampleCustomRender`) only if performance becomes an issue?

---

## 8. References

| Doc | Path |
|---|---|
| IB Strategy Base (current) | `scripts/strategies/nt8/ib_breakout/IBStrategyBase.cs` |
| Intraday Strategy Base | `scripts/strategies/nt8/base/IntradayStrategyBase.cs` |
| Risk Manager Base | `scripts/strategies/nt8/base/RiskManagerBase.cs` |
| PAX30 ORB Indicator (template) | `docs/strategies/9_30_breakout/ninjatrader/PAX30OpeningRange.cs` |
| ORB AllDay HUD (template) | `docs/strategies/9_30_breakout/0930_AllDay/ninjascript/ORB_AllDay_MultiTP.cs` |
| ICTFVGBoS (FVG reference) | `scripts/strategies/From_NT8/Vinay/ICTFVGBoS.cs` |
| Python visualizer | `scripts/viz/viz_ib_retest_trades.py` |
| Session 11 handover | `docs/architecture/SESSION_11_REGIME_KILLSWITCH_HANDOVER.md` |
| NT8 framework constraints | `.agents/skills/nt8-framework-constraints/SKILL.md` |
| Parity standard | `docs/architecture/NT8_PYTHON_PARITY_STANDARD.md` |