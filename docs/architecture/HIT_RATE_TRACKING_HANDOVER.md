# Hit Rate Tracking — Phase 2 Handover Document

> **Date**: 2026-08-04
> **Session**: NinjaScript Indicators Phase 2 — Statistics
> **Status**: Hit-rate tracking implemented and TV-validated. Remaining statistics work pending.
> **Parent docs**: [LIQUIDITY_LEVELS_INDICATOR_DESIGN.md](LIQUIDITY_LEVELS_INDICATOR_DESIGN.md) §K-L, [VISUAL_SYSTEM.md](../indicators/DailyNYLevels/VISUAL_SYSTEM.md)
> **TV reference**: `scripts/indicators-pine/ProbabilityMap/ProbabilityMap.pine`

---

## 1. What Was Done

### 1.1 Hit-Rate Tracking Engine (DONE ✅)

Built a reusable, NT8-free hit-rate tracking engine (`HitRateTrackerLib.cs`) that tracks how often price reaches a level within a configurable time window.

**Files created/modified:**

| File | Action | Purpose |
|---|---|---|
| `scripts/ninjatrader/indicators/vinay/HitRateTrackerLib.cs` | NEW | Pure C# engine — `HitWindow`, `HitRateConfig`, `HitSample`, `LevelHitStats`, `HitRateEngine` |
| `scripts/ninjatrader/indicators/vinay/LiquidityLevels.cs` | MODIFIED | Host indicator — wires engine, renders tooltip + debug table, public API |
| `scripts/utils/agentic_panel.py` | MODIFIED | Added `--language csharp` preset for Gemma/GLM/KimiK2.7 review loop |
| `launch/sync_indicators.bat` | NEW | Sync script for Vinay/RedTail indicators to NT8 Custom directory |
| `docs/architecture/LIQUIDITY_LEVELS_INDICATOR_DESIGN.md` | MODIFIED | Section K (hit-rate design) + Section L (remaining TODO) |

