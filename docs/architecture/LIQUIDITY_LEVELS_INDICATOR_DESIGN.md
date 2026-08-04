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
| **Hit Rate Tracking (Phase 2 Stats)** | ✅ Implemented | 2026-08-03 |

---

## K. Hit Rate Tracking (Phase 2 Statistics — 2026-08-03)

### K.1 Overview

Per-level hit-rate statistics tracking how often price reaches a level within a configurable time window. Validated against the TradingView ProbabilityMap indicator (`scripts/indicators-pine/ProbabilityMap/ProbabilityMap.pine`).

### K.2 Architecture — Reusable Engine

```
scripts/ninjatrader/indicators/vinay/
├── HitRateTrackerLib.cs    ← Pure C#, NT8-free (HitWindow, HitRateConfig, HitSample, LevelHitStats, HitRateEngine)
└── LiquidityLevels.cs      ← Host indicator (wires engine, renders tooltip + debug table)
```

The engine (`HitRateEngine` static class) is NT8-free and reusable by `SessionRanges` and future Asia/London indicators. Each host indicator supplies:
- A `HitWindow` (session time range, e.g. NY RTH 08:00-16:00 ET)
- A `Func<DateTime, double>` price provider per level (e.g. PDH from daily series, P12High from intraday reconstruction)

### K.3 Hit Definition

Direction-agnostic: `bar.High >= level && bar.Low <= level` (bar range intersects level). The **first** such bar in the window is the hit; its time (minutes-of-day) is recorded as `HitTimeMin` for future time-distribution analysis.

### K.4 Session Boundary

- **CME settlement boundary: 17:00 ET** (matches TV `isNewDay` at `hhmm >= 1700`, line 404 of ProbabilityMap.pine).
- `HrSessionDateFromBarEt`: bars at `>= 17:00 ET` belong to the NEXT calendar day's session.

### K.5 Fence-Post Convention

NT8 uses **close-timestamped** bars (bar stamped 08:05 opens at 08:00):
- Window start: `barMins > StartMin` (first bar whose open is at/after start)
- Window end (inclusive): `barMins <= EndMin` (last bar that closes within window)

### K.6 Historical vs Live

- **Historical sessions** (committed past sessions, up to yesterday) drive: HitRate, TotalHits, DaysInHistory, CurrentStreak, MaxHitStreak, MaxMissStreak, RecentHistory.
- **Today's session** = live, tracked separately: `TodayPrice`, `TodayHit`, `InWindow`. NOT counted in hit_rate/streak stats. On day rollover it commits into history.
- Sessions with 0 window bars (weekends/holidays) are **excluded** from the history — only trading days count.
- `HrCommitDay` and `HrAdvanceToday` fire **only on the live bar** (`CurrentBar == BarsArray[0].Count - 1`), not during historical replay.

### K.7 Tracked Levels (79 levels — all catalog entries)

All levels from `LiquidityLevelsCatalog.GetAllLevels()` are tracked. Each has a price provider that reconstructs the level price for a given historical session date.

| Category | Levels | Price Source |
|---|---|---|
| **Prior Day** (6) | PDH, PDL, PDC, PDO, PDM, Settlement | Daily series (BarsArray[1]) prior bar OHLC |
| **Prior Week** (9) | PWH, PWL, PWM, PWC, PWO, MH, ML, GH, GL | Intraday reconstruction (week H/L scan) or daily series (day-of-week) |
| **Prior Month** (4) | PMH, PML, PMM, PMO | Daily series — prior month H/L/Open scan |
| **Session Opens** (13) | MidnightOpen, LondonOpen, GlobexOpen, RTHOpen, TueOpen–FriOpen, Open_04H–Open_20H | Intraday reconstruction — first bar at/after target time |
| **Session Ranges** (9) | AsiaH, AsiaL, AsiaMid, LonH, LonL, LonMid, GlbH, GlbL, GlbMid | Intraday reconstruction — window H/L scan |
| **London OR** (1) | LonOrMid | Intraday reconstruction — 02:00-05:00 ET window |
| **IB** (3) | IBH, IBL, IBMid | Intraday reconstruction — 09:30-10:00 ET window |
| **P12/NY P12** (9) | P12High, P12Low, P12Mid, NYP12High, NYP12Low, NYP12Mid, PrevNYP12High, PrevNYP12Low, PrevNYP12Mid | Intraday reconstruction — 18:00-06:00 / 06:00-17:00 ET windows |
| **Pivots** (7) | PP, R1, R2, R3, S1, S2, S3 | Computed from PDH/PDL/PDC |
| **Fibs** (10) | Fib 23.6%–Fib -61.8% | Computed from PDH/PDL range |
| **Volume Profile** (8) | PrevDayPOC/VAH/VAL, OvernightPOC/VAH/VAL/High/Low | Computed from PDH/PDL or P12 reconstruction |

Array levels (StrongLevels, OBZones, NakedPOC/VAH/VAL) are not tracked — they require runtime sub-indicator data not available during DataLoaded reconstruction.

### K.8 Level Price Reconstruction Methods

