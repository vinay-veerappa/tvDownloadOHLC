# LiquidityLevels NT8 Indicator — Unified Design Document

> **Date**: 2026-07-30 (Session 13b) | **Updated**: 2026-08-03 (bug fixes + voice alerts)
> **Status**: Implemented — v1.3.0
> **Predecessor**: `IB_CONFLUENCE_INDICATOR_DESIGN.md` §10 (Liquidity Levels Catalog), `SESSION_RANGES_INDICATOR_DESIGN.md` §D (Gap Analysis)
> **Goal**: Build a unified `LiquidityLevels` NT8 indicator that aggregates ALL liquidity levels (prior day/week/month, session opens, intraday, volume profile, pivots/fibs) into one indicator, exposes every level programmatically, draws them on chart, detects liquidity sweeps, and fills the "Session Opens" gap.

---

## A. Expert Panel Summary

### ICT Trading Expert
- **Two liquidity classes**: External (PDH/PDL/EQH/EQL/session H/L = sweep targets) vs Internal (FVGs/OBs/naked POCs = entry zones)
- **Draw on Liquidity (DOL)**: market alternates between seeking liquidity and rebalancing imbalances
- **Sweep hierarchy**: T1 (PDH/PDL/PWH/PWL/EQH/EQL/Asia+London H/L), T2 (Midnight Open/London Open/PDC), T3 (PMH/PML/Monday/Globex), T4 (POC/VAH/VAL), T5 (pivots/fibs = confluence only)
- **Missing critical level**: Midnight Open — axis for Judas Swing detection

### NT8 Architect
- **Aggregator-composer hybrid**: Single indicator that `AddChartIndicator`s RedTail indicators + built-ins, reads their public APIs
- **Zero plots for aggregator** — expose via `GetLevels()` returning `List<LevelState>`. Only SessionOpens sub-component uses 4-6 AddPlot
- **Own SweepDetector** — RedTail's sweep logic is private and only covers its own levels. Build dedicated sweep detector on full aggregated set
- **SharpDX OnRender** — horizontal lines + labels + sweep markers, color-coded by category

### Quant Engineer
- **52+ level catalog** across 6 categories, each with source indicator + access method
- **LevelState struct**: Price, SetTime, IsActive, Swept, TouchCount, StacksWith
- **SweepEvent class**: LevelName, SweepTime, IsBullSweep, SweepDepth, WickPct, ClosePrice
- **Sweep algorithm**: wick depth ≥ 2 ticks + wick ≥ 40% of bar range + close back through level (matches RedTail defaults)

---

## B. Class Structure

```
scripts/ninjatrader/indicators/vinay/
├── LiquidityLevelsModels.cs          ← LevelDef, LevelState, SweepEvent + enums
├── LiquidityLevelsCatalog.cs         ← Static catalog: 52+ LevelDef entries
├── SessionOpensEngine.cs             ← NEW: midnight/4H/London/NY open tracking
├── LiquidityLevels.cs                ← Main indicator (IsOverlay, composes RedTail + built-ins)
```

### LevelDef (immutable catalog entry)
```csharp
public struct LevelDef
{
    public string Name;           // "PDH", "MidnightOpen", "POC", "EQH"
    public LevelCategory Category; // PriorDay, SessionOpen, Intraday, VolumeProfile, Pivot, Structure
    public LevelRole Role;         // SweepTarget, ConfluenceFactor, Both
    public LevelSource Source;     // RedTailKeyLevels, RedTailVolumeProfile, BuiltIn, SessionOpens, MarketStructure
}
```

### LevelState (mutable per-bar)
```csharp
public class LevelState
{
    public LevelDef Def;
    public double Price;
    public DateTime SetTime;
    public bool IsActive;
    public bool Swept;
    public DateTime? SweptTime;
    public int TouchCount;
    public List<double> StacksWith;
}
```

### SweepEvent
```csharp
public class SweepEvent
{
    public string LevelName;
    public double LevelPrice;
    public DateTime SweepTime;
    public bool IsBullSweep;       // true = swept lows (SSL taken)
    public double SweepDepth;      // ticks beyond level
    public double WickPct;         // wick as % of bar range
    public double ClosePrice;
    public int BarIndex;
}
```

---

## C. Level Catalog (52+ levels)

