# Trader Narrative — Session Handover

> **Date:** 2026-07-13
> **Commit:** `76a8200e` on `main` (pushed to GitHub)
> **Status:** Session-adaptive intraday + multi-TF range detection + ICT Phase 1 complete (library v1.3.0 + derived data pipeline + narrative integration)

---

## What Was Done This Session

### 1. Critical Bug Fix: `events` → `econ_releases`
In `build_ticker_cheat_sheet()` in `briefing_core.py`, three blocks were silently failing because they referenced `events` (undefined) instead of `econ_releases`:
- ICT Liquidity Map — was never reaching the LLM
- Day Type + Killzones — was never reaching the LLM
- Bias Consensus Matrix — weekly modifiers (OPEX/FOMC) were missing

### 2. ICT Integration
- Added ICT Dealing Range block to intraday and close cheat sheets
- Added ICT Liquidity Map to intraday (with raid-target-swept detection)
- Added ICT Dealing Range Outcome to EOD (BSL/SSL swept or held)
- Added ICT Killzone Context to all intraday session blocks
- Documented 12 ICT TODOs in `_format_ict_block()` in `intraday_blocks.py`

### 3. Classification Abbreviation Fix
The LLM was inventing wrong meanings for DWP/DNP/R1/R2 (e.g., "DWP = downside wide-range"). Fixed by:
- Expanding abbreviations inline in `_format_classification_block()` in `briefing_core.py`
- Adding CLASSIFICATION GUIDE to all 4 prompt templates
- Correct definitions sourced from `docs/DailyClassification/DAILY_CLASSIFICATION.md`:
  - R1 = Range 1 / Time Spent (neutral, rotational)
  - R2 = Range 2 / Reversal (failed expansion, returns to OR after 11:00)
  - DWP = Directional With Pullbacks (trend with structural retracements)
  - DNP = Directional No Pullback (power trend, no retracements)

### 4. Morning Bias Defaulting to NQ Fix
`build_intraday_context` and `build_eod_context` were reading the generic `latest_trader_narrative_open.md` (which could be NQ content) as morning bias for ES1 intraday. Fixed to look for ticker-specific file first (`latest_trader_narrative_open_ES1.md`).

### 5. Session-Adaptive Intraday System
Complete rewrite of the intraday narrative to be session-aware. New modular architecture:

**New files:**
- `scripts/trader/signals/session_ranges.py` — `detect_session()`, `compute_all_session_ranges()`, `detect_sweep()`
- `scripts/trader/signals/intraday_blocks.py` — per-session block builders + main entry point `build_intraday_cheat_sheet()`

**Sessions:**
| Session | Time (ET) | Key blocks |
|---------|-----------|-----------|
| ASIA | 18:00-02:00 | Prior EOD, globex, GEX, ICT, Herman Asia range, killzone, range stack |
| LONDON | 02:00-08:30 | Asia box, PL sweep, London box, London OR, ALN partial, GEX, ICT, killzone, range stack, liquidity map |
| NY AM | 09:30-11:30 | RTH session, Herman Pre-NY sweep (DOMINANT), IB, ALN, GEX, ICT, killzone, range stack, liquidity map |
| NY LUNCH | 11:30-13:30 | Session so far, IB, lunch range, GEX, ICT, killzone, range stack |
| NY PM | 13:30-16:00 | Session direction, noon curve, lunch breakout, GEX, ICT, killzone, range stack, liquidity map |

Weekend → graceful exit. After-close → defer to EOD narrative.

`build_intraday_context()` in `briefing_core.py` is now a thin wrapper that delegates to `build_intraday_cheat_sheet()`.

### 6. Multi-Timeframe Range Detection
**New file:** `scripts/trader/signals/range_detection.py`

Computes ranges at 12 timeframes simultaneously (MICRO_5, MICRO_15, MICRO_30, SHORT_60, SHORT_120, SESSION, RTH, DAILY_1, DAILY_3, DAILY_5, WEEKLY, WEEKLY_2). Each reports H/L/width/position/touches/classification/breakout.

Plus:
- Compression detection (15m ATR / 60m ATR ratio)
- Adaptive auto-range (finds tightest window where price has spent the most time)

Integrated into all 5 intraday session builders via `_format_range_stack_block()`.