| Method | Used By | Description |
|---|---|---|
| `GetPriorDailyBar(sessDate, field)` | PDH, PDL, PDC, PDO, Settlement | Scans BarsArray[1] backward for first bar with session date < target |
| `ReconstructSessionRange(sessDate, startMin, endMin, crossesMidnight, isHigh)` | AsiaH/L, LonH/L, IBH/L, P12H/L, NYP12H/L, GlbH/L, GH, GL | Scans BarsArray[0] for bars in the time window, returns H or L |
| `ReconstructSessionOpen(sessDate, hour, minute)` | All session opens | First bar at/after target time on session date |
| `ReconstructWeekHighLow(sessDate, isHigh)` | PWH, PWL | Scans intraday bars for the prior week (Mon–Fri) |
| `ReconstructDayOfWeek(sessDate, dayOfWeek, isHigh)` | MH, ML | Daily series bar for the specific day-of-week in current week |
| `ReconstructDayOfWeekOpen(sessDate, dayOfWeek)` | TueOpen–FriOpen | Daily series open for specific day-of-week |
| `GetPriorMonthHighLow(sessDate, isHigh)` | PMH, PML | Daily series — prior calendar month H/L |
| `GetPriorMonthOpen(sessDate)` | PMO | Daily series — first bar of prior month |
| `ReconstructWeekClose/Open(sessDate)` | PWC, PWO | Daily series — last/first trading day of prior week |

### K.8 Config Properties (Group "9. Hit Rate Tracking")

| Property | Default | Description |
|---|---|---|
| EnableHitRate | true | Enable hit-rate tracking |
| HitRateLookbackDays | 500 | Max historical trading days |
| HitRateWindowStart | "09:30" | Hit-check window start (ET HH:mm) — set to "08:00" for TV parity |
| HitRateWindowEnd | "16:00" | Hit-check window end |
| HitRateDebugLevel | "PDH" | Level shown in debug table |
| ShowHitRateDebugTable | true | Display top-right debug table |
| ShowHitRateTooltips | true | Append hit-rate stats to hover tooltips |

### K.9 Debug Table + Tooltip

- **Debug table** (top-right): shows one level's full stats. Click to cycle through tracked levels.
- **Hover tooltip**: appended to the existing level hover tooltip with Hit Ratio, Days Tracked, Current Streak, Max Hit/Miss Streak.
- Recent history: `x` = hit, `-` = miss, `/` = today/pending.

### K.10 Public API

```csharp
public LevelHitStats GetHitRateStats(string levelName);
public Dictionary<string, LevelHitStats> GetAllHitRateStats();
public List<string> GetHitRateTrackedLevels();
```

### K.11 Validation Against TradingView

Validated against TradingView ProbabilityMap indicator (`scripts/indicators-pine/ProbabilityMap/ProbabilityMap.pine`).

**Hit test parity**: TV `checkHit(price) => low <= price and price <= high` (line 226) — identical to NT8 `bar.High >= level && bar.Low <= level`.

**Session boundary parity**: TV `isNewDay` at `hhmm >= 1700` (line 404) — matches NT8 `HrSessionDateFromBarEt` at 17:00 ET.

**Hit-check window parity**: TV checks during `inPreMkt or inNYAM or inLunch or inNYPM` (line 1041) = 08:00-16:00 ET.

**Results (NQ1!, 75-day lookback, 08:00-16:00 ET):**

| Level | NT8 Hit% | NT8 Days | NT8 Streak | NT8 Max H/M | TV Hit% | TV Days | TV Streak | TV Max H/M | Match |
|---|---|---|---|---|---|---|---|---|---|
| PDH | 52.0% | 75 | 3 | 5/6 | 52.1% | 75 | 3 | 5/6 | ✅ |
| PDL | 28.0% | 75 | -3 | 5/12 | 28.1% | 75 | -3 | 5/12 | ✅ |
| PDM | 42.7% | 75 | 1 | 4/6 | 43.1% | 75 | 1 | 4/6 | ✅ |
| GlobexOpen | 56.0% | 75 | 2 | 8/4 | 57.1% | 76 | 2 | 8/4 | ≈ (1-day offset) |
| Settlement | 56.0% | 75 | 2 | 7/3 | 55.1% | 76 | 2 | 6/3 | ≈ (1-day offset) |

The 1-day difference on GlobexOpen/Settlement (TV=76 vs NT8=75) is likely the first session date where the daily series doesn't have a prior day yet.

### K.12 Bugs Found and Fixed During Validation

| Bug | Root Cause | Fix |
|---|---|---|
| 0 days in history | `Time[0]` during DataLoaded returns oldest bar, not latest | Use `BarsArray[0].GetTime(Count-1)` for today's session date |
| 29.7% instead of 50% | `HrCommitDay` fired on every historical bar-rollover, corrupting history | Gate to live bar only (`CurrentBar == BarsArray[0].Count - 1`) |
| Weekends counted as misses | Sessions with 0 window bars included as `Hit=false` | Skip sessions with `WindowBars.Count == 0` in `BuildHistory` |
| TodayPrice = 0.00 | Sub-indicators not ready during DataLoaded | Refresh TodayPrice on first live `OnBarUpdate` via `hrTodayPriceRefreshed` flag |
| 18:00 ET boundary mismatch | NT8 used Globex 18:00; TV uses CME settlement 17:00 | Changed `HrSessionDateFromBarEt` to 17:00 ET |
| Window fence-post wrong | Initial `>=` included pre-window bars; NT8 uses close-timestamped bars | Reverted to `> StartMin` (first bar whose open is at/after start) |

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