| Category | Levels | Source | Access |
|---|---|---|---|
| **PriorDay** | PDH, PDL, PDC | RedTailKeyLevels + @PriorDayOHLC | `.PDH[0]`, `.PriorClose[0]` |
| **PriorWeek** | PWH, PWL, MH, ML, GH, GL | RedTailKeyLevels | `.PWH[0]` etc. |
| **PriorMonth** | PMH, PML | RedTailKeyLevels | `.PMH[0]` etc. |
| **SessionOpen** | MidnightOpen, LondonOpen, NYOpen, 4H opens (×6) | **NEW** SessionOpensEngine | internal |
| **SessionRange** | AsiaHigh/Low, LondonHigh/Low, GlobexHigh/Low, IBHigh/Low/Mid | SessionRanges indicator | `.GetRange("Asia").High` |
| **Intraday** | HOD, LOD, NYH, NYL | @CurrentDayOHL / RedTailKeyLevels | `.CurrentHigh[0]` |
| **VolumeProfile** | CurrentPOC/VAH/VAL, PrevDayPOC/VAH/VAL, OvernightPOC/VAH/VAL/H/L, Naked POC/VAH/VAL | RedTailVolumeProfile | `.CurrentPOCPlot[0]` + `.GetWeeklyNakedPOCLevels()` |
| **Structure** | StrongLevels[], OBZones[], EQH/EQL | RedTailMarketStructure | `.GetStrongLevels()`, `.GetOBZones()` |
| **Pivot/Fib** | PP, R1-R3, S1-S3, midlines, Fib1-10 | RedTailKeyLevels | `.Pp[0]` etc. (off by default) |

---

## D. Session Opens Sub-Component (NEW — fills §10a gap)

The `SessionOpensEngine` is the only genuinely new computation:

| Open | Time (ET) | DST handling |
|---|---|---|
| Midnight Open | 00:00 | Fixed |
| 4H opens | 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 | Fixed |
| London Open | 02:00 (EST) / 03:00 (EDT) | DST-aware via `TimeZoneInfo.IsDaylightSavingTime()` |
| NY Open | 09:30 | Fixed (= IB open) |

**DST**: London open shifts 02:00→03:00 ET when US goes to DST (2nd Sunday March → 1st Sunday November).

---

## E. Sweep Detection Algorithm

```
FOR each active level WHERE Role == SweepTarget OR Role == Both:
    IF !crossed (level.Price < low OR level.Price > high): CONTINUE
    IF CurrentBar - level.SetBarIndex < MinBarsAfterLevel: CONTINUE

    IF SweepMode == Wick:
        IF close < level.Price:  // swept a high (BSL taken)
            sweepDepth = high - level.Price
            wickPct = (high - max(open, close)) / range * 100
            IF sweepDepth >= 2 ticks AND wickPct >= 40%: EMIT sweep
        ELIF close > level.Price:  // swept a low (SSL taken)
            sweepDepth = level.Price - low
            wickPct = (min(open, close) - low) / range * 100
            IF sweepDepth >= 2 ticks AND wickPct >= 40%: EMIT sweep

    IF SweepMode == BodyClose:
        IF prevClose > level AND close < level: EMIT sweep (BSL)
        ELIF prevClose < level AND close > level: EMIT sweep (SSL)

    Mark level.Swept = true, add to sweep history
```

**Configurable**: `SweepMinDepthTicks` (default 2), `SweepMinWickPct` (default 40), `SweepMode` (Wick/BodyClose/Both), `MinBarsAfterLevel` (default 3), `StackingToleranceTicks` (default 5).

---

## F. Public API

```csharp
// Level access
public List<LevelState> GetActiveLevels();
public List<LevelState> GetLevelsByCategory(LevelCategory c);
public List<LevelState> GetSweepTargets();
public LevelState GetLevel(string name);
public double GetLevelPrice(string name);
public List<LevelState> GetStackedLevels(double price, double toleranceTicks);

// Sweep access
public List<SweepEvent> GetSweepEvents();
public List<SweepEvent> GetSweepsToday();
public SweepEvent GetLastSweep();
public bool WasLevelSwept(string name);

// Session Opens (NEW)
public double MidnightOpen { get; }
public double LondonOpen { get; }
public double NyOpen { get; }
public double Get4HOpen(int hour);
public Dictionary<string, double> GetAllOpens();

// Convenience proxies
public double PDH { get; }
public double PDL { get; }
public double PWH { get; }
public double PWL { get; }
public double PDC { get; }
public double HOD { get; }
public double LOD { get; }
```

---

## G. Integration Architecture

```
LiquidityLevels (IsOverlay, composes)
  ├─ AddChartIndicator: RedTailKeyLevels       [35 plots — read .PDH[0] etc.]
  ├─ AddChartIndicator: RedTailVolumeProfile   [POC/VAH/VAL + naked levels]
  ├─ AddChartIndicator: RedTailMarketStructure [GetStrongLevels() + GetOBZones()]
  ├─ Add: @PriorDayOHLC, @CurrentDayOHL         [built-in liquidity refs]
  ├─ Add: SessionRanges (if available)          [Asia/London/Globex/IB H/L]
  ├─ Owns: SessionOpensEngine                   [NEW — midnight/4H/London/NY]
  ├─ Owns: LevelAggregator                      [merges all → List<LevelState>]
  ├─ Owns: SweepDetector                        [wick/body sweep on 52+ levels]
  └─ Draws: SharpDX lines + labels + sweep markers
      │
      ▼
  IBConfluenceEngine.LiquiditySweepDetector
    → reads GetActiveLevels() + GetSweepEvents()
    → sees 52+ levels instead of current 4
```

