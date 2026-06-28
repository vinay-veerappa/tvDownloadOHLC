# Handover: Daily Briefing System

**Date**: 2026-06-27
**Session Goal**: Build a DB-first macro briefing system with weekly + daily (Open/EOD) narratives.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    DATA SOURCES                          │
│  unified_levels.json        (live, latest pipeline)      │
│  unified_levels_open.txt     (RTH open snapshot)         │
│  unified_levels_close.txt    (RTH close snapshot)        │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│              STAGE 1: AGGREGATION                        │
│                                                          │
│  weekly_briefing.py   → Prisma DB (WeeklyBriefing)       │
│  daily_eod_update.py  → Prisma DB (DailyEodUpdate)       │
│    --session open|eod|live                               │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│              STAGE 2: NARRATIVE                          │
│                                                          │
│  weekly_narrative.py  → Ollama LLM → DB + Discord + Disk │
│  daily_narrative.py   → (PENDING — not yet created)     │
└─────────────────────────────────────────────────────────┘
```

---

## File Inventory

### Core Library
| File | Status | Purpose |
|------|--------|---------|
| `scripts/trader/briefing_core.py` | ✅ Working | Shared library: data loaders, DB helpers, price context, track alignment, level interactions |
| `scripts/trader/weekly_briefing.py` | ✅ Working | Stage 1: Weekly aggregation into DB |
| `scripts/trader/weekly_narrative.py` | ✅ Working | Stage 2: Weekly LLM narrative + Discord delivery |
| `scripts/trader/daily_eod_update.py` | ✅ Updated | Stage 1: Daily aggregation (Open/EOD) into DB |
| `scripts/trader/daily_narrative.py` | ❌ NOT CREATED | Stage 2: Daily LLM narrative (PENDING) |

### Prompts
| File | Status | Purpose |
|------|--------|---------|
| `scripts/trader/prompts/weekly_briefing.md` | ✅ Working | Weekly briefing LLM prompt template |
| `scripts/trader/prompts/daily_eod_update.md` | ✅ Working | Daily EOD progress check prompt template |
| `scripts/trader/prompts/daily_open_update.md` | ❌ NOT CREATED | Daily Open narrative prompt (PENDING) |

### Data Files
| File | Location | Purpose |
|------|----------|---------|
| `unified_levels.json` | `data/options/current/` | Live pipeline output (JSON, all tickers) |
| `unified_levels_open.txt` | `data/options/current/` | RTH open snapshot (tokenized text) |
| `unified_levels_close.txt` | `data/options/current/` | RTH close snapshot (tokenized text) |

---

## Key Functions in `briefing_core.py`

### Data Loaders
- **`load_macro_levels(session="live"|"open"|"close")`** (line ~334)
  - `"live"` → reads `unified_levels.json` (JSON format)
  - `"open"` → reads `unified_levels_open.txt` (tokenized text via `load_unified_levels_txt`)
  - `"close"` → reads `unified_levels_close.txt` (tokenized text via `load_unified_levels_txt`)
  - Returns: `{"SPX": {ticker, line, tokens, ...}, "QQQ": {...}, ...}`

- **`load_unified_levels_txt(txt_path)`** (line ~268)
  - Parses the tokenized `.txt` format into the same dict structure as the JSON loader
  - Extracts `META_*` fields and token lines

- **`parse_meta_fields(unified_entry)`** (line ~207)
  - Extracts `META_REGIME`, `META_GEX`, `META_SPOT`, etc. from the unified entry

### Price Context
- **`load_daily_price_context(loader, ticker)`** (line ~534)
  - Returns today's OHLC + change_pct + range_pct + body classification
- **`load_weekly_price_context(loader, ticker)`** (line ~455)
  - Returns weekly OHLC context

### Analysis
- **`compute_level_interactions(today, call_wall, put_wall, em_upper, em_lower, zero_gamma, gamma_magnet)`** (line ~619)
  - Returns dict of tested/broken flags for each level
- **`assess_track_alignment(track, today, interactions)`** (line ~580)
  - Returns `(on_track: bool, assessment: str)`
- **`compute_weekly_ems(unified_entry, spot)`** (line ~358)
  - Computes per-day EM envelope using sqrt(time) scaling
  - Returns `{"monday": {"upper", "lower", "em"}, ...}`

### DB Helpers
- **`load_weekly_briefing_from_db(week_start=None)`** (line ~865)
  - Loads the latest (or specified) weekly briefing from Prisma DB
  - Returns `{"meta": {...}, "tickers": [...]}`
- **`save_daily_eod_to_db(eod_date, weekly_briefing_id, ticker_snapshots)`** (line ~988)
  - Upserts DailyEodUpdate + DailyEodTickerSnapshot rows
  - Uses upsert so re-running for the same date updates in place
- **`save_narrative_to_db(briefing_id, summary, is_daily=False)`**
  - Stores the LLM narrative back in the DB

---

## `daily_eod_update.py` — Current State

**Status**: ✅ Updated to support `--session open|eod|live`

### CLI
```bash
# EOD session (default)
python -m scripts.trader.daily_eod_update --session eod

