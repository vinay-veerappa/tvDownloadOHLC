# IB Confluence Indicator — Architecture Brainstorm

> **Date**: 2026-07-30 (Session 12)
> **Status**: Design DECIDED — agent loop recommendation adopted (Option B: Compose)
> **Goal**: Build `IBConfluenceIndicator` that composes RedTailAutoVWAP + FairValueGapICT(visual) + @Swing, driven by a shared `IBConfluenceEngine` extracted from IBStrategyBase (parity-locked by construction).

---

## 0. Architecture Decision (Agent Loop — adopted)

After a 3-expert panel debate (ICT trading expert, NT8 NinjaScript architect, quantitative systems engineer), **Option B** was selected:

**Create a new `IBConfluenceIndicator` that COMPOSES RedTailAutoVWAP + FairValueGapICT (visual) + `@Swing`, with a shared `IBConfluenceEngine` extracted from IBStrategyBase.**

Key positions:
- **FVG:** detection = IBStrategyBase's parity-verified 5-min FVG (single source of truth); visual = `FairValueGapICT` with IB time window. Never two detectors.
- **Structure:** `@Swing` + custom BoS/CHoCH; LuxAlgo SMC is visual-only (compiled, no API).
- **OB:** custom minimal detector scoped to IB break impulse; do not adapt SupDemZones.
- **Liquidity:** `@PriorDayOHLC` + `@CurrentDayOHL` as refs + custom sweep detector.
- **RedTailAutoVWAP:** do NOT fork the 147KB. Add ~10 lines exposing `IbHigh/IbLow/IbMid/IbRange` public props; otherwise leave untouched.
- **Parity:** the `IBConfluenceEngine` is the SAME class IBStrategyBase uses — extract to a shared file. Indicator and strategy see identical confluence state. Parity preserved by construction, not re-implementation.

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

### 3e. Unimported indicators in `C:\ICT_Videos\NinjaTraderIndicators`

| File | Size | What it does | Reusable for IB Confluence? |
|---|---|---|---|
| **LuxAlgo SmartMoneyConcepts** | 15.8KB | Full SMC suite (BoS/CHoCH, order blocks, FVG, PDHL/PWHL/PMHL, supply/demand, trend). **Compiled DLL** — `.cs` is wrapper stub only. 50+ constructor params. MTF FVG support. | **Partial** — visual overlay only. No programmatic data access (no public zone lists). Use as visual reference; build own detection for filter logic. |
| **SupDemZones** | 34.2KB | Supply/demand zones via swing fractals + Keltner Channel impulse + continuation patterns. Full source. Custom `OnRender` (SharpDX). Private `Zones` list (needs public accessor). | **Partial** — excellent zone-detection source template. Must add public `Zones` accessor + convert to `Draw.Rectangle`. |
| **mjTimeAndPriceLines** | 36.4KB | Draws horizontal rays at the **open price** of user-specified times (up to 20 levels). `Draw.Ray` + custom `OnRender` labels. `DaysBack` controls persistence. | **Yes** — perfect for IB time levels (09:30 open, 10:00). `LevelCollection` with `LevelEnabled`/`Time`/`Stroke` per level. |
| **HalfTrend** | 10.7KB | ATR-based trend-following channel. Public `Trend` Series for programmatic access. `UpSignal`/`DnSignal` reversal markers. `Draw.Region` for shaded area. | **Yes** — trend filter via `Trend[0]`. Channel bands as dynamic S/R. Clean source. |
| **RCTitanium_V1 / RCTrillium_V1** | 1.1KB each | **Empty stubs** — no code, just NT8 generated wrappers. | **No** |
| **ChartToCSV** | 11.2KB | Data export utility — reads all indicators on chart + OHLCV, writes CSV. `Draw.TextFixed` status. | **No** (utility) — useful for exporting indicator values to CSV for Python analysis. |

### 3f. LuxAlgo free library (www.luxalgo.com/library)

The LuxAlgo library has **6,535 indicators** across TradingView, NinjaTrader, and MT4/5. Several are directly relevant to IB Confluence and available for NT8:

