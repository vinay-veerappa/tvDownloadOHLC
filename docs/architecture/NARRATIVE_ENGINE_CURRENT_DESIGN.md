# Narrative Engine — Current Design & Status

**Last updated:** 2026-07-23
**Supersedes:** `NARRATIVE_ENGINE_ARCHITECTURE.md`, `NARRATIVE_ENGINE_V2_PLAN.md`,
`NARRATIVE_ENGINE_V2_BUILD_PLAN.md`, `NARRATIVE_ENGINE_V2_ARCHITECTURE.md`,
`NARRATIVE_AUDIT_2026-07-14.md`, `NARRATIVE_FEEDBACK_LOOP.md`
(Those docs are kept for historical reference but this is the canonical current-state doc.)

---

## 1. What the narrative engine does

Generates trader-facing briefs from pre-computed data + KB knowledge:

| Narrative | Schedule | Prompt | Output | Data source |
|---|---|---|---|---|
| **Premarket** | Before 09:30 ET | `trader_premarket.md` | `data/options/daily/latest_trader_narrative_premarket_*.md` | `build_premarket_context()` |
| **Open** | 09:30 ET | `trader_morning.md` | `data/options/daily/latest_trader_narrative_open_*.md` | `build_ticker_cheat_sheet(mode=open)` |
| **Intraday** | On-demand / 12:00 | `trader_intraday.md` | `data/options/daily/latest_trader_narrative_intraday_*.md` | `build_intraday_context()` — session-adaptive |
| **Close** | 16:00 ET | `trader_close.md` | `data/options/daily/latest_trader_narrative_close_*.md` | `build_eod_context()` |
| **Weekly** | Friday 17:10 ET | `weekly_briefing.md` | `data/options/weekly/latest_summary.md` | `build_weekly_cheat_sheet()` + `build_weekly_static_template()` |
| **Daily open/EOD** | 09:30 / 16:15 | `daily_open_update.md` / `daily_eod_update.md` | DB `summaryMd` + `data/options/daily/` | `daily_narrative.py` — JSON slot-filling |

All daily trader narratives use free-form prose. Weekly and daily open/EOD use JSON slot-filling.

---

## 2. Architecture

```
Data Sources                     Cheat Sheet Builder              LLM Prompt              Output
─────────────                    ───────────────────              ──────────              ──────
Live storage parquet ──► build_premarket_context() ──┐
                         build_ticker_cheat_sheet()  │
                         build_intraday_context()   │    trader_premarket.md
                         build_eod_context()        ├──► + KB context  ──► Ollama ──► Markdown
Unified levels JSON ──►  load_macro_levels()         │    trader_morning.md
                         load_unified_levels_txt()   │    trader_intraday.md
                         _extract_gex_levels()      │    trader_close.md
                                                     │
KB API (port 8900) ──►  fetch_kb_context()  ────────┤
                         (57 concept triggers)       │
                                                     │
Herman/NQStats ──►      compute_herman_pre_ny_sweep()│
                         compute_all_session_ranges()│
                         NQStatsEngine               │
                                                     │
Daily classification ──► analyze_daily_classification│
                                                     │
ICT features ──►        _format_kz_pivots_block()    │
                         _format_ipda_block()        │
                         _format_gaps_block()        │
                         _format_imbalance_block()   │
                         _format_ftfc_block()        │
                         session_interplay_block()   │
                         weekly_profile_block()      │

Weekly briefing:
  weekly_briefing.py ──► build_ticker_block() ──► DB (WeeklyBriefingTicker)
                         load_weekly_price_context() ──► live storage parquet
  weekly_narrative.py ──► build_weekly_cheat_sheet() ──► + KB context ──► Ollama ──► JSON slots ──► render_weekly_summary()
```

### Key modules

