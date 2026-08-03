# SessionRanges NT8 Indicator — Unified Design Document

> **Date**: 2026-07-30 (Session 13) | **Updated**: 2026-08-03 (bug fixes + end-of-bar convention)
> **Status**: Implemented — v1.1.0 (window gating + Globex rollover fixed)
> **Predecessor**: `IB_CONFLUENCE_INDICATOR_DESIGN.md` (Option B: Compose)
> **Goal**: Build a unified `SessionRanges` NT8 indicator that tracks ALL session ranges (Asia, London, Globex, IB, NY OR, Magic Hours, custom) with public data exposure + visual boxes, serving as the range data provider for `IBConfluenceEngine`.

---

## A. Expert Panel Debate

### Expert 1 — ICT Trading Expert

**Which session ranges matter?**

| Priority | Range | Window (ET) | Role in ICT/Herman |
|---|---|---|---|
| **Critical** | Asia Range | 00:00–02:00 | **Base range** — sets the trap. Size gates continuation vs. mean-reversion (<0.48% = trend, >0.48% = chop). Herman: 85-90% of days are small Asia. |
| **Critical** | London OR | 02:00–03:00 | **Trigger** — breakout determines continuation/reversal. 76.5% bullish / 73.8% bearish. |
| **Critical** | London Range | 02:00–05:00 | **Expansion engine** — sweeps Asia ~90% combined. NY fractal base. |
| **Critical** | IB | 09:30–10:00 | **NY trigger** — IB Confluence core. Parity-locked. |
| **High** | NY Opening Range | 09:30–09:35 | First-5-min OR. RedTail already has this (private). |
| **High** | Globex / Overnight | 18:00–08:30 | Overnight session range — liquidity accumulated before RTH. |
| **Medium** | Magic Hour | 03:00–07:00 | Wide 4-hr pre-market range (DailyNYLevels preset B). |
| **Medium** | Q1 Break | 06:00–08:30 | European open / first quarter. |
| **Low** | 1100 BO / Lunch / 1400 | Various | Intraday breakout tracking (DailyNYLevels preset C). |

**Fractal liquidity chain:**
```
Asia (base) → London sweeps Asia → London range becomes NY's base
                                    → NY AM (07:00-10:00) sweeps London
                                    → IB (09:30-10:00) is the NY trigger
                                    → NY PM (13:00-16:00) is the expansion
```

### Expert 2 — NT8 NinjaScript Architect

**Structure**: Single indicator with `List<RangeSpec>` configuration, each spec owning its own `RangeState`.

| Decision | Recommendation | Rationale |
|---|---|---|
| Single vs multi-indicator | **Single indicator, N ranges** | One install = all ranges. Matches PineScript profiler. |
| Range config | **`RangeSpec` list + preset enum + custom** | Mirror PineScript `f_resolve_preset()`. |
| Data exposure | **`GetRange(name)` indexer + convenience props** | Avoids flat property explosion. |
| Drawing | **SharpDX `OnRender`** | RedTail pattern. No `Draw.*` object-count limits. |
| Performance | **Minute-based detection, no AddDataSeries** | Primary series = 1-min. ~8000 state updates/day for 20 ranges = trivial. |
| Multi-range rendering | **Stagger boxes, hue-offset colors** | Avoid overlap. PineScript pattern. |

### Expert 3 — Quantitative Systems Engineer

**Parity with PineScript RangeSessionLib**: C# port must match `CORE_ENGINE_SPEC.md` exactly:
- `RangeSpec` → 1:1 field mapping (or_start_min, or_end_min, cutoff_min as int minutes)
- `RangeState` → 1:1 field mapping (all 40+ fields including sig_side, sig_outcome, MFE/MAE)
- Session detection → minute-based portable path (CORE_ENGINE_SPEC §4.2)
- MFE/MAE → price percentage per ADR-002
- Percentile computation → nearest-rank method (CORE_ENGINE_SPEC §11)

**What the indicator does NOT do** (deferred to IBConfluenceEngine):
- FVG detection, AVWAP, EMA, confluence filters — all engine's job
- SessionRanges is **purely range tracking + drawing + data exposure**

---

## B. Final Design

### B.1 File Structure

```
scripts/ninjatrader/indicators/vinay/
├── SessionRanges.cs              ← Main indicator (IsOverlay=true, SharpDX OnRender)
├── SessionRangesModels.cs        ← RangeSpec, RangeState, ExcursionHistory classes
└── SessionRangesPresets.cs       ← Preset catalog + ResolvePreset()
```

### B.2 RangeSpec (C# class — mirrors PineScript UDT)