# Open session
python -m scripts.trader.daily_eod_update --session open

# Live session
python -m scripts.trader.daily_eod_update --session live

# Custom tickers
python -m scripts.trader.daily_eod_update --session open --tickers SPX QQQ NVDA
```

### Session → File Mapping
| `--session` | `load_macro_levels(session=)` | File loaded |
|-------------|------------------------------|------------|
| `open` | `"open"` | `unified_levels_open.txt` |
| `eod` | `"close"` | `unified_levels_close.txt` |
| `live` | `"live"` | `unified_levels.json` |

### Flow
1. Load latest weekly briefing from DB (the anchor)
2. Load current unified levels based on session
3. Initialize DataLoader (10-day lookback)
4. Compute days elapsed/remaining in week
5. Build per-ticker snapshots (price, level interactions, track alignment, invalidation proximity)
6. Save to DB via `save_daily_eod_to_db`

### `build_daily_snapshot()` Output Dict
```python
{
    "ticker": "SPX",
    "open_price": ..., "high_price": ..., "low_price": ..., "close_price": ...,
    "change_pct": ..., "range_pct": ..., "body": "bullish"|"bearish"|"neutral",
    "mandated_track": "MOMENTUM_LONG",
    "call_wall": ..., "put_wall": ...,
    "today_em_upper": ..., "today_em_lower": ...,
    "call_wall_tested": bool, "call_wall_broken": bool,
    "put_wall_tested": bool, "put_wall_broken": bool,
    "em_upper_tested": bool, "em_upper_broken": bool,
    "em_lower_tested": bool, "em_lower_broken": bool,
    "bullish_invalidation": ..., "bearish_invalidation": ...,
    "dist_to_bullish_inv_pct": float, "dist_to_bearish_inv_pct": float,
    "on_track": bool, "track_assessment": str,
    "weekly_regime": str, "current_regime": str, "regime_changed": bool,
    "position_in_em_envelope": float|None,  # 0.0–1.0
    "days_elapsed_in_week": int, "days_remaining_in_week": int,
}
```

---

## Pending Tasks

### Task 1: Create `daily_narrative.py`

**Purpose**: Stage 2 for daily narratives. Reads daily EOD data from DB, calls Ollama LLM, delivers to Discord.

**Pattern to follow**: Mirror `weekly_narrative.py` structure exactly.

**Key differences from weekly_narrative.py**:
- Load daily EOD data from DB instead of weekly briefing
- Use `daily_eod_update.md` prompt (for EOD session) or `daily_open_update.md` prompt (for Open session)
- Write output to `data/options/daily/` instead of `data/options/weekly/`
- Discord webhook key: `macro-alerts` (same channel)
- Add `--session open|eod` CLI arg to select prompt + DB query

**Suggested structure**:
```python
"""
daily_narrative.py
Stage 2: Daily LLM Narrative Generator (Open & EOD).

Usage:
    python -m scripts.trader.daily_narrative --session eod [--model gemma4:31b-cloud] [--discord]
    python -m scripts.trader.daily_narrative --session open [--model gemma4:31b-cloud] [--discord]
"""
from scripts.trader.briefing_core import (
    REPO_ROOT,
    # Need: load_daily_eod_from_db (or similar DB reader for DailyEodUpdate)
    # Need: save_daily_narrative_to_db (or reuse save_narrative_to_db with is_daily=True)
)