**Deployed to:** `Documents\NinjaTrader 8\bin\Custom\Indicators\Vinay\` (subfolder organized to match namespace)

### 1.2 Key Design Decisions

| Decision | Value | Rationale |
|---|---|---|
| Session boundary | 17:00 ET (CME settlement) | Matches TV ProbabilityMap `isNewDay` at `hhmm >= 1700` (line 404) |
| Fence-post (window start) | `barMins > StartMin` | NT8 uses close-timestamped bars (bar stamped 08:05 opens at 08:00) |
| Fence-post (window end) | `barMins <= EndMin` (inclusive) | Last bar that closes within window |
| Hit definition | `bar.High >= level && bar.Low <= level` | Direction-agnostic, matches TV `checkHit()` (line 226) |
| First hit only | Yes | `HitTimeMin` recorded for future time-distribution analysis |
| Today's session | NOT counted in historical stats | Committed into history on day rollover |
| Empty sessions | Excluded | Weekends/holidays with 0 window bars don't count as misses |
| Live bar gating | `CurrentBar == BarsArray[0].Count - 1` | `HrCommitDay` and `HrAdvanceToday` only fire on live bar, not historical replay |
| DataLoaded today date | `BarsArray[0].GetTime(Count-1)` | `Time[0]` returns oldest bar during DataLoaded, not latest |
| TodayPrice refresh | First live `OnBarUpdate` | Sub-indicators not ready during DataLoaded; `hrTodayPriceRefreshed` flag |

### 1.3 Tracked Levels (79 levels)

All levels from `LiquidityLevelsCatalog.GetAllLevels()` have price providers:

| Category | Levels | Reconstruction Method |
|---|---|---|
| Prior Day (6) | PDH, PDL, PDC, PDO, PDM, Settlement | `GetPriorDailyBar()` — daily series scan |
| Prior Week (9) | PWH, PWL, PWM, PWC, PWO, MH, ML, GH, GL | `ReconstructWeekHighLow()`, `ReconstructDayOfWeek()` — intraday/daily scan |
| Prior Month (4) | PMH, PML, PMM, PMO | `GetPriorMonthHighLow()` — daily series prior month scan |
| Session Opens (13) | Midnight, London, Globex, RTH, Tue-Fri, 4H opens ×5 | `ReconstructSessionOpen()` — first bar at/after target time |
| Session Ranges (9) | AsiaH/L/Mid, LonH/L/Mid, GlbH/L/Mid | `ReconstructSessionRange()` — window H/L scan |
| London OR (1) | LonOrMid | `ReconstructSessionRange(02:00-05:00)` |
| IB (3) | IBH, IBL, IBMid | `ReconstructSessionRange(09:30-10:00)` |
| P12/NY P12 (9) | P12H/L/Mid, NYP12H/L/Mid, PrevNYP12H/L/Mid | `ReconstructSessionRange()` — 18:00-06:00 / 06:00-17:00 ET |
| Pivots (7) | PP, R1-R3, S1-S3 | Computed from PDH/PDL/PDC |
| Fibs (10) | Fib 23.6% through Fib -61.8% | Computed from PDH/PDL range |
| Volume Profile (8) | PrevDayPOC/VAH/VAL, OvernightPOC/VAH/VAL/High/Low | Computed from PDH/PDL or P12 reconstruction |

**Not tracked:** StrongLevels, OBZones, NakedPOC/VAH/VAL (array levels — require runtime sub-indicator data not available during DataLoaded reconstruction).

### 1.4 Validation Against TradingView

Validated against TV ProbabilityMap indicator on NQ1!, 75-day lookback, 08:00-16:00 ET window.

| Level | NT8 Hit% | TV Hit% | Match? |
|---|---|---|---|
| PDH | 52.0% | 52.1% | ✅ |
| PDL | 28.0% | 28.1% | ✅ |
| PDM | 42.7% | 43.1% | ✅ |
| GlobexOpen | 56.0% (75d) | 57.1% (76d) | ≈ (1-day offset) |
| Settlement | 56.0% (75d) | 55.1% (76d) | ≈ (1-day offset) |

TV tooltip data (from `data_get_pine_labels` with `study_filter="Daily Profile"`):
- PDH: 52.1%, 75 days, streak ↑3, max 5/6
- PDL: 28.1%, 75 days, streak ↓3, max 5/12
- PDM: 43.1%, 75 days, streak ↑1, max 4/6
- GlobexOpen: 57.1%, 76 days, streak ↑2, max 8/4
- Settlement: 55.1%, 76 days, streak ↑2, max 6/3

### 1.5 Bugs Found and Fixed During Validation

| Bug | Root Cause | Fix |
|---|---|---|
| 0 days in history | `Time[0]` during DataLoaded returns oldest bar | Use `BarsArray[0].GetTime(Count-1)` |
| 29.7% instead of 50% | `HrCommitDay` fired on every historical bar-rollover | Gate to live bar only |
| Weekends counted as misses | Sessions with 0 window bars included as `Hit=false` | Skip 0-window-bar sessions in `BuildHistory` |
| TodayPrice = 0.00 | Sub-indicators not ready during DataLoaded | Refresh on first live `OnBarUpdate` |
| 18:00 ET boundary | NT8 used Globex 18:00; TV uses CME settlement 17:00 | Changed to 17:00 ET |
| Window fence-post | Initial `>=` included pre-window bars | Reverted to `> StartMin` |

---

## 2. What Remains (TODO)

### 2.1 High Priority

| # | Item | Description | TV Reference |
|---|---|---|---|
| 1 | Display hit-rate % on chart labels | TV shows "PDH 52.1% (↑3)" on the line label, not just in debug table. NT8 currently only shows in hover tooltip + debug table. | Lines 1218-1227 — `lblPDH := LStack.drawLevelLabel(pdH, str.format("PDH: {0,number,#.#}%", getGlobalProb("PDH")), ...)` |
| 2 | Today's hit indicator | Show green check / red X on chart when today's level is hit/missed within the hit-check window. TV shows "Today PDH hit? YES/NO" in debug table. | Lines 1041-1086 — `hitPDH := true` when `checkHit(pdH)` |

### 2.2 Medium Priority

| # | Item | Description | TV Reference |
|---|---|---|---|
| 3 | Conditional probabilities | Pattern + NY position conditioned hit-rate. TV uses `getCondProbLonH(pattern, nyPos)` etc. — probability of a level being hit given the current session pattern and NY position. | Lines 719-816 — `getCondProb*` functions using `_byIx()` lookup |
| 4 | Leverage TV limitations | NT8 advantages: more levels (no 500 label limit), real-time alerts (no repaint), per-level custom hit windows, multi-timeframe, unlimited history, no Pine compile limits, dynamic catalog | N/A |
| 5 | Fix 1-day offset | GlobexOpen/Settlement: TV has 76 days, NT8 has 75. Likely first session date where daily series lacks a prior day. | N/A |
| 6 | NT MCP tooltip reading | Expose tooltip text as public property on level objects so NT MCP can read hit-rate stats programmatically. Requires standardizing tooltip format. | N/A |

### 2.3 Low Priority

| # | Item | Description | TV Reference |
|---|---|---|---|
| 7 | Global probability lookup tables | Static research values per instrument (NQ/ES/RTY/YM/CL/GC). TV `getGlobalProb()` uses hardcoded lookup arrays for ~12 levels. | Lines 854-868 |
| 8 | Sigma probabilities | ±1σ/±2σ move probability conditioned on bias (bullish/bearish/neutral). | Lines 870-896 — `getSigmaProb()` |
| 9 | 72-scenario probabilities | Base bias probability from pattern + NY position + session size. | Lines 903-905 — `get72ScenarioProb()` |
| 10 | DOW adjustment | Day-of-week probability adjustment factor. | Line 904 — `getDOWAdj()` |
| 11 | UI standardization | Refactor to NtDrawingLib per `VISUAL_SYSTEM.md` spec. Includes LevelLine class with line + label + tooltip, theme resolver, display profiles. Separate session. | `VISUAL_SYSTEM.md` §9.4 |

---

## 3. Architecture

### 3.1 HitRateTrackerLib.cs (Pure C#, NT8-free)

```
namespace NinjaTrader.NinjaScript.Indicators.Vinay