| Module | Location | Role |
|---|---|---|
| `briefing_core.py` | `scripts/trader/` | All cheat sheet builders, GEX extraction, data loading |
| `trader_narrative.py` | `scripts/trader/` | Daily trader narrative CLI (premarket/open/intraday/close) |
| `weekly_narrative.py` | `scripts/trader/` | Weekly narrative CLI (JSON slot-filling) |
| `weekly_briefing.py` | `scripts/trader/` | Weekly data aggregation → DB |
| `daily_narrative.py` | `scripts/trader/` | Daily open/EOD narrative CLI (JSON slot-filling) |
| `kb_context.py` | `scripts/knowledge_bridge/` | KB context retrieval (57 concept triggers) |
| `confluence_engine.py` | `scripts/knowledge_bridge/` | Runtime cross-domain confluence detection |
| `intraday_blocks.py` | `scripts/trader/signals/` | Per-session block builders (Asia/London/NY AM/Lunch/PM) |
| `econ_calendar.py` | `scripts/trader/signals/` | Economic event retrieval + US-only filter |

### LLM configuration

| Setting | Value | Notes |
|---|---|---|
| Endpoint | `http://localhost:11434/api/generate` | Local Ollama |
| Context window | 262,144 tokens | Was 32K — increased for KB context |
| Output tokens | 32,768 | Was 16K — no word limits |
| Default model | `gemma4:latest` (daily), `glm-5.2:cloud` (weekly) | Fallback: `gemma4:31b-cloud` |
| Temperature | 0.3 | Low for factual consistency |

---

## 3. KB Integration (2026-07-23)

### How it works

1. `build_premarket_context()` assembles the cheat sheet from live data
2. `fetch_kb_context(cheat_sheet)` scans the cheat sheet for 57 concept triggers:
   - 34 ICT setup triggers (FVG, CSD, MSS, Silver Bullet, OTE, killzone, etc.)
   - 23 conditional session/weekly triggers (asia, london, pre-ny, classification, macro, profile, opex, NWOG, day-of-week, etc.)
3. Session-interplay triggers are **prioritized** (processed first) so conditional knowledge isn't crowded out by generic setup triggers
4. KB API (port 8900) is queried for each trigger; results deduped by `unit_id`
5. Formatted as `# ICT KNOWLEDGE BASE CONTEXT` block with timeframes, sessions, instruments
6. Appended to the cheat sheet before the LLM call
7. Prompts instruct the LLM to USE the KB for inference, not just citation

### KB context budget

- `max_context_chars = 8000` (was 2000 — increased for 256K context)
- `k_per_concept = 3` (3 KB units per concept trigger)
- Timeframe extracted from `concepts` field (`timeframe_m5` → `TFs: M5`)
- Session and instrument included in `Context:` line

---

## 4. Cheat sheet sections

### Daily (premarket)

| Section | Source | KB-aware? |
|---|---|---|
| Overnight (Globex) | `build_overnight_context()` from live storage | — |
| GEX positioning | `load_macro_levels()` → `_extract_gex_levels()` | — |
| Prior EOD classification | `analyze_daily_classification_bias` | — |
| Econ releases + earnings | `get_econ_releases()` (US-only filtered) | — |
| Caution score | `calculate_caution_score()` | — |
| ICT KZ pivots + **session interplay** | `_format_kz_pivots_block()` | ✅ |
| IPDA 20/40/60 | `_format_ipda_block()` | — |
| Silver Bullet / macros | `_format_silver_bullet_block()` | — |
| Gaps | `_format_gaps_block()` | — |
| FTFC bias | `_format_ftfc_block()` | — |
| Herman Pre-NY sweep | `compute_herman_pre_ny_sweep()` | ✅ |
| Delivery triad | `_format_delivery_triad_1liner()` | — |
| **KB context** | `fetch_kb_context()` | ✅ |

### Weekly

| Section | Source |
|---|---|
| Intermarket macro matrix | `build_intermarket_macro_summary()` |
| Options tape + GEX | `build_ticker_block()` from unified levels |
| ICT profile + **weekly profile expectation** | `determine_weekly_archetype()` |
| Structural playing field | Ticker blocks from DB |
| High-impact catalysts | `fetch_week_events()` (US-only filtered) |
| Earnings (index-moving only) | `fetch_week_earnings()` filtered to mega-caps |
| Account invalidation | From ticker blocks |
| **KB context** | `fetch_kb_context()` |

---

## 5. Known issues and open work

### GEX levels — macro vs daily (OPEN, needs discussion)

