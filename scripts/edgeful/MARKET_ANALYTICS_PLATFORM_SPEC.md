# Market Analytics Platform — Unified Design Specification
## Quantitative Research Infrastructure for Futures Day Trading

**Date:** April 9, 2026
**Version:** 1.0 — Consolidates range analytics, macro retrofit, and cross-system architecture
**Status:** DRAFT — for review before build

---

## Table of Contents

1. Platform Vision
2. Architecture Overview
3. Shared Infrastructure Layer
4. Module 1: ICT Macro Analytics (existing — enhancements)
5. Module 2: Time-Based Range Analytics (new)
6. Module 3: Daily Context Reports (new)
7. Module 4: Strategy Simulation Engine (new)
8. Module 5: Cross-Report Confluence & Screener (future)
9. Dashboard System
10. Backtest Framework Enhancements
11. Implementation Plan
12. Design Principles

---

## 1. Platform Vision

This platform answers one question across multiple dimensions:

> **What does price typically do in this situation, and how confident should I be?**

"This situation" can be a time window (macro, opening range, initial balance), a price
relationship (gap, inside/outside day, proximity to prior day levels), or a market
condition (VIX regime, day of week, streak context). The platform computes historical
probabilities for all of these and surfaces actionable edges through interactive
dashboards and strategy simulation.

**What exists today:**
- ICT Macro Pipeline (`scripts/edgeful/`) — 27 macro windows/day, Judas classification, FVG detection
- Options/GEX Pipeline — Schwab API, dealer levels, regime classification
- Quant Backtest Framework — signal hunt, MFE/MAE, strategy optimization

**What this spec adds:**
- Generic time-based range analytics (OR, IB, session ranges, custom)
- Daily context reports (gap fill, reference levels, OCC, streaks, ATR)
- Shared infrastructure layer (data loading, context computation, filter system)
- Retrofit enhancements to the existing macro pipeline
- Cross-report confluence engine

**Our edge over commercial alternatives (Edgeful, etc.):**
- 20 years of 1-minute data vs 5-7 years
- GEX/DEX overlay capability (no commercial platform has this)
- ICT macro analytics already built
- Purged walk-forward cross-validation for strategy testing
- Full control over computation — any custom filter or feature

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     SHARED INFRASTRUCTURE LAYER                         │
│                                                                         │
│  lib/                                                                   │
│  ├── data_loader.py      1m/5m/daily parquet loading + caching         │
│  ├── session_tagger.py   Session boundaries, RTH/ETH, trading_date     │
│  ├── context.py          DailyContext: VIX, ATR, DOW, gaps, PD levels  │
│  ├── range_core.py       Generic range H/L/Mid, extensions, MR metrics │
│  ├── trade_simulator.py  Entry/exit/MFE/MAE simulation engine          │
│  └── filters.py          Universal filter dimensions + subreport logic │
└────────────────┬──────────────────┬──────────────────┬─────────────────┘
                 │                  │                  │
    ┌────────────▼───────┐ ┌───────▼────────┐ ┌───────▼────────┐
    │  MODULE 1          │ │  MODULE 2      │ │  MODULE 3      │
    │  ICT Macros        │ │  Time Ranges   │ │  Daily Context │
    │  (existing +       │ │  (OR, IB,      │ │  (gaps, PD     │
    │   enhancements)    │ │   sessions)    │ │   levels, OCC, │
    │                    │ │                │ │   streaks, ATR)│
    │  scripts/edgeful/  │ │  scripts/      │ │  scripts/      │
    │                    │ │  ranges/       │ │  context/      │
    └────────┬───────────┘ └───────┬────────┘ └───────┬────────┘
             │                     │                  │
             ▼                     ▼                  ▼
    ┌──────────────────────────────────────────────────────────┐
    │              data/derived/                                │
    │                                                          │
    │  macro_records.parquet      (existing, enhanced)         │
    │  fvg_detail.parquet         (existing)                   │
    │  range_records.parquet      (new)                        │
    │  range_trades.parquet       (new)                        │
    │  daily_context.parquet      (new — shared by all)        │
    │  gap_records.parquet        (new)                        │
    │  reference_levels.parquet   (new)                        │
    └────────────────────────┬─────────────────────────────────┘
                             │
    ┌────────────────────────▼─────────────────────────────────┐
    │              DASHBOARD LAYER                              │
    │                                                          │
    │  Next.js + DuckDB-WASM                                   │
    │  /research/macros/edgeful    (existing, enhanced)         │
    │  /research/ranges            (new)                        │
    │  /research/context           (new)                        │
    │  /research/screener          (future — cross-report)      │
    └──────────────────────────────────────────────────────────┘