---

## H. Phase Plan

| Phase | Scope | Exit Gate |
|---|---|---|
| **P0** | Models + Catalog (52+ LevelDef entries) | Compiles. Catalog covers all 6 categories. |
| **P1** | SessionOpensEngine (midnight/4H/London/NY + DST) | Open lines at correct times. DST transition correct. |
| **P2** | LevelAggregator + main indicator (compose RedTail + built-ins) | `GetActiveLevels()` returns 52+ levels. |
| **P3** | SweepDetector (wick + body close modes) | Sweeps match RedTail on overlapping levels. |
| **P4** | SharpDX drawing (lines + labels + sweep markers) | Visual parity with PineScript patterns. |
| **P5** | RedTailMarketStructure integration (EQH/EQL via GetStrongLevels) | EQH/EQL in GetActiveLevels(). |
| **P6** | SessionRanges integration (Asia/London/Globex/IB H/L) | Session range levels match. |
| **P7** | IBConfluenceEngine integration (refactor LiquiditySweepDetector) | Backtest parity preserved. |
| **P8** | Stacking detection + DOL assessment | Stack sweeps flagged. DOL direction matches ICT bias. |

---

## I. Gap Analysis

| Need | Status | Solution |
|---|---|---|
| PDH/PDL/PWH/PWL/PMH/PML + Monday/Globex/RTH | ✅ Have (RedTailKeyLevels) | Read directly |
| POC/VAH/VAL + naked levels | ✅ Have (RedTailVolumeProfile) | Read directly |
| EQH/EQL + Strong levels + OB zones | ✅ Have (RedTailMarketStructure) | GetStrongLevels() + GetOBZones() |
| PDC / HOD / LOD / PDO | ✅ Have (@PriorDayOHLC / @CurrentDayOHL) | Read directly (PDO fixed 2026-08-03) |
| **Midnight Open** | ✅ Implemented (SessionOpensEngine) | P1 |
| **4H opens** | ✅ Implemented (SessionOpensEngine) | P1 |
| **London Open** | ✅ Implemented (SessionOpensEngine, DST-aware) | P1 |
| **Sweep detection on 52+ levels** | ✅ Implemented (SweepDetector) | P3 |
| **Level aggregation API** | ✅ Implemented (LevelAggregator) | P2 |
| **Stacking detection** | ✅ Implemented | P8 |
| **DOL assessment** | ❌ Deferred | Phase 2 |
| **Voice alerts** | ✅ Implemented (System.Speech pre-generated WAVs) | 2026-08-03 |

---

## J. Implementation Notes (2026-08-03)

### J.1 End-of-Bar Timestamp Convention

NinjaTrader bars carry **close timestamps** (bar stamped 09:31 covers 09:30-09:31, opened at 09:30).
TradingView bars carry **open timestamps**.
All session window gating uses end-of-bar convention:
- **Window start**: `barMins > startMin` (first bar whose open is at/after start)
- **Window end (inclusive)**: `barMins <= endMin` (last bar whose open is within window)

### J.2 Voice Alert System

Pre-generated WAV files via `System.Speech.Synthesis.SpeechSynthesizer` (in-process, fast):
- **Startup**: Generates WAV files per sweep target level (Bull/Bear variants) — cached in `UserDataDir/sounds/`
- **At sweep time**: Plays pre-generated WAV via NT8 native `Alert()` — instant, no process spawn
- **Cooldown**: Per-level+direction cooldown (default 30s) prevents alert spam
- **Live bar only**: Alerts only fire on `CurrentBar == BarsArray[0].Count - 1` — no historical replay
- **Voice gender**: Female (Zira/Hazel/Susan) or Male (David/George/Mark) selected from installed SAPI voices
- **Async generation**: WAV generation runs on ThreadPool to not block chart loading
- **Settings cache**: Marker file tracks voice settings; regenerates only when gender/rate changes

### J.3 Bug Fixes Applied (2026-08-03)

| Bug | Fix |
|---|---|
| Asia range `barMins < 0` always false | Changed to `barMins == 0` (include midnight bar) |
| P12 fence-post at 06:00/17:00 | Changed `>=` to `>` for cutoffs, `<=` for inclusion |
| PDO always returned 0 | Added `PriorOpen` case to `ReadPriorDayOHLC()` |
| `prevClose` uninitialized on bar 0 | Initialize to `Close[0]` on `CurrentBar < 1` |
| Voice alerts fired on historical bars | Gate to live bar only (`CurrentBar == BarsArray[0].Count - 1`) |
| Voice alerts all fired at once on toggle | Live-bar guard + cooldown per level |
| Male voice despite Female selected | SAPI voice selection by name (Zira/Hazel/etc.) |
| PowerShell process spawned per alert | Replaced with System.Speech in-process WAV generation |
| Voice generation blocked chart | Run async on ThreadPool |