```csharp
public class RangeSpec
{
    public string Name { get; set; }              // "IB", "Asia", "London OR", etc.
    public string PresetGroup { get; set; }       // "Overnight", "Pre-Market", "Intraday", "Custom"
    public int OrStartMin { get; set; }           // minutes-of-day (e.g., 570 = 09:30)
    public int OrEndMin { get; set; }             // minutes-of-day (e.g., 600 = 10:00)
    public int CutoffMin { get; set; }            // minutes-of-day (e.g., 960 = 16:00)
    public string Days { get; set; }              // "23456" = Mon-Fri
    public string Timezone { get; set; }          // "America/New_York"
    public bool IsTransfer { get; set; }          // 0300 Transfer special logic
    public double EvTargetPct { get; set; }       // 0.30 = 0.30% EV target
    public bool IsEnabled { get; set; }           // user can toggle individual ranges
    public System.Windows.Media.Brush BoxColor { get; set; }
    public System.Windows.Media.Brush BullColor { get; set; }
    public System.Windows.Media.Brush BearColor { get; set; }
    public DashStyleHelper HighLineStyle { get; set; }
    public DashStyleHelper LowLineStyle { get; set; }
    public int LineWidth { get; set; }
    public int FillOpacity { get; set; }          // 0=solid, 100=transparent
    public bool ShowLabel { get; set; }
    public int FontSize { get; set; }

    public bool CrossesMidnight => OrEndMin < OrStartMin || CutoffMin < OrEndMin;
}
```

### B.3 RangeState (C# class — mirrors PineScript UDT)

```csharp
public class RangeState
{
    public RangeSpec Spec { get; set; }

    // OR values
    public double SessionOpen;
    public double OrHigh;
    public double OrLow;
    public double OrLastClose;
    public bool OrBuilding;
    public bool OrComplete;
    public int OrStartBarIndex;

    // References
    public double BullRef;     // = OrHigh when complete
    public double BearRef;     // = OrLow when complete
    public double OrMid;       // = (OrHigh + OrLow) / 2
    public bool RefSet;

    // MFE (price % per ADR-002)
    public double DailyBullMfe;
    public double DailyBearMfe;
    public int DailyBullPeakMin;
    public int DailyBearPeakMin;

    // MAE absolute
    public double DailyMaeBullAbs;
    public double DailyMaeBearAbs;

    // MAE pullback
    public double DailyMaeBullPb;
    public double DailyMaeBearPb;

    // Breakout-post MFE/MAE
    public double DailyBoMfeBull;
    public double DailyBoMfeBear;
    public double DailyBoMaeBull;
    public double DailyBoMaeBear;

    // Mid-hit tracking
    public bool MidHitBull;
    public bool MidHitBear;

    // Entry triggers (for fakeout)
    public bool EntryTriggeredBull;
    public bool EntryTriggeredBear;

    // Cutoff
    public double CloseAtCutoff;
    public bool IsCommitted;

    // Signal
    public int SigSide;            // 0=None, 1=Bull, -1=Bear
    public int SigOutcome;         // 0=Pending, 1=Full, -1=Failed
    public bool IsTerminated;
    public int SigBreakoutSide;    // 0=None, 1=Bull, -1=Bear
    public double SigBreakoutPx;
    public int SigBreakoutBarIndex;
    public double SigTargetPx;
    public double SigInvalidPx;

    // Session transition tracking
    public bool PrevInOr;
    public bool PrevInData;

    // Convenience
    public double Range => OrHigh - OrLow;
    public double RangePct => OrLow > 0 ? (Range / OrLow) * 100.0 : 0;
    public bool IsForming => OrBuilding;
    public DateTime BreakoutTime;
    public DateTime SessionDate;
}
```

### B.4 Session Catalog

#### ICT Core preset (recommended default)

| Range Name | OR Start | OR End | Cutoff | Source |
|---|---|---|---|---|
| Asia Range | 00:00 | 02:00 | 05:00 | Herman base range |
| London OR | 02:00 | 03:00 | 05:00 | Herman trigger |
| London Range | 02:00 | 05:00 | 09:30 | Herman expansion |
| Globex Range | 18:00 | 08:30 | 09:30 | Overnight liquidity |
| IB | 09:30 | 10:00 | 16:00 | IB Confluence core |
| NY Opening Range | 09:30 | 09:35 | 12:00 | First 5-min OR |

#### DailyNYLevels Presets A/B/C — 9 ranges total

See `docs/indicators/DailyNYLevels/PRD.md` §3 for full catalog.

#### Herman Full preset

Adds Pre-London (00:00-02:00), NY AM (07:00-10:00), NY PM (13:00-16:00) to ICT Core.

#### Magic Hours preset — 7 strategies

00:00, 01:00, 02:00, 06:00, 07:00, 08:00, 23:00 magic hour ranges.

#### Custom — from `config/ib_custom_ranges.yaml` or NT8 properties

### B.5 Public API Surface