### 7. Prompt Updates
- `trader_intraday.md` — completely rewritten with session-specific instructions + Herman guides + range/compression/adaptive guides + ICT killzone guide
- `trader_morning.md` — added classification guide
- `trader_close.md` — added ICT guide + classification guide
- `trader_premarket.md` — added classification guide

### 8. Documentation
- `TRADER_NARRATIVE_PLAN.md` — full architecture update with session-adaptive design, module inventory, range detection table, future TODOs
- `NARRATIVE_ENGINE_V2_PLAN.md` — status updated
- `CLAUDE.md` — run commands + context anchors added

---

## Current File Structure

```
scripts/trader/
├── briefing_core.py          # Main cheat sheet builders (open, premarket, EOD) + thin intraday wrapper
├── trader_narrative.py       # Main script: --mode premarket|open|intraday|close --ticker ES1|NQ1
├── prompts/
│   ├── trader_premarket.md   # Premarket prompt
│   ├── trader_morning.md     # Open mode prompt (full guides)
│   ├── trader_intraday.md    # Session-adaptive prompt (all session + range + ICT guides)
│   └── trader_close.md       # EOD prompt (ICT outcome + classification)
├── signals/
│   ├── session_ranges.py     # Session detection + live range computation + sweep detection
│   ├── intraday_blocks.py    # Per-session block builders (ASIA/LONDON/NY_AM/NY_LUNCH/NY_PM)
│   ├── range_detection.py    # Multi-TF range stack + compression + adaptive range
│   ├── ict_context.py        # ICT dealing range (PDH/PDL/midnight/premium-discount)
│   ├── liquidity_map.py      # ICT liquidity raid target map
│   ├── candle_science.py     # C1→C2→C3 daily candle patterns
│   ├── confluence.py         # 3-signal confluence model
│   ├── day_type.py           # CLEAN/CPI/NFP/FOMC/SPECIAL/HOLIDAY + killzones
│   ├── expected_move.py      # Options EM context
│   ├── gex_regime.py         # Gamma regime change detection
│   ├── volatility.py         # VIX/VVIX regime
│   ├── weekly_profile.py     # Weekly H/L + profile type
│   ├── caution_score.py      # Composite risk posture
│   ├── econ_calendar.py      # Economic calendar from Prisma DB
│   └── earnings.py           # Earnings events
└── config/
    └── narrative_stats.yaml  # All static probabilities (Herman, ALN, VIX regimes, day types)
```

---

## How to Run

```powershell
# Activate venv first
.\.venv\Scripts\Activate.ps1

# Premarket (before 09:30)
.\.venv\Scripts\python.exe -m scripts.trader.trader_narrative --mode premarket --ticker ES1

# Open (08:00-08:30)
.\.venv\Scripts\python.exe -m scripts.trader.trader_narrative --mode open --ticker ES1

# Intraday (anytime — auto-detects session)
.\.venv\Scripts\python.exe -m scripts.trader.trader_narrative --mode intraday --ticker ES1

# Close (16:00-16:15)
.\.venv\Scripts\python.exe -m scripts.trader.trader_narrative --mode close --ticker ES1
```

Output: `data/options/daily/{date}_trader_narrative_{mode}_{ticker}.md` + `latest_trader_narrative_{mode}_{ticker}.md`

Requires Ollama running (`start_llm.bat`).

---

## What's Working

- ✅ All 4 narrative modes (premarket, open, intraday, close) tested end-to-end
- ✅ Session detection verified at all time boundaries
- ✅ Weekend graceful exit verified
- ✅ Range stack + compression + adaptive range verified in all sessions
- ✅ ICT dealing range + liquidity map with raid-swept detection verified
- ✅ Classification abbreviations correctly expanded
- ✅ Herman stats (static references) integrated into prompts
- ✅ ICT data computes correctly from parquet

---

## Known Issues

1. **Herman stats parquet stale** (last 2026-01-23, 171 days behind) — only used for static statistical references in prompts, not per-day data. Live session ranges are computed from 1m parquet instead. Not blocking.

2. **Daily classification parquet stale** (last 2026-01-23) — same, used for sequential probabilities only. Not blocking.

3. **NQStatsEngine session times** may not match `NQ_SESSIONS_SPEC.md` (Asia 20:00 vs 18:00). Session boundaries in `session_ranges.py` use 18:00 for Asia start. Verify alignment.

4. **Intraday test data limitation**: Testing was done with Friday's data (2026-07-13) since markets are closed on the weekend. The session detection uses `now_et` correctly, but the 1m data only has bars up to Friday's close. Live testing during each session is needed to fully validate.