HitMode enum: Through (default), Close (future), Sweep (future)

HitWindow
  - StartMin, EndMin (ET minutes-of-day)
  - CrossesMidnight
  - InWindow(barMins) → bool
  - TimeRangeString → "08:00-16:00"
  - TimeStrToMin("08:00") → 480

HitRateConfig
  - LookbackDays = 500
  - RecentN = 10
  - StreakMinHits = 1
  - Mode = HitMode.Through

BarData (lightweight bar snapshot, decoupled from NT8)
  - TimeEt, BarMins, High, Low, Open, Close, BarIndex

SessionBars (per-session-date window bars)
  - SessionDate, List<BarData> WindowBars

HitSample (committed per-day, per-level result)
  - SessionDate, LevelPrice, Hit (bool), HitTimeMin (int, 0 if miss)

LevelHitStats (computed statistics — drives tooltip + debug table)
  - LevelName, DaysInHistory, TotalHits, HitRate
  - CurrentStreak (signed: +N hits / -N misses)
  - MaxHitStreak, MaxMissStreak
  - TodayPrice, TodayHit, InWindow
  - TimeWindowLabel, NewDaysDetected, LocalIndex, LookbackDays
  - RecentHistory (List<bool?>, null=today), RecentHitsCount
  - RecentHistoryString → "x x x x - - - x x /"
  - CurrentStreakDisplay → "11 hits" / "-2 misses"

HitRateEngine (static, pure computation)
  - BuildSessionBars(allBars, window, sessionDateMapper) → List<SessionBars>
  - BuildHistory(levelName, priceProvider, sessions, cfg) → List<HitSample>
  - IsHit(bar, levelPrice, mode) → bool
  - ComputeStats(levelName, history, todayPrice, todayHit, inWindow, ...) → LevelHitStats
  - AdvanceToday(stats, barEt, barHigh, barLow, levelPrice) — live first-hit detection
  - CommitToday(levelName, sessionDate, levelPrice, hit, hitTimeMin) → HitSample
  - TrimHistory(history, lookbackDays) → List<HitSample>