| Indicator | What it does | NT8 available? | IB Confluence value |
|---|---|---|---|
| **Smart Money Concepts** (already installed) | BoS/CHoCH, order blocks, FVG, PDHL/PWHL, supply/demand, trend | ✅ Installed | Full SMC confluence layer |
| **Structure & Trend Dashboard** | Multi-timeframe structure, liquidity sweeps, trend alignment dashboard | Soon | HUD + multi-TF confluence |
| **Session Sweep & iFVG RR** | Liquidity sweep setups during sessions + Inverted FVG risk/reward | Soon | Session-based sweep + iFVG (directly relevant to IB) |
| **Significant Breakout Levels (FVG)** | FVG + pivot-based S/R + volume volatility filter + breakout signals | Soon | FVG breakout confluence at IB boundaries |
| **Gap Fill Breakouts** | FVG detection with ATR volatility filter + adaptive box shrink on mitigation + pivot breakout signals | Soon | FVG mitigation tracking (relevant to IB retest) |
| **MSS Sweep Fib Retrace** | Liquidity sweep + MSS + Fibonacci retracement entries | Soon | Sweep + reversal confluence |
| **HTF Swing Structure Signals** | Multi-TF trend + swing points + dynamic Fib retracement pullback zones | Soon | HTF structure alignment for IB bias |
| **8am Road Map Zone** | 8:00-8:15 EST opening range + 9:30 AM breakout tracking | Soon | Pre-IB range (8am) → IB (9:30) confluence |
| **9:30 AM 15m Fib Breakout** | 15-min NY opening range + ATR filter + Fib projections | Soon | ORB confluence at IB time |
| **HTF CISD Projections** | Change in Support/Demand zones + HTF trend filter | Soon | CISD confluence for IB bias |
| **Ultimate AMD Indicator** | Accumulation/Manipulation/Distribution cycle + FVG | Soon | AMD cycle for IB session structure |
| **Market Structure & Fibonacci Zones + RR** | Structure breaks + Fib zones + auto RR calculation | Soon | Structure + Fib confluence at IB levels |

> **Note**: LuxAlgo's GitHub (github.com/LuxAlgo) only has PineTS and pinets-cli (TypeScript Pine Script runtime) — no NT8 indicator source code. The NT8 indicators are distributed via the LuxAlgo platform/library, compiled.

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

## 5. File Structure (revised per Option B)

```
scripts/strategies/nt8/
├── shared/
│   └── IBConfluenceEngine.cs          ← NEW: parity-verified engine (extracted from IBStrategyBase)
│         IB range, FVG (5-min), break dir, depth, VCP, OPEX, EMA, calendar,
│         StructureDetector (BoS/CHoCH on @Swing), OrderBlockDetector, LiquiditySweepDetector,
│         Confluence evaluator (P1/P2/P3 filter stacks)
├── indicators/
│   └── IBConfluenceIndicator.cs       ← NEW: standalone indicator (IsOverlay)
│         Composes: RedTailAutoVWAP (AddChartIndicator), FairValueGapICT (visual), @Swing,
│                   @PriorDayOHLC, @CurrentDayOHL
│         Owns: IBConfluenceEngine instance
│         Draws: clean HUD table (Draw.TextFixed), OB box, sweep arrows, IB boundaries
│         Exposes: all confluence properties for strategies to read
├── base/
│   ├── RiskManagerBase.cs             (unchanged)
│   └── IntradayStrategyBase.cs        (unchanged — range window only)
├── ib_breakout/
│   ├── IBStrategyBase.cs              (refactored — references IBConfluenceEngine, no internal confluence)
│   ├── IBBreakoutBot.cs               (thin — reads engine via indicator)
│   ├── IBRetestBot.cs                 (thin — reads engine via indicator)
│   └── IBFadeBot.cs                   (thin — reads engine via indicator)
```

The `IBConfluenceEngine` is shared — both the indicator and IBStrategyBase reference it. This guarantees identical confluence state. Parity is preserved by construction.

---

## 6. Feature-to-Indicator Mapping (Agent Loop — final)