```csharp
// Range lookup
public RangeState GetRange(string name);
public RangeState GetRange(int index);
public int RangeCount { get; }
public List<string> ActiveRangeNames { get; }

// IB convenience
public double IbHigh { get; }
public double IBLow { get; }
public double IBMid { get; }
public double IBRange { get; }
public bool IBComplete { get; }
public double IBOpen { get; }
public double IBClose { get; }
public int IBBreakoutSide { get; }
public DateTime IBBreakoutTime { get; }

// Asia convenience (Herman)
public double AsiaHigh { get; }
public double AsiaLow { get; }
public double AsiaRange { get; }
public double AsiaRangePct { get; }     // <0.48% = trend, >0.48% = chop
public bool AsiaComplete { get; }

// London convenience
public double LondonHigh { get; }
public double LondonLow { get; }
public double LondonRange { get; }
public bool LondonComplete { get; }

// Globex convenience
public double GlobexHigh { get; }
public double GlobexLow { get; }
public bool GlobexComplete { get; }

// Aggregate
public bool AnyRangeForming { get; }
public List<RangeState> CompletedRanges { get; }
public List<RangeState> FormingRanges { get; }

// Historical stats
public ExcursionHistory GetHistory(string rangeName);

// Methods
public void AddCustomRange(string name, string startHHMM, string endHHMM, string cutoffHHMM, string days);
public void EnableRange(string name);
public void DisableRange(string name);
```

### B.6 Drawing Approach

**SharpDX `OnRender`** per range:
1. Box (OrHigh to OrLow, start bar to current/end bar) with fill opacity
2. High line (BullColor, configurable dash style)
3. Low line (BearColor, configurable dash style)
4. Mid line (dotted, optional)
5. Label at right edge: `"IB 22109/21922 (187.25)"`
6. Breakout marker (triangle at breakout bar + price)
7. Quarter lines (25%/75%, optional, gray dotted)

Historical ranges: faded (30% opacity) boxes for prior days up to `MaxHistory`.

### B.7 Integration with IBConfluenceEngine

```
SessionRanges (indicator)
  ├─ Computes IB + Asia + London + Globex ranges
  ├─ Exposes all as public properties
  │
  └─ IBConfluenceEngine reads:
       ├─ IB range (parity-locked, engine computes independently for now)
       ├─ asiaRangePct  ← NEW: Herman regime filter
       ├─ londonHigh    ← NEW: NY sweep target
       └─ londonLow     ← NEW: NY sweep target
```

**Phase 1**: Engine continues to compute IB range independently (parity-safe). SessionRanges provides Asia/London/Globex as **new** reads (no parity risk).

**Phase 2**: After parity validation, engine can read IB from SessionRanges directly.

### B.8 RedTailAutoVWAP Additions (P1 — ~15 lines, non-breaking)

```csharp
// Add to RedTailAutoVWAP public properties section:
[XmlIgnore][Browsable(false)]
public double DayIbHigh => dayInitialBalance?.High ?? 0;

[XmlIgnore][Browsable(false)]
public double DayIbLow => dayInitialBalance?.Low ?? 0;

[XmlIgnore][Browsable(false)]
public double DayIbMid => dayInitialBalance != null && dayInitialBalance.High > 0 
    ? (dayInitialBalance.High + dayInitialBalance.Low) / 2.0 : 0;

[XmlIgnore][Browsable(false)]
public double DayIbRange => dayInitialBalance != null ? dayInitialBalance.High - dayInitialBalance.Low : 0;

[XmlIgnore][Browsable(false)]
public bool DayIbComplete => dayInitialBalance != null && !dayInitialBalance.IsForming && dayInitialBalance.High > 0;

[XmlIgnore][Browsable(false)]
public double NyOrHigh => nyOpeningRange?.High ?? 0;

[XmlIgnore][Browsable(false)]
public double NyOrLow => nyOpeningRange?.Low ?? 0;
```

---

## C. Phase Plan

| Phase | Scope | Exit Gate |
|---|---|---|
| **P0** | Models (`SessionRangesModels.cs`) + Presets (`SessionRangesPresets.cs`) | Compiles. Preset resolution matches PineScript. |
| **P1** | Core indicator (ICT Core preset: IB + Asia + London + Globex + NY OR). SharpDX drawing. Public props. | Visual parity with PineScript profiler boxes. IB range matches IBStrategyBase. |
| **P2** | MFE/MAE + breakout tracking per CORE_ENGINE_SPEC §6-10. ExcursionHistory. | Parity test: 30 days vs PineScript DailyNYLevels. |
| **P3** | All 9 DailyNYLevels presets + Herman Full + Magic Hours + Custom ranges. | All presets correct. Custom from YAML loads. |
| **P4** | RedTailAutoVWAP public props (~15 lines). | RedTail compiles. Engine can read from either source. |
| **P5** | IBConfluenceEngine integration (Asia/London/Globex reads — new, non-parity-breaking). | Backtest with Asia regime filter. |
| **P6** | Historical display + per-range HUD table + percentile levels. | HUD matches PineScript DailyNYLevels. |
| **P7** | Session Opens indicator (midnight/4H/London/NY open price lines — fills §10a gap). | Open lines at 00:00, 04:00, 08:00, 12:00, 16:00, 20:00. |