```

### 3.2 LiquidityLevels.cs Integration Points

| Lifecycle | Hit-Rate Hook | What It Does |
|---|---|---|
| `State.Configure` | Init collections | `hrHistory`, `hrStats`, `hrProviders`, `hrTodayHit/HitMin/Level`, `hrTrackedLevels` |
| `State.DataLoaded` | `BuildHitRateEngine()` | Scans intraday bars → session groupings, registers providers, builds history + stats |
| `State.DataLoaded` | `RegisterLevelProviders()` | 79 level price providers (daily series, intraday reconstruction, computed) |
| `State.DataLoaded` | `UpdateLevelPrices()` | Force level price update (sub-indicators may not be ready; TodayPrice refreshed on first live bar) |
| `OnBarUpdate` (day rollover) | `HrCommitDay()` | Commits today's results into history, recomputes stats (live bar only) |
| `OnBarUpdate` (every bar) | `HrAdvanceToday()` | Live first-hit detection within window (live bar only) |
| `OnBarUpdate` (first live bar) | TodayPrice refresh | Populates TodayPrice from sub-indicator data via `hrTodayPriceRefreshed` flag |
| `OnRender` | `RenderHitRateDebugTable()` | Top-right SharpDX panel, click-to-cycle through levels |
| `OnRender` | `RenderHoverTooltip()` | Appends hit-rate stats block to existing level hover tooltip |
| `OnRender` | `HrCheckDebugTableClick()` | Click-to-cycle debug level |

### 3.3 Config Properties (Group "9. Hit Rate Tracking")

| Property | Default | Description |
|---|---|---|
| EnableHitRate | true | Enable hit-rate tracking |
| HitRateLookbackDays | 500 | Max historical trading days |
| HitRateWindowStart | "09:30" | Hit-check window start (ET HH:mm) — set to "08:00" for TV parity |
| HitRateWindowEnd | "16:00" | Hit-check window end |
| HitRateDebugLevel | "PDH" | Level shown in debug table (click table to cycle) |
| ShowHitRateDebugTable | true | Display top-right debug table |
| ShowHitRateTooltips | true | Append hit-rate stats to hover tooltips |

### 3.4 Public API

```csharp
public LevelHitStats GetHitRateStats(string levelName);
public Dictionary<string, LevelHitStats> GetAllHitRateStats();
public List<string> GetHitRateTrackedLevels();
```

### 3.5 Level Price Reconstruction Methods

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

---

## 4. TV ProbabilityMap Reference

The TV indicator (`scripts/indicators-pine/ProbabilityMap/ProbabilityMap.pine`) computes:

| Feature | TV Function | Lines | Status |
|---|---|---|---|
| Hit tracking | `checkHit(price)` | 226 | ✅ NT8 parity |
| Hit reset (new day) | `isNewDay` at 17:00 ET | 404, 1012 | ✅ NT8 parity |
| Hit-check window | `inPreMkt or inNYAM or inLunch or inNYPM` = 08:00-16:00 | 1041 | ✅ NT8 parity |
| Global probabilities | `getGlobalProb(level)` | 854-868 | ❌ TODO (low) |
| Conditional probabilities | `getCondProbLonH(pattern, nyPos)` etc. | 719-816 | ❌ TODO (medium) |
| Sigma probabilities | `getSigmaProb(sig, man)` | 870-896 | ❌ TODO (low) |
| 72-scenario bias | `get72ScenarioProb(pattern, nyPos, asiaSize, londonSize)` | 903 | ❌ TODO (low) |
| DOW adjustment | `getDOWAdj()` | 904 | ❌ TODO (low) |
| Hit-rate tooltip | Label text + tooltip | 1218-1227, tooltips | ✅ NT8 has hover tooltip (TODO: chart label display) |
| Debug table | HUD table | 1420-1490 | ✅ NT8 has debug table |

---

## 5. Agentic Panel (C# Support)

`scripts/utils/agentic_panel.py` now supports `--language csharp` for the Maker-Judge-Refiner loop:

```bash
python -m scripts.utils.agentic_panel --prompt "..." --language csharp --maker gemma4:31b-cloud --max-retries 1
```

- **Maker**: Gemma (`gemma4:31b-cloud`) — drafts C# NinjaScript code
- **Judges**: GLM (`glm-5.2:cloud`), KimiK2.7 (`kimi-k2.7-code:cloud`), MiniMax (`minimax-m3:cloud`), Qwen (`qwen3.5:397b-cloud`)
- **Refiner**: DeepSeek (`deepseek-v4-flash:cloud`)
- C# rubrics: NT8 framework compliance, SharpDX disposal, KeyNotFoundException checks, fence-post convention
- No ADR-017 vectorization check (Python-only)

---

## 6. Deployment

### 6.1 Folder Structure

```
Documents\NinjaTrader 8\bin\Custom\Indicators\
├── Vinay\
│   ├── HitRateTrackerLib.cs
│   ├── LiquidityLevels.cs
│   ├── LiquidityLevelsCatalog.cs
│   ├── LiquidityLevelsModels.cs
│   ├── SessionOpensEngine.cs
│   ├── SessionRanges.cs
│   ├── SessionRangesModels.cs
│   └── SessionRangesPresets.cs
└── RedTail\
    ├── RedTailKeyLevels.cs
    ├── RedTailVolumeProfile.cs
    └── ... (14 files)