The weekly briefing currently uses **daily/intraday GEX levels** from `unified_levels.json` (front-week weighted, 0D). The `macro_levels.json` / `macro_levels.txt` has **all-expiries weighted** (0-365 DTE) levels which are the correct view for a weekly horizon. The formats differ — need to unify before switching.

| Level type | Source | Scope | ES CW | ES PW |
|---|---|---|---|---|
| Daily/intraday (current) | `unified_levels.json` | Front-week 0D | 7,550 | 7,425 |
| Macro (should use for weekly) | `macro_levels.txt` | All expiries 0-365 DTE | 7,538.50 | 7,357.00 |

### Expected Moves N/A (OPEN, data pipeline)

Both ES and NQ show "Expected High N/A <-> Expected Low N/A" in the weekly. The options EM pipeline isn't populating weekly EMs for ES/NQ.

### Prior week trades (DISABLED)

Section 0 (Prior Week Review) was removed because trade generation is unreliable. Pending trade pipeline fix.

### Phase B-D: Historical replay (NOT STARTED)

See `docs/architecture/KB_NARRATIVE_REPLAY_ROADMAP.md` for the phased plan:
- Phase B: Historical day replay harness
- Phase C: Virtual trade execution + outcome eval
- Phase D: End-to-end day replay report

---

## 6. Prompt design principles (2026-07-23)

1. **No word limits** — 256K context, let the LLM write thorough narratives
2. **KB-aware jargon** — ICT terminology allowed when grounded in KB context, translate for reader
3. **Conditional session inference** — connect session outcomes to conditional rules from KB
4. **Timeframe annotation** — every FVG/CSD/level reference must state its timeframe
5. **Intermarket context** — reference VIX, DXY, yields, NQ/ES ratio
6. **Weekly profile** — map ICT archetype to day-by-day behavioral expectations
7. **US-only events** — filter international events, focus on what moves ES/NQ
8. **Index-moving earnings only** — filter to mega-caps that actually move the index

---

## 7. Narrative goals (from brainstorming doc, still relevant)

From `docs/TRADER_NARRATIVE_BRAINSTORMING.md`:

> **The Narrative (LLM-Generated Briefs)**
> * Primary Role: Qualitative Synthesis, Macro Contextualization, & Cognitive Framing
> * Core Responsibilities:
>   * Storytelling: Synthesize multi-dimensional data into a cohesive "story of the day"
>   * Trader's Brief: Translate mathematical boundaries into plain-English tactical briefs
>   * Contextual Blending: Integrate qualitative external factors (CPI windows, day types, macro trends)

**Current status:** ✅ Achieved for daily narratives. The KB integration adds the "qualitative synthesis" layer that was missing — ICT methodology and conditional session rules are now grounded in the KB, not just hardcoded in prompts.

**Still needed for weekly:** The weekly narrative is JSON slot-filling (not free-form prose), which limits the LLM's ability to synthesize a cohesive "story of the week." A future refactor could switch the weekly to free-form prose like the daily narratives, but that requires restructuring the `render_weekly_summary` pipeline.

---

## 8. Related docs

| Doc | Status | Purpose |
|---|---|---|
| **This doc** | ✅ Current | Canonical design + status |
| `KB_NARRATIVE_REPLAY_ROADMAP.md` | ✅ Current | Phase B-D plan |
| `KB_BRIDGE.md` | ✅ Current | KB API, bridge module, integration status |
| `TRADER_NARRATIVE_PLAN.md` | ✅ Current | Session-adaptive design, modular signal architecture |
| `NARRATIVE_ENGINE_V2_PLAN.md` | Historical | V2 design (all phases complete) |
| `NARRATIVE_ENGINE_V2_BUILD_PLAN.md` | Historical | V2 build plan (all phases complete) |
| `NARRATIVE_ENGINE_V2_ARCHITECTURE.md` | Historical | V2 architecture spec |
| `NARRATIVE_ENGINE_ARCHITECTURE.md` | Historical | V1 architecture (superseded by V2) |
| `NARRATIVE_AUDIT_2026-07-14.md` | Historical | Audit findings (most resolved) |
| `NARRATIVE_FEEDBACK_LOOP.md` | Historical | Feedback loop design (prior week trades disabled) |
| `TRADER_NARRATIVE_BRAINSTORMING.md` | Historical | Original brainstorming (goals still relevant) |