---

## D. Gap Analysis Summary

| Need | Status | Solution |
|---|---|---|
| IB range (09:30-10:00) | ✅ Implemented | SessionRanges with window gating |
| Asia range (00:00-02:00) | ✅ Implemented | SessionRanges |
| London range/OR (02:00-05:00) | ✅ Implemented | SessionRanges |
| Globex range (18:00-08:30) | ✅ Implemented | SessionRanges (crosses midnight) |
| NY Opening Range (09:30-09:35) | ✅ Implemented | SessionRanges |
| DailyNYLevels 9 presets | ✅ Implemented | SessionRangesPresets |
| Magic Hours (7) | ✅ Implemented | SessionRangesPresets |
| MFE/MAE tracking | ✅ Wired (CheckBreakout/UpdateMfe/UpdateMidHit called post-OR) | SessionRanges |
| Custom range config | ✅ Implemented | CustomRangeDefs string parser |
| Midnight/4H opens | ✅ Implemented | SessionOpensEngine (in LiquidityLevels) |
| BoS/CHoCH events | ⚠️ Private in RedTailMarketStructure | Defer — build custom in engine |
| EQH/EQL | ⚠️ Private in RedTailMarketStructure | Defer — build custom in engine |
| Historical stats exposure | ❌ Phase 2 | ExcursionHistory populated but not yet exposed via public API |
| Percentile bands | ❌ Phase 2 | ExcursionHistory.Percentile exists, not wired to UI |

---

## E. Implementation Notes (2026-08-03)

### E.1 End-of-Bar Timestamp Convention

NinjaTrader bars carry **close timestamps** (bar stamped 09:31 covers 09:30-09:31, opened at 09:30).
All session window gating uses end-of-bar convention via `IsBarInWindow()`:
- **Window start**: `barMins > startMin` (first bar whose open is at/after start)
- **Window end (inclusive)**: `barMins <= endMin` (last bar whose open is within window)
- **Cross-midnight windows** (e.g. Globex 18:00-08:30): `barMins > startMin || barMins <= endMin`

### E.2 Globex Day Rollover

Day rollover uses **Globex date** (18:00 ET boundary), not calendar midnight:
- Bar stamped 18:05 ET → opened at 18:00 → belongs to next calendar day's Globex session
- Bar stamped 18:00 ET → opened at 17:55 → still prior session (uses `>` not `>=`)
- All range states reset on Globex date change, not calendar date change

### E.3 Window Gating + Finalization

`OnBarUpdate` processes each range spec:
1. **Days filter**: Skip if current day-of-week not in spec.Days (TV convention: 1=Sun..7=Sat)
2. **Window check**: `IsBarInWindow(barMins, spec)` determines if bar is within OR window
3. **Building**: First in-window bar → `UpdateOr()` captures H/L/open. Subsequent in-window bars extend H/L.
4. **Finalization**: First bar OUT of window after building → `FinalizeOr(CurrentBar)` sets `OrComplete`, `IsCommitted`, `OrEndBarIndex`
5. **Post-OR analysis**: After finalization, `CheckBreakout/UpdateMfe/UpdateMidHit` run on each bar

### E.4 Rendering

- **Building ranges**: Box extends from `OrStartBarIndex` to current bar (live)
- **Completed ranges**: Box extends from `OrStartBarIndex` to `OrEndBarIndex` (fixed)
- **IsCommitted flag**: Controls whether x2 extends to current bar or stops at `OrEndBarIndex`

### E.5 Bug Fixes Applied (2026-08-03)

| Bug | Fix |
|---|---|
| Ranges never finalized (one big box) | Added `IsBarInWindow()` gating + `FinalizeOr()` call on window end |
| Day rollover used calendar midnight | Changed to Globex date (18:00 ET boundary) |
| `FinalizeOr()` called without bar index | Pass `CurrentBar` to set `OrEndBarIndex` |
| `IsCommitted` never set | Set in `FinalizeOr()` |
| `CheckBreakout/UpdateMfe/UpdateMidHit` never called | Wired in `OnBarUpdate` post-OR |
| Days-of-week filter missing | Added `IsDayEnabled()` with TV convention (1=Sun..7=Sat) |
| Render extended completed ranges to current bar | Use `OrEndBarIndex` when `OrComplete && OrEndBarIndex > 0` |