```

### 6.2 Sync & Compile

```bash
# Sync from repo to NT8
launch\sync_indicators.bat

# Or manually
copy scripts\ninjatrader\indicators\vinay\*.cs "Documents\NinjaTrader 8\bin\Custom\Indicators\Vinay\"

# Compile via NT MCP
# nt_compile tool
```

### 6.3 Debug

- Debug table: top-right corner of chart (click to cycle through levels)
- NT8 Output log: `Print` statements on DataLoaded (engine ready message, per-level summary)
- TV comparison: `data_get_pine_labels` with `study_filter="Daily Profile"` to get TV tooltip stats
- TV debug table: `data_get_pine_tables` with `study_filter="Daily Profile"`

---

## 7. Key Gotchas

1. **`Time[0]` during DataLoaded** returns the oldest bar, not the latest. Use `BarsArray[0].GetTime(Count-1)`.
2. **Sub-indicators** (`_priorDayOHLC`, `_currentDayOHL`) are NOT ready during `State.DataLoaded`. Level prices are 0 until first `OnBarUpdate`.
3. **`HrCommitDay` must only fire on the live bar** — otherwise every historical day-rollover corrupts the history by committing garbage samples.
4. **Session boundary is 17:00 ET** (CME settlement), NOT 18:00 ET (Globex open). TV uses `hhmm >= 1700`.
5. **Fence-post**: NT8 uses close-timestamped bars. `> StartMin` = first bar whose open is at/after start. `<= EndMin` = last bar that closes within window.
6. **Weekends/holidays**: sessions with 0 window bars must be excluded from history, not counted as misses.
7. **The debug table was moved 60px left** from the right edge so long level names (e.g. "PrevNYP12High") aren't clipped by the price axis.

---

## 8. Next Session Entry Points

1. **Start here**: Read this document, then `LIQUIDITY_LEVELS_INDICATOR_DESIGN.md` §K-L.
2. **High-priority work**: Display hit-rate % on chart labels (item 1) and today's hit indicator (item 2).
3. **For UI work**: Read `VISUAL_SYSTEM.md` first — it defines the full NtDrawingLib spec.
4. **For TV comparison**: Use `tradingview_data_get_pine_labels` and `tradingview_data_get_pine_tables` with `study_filter="Daily Profile"`.
5. **For compilation**: Sync to NT8 Custom\Indicators\Vinay\, then `nt_compile`.
6. **For agentic review**: `python -m scripts.utils.agentic_panel --prompt "..." --language csharp --maker gemma4:31b-cloud`.