```

**Key architectural decision:** Every module reads from the shared `daily_context.parquet`
for VIX, ATR, DOW, gap, and PD level data. No module computes context independently.
This eliminates duplication and guarantees consistency across all reports.

---

## 3. Shared Infrastructure Layer

### 3.1 `lib/data_loader.py` — Data Loading & Caching

Shared by all modules. Loads 1m/5m/daily bars from existing parquet store.

```python
class DataLoader:
    """
    Loads and caches OHLCV data from the parquet store.
    All modules use this — never load data directly.
    """
    def __init__(self, data_root: Path):
        self.data_root = data_root     # C:\Users\vinay\tvDownloadOHLC\data
        self._cache: dict[str, pd.DataFrame] = {}
    
    def load_1m(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Load 1-minute bars. Returns: datetime, open, high, low, close, volume."""
    
    def load_5m(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Load 5-minute bars."""
    
    def load_daily(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Load daily bars (derived from 1m if not stored separately)."""
    
    def load_vix(self, start: date, end: date) -> pd.DataFrame:
        """Load VIX daily close."""
    
    def load_news(self, start: date, end: date) -> pd.DataFrame:
        """Load news/events from Prisma SQLite DB."""
```

### 3.2 `lib/session_tagger.py` — Session & Time Classification

Assigns `trading_date` (6 PM ET rollover), session labels, RTH/ETH flags.
Used by macros, ranges, and context modules identically.

```python
def tag_session(bars: pd.DataFrame, tz: str = "America/New_York") -> pd.DataFrame:
    """
    Adds columns:
      - trading_date:  date (rolls at 18:00 ET)
      - session:       ASIA | LONDON | NY_PRE | NY_AM | NY_LUNCH | NY_PM
      - is_rth:        bool (09:30-16:00 ET)
      - day_of_week:   int (0=Mon..4=Fri)
      - minutes_into_session: int
    """
```

### 3.3 `lib/context.py` — DailyContext Computation

**This is the architectural centerpiece.** Every module reads from a single
`daily_context.parquet` that contains all per-day context variables. Compute
once, use everywhere.

```python
@dataclass
class DailyContext:
    """One row per (symbol, trading_date). Shared by ALL modules."""
    
    symbol: str
    trading_date: date
    day_of_week: int                    # 0=Mon..4=Fri
    
    # ── VIX / Volatility ────────────────────────────────────────
    vix_close: float | None
    vix_regime: str                     # LOW (<15), NORMAL (15-25), HIGH (25-35), EXTREME (>35)
    vix_pctile_60d: float | None        # Percentile rank over trailing 60d
    
    # ── ATR ─────────────────────────────────────────────────────
    atr_14d: float                      # 14-day ATR (points)
    session_range: float                # Today's RTH high - low
    atr_usage_pct: float                # session_range / atr_14d * 100
    atr_respected: bool                 # session_range <= atr_14d
    
    # ── Prior Day Levels ────────────────────────────────────────
    pdh: float                          # Prior Day High (RTH)
    pdl: float                          # Prior Day Low (RTH)
    pdc: float                          # Prior Day Close
    pd_mid: float                       # (PDH + PDL) / 2
    pd_range: float                     # PDH - PDL
    
    # ── Gap ─────────────────────────────────────────────────────
    session_open: float                 # First RTH bar open (09:30)
    gap_size_points: float              # session_open - pdc (signed)
    gap_size_pct: float                 # gap / pdc * 100
    gap_direction: str                  # "UP", "DOWN", "NONE" (threshold: ±0.05%)
    gap_size_bucket: str                # "NONE", "SMALL" (<0.25%), "MEDIUM" (0.25-0.5%), "LARGE" (>0.5%)
    gap_filled: bool                    # Did price reach pdc during session?
    gap_fill_time_minutes: float | None
    
    # ── Overnight / Globex ──────────────────────────────────────
    overnight_high: float               # ETH high between prior RTH close and today's RTH open
    overnight_low: float
    midnight_open: float                # Open of 00:00 ET candle
    
    # ── Open Location ───────────────────────────────────────────
    open_vs_pd_range: str               # "ABOVE_PDH", "INSIDE", "BELOW_PDL"
    open_vs_midnight: str               # "ABOVE", "BELOW"
    is_inside_day: bool                 # Today's developing range inside PD range
    is_outside_day: bool                # Opened outside PD range
    
    # ── Session Outcome (filled at end of day) ──────────────────
    session_close: float
    session_direction: str              # "GREEN" (close > open), "RED"
    pdh_broken: bool
    pdl_broken: bool
    both_pd_broken: bool                # Outside day — broke both PDH and PDL
    pdh_break_time_minutes: float | None
    pdl_break_time_minutes: float | None
    
    # ── Streaks ─────────────────────────────────────────────────
    streak_length: int                  # Consecutive same-direction days (including today)
    streak_direction: str               # "GREEN" or "RED"
    
    # ── Events ──────────────────────────────────────────────────
    is_event_day: bool
    event_type: str | None              # "FOMC", "CPI", "NFP", "OPEX", etc.
    is_opex_week: bool
    
    # ── Weekly Levels ───────────────────────────────────────────
    prior_week_high: float
    prior_week_low: float
    prior_week_close: float
    weekly_open: float                  # Monday's open
```

**Output:** `data/derived/daily_context.parquet` — one row per `(symbol, trading_date)`.

**All other modules join on this.** Macro records, range records, gap records, strategy
trades — they all carry `(symbol, trading_date)` and join to `daily_context` for any
context field they need. No module computes VIX, ATR, PDH/PDL, or gap data independently.

### 3.4 `lib/range_core.py` — Generic Range Computation

The reusable engine for computing H/L/Mid of any time window and tracking post-range
behavior. Used by both the macro module (existing) and the range module (new).

```python
def compute_range_hl(
    bars: pd.DataFrame,
    start_time: str,
    end_time: str,
    tz: str = "America/New_York",
) -> pd.DataFrame:
    """
    For each trading_date, compute range high, low, mid, open, close, width
    within the specified time window.
    """

def compute_extensions(
    bars: pd.DataFrame,
    range_high: float,
    range_low: float,
    levels: list[float] = [0.5, 1.0, 1.5, 2.0, 3.0],
    observe_until: str | None = None,
) -> dict:
    """
    For each extension level, determine:
      - hit_up: bool (price reached range_high + level * width)
      - hit_dn: bool (price reached range_low - level * width)
      - time_to_hit_up: float | None (minutes)
      - time_to_hit_dn: float | None (minutes)
    """

def compute_mr_metrics(
    bars: pd.DataFrame,
    range_high: float,
    range_low: float,
    range_mid: float,
) -> dict:
    """
    After first boundary break:
      - broke_high_first / broke_low_first
      - retest_mid: bool, time_minutes
      - retest_opposite: bool, time_minutes
      - failed_breakout: broke out then fully returned inside
    """
```

### 3.5 `lib/trade_simulator.py` — Strategy Simulation Engine

Generic entry/exit/MFE/MAE simulator. Consumes a `StrategyDefinition` and 1m bars,
produces `StrategyTrade` records. Used by the range module and eventually by the
backtest framework.

```python
def simulate_strategy(
    bars: pd.DataFrame,
    range_record: dict,       # H/L/Mid/width from any range type
    strategy: StrategyDefinition,
) -> StrategyTrade | None:
    """
    Walk bars after range close. Apply entry/exit rules.
    Return a StrategyTrade with entry, exit, P&L, MFE, MAE.
    Returns None if entry never triggered.
    """
```

### 3.6 `lib/filters.py` — Universal Filter & Subreport System

Every report type is sliceable by the same set of dimensions. This module
defines the filter system that all dashboards use.

```python
@dataclass
class FilterDimension:
    """A single filterable axis."""
    name: str                           # "day_of_week", "vix_regime", etc.
    display_name: str                   # "Day of Week"
    field: str                          # Column name in parquet
    type: str                           # "categorical", "numeric_bucket", "date_range"
    values: list[str] | None = None     # For categorical: ["Mon","Tue","Wed","Thu","Fri"]
    buckets: list[tuple] | None = None  # For numeric: [(0,15,"LOW"),(15,25,"NORMAL"),...]


# Universal dimensions available on ALL reports
UNIVERSAL_FILTERS = [
    FilterDimension("day_of_week", "Day of Week", "day_of_week", "categorical",
                    ["Mon","Tue","Wed","Thu","Fri"]),
    FilterDimension("vix_regime", "VIX Regime", "vix_regime", "categorical",
                    ["LOW","NORMAL","HIGH","EXTREME"]),
    FilterDimension("gap_direction", "Gap Direction", "gap_direction", "categorical",
                    ["UP","DOWN","NONE"]),
    FilterDimension("gap_size_bucket", "Gap Size", "gap_size_bucket", "categorical",
                    ["NONE","SMALL","MEDIUM","LARGE"]),
    FilterDimension("open_vs_pd_range", "Open Location", "open_vs_pd_range", "categorical",
                    ["ABOVE_PDH","INSIDE","BELOW_PDL"]),
    FilterDimension("is_event_day", "Event Day", "is_event_day", "categorical",
                    ["Yes","No"]),
    FilterDimension("atr_respected", "ATR Respected", "atr_respected", "categorical",
                    ["Yes","No"]),
    FilterDimension("lookback_days", "Lookback Period", "__lookback__", "date_range"),
]

# Module-specific filters added by each module
# e.g., range module adds: range_width_category, first_boundary_broken
# e.g., macro module adds: judas_direction, indicator_class
```

**Dashboard implementation:** Each dashboard panel renders filters from
`UNIVERSAL_FILTERS` + module-specific filters. The DuckDB-WASM query adds
`WHERE` clauses based on active filter selections. This is declarative —
adding a new filter dimension to any report requires zero dashboard code changes.

---

## 4. Module 1: ICT Macro Analytics (Existing — Enhancements)

### 4.1 Current State

Pipeline: `scripts/edgeful/` → `macro_records.parquet` + `fvg_detail.parquet`
Dashboard: `/research/macros/edgeful`

Computes: 27 macro windows/day across ES/NQ/YM/RTY/CL/GC. Per macro: H/L/Mid/Open,
Judas classification, indicator_class (Accum/Expansion/Manip via pivot breaks),
FVG detection, post-macro outcomes, inter-macro sequencing. Key finding: Manip→mid
retest at 58% win rate, 2.4:1 R:R, 10:50 ET primary window.

### 4.2 Enhancements to Apply

**4.2.1 Join to `daily_context.parquet` (HIGH priority, trivial effort)**

The macro pipeline currently has no VIX, no ATR, no gap, no PD level, no DOW
context. Fix: after computing macro records, join on `(symbol, trading_date)` to
`daily_context.parquet`. This instantly gives every macro record access to all
universal filter dimensions.

Fields added to each macro record via join:
`day_of_week`, `vix_regime`, `vix_close`, `atr_14d`, `atr_usage_pct`,
`gap_direction`, `gap_size_bucket`, `open_vs_pd_range`, `pdh`, `pdl`, `pdc`,
`midnight_open`, `is_event_day`, `event_type`, `streak_length`, `streak_direction`,
`session_direction` (was this a green or red day?)

**4.2.2 Extension Level Tracking (HIGH priority, medium effort)**

Currently tracks: `post_macro_max_up`, `post_macro_max_dn` (raw points).
Add: standardized extension levels as multiples of macro width.

```python
# New fields per macro record
macro_width: float                      # macro_high - macro_low
ext_up_50_hit: bool                     # Did price reach macro_high + 0.5 * width?
ext_up_50_time_minutes: float | None
ext_up_100_hit: bool
ext_up_100_time_minutes: float | None
ext_up_150_hit: bool
ext_up_200_hit: bool
ext_up_300_hit: bool
ext_dn_50_hit: bool                     # Mirror for downside
ext_dn_50_time_minutes: float | None
# ... (same pattern for 100, 150, 200, 300)
```

Implementation: Use `lib/range_core.compute_extensions()` — the macro pipeline
becomes the first consumer of the shared range engine.

**4.2.3 Rolling Lookback Window in Dashboard (HIGH priority, small effort)**

Add a date-range filter to the macro dashboard. Instead of "all time" stats, let
the user select last 30 / 90 / 180 / 365 days. Also show a time-series chart of
key probabilities (e.g., Manip→mid retest rate over rolling 90-day windows) so
the user can see whether the edge is stable, improving, or decaying.

**4.2.4 Prior Day Range Context on Macros (MEDIUM-HIGH priority, small effort)**

From `daily_context`, compute per macro:
- `macro_high_vs_pdh`: "ABOVE" | "BELOW" — did the macro range break PDH?
- `macro_low_vs_pdl`: "ABOVE" | "BELOW"
- `broke_pdh_during_macro`: bool
- `broke_pdl_during_macro`: bool

This enables questions like: "When a 10:50 macro expansion breaks PDH, how often
does price continue vs. reverse?" (Edgeful data suggests PDH breaks are 81%
continuation on YM.)

**4.2.5 Opening Candle Continuation Overlay (MEDIUM priority, small effort)**

From `daily_context`:
- `first_hour_direction`: "GREEN" | "RED" (IB close vs IB open)
- `macro_aligned_with_first_hour`: bool

Dashboard: split macro stats by alignment. Hypothesis: macros that fire in the
same direction as the first hour have higher continuation rates.

**4.2.6 Gap Context for AM Macros (MEDIUM priority, small effort)**

From `daily_context`: `gap_direction`, `gap_size_bucket`.
AM macros (9:50, 10:50) occurring during a gap-fill sequence may behave differently
from those on no-gap days. Dashboard filter already available via universal filters.

### 4.3 Macro-Specific Filters (in addition to universal)

```python
MACRO_FILTERS = [
    FilterDimension("judas_direction", "Judas Direction", "judas_direction",
                    "categorical", ["BULL","BEAR"]),
    FilterDimension("indicator_class", "Indicator Class", "indicator_class",
                    "categorical", ["ACCUM","EXPANSION","MANIP"]),
    FilterDimension("macro_window", "Macro Window", "macro_window",
                    "categorical"),  # Dynamic: NY_AM_1, NY_AM_2, etc.
    FilterDimension("session_group", "Session", "session_group",
                    "categorical", ["ASIA","LONDON","NY_AM","NY_PM"]),
]
```

---

## 5. Module 2: Time-Based Range Analytics (New)

### 5.1 RangeDefinition — The Atomic Unit

Every range type is an instance of this. Adding a new range is a config addition, not code.

```python
@dataclass
class RangeDefinition:
    name: str                          # "OR_5", "IB_60", "LUNCH", "ASIA"
    display_name: str                  # "5-Min Opening Range"
    start_time: str                    # "09:30" ET (HH:MM)
    end_time: str                      # "09:35" ET
    timezone: str = "America/New_York"
    session: str = "RTH"               # RTH, ETH, FULL
    
    formation_field: str = "hl"        # "hl" = high/low, "oc" = open/close only
    require_complete: bool = True      # Only compute if all bars in window exist
    
    extension_levels: list[float] = field(
        default_factory=lambda: [0.5, 1.0, 1.5, 2.0, 3.0])
    fib_levels: list[float] = field(
        default_factory=lambda: [0.0, 0.25, 0.5, 0.75, 1.0])
    
    observe_until: str | None = None   # "16:00" or None for end of session
    observe_minutes: int | None = None # Alternative: N minutes after close
```

### 5.2 Standard Presets

```python
RANGE_PRESETS = {
    # ── Opening Ranges ──────────────────────────────────────────
    "OR_5":  RangeDefinition("OR_5",  "5-Min Opening Range",  "09:30", "09:35"),
    "OR_15": RangeDefinition("OR_15", "15-Min Opening Range", "09:30", "09:45"),
    "OR_30": RangeDefinition("OR_30", "30-Min Opening Range", "09:30", "10:00"),
    
    # ── Initial Balance ─────────────────────────────────────────
    "IB_30": RangeDefinition("IB_30", "30-Min Initial Balance", "09:30", "10:00"),
    "IB_60": RangeDefinition("IB_60", "60-Min Initial Balance", "09:30", "10:30"),
    
    # ── Session Ranges ──────────────────────────────────────────
    "ASIA":    RangeDefinition("ASIA",    "Asia Range",    "20:00", "00:00", session="ETH"),
    "LONDON":  RangeDefinition("LONDON",  "London Range",  "03:00", "04:30", session="ETH"),
    "LUNCH":   RangeDefinition("LUNCH",   "Lunch Range",   "12:00", "13:30"),
    "NY_AM":   RangeDefinition("NY_AM",   "NY AM Range",   "09:30", "12:00"),
    "NY_PM":   RangeDefinition("NY_PM",   "NY PM Range",   "13:30", "16:00"),
    
    # ── Overnight ───────────────────────────────────────────────
    "OVERNIGHT": RangeDefinition("OVERNIGHT", "Overnight Range", "18:00", "09:30",
                                  session="ETH"),
    "PRIOR_DAY": RangeDefinition("PRIOR_DAY", "Prior Day RTH",  "09:30", "16:00"),
    
    # ── ICT-Specific ────────────────────────────────────────────
    "SILVER_BULLET_AM": RangeDefinition("SILVER_BULLET_AM", "AM Silver Bullet",
                                         "10:00", "11:00"),
    "SILVER_BULLET_PM": RangeDefinition("SILVER_BULLET_PM", "PM Silver Bullet",
                                         "14:00", "15:00"),
    "POWER_HOUR":       RangeDefinition("POWER_HOUR", "Power Hour",
                                         "15:00", "16:00"),
}
```

### 5.3 RangeRecord — Output Schema

One row per `(symbol, range_name, trading_date)`.

```python
@dataclass
class RangeRecord:
    # ── Identity ────────────────────────────────────────────────
    symbol: str
    range_name: str
    trading_date: date
    
    # ── Range Levels ────────────────────────────────────────────
    range_high: float
    range_low: float
    range_mid: float
    range_width: float                  # points
    range_width_pct: float              # width / mid * 100
    range_open: float                   # First bar open
    range_close: float                  # Last bar close
    
    # ── Range Classification ────────────────────────────────────
    range_width_pctile_20d: float       # Percentile vs prior 20 days (causal)
    range_width_pctile_50d: float
    range_width_category: str           # "NARROW" (<P25), "NORMAL", "WIDE" (>P75)
    
    # ── Directional Bias ────────────────────────────────────────
    close_vs_mid: str                   # "ABOVE" or "BELOW"
    close_pct_of_range: float           # 0=low, 1=high
    first_boundary_broken: str          # "HIGH" or "LOW"
    
    # ── Extension Hits (all directions) ─────────────────────────
    # Dynamically generated from extension_levels config
    # ext_{direction}_{level}_hit: bool
    # ext_{direction}_{level}_time_min: float | None
    
    # ── Post-Range Outcomes ─────────────────────────────────────
    max_excursion_up: float
    max_excursion_dn: float
    max_excursion_up_pct: float         # As % of range width
    max_excursion_dn_pct: float
    close_vs_range: str                 # "ABOVE", "INSIDE", "BELOW"
    
    # ── Mean Reversion Metrics ──────────────────────────────────
    broke_high_first: bool
    retest_mid_after_high_break: bool
    retest_mid_time_minutes: float | None
    retest_opposite_after_high_break: bool
    broke_low_first: bool
    retest_mid_after_low_break: bool
    retest_opposite_after_low_break: bool
    
    # ── Breakout Metrics ────────────────────────────────────────
    first_bo_direction: str             # "UP", "DOWN", "NONE"
    first_bo_held: bool                 # Stayed beyond for 2+ bars
    first_bo_retested_boundary: bool    # Any later bar retested the broken boundary
    first_bo_failed: bool               # Closed fully back inside range
    final_direction: str                # Which direction dominated by close
    
    # ── OR-Specific (populated only for OR range types) ─────────
    gap_type: str | None                # "GAP_UP_OUT", "GAP_DOWN_IN", etc.
    first_bar_direction: str | None
    first_bar_range_pct: float | None   # First bar range as % of OR width
    
    # ── Context (joined from daily_context) ─────────────────────
    # All DailyContext fields available via join.
    # Not stored redundantly — accessed at query time via DuckDB JOIN.
```

### 5.4 Range-Specific Filters

```python
RANGE_FILTERS = [
    FilterDimension("range_width_category", "Range Width", "range_width_category",
                    "categorical", ["NARROW","NORMAL","WIDE"]),
    FilterDimension("first_boundary_broken", "First Break", "first_boundary_broken",
                    "categorical", ["HIGH","LOW"]),
    FilterDimension("close_vs_mid", "Close vs Mid", "close_vs_mid",
                    "categorical", ["ABOVE","BELOW"]),
    FilterDimension("range_name", "Range Type", "range_name",
                    "categorical"),  # Dynamic from presets
]
```

---

## 6. Module 3: Daily Context Reports (New)

These are not time-based ranges but standalone daily reports. They compute
once per day and are stored in their own parquet files.

### 6.1 Gap Records (`gap_records.parquet`)

One row per `(symbol, trading_date)`. Detailed gap analysis beyond what
`daily_context` stores (which has basic gap fields).

```python
@dataclass
class GapRecord:
    symbol: str
    trading_date: date
    
    # Core gap
    gap_size_points: float
    gap_size_pct: float
    gap_direction: str
    gap_size_bucket: str
    
    # Gap fill
    gap_filled: bool
    gap_fill_time_minutes: float | None
    gap_fill_pct: float                 # What % of gap was filled
    
    # Spike before fill (entry timing)
    spike_size_points: float            # Max continuation before reversal
    spike_size_pct: float               # As % of gap size
    spike_time_minutes: float | None
    
    # Partial fills
    fill_25_pct: bool
    fill_50_pct: bool
    fill_75_pct: bool
    fill_25_time: float | None
    fill_50_time: float | None
    fill_75_time: float | None
```

### 6.2 Reference Level Records (`reference_levels.parquet`)

One row per `(symbol, trading_date)`. Tracks how price interacted with key
reference levels throughout the session.

```python
@dataclass
class ReferenceLevelRecord:
    symbol: str
    trading_date: date
    
    # Midnight Open retracement
    mop_retrace: bool                   # Did NY session price retrace to midnight open?
    mop_retrace_time_minutes: float | None
    mop_retrace_from: str               # "ABOVE" or "BELOW" — where price came from
    
    # PDH/PDL interaction
    pdh_broken: bool
    pdl_broken: bool
    pdh_break_continuation: bool        # After PDH break, session closed green?
    pdl_break_continuation: bool        # After PDL break, session closed red?
    pdh_break_time: float | None
    pdl_break_time: float | None
    
    # Inside/Outside day
    is_inside_day: bool
    is_outside_day: bool
    outside_day_reversal: bool          # Reversed back to touch PD boundary
    
    # Weekly
    weekly_open_retrace: bool
    prior_week_high_broken: bool
    prior_week_low_broken: bool
```

### 6.3 Opening Candle Continuation (`occ_records.parquet`)

One row per `(symbol, trading_date, candle_duration)`.

```python
@dataclass
class OCCRecord:
    symbol: str
    trading_date: date
    candle_duration_minutes: int        # 15, 30, 60
    
    first_candle_direction: str         # "GREEN" or "RED"
    first_candle_range: float
    first_candle_body_pct: float        # Body / total range (conviction)
    
    session_direction: str
    continuation: bool                  # first == session direction
    
    max_against: float                  # Max adverse move against first candle
```

### 6.4 Streak Records (`streak_records.parquet`)

One row per `(symbol, trading_date)`. Tracks consecutive day streaks.

```python
@dataclass
class StreakRecord:
    symbol: str
    trading_date: date
    session_direction: str
    streak_length: int
    streak_direction: str
    next_day_continuation: bool         # Did streak continue? (label for analysis)
```

---

## 7. Module 4: Strategy Simulation Engine (New)

### 7.1 StrategyDefinition

```python
@dataclass
class StrategyDefinition:
    name: str
    display_name: str
    entry_type: str                     # "MR" or "BO"
    
    # MR entry rules
    mr_trigger: str = "retest_boundary" # "retest_boundary", "retest_mid", "retest_fib"
    mr_fib_level: float = 0.5
    mr_confirmation_bars: int = 2
    
    # BO entry rules
    bo_trigger: str = "close_beyond"    # "close_beyond", "hold_N_bars"
    bo_hold_bars: int = 2
    bo_pullback_entry: bool = False
    
    # Target rules
    target_type: str = "extension"      # "extension", "fib", "opposite", "time", "next_range"
    target_extension: float = 1.0
    target_fib: float = 0.0
    target_minutes: int = 60
    
    # Stop rules
    stop_type: str = "range_based"      # "range_based", "atr_based", "opposite", "swing"
    stop_range_fraction: float = 0.25
    stop_atr_multiple: float = 1.5
    
    # Risk management
    cover_the_queen: bool = True
    ctq_fraction: float = 0.5
    trail_after_ctq: bool = True
    max_hold_minutes: int = 240
```

### 7.2 StrategyTrade — Output Schema

One row per `(symbol, range_name, strategy_name, trading_date)`.

```python
@dataclass
class StrategyTrade:
    symbol: str
    range_name: str
    strategy_name: str
    trading_date: date
    
    entry_triggered: bool
    entry_price: float | None
    entry_time: datetime | None
    entry_side: str | None              # "LONG" or "SHORT"
    entry_minutes_after_range: float | None
    
    exit_price: float | None
    exit_time: datetime | None
    exit_reason: str | None             # "TARGET", "STOP", "TIME_STOP", etc.
    exit_bar_check_order: str | None    # "STOP_ONLY", "TARGET_ONLY", "AMBIGUOUS_BOTH", ...
    ambiguous_bar: bool                 # True when stop+target touched on same bar
    
    pnl_points: float | None
    pnl_r_multiple: float | None
    initial_risk_points: float | None
    
    mfe_points: float | None
    mae_points: float | None
    mfe_pct_of_range: float | None
    mae_pct_of_range: float | None
    mfe_time_minutes: float | None
    mae_time_minutes: float | None


@dataclass
class SimulationPolicy:
    # Resolution for bars that hit both stop and target in the same OHLC bar.
    # "SPLIT" is the default research policy.
    ambiguous_bar_resolution: str = "SPLIT"  # "STOP_FIRST", "TARGET_FIRST", "SPLIT", "EXCLUDE"
```

### 7.3 Strategy Presets

```python
STRATEGY_PRESETS = {
    "MR_TO_MID":         StrategyDefinition("MR_TO_MID", "MR to Midpoint", "MR",
                           target_type="fib", target_fib=0.5,
                           stop_type="range_based", stop_range_fraction=0.25),
    
    "MR_TO_OPPOSITE":    StrategyDefinition("MR_TO_OPPOSITE", "MR to Opposite", "MR",
                           target_type="opposite",
                           stop_type="range_based", stop_range_fraction=0.5),
    
    "BO_1X":             StrategyDefinition("BO_1X", "Breakout 1x Extension", "BO",
                           target_type="extension", target_extension=1.0,
                           stop_type="opposite"),
    
    "BO_PULLBACK_1X":    StrategyDefinition("BO_PULLBACK_1X", "BO Pullback 1x", "BO",
                           bo_pullback_entry=True,
                           target_type="extension", target_extension=1.0,
                           stop_type="range_based", stop_range_fraction=0.5),
    
    "BO_TIME_HOLD":      StrategyDefinition("BO_TIME_HOLD", "BO Time Exit", "BO",
                           target_type="time", target_minutes=60,
                           stop_type="range_based", stop_range_fraction=0.5),
    
    "FAILED_BO_REVERSE": StrategyDefinition("FAILED_BO_REVERSE", "Failed BO Reversal", "MR",
                           mr_confirmation_bars=3, target_type="opposite",
                           stop_type="swing"),
}
```

---

## 8. Module 5: Cross-Report Confluence & Screener (Future)

### 8.1 Confluence Record

Computed daily after all modules run. Answers: "How many reports align today?"

```python
@dataclass
class DailyConfluenceRecord:
    symbol: str
    trading_date: date
    
    # Individual report probabilities (from historical data + today's conditions)
    gap_fill_probability: float
    or_breakout_probability: float
    ib_single_break_probability: float
    occ_continuation_probability: float
    mop_retrace_probability: float
    pdh_pdl_break_probability: float
    streak_reversal_probability: float
    
    # Combined
    reversal_confluence_count: int      # Reports aligning for reversal
    continuation_confluence_count: int  # Reports aligning for continuation
    dominant_bias: str                  # "BULLISH", "BEARISH", "NEUTRAL"
    confidence: str                     # "LOW" (1-2), "MEDIUM" (3), "HIGH" (4+)
```

### 8.2 "What's in Play" Screener

Dashboard at `/research/screener`. Morning prep tool:

1. Check today's gap → pull gap fill probabilities by size/direction/DOW
2. Check open location vs PD/MOP → pull reference level probabilities
3. Wait for OR/IB to form → pull breakout/MR probabilities
4. Check streak status → pull reversal/continuation bias
5. Display: which setups are active, which have >60% probability, which are confluent

---

## 9. Dashboard System

### 9.1 Shared Components

All dashboards use the same DuckDB-WASM + Next.js pattern:

**Filter Bar:** Renders from `UNIVERSAL_FILTERS` + module-specific filters. Persists
selections in URL params so dashboards are shareable/bookmarkable.

**Stats Panel:** N / Median / Mode / P25 / P75 / P90 / IQR — same format as
existing Edgeful macro dashboard.

**Distribution Chart:** Histogram with percentile markers. Reusable component.

**Probability Time Series:** Rolling-window probability line chart. Shows how a
stat evolves over time. Every probability should have this, not just a single number.

**Conditional Heatmap:** dimension × metric grid, color = value. Used for extension
probability curves, DOW × strategy win rate, etc.

### 9.2 Dashboard Pages

| Page | Path | Module | Priority |
|------|------|--------|----------|
| Macro Analytics | `/research/macros/edgeful` | Module 1 (enhanced) | EXISTS — enhance |
| Range Analytics | `/research/ranges` | Module 2 | Phase 4 |
| Gap Analysis | `/research/gaps` | Module 3 | Phase 4 |
| Reference Levels | `/research/levels` | Module 3 | Phase 5 |
| Strategy Simulator | `/research/strategies` | Module 4 | Phase 4 |
| Range Comparison | `/research/compare` | Module 2 | Phase 5 |
| Screener | `/research/screener` | Module 5 | Phase 6 |

### 9.3 Macro Dashboard Enhancement Specifics

Add to existing dashboard:
- Universal filter bar (DOW, VIX regime, gap, event day, lookback period)
- Extension probability panel (new)
- Rolling probability time series (new)
- PD level interaction panel (new)

---

## 10. Backtest Framework Enhancements

These apply to the existing quant backtest framework (`run_raw_analysis.py`, etc.):

### 10.1 Mandatory: Day-of-Week Conditional Tables

Add `day_of_week` to signal enrichment adapter. Include as a required grouping
dimension in all conditional table outputs.

### 10.2 Mandatory: Rolling Performance Windows

For every strategy, compute win rate / avg R:R / Sharpe / max DD over rolling
30-day and 90-day windows. Plot as time series. Flag when any metric crosses
a threshold (e.g., win rate drops below 50%).

### 10.3 Add: "By Performance" Measurement

For ORB/IB strategies, compute average breakout excursion using both wick-based
and close-based measurement. Edgeful's "by performance" subreport shows these
produce different targets (e.g., 0.4% by wick vs 0.3% by close on YM ORB).

### 10.4 Add: First-Boundary-Broken as Signal Context

For ORB/IB strategies, include `first_boundary_broken` in signal context.
Use as conditional table dimension. The "by rejection" insight — which side
formed first predicts breakout direction — is one of Edgeful's most
actionable findings.

### 10.5 Enhance: Event Type Granularity

Ensure signal adapter enriches with `event_type` ("FOMC", "CPI", "NFP", "OPEX")
not just `is_event_day` boolean. FOMC and CPI days produce structurally different
behavior and should be analyzed separately.

---

## 11. Implementation Plan

### Phase 1: Shared Infrastructure + Context (1-2 sessions)

**Goal:** Build the foundation everything else depends on.

- [ ] `lib/data_loader.py` — parquet loading with caching
- [ ] `lib/session_tagger.py` — session/DOW/trading_date tagging
- [ ] `lib/context.py` — `DailyContext` computation
- [ ] Generate `daily_context.parquet` for all symbols, all dates
- [ ] `lib/filters.py` — `FilterDimension`, `UNIVERSAL_FILTERS`
- [ ] Validate: spot-check 10 random days against TradingView

### Phase 2: Macro Pipeline Retrofit (1 session)

**Goal:** Enhance existing macro pipeline with shared context.

- [x] Join `macro_records` to `daily_context` on `(symbol, trading_date)`
- [x] Add extension level computation via `lib/range_core.compute_extensions()`
- [x] Add PD level interaction fields
- [x] Add OCC overlay field
- [x] Update macro dashboard: universal filter bar, extension panel, rolling lookback
- [x] Validate: compare macro stats with vs without DOW/VIX filters

### Phase 3: Range Pipeline Core (1-2 sessions)

**Goal:** Build OR/IB computation.

- [x] `lib/range_core.py` — generic range H/L/Mid, extensions, MR metrics
- [x] `scripts/ranges/compute_ranges.py` — generates `range_records.parquet`
- [x] Implement for OR_5, OR_15, OR_30, IB_60
- [x] Join to `daily_context`
- [x] Validate: spot-check 10 random days

### Phase 4: Strategy Simulation + Dashboard MVP (2-3 sessions)

**Goal:** Strategy simulation and first interactive dashboards.

- [x] `lib/trade_simulator.py` — generic entry/exit simulation
- [x] Generate `range_trades.parquet` for MR_TO_MID, BO_1X, BO_PULLBACK_1X
- [x] Dashboard: Range Profile panel (width distributions, bias)
- [x] Dashboard: Extension Probability panel (hit rates, conditional)
- [x] Dashboard: Strategy Simulator panel (win rate, R:R, equity curve)
- [x] Dashboard: Gap Analysis page (from `gap_records.parquet`)

### Phase 5: Daily Context Reports + Full Dashboard (2-3 sessions)

**Goal:** Complete the report library.

- [x] `gap_records.parquet` — gap fill, spike, partial fills
- [x] `reference_levels.parquet` — MOP, PDH/PDL, weekly
- [x] `occ_records.parquet` — opening candle continuation
- [x] `streak_records.parquet` — green/red streaks
- [x] Dashboard: Reference Levels page
- [x] Dashboard: Range Comparison page (OR_5 vs OR_15 vs IB_60)
- [x] Dashboard: Mean Reversion analytics panel

### Phase 6: Additional Ranges + Cross-Report (future)

- [ ] Add LUNCH, ASIA, OVERNIGHT, SILVER_BULLET, POWER_HOUR presets
- [ ] Market Session Breakout analysis (London → NY)
- [ ] `DailyConfluenceRecord` computation
- [ ] "What's in Play" screener dashboard
- [ ] GEX overlay on range boundaries (cross-system with options pipeline)

### Phase 7: Backtest Framework Integration (parallel)

**Can run in parallel with Phases 3-5.**

- [ ] Add `day_of_week` to signal enrichment adapter
- [ ] Add rolling performance window analysis
- [ ] Add "by performance" (wick vs close) measurement
- [ ] Add `first_boundary_broken` to ORB/IB signal context
- [ ] Add `event_type` granularity to signal adapter

---

## 12. Design Principles

1. **Shared context, computed once.** `daily_context.parquet` is the single source
   of truth for VIX, ATR, DOW, gap, PD levels. No module recomputes these.

2. **Configuration over code.** New ranges = `RangeDefinition`. New strategies =
   `StrategyDefinition`. New filters = `FilterDimension`. Zero code changes required.

3. **Causal-only computation.** No field uses future data. All percentiles and
   classifications are strictly backward-looking.

4. **Parquet-first, query at dashboard time.** Compute pipelines produce parquet.
    Dashboards query with DuckDB-WASM. Joins happen at read time, not write time.
    This means `range_records` stays lean and does not redundantly store context
    columns like VIX/ATR/gap/event data; those are joined from `daily_context`
    at query time. Keep only intrinsic denormalized fields required for standalone
    interpretability: `symbol`, `trading_date`, `day_of_week`, and range-native
    metrics such as `range_width_category`.

5. **Extension levels as universal language.** Every range type expresses post-range
   behavior in multiples of range width. This makes OR, IB, macros, and session
   ranges directly comparable.

6. **Rolling windows, not static numbers.** Every probability should be viewable
   as a time series over rolling windows. A single "all time" number hides regime
   dependence and edge decay.

7. **Subreports are first-class.** The filter system is declarative. Adding a new
   slicing dimension (e.g., "by VIX regime") works identically across all reports
   with zero per-report code.

8. **Strategies are simulations, not signals.** The trade simulator measures
   historical edge. Live execution is a separate system. The output is "historically,
   this rule produced X win rate and Y R:R" — you decide what to trade.

9. **Cross-system is the unique edge.** The GEX overlay, macro+range correlation,
   and options-derived regime classification are capabilities no commercial platform
   offers. The architecture should make cross-system joins trivial.

10. **Match the existing pattern.** Same directory structure, same parquet output,
    same DuckDB-WASM dashboard, same stats panel format as the existing Edgeful
    macro system. Consistency reduces cognitive load and build time.