| Concept | Best indicator | Programmatic access | Visual drawing | Integration approach |
|---|---|---|---|---|
| **IB range** | RedTailAutoVWAP (consumer) + IBConfluenceEngine (parity logic) | Add `IbHigh/IbLow/IbMid/IbRange` props to RedTail (~10 lines) | RedTail's existing IB box | Consume RedTail's IB props; authoritative calc in engine |
| **VWAP / AVWAP** | RedTailAutoVWAP | Public VWAP Series (already) | Existing plots | Overlay; engine reads AVWAP from IBStrategyBase's 09:30-anchored calc (parity) — do NOT recompute from RedTail's session VWAP |
| **FVG (detection)** | IBConfluenceEngine (5-min resampled, parity-verified) | `biasFvg`, `fvgTop`, `fvgBottom` | `Draw.Rectangle` | Single source of truth — lifted from IBStrategyBase |
| **FVG (visual)** | `FairValueGapICT` | `FVGList`, `getUpperPrice/LowerPrice` | Custom SharpDX + CE line | Chart overlay only, time window=09:30–10:00; does NOT feed filter |
| **BoS / CHoCH** | `@Swing` (built-in) + custom logic | `SwingHighBar/SwingLowBar` | Custom `Draw.Arrow` + text | New `StructureDetector` in engine; emits `biasStructure` |
| **Order Blocks** | Custom (build in engine) | `DetectOrderBlock()` → `(obTop,obBottom,obTime)` | `Draw.Rectangle` per day | New `OrderBlockDetector`; feeds depth-tier + retest viz |
| **Liquidity** | `@PriorDayOHLC` + `@CurrentDayOHL` + custom sweep logic | `PriorHigh/PriorLow/CurrentHigh/CurrentLow` | `Draw.Arrow` on sweep | New `LiquiditySweepDetector`; emits `biasLiquiditySweep` |
| **Supply/Demand** | `SupDemZones` (unimported) — optional, defer | None (private `Zones`) | Its own OnRender | Defer to Phase 4; OB covers the IB-relevant case |
| **EMA trend** | IBConfluenceEngine (daily EMA 20/50, session-window close) | Direct fields | HUD text | Lift from IBStrategyBase — parity contract; do NOT use NT8's EMA (different convention) |
| **Depth / retest** | IBConfluenceEngine `RetestDepth` + depth tier | Direct fields | Depth shade | Lift from IBStrategyBase |
| **Calendar filters** | IBConfluenceEngine (Mon/Feb/May/Oct, OPEX, quarterly OPEX) | Bool props | HUD text only | Lift from IBStrategyBase |
| **Pivots / levels** | `@Pivots`, `@CamarillaPivots` (built-in) | `Pp/R1..R3/S1..S3` | Built-in OnRender | Overlay only — not a confluence input (IB doesn't use pivots) |
| **Prior day** | `@PriorDayOHLC` (built-in) | `PriorHigh/PriorLow/PriorClose` | Built-in | Liquidity ref + bias context |
| **Confluence HUD** | New `IBConfluenceIndicator` | — | `Draw.TextFixed` clean table | Build fresh (IBStrategyBase's HUD is the model to copy) |

---

## 7. Architecture (Option B — adopted)

```
IBConfluenceIndicator (new, IsOverlay=true)
  ├─ Adds: RedTailAutoVWAP (AddChartIndicator)         [VWAP + IB range + OR — untouched]
  ├─ Adds: FairValueGapICT (visual, IB time window)     [FVG drawing — untouched, no logic coupling]
  ├─ Adds: @Swing (Strength=3)                         [structure pivots]
  ├─ Adds: @PriorDayOHLC, @CurrentDayOHL                [liquidity refs]
  ├─ Owns: IBConfluenceEngine (extracted from IBStrategyBase)
  │     ├─ IB range calc (parity)        → reads RedTail's IbHigh/IbLow if exposed, else recomputes
  │     ├─ 5-min FVG detection (parity)  → biasFvg, fvgTop/Bottom
  │     ├─ Break direction + time
  │     ├─ Retest depth + depth tier
  │     ├─ VCP 3-day contracting
  │     ├─ OPEX / quarterly OPEX / calendar filters
  │     ├─ Daily EMA 20/50 (session-close convention)
  │     ├─ StructureDetector (BoS/CHoCH on @Swing)     → biasStructure
  │     ├─ OrderBlockDetector                          → obTop/Bottom/Time
  │     ├─ LiquiditySweepDetector (PDH/PDL/IBH/IBL)    → biasLiquiditySweep
  │     └─ Confluence evaluator (P1/P2/P3 filter stacks) → per-play pass/fail
  └─ Draws: clean HUD table (Draw.TextFixed) + OB box + sweep arrows + IB boundaries
```

**Key reuse property:** the `IBConfluenceEngine` is the SAME class IBStrategyBase uses — extract it to a shared file, have the strategy reference it, and the indicator references it. This guarantees the indicator and the live strategy see **identical** confluence state. Parity is preserved by construction, not by re-implementation.

**Why not fork RedTailAutoVWAP (Option A):**
1. 147KB = ~5000 lines. Risk of breaking existing VWAP/IB/OR logic the user relies on.
2. Redundant IB range — its IB logic may differ subtly from the parity-verified IBStrategyBase IB logic. Forking risks two IB definitions diverging.
3. Maintenance: every RedTail update forces a re-merge.
4. Single Responsibility: VWAP + IB range + OR is a coherent "anchored-volume + range" indicator. Confluence (structure, FVG, OB, liquidity, filters) is a different concern.

---

## 8. Phase Plan (Agent Loop — final)

### Phase 1 — Engine extraction + parity lock (no new visuals)
- Extract `IBConfluenceEngine` from `IBStrategyBase.cs` into a shared `shared/IBConfluenceEngine.cs`.
- Strategy and indicator both reference it.
- Run the parity harness against the strategy to confirm 100% identical trades.
- **Exit gate:** harness shows zero divergence vs `scratch/nt8_ib_retest_fvg_sep26_full.json`.

### Phase 2 — IBConfluenceIndicator skeleton + HUD
- New indicator, overlay, adds `@Swing` + `@PriorDayOHLC` + `@CurrentDayOHL`.
- Wire engine. Render the **clean HUD table** (`Draw.TextFixed` rows: Play | Time | IB range | Break | FVG | Structure | OB | Liquidity | AVWAP | Trend | Depth | Confluence).
- Add `AddChartIndicator<RedTailAutoVWAP>()` and `AddChartIndicator<FairValueGapICT>()` (IB time window) so one install = full stack.
- **Exit gate:** HUD matches strategy HUD on a replay day.

### Phase 3 — Detectors (structure, OB, liquidity)
- `StructureDetector` on `@Swing` → `biasStructure`, draw BoS/CHoCH arrows.
- `OrderBlockDetector` → daily OB box near IB break.
- `LiquiditySweepDetector` → pre-IB sweep bias + post-IB sweep fade, arrows on chart.
- Add `BiasStructureAlignedWithBreak` / `LiquiditySweepFavorsBreak` as **non-blocking** confluence tiers (display only initially; gate only after live validation).

### Phase 4 — Optional supply/demand layer
- Import `SupDemZones.cs`, add public `GetZones()` accessor, overlay only. Low priority — OB covers the IB-critical case.

### Phase 5 — Strategy wiring
- Expose confluence tiers in IBStrategyBase as `BiasStructure`, `BiasLiquiditySweep`, `BiasOrderBlock` props (mirroring `BiasFvgAlignedWithBreak`).
- Backtest each tier independently to measure OOS edge before promoting from "display" to "filter" — repeat the Session 10 OOS-validation discipline that flagged FVG-aligned as the only valid filter.

---

## 9. Open Questions (remaining)

1. **HUD position**: TopRight (like ORB_0930) or TopLeft? → user preference
2. **Multi-day IB display**: Should the indicator show prior days' IB levels (like `PAX30OpeningRange` shows 8 days)? Useful for IB range persistence patterns.
3. **RedTailAutoVWAP IB props**: Can we confirm RedTail exposes `IbHigh/IbLow` or do we need to add them? Need to read the 147KB file's property section.
4. **FairValueGapICT time window**: Can we set a single window to 09:30-10:00 via its `StartTime1`/`TimeRangeMinutes1` properties? (Confirmed yes from the survey — `UseTimeRange1` + `StartTime1` + `TimeRangeMinutes1`).
5. **OB detection scope**: Should OB detection be limited to the IB break impulse only, or also track subsequent OBs formed during the retest phase?

---

## 10. Liquidity Levels Catalog

A comprehensive list of all liquidity levels the IB Confluence system should reference. Each level is a potential sweep target or confluence factor.

### 10a. Time-based opens (liquidity resting at session opens)

| Level | Time (ET) | Description | Source indicator | Status |
|---|---|---|---|---|
| **Midnight open** | 00:00 | Price at midnight — key ICT reference for daily bias | **NONE** — needs custom indicator or adapt `mjTimeAndPriceLines` | ❌ Missing |
| **4H opens** | 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 | 4-hour candle opens — institutional reference points | **NONE** — needs custom indicator or adapt `mjTimeAndPriceLines` | ❌ Missing |
| **London open** | 02:00/03:00 (DST) | London session open price | **NONE** — needs custom | ❌ Missing |
| **NY open** | 09:30 | RTH session open — this IS the IB open | IBConfluenceEngine (IB open) | ✅ Have |
| **Prior day close** | 16:00 prev | Previous session close | `@PriorDayOHLC` / RedTail Key Levels (`PDC`) | ✅ Have |
| **Settlement price** | ~16:00/17:00 | Daily settlement (varies by instrument) | RedTail Goldbach Po3 (has settlement detection) | ⚠️ Optional |

> **Action item**: Build a **Session Opens** indicator (or adapt `mjTimeAndPriceLines`) that draws horizontal lines at midnight, 4H opens, London open, and NY open. This fills the gap no existing indicator covers.

### 10b. Prior session ranges (resting liquidity from prior sessions)

| Level | Description | Source indicator | Plot output? |
|---|---|---|---|
| **PDH / PDL** | Prior day high/low — primary sweep targets | RedTail Key Levels (`PDH`/`PDL`), `@PriorDayOHLC` (`PriorHigh`/`PriorLow`) | ✅ Yes |
| **PWH / PWL** | Prior week high/low — major liquidity | RedTail Key Levels (`PWH`/`PWL`) | ✅ Yes |
| **PMH / PML** | Prior month high/low — institutional levels | RedTail Key Levels (`PMH`/`PML`) | ✅ Yes |
| **PDC** | Prior day close — gap reference | `@PriorDayOHLC` (`PriorClose`), RedTail Key Levels | ✅ Yes |
| **Monday H/L** | Monday session range — ICT weekly reference | RedTail Key Levels (`MH`/`ML`) | ✅ Yes |
| **Globex H/L** | Full Globex week range | RedTail Key Levels (`GH`/`GL`) | ✅ Yes |
| **RTH H/L (NYH/NYL)** | Current RTH session H/L (developing) | RedTail Key Levels (`NYH`/`NYL`), `@CurrentDayOHL` | ✅ Yes |
| **Overnight H/L** | Overnight session (18:00-08:30) H/L | RedTail Volume Profile (overnight levels) | ✅ Yes |

### 10c. Intraday liquidity (developing during the session)

| Level | Description | Source indicator | Plot output? |
|---|---|---|---|
| **IB High / Low / Mid** | 09:30-09:59 IB range | IBConfluenceEngine, RedTail AutoVWAP (Day IB) | ✅ Yes |
| **NY Opening Range H/L** | 09:30-09:45 OR | RedTail AutoVWAP (`ShowNyOpeningRange`) | ✅ Yes |
| **HOD / LOD** | High/low of day (developing) | `@CurrentDayOHL` (`CurrentHigh`/`CurrentLow`) | ✅ Yes |
| **Session VWAP** | 09:30-anchored VWAP | RedTail AutoVWAP (`NyVwap`) | ✅ Yes |
| **Prior session VWAP** | Yesterday's NY VWAP | RedTail AutoVWAP (`PrevDayNyVwap`) | ✅ Yes |
| **EQH / EQL** | Equal highs/lows — liquidity pools | RedTail Market Structure | ⚠️ Visual only (check if exposeable) |
| **Strong/Weak levels** | Scored swing levels | RedTail Market Structure | ⚠️ Visual only (check if exposeable) |

### 10d. Volume profile levels (structural liquidity)

| Level | Description | Source indicator | Plot output? |
|---|---|---|---|
| **POC** | Point of Control — highest volume price | RedTail Volume Profile | ✅ Yes |
| **VAH / VAL** | Value Area High/Low | RedTail Volume Profile | ✅ Yes |
| **Naked POC** | Un revisited prior POC levels | RedTail Volume Profile | ✅ Yes |
| **Prior day POC/VAH/VAL** | Previous session volume levels | RedTail Volume Profile | ✅ Yes |
| **LVN zones** | Low Volume Nodes — breakout zones | RedTail LVN Hunter | ⚠️ Visual only |

### 10e. Pivot / Fibonacci levels (calculated liquidity)

| Level | Description | Source indicator | Plot output? |
|---|---|---|---|
| **Floor pivots** | PP, R1-R3, S1-S3 | RedTail Key Levels, `@Pivots` | ✅ Yes (33 plots) |
| **Camarilla pivots** | R1-R4, S1-S4 | `@CamarillaPivots` | ✅ Yes |
| **Daily/Weekly/Monthly Fibs** | Auto Fib retracements | RedTail Auto Fibs, RedTail Key Levels (Fib1-10) | ✅ Yes |

### 10f. Summary — gaps to fill

| Missing level | Solution | Priority |
|---|---|---|
| **Midnight open** | Build "Session Opens" indicator (or adapt `mjTimeAndPriceLines`) | HIGH |
| **4H opens** | Same indicator — configurable 4H intervals | HIGH |
| **London open** | Same indicator — London session open price | MEDIUM |
| **Round numbers / psychological** | Build custom "Psychological Levels" indicator | LOW |
| **EQH/EQL (programmatic)** | Fork RedTail Market Structure to expose lists | MEDIUM |

---

## 11. PineScript Indicators to Port to NinjaTrader

The repo has **70+ PineScript files** across `scripts/indicators-pine/`, `pinescript/`, and `docs/`. Here's the prioritized port roadmap:

### Tier 1 — Port first (core IB/ICT workflow)

| PineScript | Path | What it does | NT8 port priority | Why |
|---|---|---|---|---|
| **DailyNYLevels** | `scripts/indicators-pine/daily-ny-levels/` | Daily NY session levels (open, high, low, mid, IB, OR) | 🥇 HIGH | Core levels for IB trading — complement RedTail |
| **DailyClassification** | `scripts/indicators-pine/DailyClassification/` | R1/R2/DWP/DNP daily classification | 🥇 HIGH | Daily bias classification — gates IB direction |
| **IB Stats Extensions** | `scripts/indicators-pine/IB/` | IB statistics, probability maps, extensions | 🥇 HIGH | IB range analysis + probability — core IB tool |
| **ProfilerIndicator** | `scripts/indicators-pine/profiler/ProfilerIndicator.pine` | Daily Profiler — session boxes, status logic, P12 scenarios, HOD/LOD timing | 🥇 HIGH | Session profiling — IB context + timing |
| **HTF EMA Analysis** | `scripts/indicators-pine/htf_ema_analysis/` | Higher-timeframe EMA trend analysis | 🥈 MEDIUM | Trend filter for IB bias (replaces simple EMA 20/50) |
| **ProbabilityMap** | `scripts/indicators-pine/ProbabilityMap/` | ICT probability map for directional bias | 🥈 MEDIUM | ICT bias model — confluence for IB direction |

### Tier 2 — Port second (statistical / session analysis)

| PineScript | Path | What it does | NT8 port priority | Why |
|---|---|---|---|---|
| **Magic Hour Analysis** | `scripts/indicators-pine/magic_hour_analysis/` | Magic hour (10:00-11:00) statistics and signals | 🥈 MEDIUM | Post-IB session timing |
| **NQStats Playbook** | `docs/nqstats/strategies/` | NQ statistical playbook strategy | 🥈 MEDIUM | NQ-specific session stats |
| **Noon Curve Strategy** | `docs/nqstats/noon_curve/` | Noon reversal curve analysis | 🥈 MEDIUM | Post-noon IB reversal timing |
| **ICT Probability Engine** | `docs/research/ict/indicators/` | ICT directional probability engine | 🥈 MEDIUM | ICT concept probability scoring |
| **Session Statistical Levels** | Already available as RedTail indicator | Percentile-based session ranges | ✅ Have | Covered by RedTail |

### Tier 3 — Port later (options / advanced)

| PineScript | Path | What it does | NT8 port priority | Why |
|---|---|---|---|---|
| **Options: Daily OC Levels** | `scripts/indicators-pine/options/Daily_OC_levels.pine` | Options open interest levels | 🥉 LOW | GEX/Dealer levels — advanced confluence |
| **Options: Expected Move** | `scripts/indicators-pine/options/DailyExpectedMove.pine` | Expected move from options data | 🥉 LOW | Volatility expectation for IB range |
| **Options: Dealer Levels** | `scripts/indicators-pine/options/DealerLevels.pine` | Dealer positioning levels | 🥉 LOW | Institutional level reference |
| **Options: ExecutionHUD** | `scripts/indicators-pine/options/ExecutionHUD.pine` | Options execution HUD | 🥉 LOW | Options execution dashboard |
| **CandleScience** | `scripts/indicators-pine/CandleScience/` | Candle pattern analysis | 🥉 LOW | Candle pattern confluence |
| **TCM/ONS** | `scripts/indicators-pine/TCM/` | TCM ONS verification indicators | 🥉 LOW | TCM strategy verification |

### Tier 4 — Strategies (port as NT8 strategies, not indicators)

| PineScript | Path | What it does | Port priority | Why |
|---|---|---|---|---|
| **IB 3 Play Strategy** | `docs/strategies/initial_balance_break/pinescript/` | IB 3-play strategy (breakout/retest/fade) | Already in NT8 (IBBreakoutBot/RetestBot/FadeBot) | ✅ Done |
| **ORB V7 Strategy** | `docs/strategies/9_30_breakout/pinescript/` | 9:30 ORB strategy | Already in NT8 (ORB_0930_1min) | ✅ Done |
| **ORB AllDay MultiTP** | `docs/strategies/9_30_breakout/0930_AllDay/pinescript/` | All-day ORB with multi-TP | Already in NT8 | ✅ Done |
| **HMA SuperTrend Scalper** | `scripts/strategies/pinescript/` | HMA + SuperTrend momentum scalper | 🥈 MEDIUM | Independent strategy — port for variety |
| **Unified Quant Scalper** | `scripts/strategies/pinescript/` | BBW squeeze + HMA expansion dual-engine | 🥈 MEDIUM | Independent strategy — port for variety |
| **Generic Periodic ORB** | `docs/strategies/generic_periodic_orb/` | Generic ORB for any session | 🥉 LOW | Generalization of ORB |
| **Herman IB Probability** | `pinescript/ib_probability_map_herman.pine` | Herman IB probability map | 🥉 LOW | IB probability analysis |
| **NQStats Playbook Strategy** | `docs/nqstats/strategies/` | NQ statistical playbook | 🥉 LOW | NQ-specific strategy |

### Libraries (port as NT8 shared code, not standalone indicators)

| PineScript Library | Path | What it does | Port priority |
|---|---|---|---|
| **RangeSessionLib** | `scripts/indicators-pine/lib-pine/RangeSessionLib.pine` | Range session utilities | 🥈 MEDIUM — needed by IB indicator |
| **PineDrawingLib** (7 files) | `scripts/indicators-pine/lib-pine/PineDrawing*.pine` | Drawing utilities (lines, boxes, zones, tables, markers) | 🥈 MEDIUM — needed for HUD/drawing |
| **StatsLib** | `scripts/indicators-pine/lib-pine/StatsLib.pine` | Statistical functions | 🥉 LOW |
| **market_calendar** | `scripts/indicators-pine/lib-pine/market_calendar.pine` | Market calendar (holidays, OPEX) | 🥈 MEDIUM — needed for calendar filters |
| **HitTracking** | `scripts/indicators-pine/lib-pine/HitTracking.pine` | Level touch/hit tracking | 🥉 LOW |

---

## 12. File Organization — COMPLETED

> **Status**: Option A restructure completed on 2026-07-30.

### New structure (source of truth)
```
scripts/ninjatrader/
├── strategies/                    → Custom/Strategies/Vinay/
│   ├── base/                      (RiskManagerBase, IntradayStrategyBase)
│   ├── ib_breakout/               (IBStrategyBase, 3 bots)
│   ├── ema_pullback/
│   ├── failed_auction/
│   └── vwap_reclaim/
├── indicators/                    → Custom/Indicators/
│   ├── vinay/                     (our custom indicators — IBConfluenceIndicator goes here)
│   ├── redtail/                   (14 RedTail .cs files + README.md + INDEX.md)
│   └── third_party/               (future third-party indicators)
├── addons/                        → Custom/AddOns/
│   (McpBridge, RiskGuard, TradeCopier, etc.)
└── shared/                        → Custom/Strategies/Vinay/ (compiled with strategies)
    (IBConfluenceEngine goes here)
```

### Sync script — updated
`scripts/utils/sync_nt8_strategies.py` now syncs from `scripts/ninjatrader/`:
- `strategies/**/*.cs` → `Custom/Strategies/Vinay/`
- `shared/*.cs` → `Custom/Strategies/Vinay/`
- `indicators/**/*.cs` → `Custom/Indicators/` (NEW)
- `addons/*.cs` → `Custom/AddOns/`
- Orphan detection covers all 3 destinations

### Old location
`scripts/strategies/nt8/` still exists (not yet deleted). Once the first real sync + compile from the new location is verified, the old folder can be removed.

---

## 13. References

| Doc | Path |
|---|---|
| IB Strategy Base (current) | `scripts/ninjatrader/strategies/ib_breakout/IBStrategyBase.cs` |
| Intraday Strategy Base | `scripts/ninjatrader/strategies/base/IntradayStrategyBase.cs` |
| Risk Manager Base | `scripts/ninjatrader/strategies/base/RiskManagerBase.cs` |
| PAX30 ORB Indicator (template) | `docs/strategies/9_30_breakout/ninjatrader/PAX30OpeningRange.cs` |
| ORB AllDay HUD (template) | `docs/strategies/9_30_breakout/0930_AllDay/ninjascript/ORB_AllDay_MultiTP.cs` |
| ICTFVGBoS (FVG reference) | `scripts/strategies/From_NT8/Vinay/ICTFVGBoS.cs` |
| Python visualizer | `scripts/viz/viz_ib_retest_trades.py` |
| Session 11 handover | `docs/architecture/SESSION_11_REGIME_KILLSWITCH_HANDOVER.md` |
| NT8 framework constraints | `.agents/skills/nt8-framework-constraints/SKILL.md` |
| Parity standard | `docs/architecture/NT8_PYTHON_PARITY_STANDARD.md` |
| RedTail indicators index | `scripts/ninjatrader/indicators/redtail/INDEX.md` |
| RedTail full README | `scripts/ninjatrader/indicators/redtail/README.md` |
| NT8 file organization | `docs/architecture/NT8_FILE_ORGANIZATION.md` |
| Sync script | `scripts/utils/sync_nt8_strategies.py` |
| PineScript indicators | `scripts/indicators-pine/` (70+ files) |
| PineScript strategies | `scripts/strategies/pinescript/` + `docs/strategies/` |