PROMPT_PATHS = {
    "open": REPO_ROOT / "scripts" / "trader" / "prompts" / "daily_open_update.md",
    "eod":  REPO_ROOT / "scripts" / "trader" / "prompts" / "daily_eod_update.md",
}
DAILY_OUTPUT_DIR = REPO_ROOT / "data" / "options" / "daily"

# Reuse: call_ollama(), send_discord_summary(), write_summary_to_disk()
# (copy from weekly_narrative.py or factor into briefing_core.py)
```

**Missing DB helper**: Need a `load_daily_eod_from_db(date)` function in `briefing_core.py` that reads the latest DailyEodUpdate + its ticker snapshots. This does NOT exist yet — must be created.

### Task 2: Create `daily_open_update.md` prompt

**Purpose**: LLM prompt for the RTH Open narrative (morning session).

**Difference from `daily_eod_update.md`**:
- Focus on the **opening setup** rather than end-of-day progress
- Emphasize: where price opened relative to weekly levels, initial level interactions, track setup for the day
- De-emphasize: invalidation proximity (less relevant at open), days elapsed
- Add: "Key levels to watch today" section based on open position

**Template**: Copy `daily_eod_update.md` and modify:
- Change title from "EOD PROGRESS CHECK" to "RTH OPEN SETUP"
- Change "Where price closed" → "Where price opened"
- Change "Tomorrow's Focus" → "Today's Focus"
- Add section for "Opening Range Assessment" if available

### Task 3: Add `load_daily_eod_from_db()` to `briefing_core.py`

**Purpose**: Read the latest DailyEodUpdate + ticker snapshots from Prisma DB.

**Pattern**: Mirror `load_weekly_briefing_from_db()`.

```python
async def load_daily_eod_from_db(target_date: date | None = None) -> dict | None:
    """Load the latest (or specified) daily EOD update from DB.
    
    Returns:
        {"meta": {id, date, weekly_briefing_id, ...}, 
         "tickers": [{ticker, close_price, ...}, ...]}
    """
    db = await get_db()
    # Query DailyEodUpdate by date (latest if None)
    # Include ticker snapshots via relation
    # Return structured dict
```

---

## Bug Fix Applied This Session

### `briefing_core.py` — Lost function definition
**Problem**: During earlier edit to remove duplicate `load_macro_levels`, the `def compute_weekly_ems(...)` line was accidentally deleted, leaving an orphaned docstring + body at lines 359-413.

**Fix applied**: Restored the function signature:
```python
def compute_weekly_ems(unified_entry: dict, spot: float) -> dict:
    """Compute per-day EM envelope from the weekly EM tokens.
    ...
    """
```

**Verify**: Run `python -c "from scripts.trader.briefing_core import compute_weekly_ems; print('OK')"` to confirm no syntax errors.

---

## How to Run (Current State)

### Weekly cycle (Friday or weekend)
```bash
# 1. Aggregate weekly data into DB
python -m scripts.trader.weekly_briefing

# 2. Generate weekly narrative via LLM + send to Discord
python -m scripts.trader.weekly_narrative --model gemma4:31b-cloud
```

### Daily cycle (RTH Open ~09:45 ET)
```bash
# 1. Aggregate open snapshot into DB
python -m scripts.trader.daily_eod_update --session open