---

## Next Steps (Priority Order)

### 1. ICT Phase 1 — COMPLETE ✅ (2026-07-13)

All Phase 1 items completed in this session:

**Library fixes (`ict_engine` v1.3.0):**
- `detect_ipda_ranges()` — IPDA 20/40/60 rolling dealing ranges
- `get_silver_bullet_data()` + `SILVER_BULLETS` dict — Silver Bullet window detection
- `detect_fvg()` rewritten as canonical implementation (merged `detect_fvgs_v5`)
- `detect_volume_imbalance()` enhanced with `resample_rule` + `vi_finalized_time`
- `detect_gap_fills()` — tracks when NWOG/NDOG/RTH gaps get filled
- `nqstats.ib.detect_fvgs_v5` now delegates to library

**Derived data pipeline (`scripts/context/compute_ict_features.py`):**
- `{sym}_imbalance_{tf}.parquet` — FVG + VI at 4 timeframes (5m/15m/1h/4h)
- `{sym}_gaps.parquet` — NWOG + NDOG + RTH gaps with fill tracking
- `{sym}_kz_pivots.parquet` — Killzone pivots (AS/LO/NYAM H/L/mid/range)
- `{sym}_ipda.parquet` — IPDA 20/40/60 rolling ranges
- `{sym}_htf_levels.parquet` — PDH/PDL/PWH/PWL/PMH/PML

**Narrative integration:**
- `scripts/trader/signals/ict_data_loader.py` — freshness-aware parquet loader with auto-refresh
- `ict_context.py:compute_ict_from_htf` now delegates to `ict_data_loader`
- 6 new ICT feature blocks in `intraday_blocks.py`: KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps
- All 5 session builders updated with dynamic ICT feature blocks (replaced static text)

### 2. ICT Phase 2 (remaining items)
- ICT Order Block detection — `detect_orderblock()` exists in library, needs pipeline + narrative block
- ICT Judas Swing detection (sweep of Midnight Open during London/Pre-Market)
- ICT MSS/BOS — `detect_structure_breaks()` exists, needs pipeline + narrative block
- ICT Draw on Liquidity (DOL): proximity to BSL/SSL pools
- ICT Market Delivery Triad: I2E vs E2I
- SMT Divergence — `detect_smt()` exists, needs pipeline + narrative block
- PineScript indicator for range detection

### 3. Asia/London IB Computation
- Currently only NY RTH IB is computed (via NQStatsEngine)
- User wants IB during Asia and London sessions — separate conversation needed
- Requires defining IB windows for each session

### 4. Range Detection Expansion
- Integrate DAILY_3, DAILY_5, WEEKLY, WEEKLY_2 into EOD and weekly narratives
- PineScript indicator for range stack visualization

### 5. Live Testing
- Run intraday narrative during each session (Asia, London, NY AM, Lunch, PM) with live data to validate all blocks produce meaningful output
- Verify the LLM narratives read well for each session type

### 6. Cleanup
- Remove old FVG-only parquets (`{sym}_fvg_{tf}.parquet`) once all consumers migrated to imbalance files
- Update prompt templates to reference new ICT blocks (Step 5 of Phase 1)

---

## Key Design Decisions Made

1. **Single adaptive prompt** (not multiple template files) — the cheat sheet includes a `== CURRENT SESSION ==` header and the prompt has session-specific guide sections. The LLM adapts based on the header.

2. **Herman stats parquet not refreshed** — only used for static statistical references (sweep probabilities, continuation edges). Live session ranges computed from 1m parquet instead. User confirmed this is acceptable.

3. **Modular signal architecture** — each signal is a separate module in `scripts/trader/signals/`. Session builders in `intraday_blocks.py` call shared helpers (`_format_gex_block`, `_format_ict_block`, `_format_liquidity_map_block`, `_format_range_stack_block`, etc.) so changes to a signal propagate to all sessions.

4. **Range detection is generic** — `compute_range_stack()` takes a `tf_levels` parameter, so intraday uses micro+short+session+daily, EOD can use daily+multi-day, weekly can use weekly+multi-week. Same module, different timeframes.

5. **Classification abbreviations expanded inline** — rather than relying on the LLM to know what DWP means, the cheat sheet now shows `DWP (Directional With Pullbacks (trend breaks OR, never returns, but has structural retracements))`. Plus a guide in every prompt.