# 2. Generate open narrative (PENDING — daily_narrative.py not yet created)
# python -m scripts.trader.daily_narrative --session open
```

### Daily cycle (RTH Close ~16:00 ET)
```bash
# 1. Aggregate EOD snapshot into DB
python -m scripts.trader.daily_eod_update --session eod

# 2. Generate EOD narrative (PENDING — daily_narrative.py not yet created)
# python -m scripts.trader.daily_narrative --session eod
```

---

## Prisma DB Schema

### WeeklyBriefing
- `id`: String (cuid)
- `weekStart`: DateTime
- `weekEnd`: DateTime
- `summaryMd`: String? (LLM narrative stored here)
- `tickers`: WeeklyBriefingTicker[]

### WeeklyBriefingTicker
- `ticker`, `spotPrice`, `weeklyChangePct`
- `gexRegime` (JSON), `mandatedExecutionTrack`
- `keyLevels` (JSON: call_wall, put_wall, zero_gamma, gamma_magnet)
- `expectedMove` (JSON: upper, lower, straddle_pct)
- `accountInvalidation` (JSON: bullish, bearish, mandate)
- `weeklyEms` (JSON: per-day EM envelope)

### DailyEodUpdate
- `id`: String (cuid)
- `date`: DateTime
- `weeklyBriefingId`: String? (FK to WeeklyBriefing)
- `tickersCovered`: Int
- `generatedAt`: DateTime
- `tickerSnapshots`: DailyEodTickerSnapshot[]

### DailyEodTickerSnapshot
- `id`, `eodUpdateId` (FK)
- `ticker`, `openPrice`, `highPrice`, `lowPrice`, `closePrice`
- `changePct`, `rangePct`, `body`
- `mandatedTrack`, `callWall`, `putWall`
- `todayEmUpper`, `todayEmLower`
- `callWallTested/Broken`, `putWallTested/Broken`
- `emUpperTested/Broken`, `emLowerTested/Broken`
- `bullishInvalidation`, `bearishInvalidation`
- `distToBullishInvPct`, `distToBearishInvPct`
- `onTrack`, `trackAssessment`
- `weeklyRegime`, `currentRegime`, `regimeChanged`
- `positionInEmEnvelope` (Float?)
- `daysElapsedInWeek`, `daysRemainingInWeek`

---

## Key Design Decisions

1. **DB as single source of truth**: All data flows through Prisma DB. No file-based state.
2. **Session-based data loading**: `load_macro_levels(session=...)` routes to the correct file (JSON for live, TXT for open/close).
3. **GEX DA sanity check**: In `weekly_briefing.py`, if `ZERO GEX DA` is >20% from spot, falls back to `ZERO GEX` or `MAGNET`.
4. **ETF-scale values**: `file_writer.py` prioritizes `cash_levels` over translated futures levels to avoid the translation bug.
5. **Token matching**: `_find_token` uses exact label matching to avoid `ZERO GEX` matching when `ZERO GEX DA` is intended.
6. **Ollama models**: Primary = `gemma4:31b-cloud`, Fallback = `glm-5.2:cloud`.
7. **Discord delivery**: All narratives sent to `macro-alerts` webhook channel.

---

## ADR Compliance Notes
- **ADR-001**: All times in ET. `briefing_core.py` uses `ZoneInfo("America/New_York")`.
- **ADR-002**: All performance metrics as percentages (`change_pct`, `range_pct`, `dist_to_*_inv_pct`).
- **ADR-017**: No `for` loops in calculation paths (vectorized Pandas/NumPy). `daily_eod_update.py` uses a loop over tickers but only for orchestration, not calculation.
- **ADR-018**: Visual compliance not applicable (no chart indicators in this system).
- **ADR-020**: Prop firm liquidation rules not directly applicable to briefing system.
- **ADR-021**: Not applicable (no prop firm simulation in briefing system).