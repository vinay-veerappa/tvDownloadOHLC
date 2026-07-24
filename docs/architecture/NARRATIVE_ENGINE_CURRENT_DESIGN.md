# Narrative Engine — Current Design & Status

**Last updated:** 2026-07-23 (calendar context + timeline + time map update)
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
                         (75 concept triggers)       │
                         fetch_kb_context_for_queries()│
                                                     │
Calendar state ──►      build_calendar_context_block()│
                         (FOMC/CPI/NFP/Jackson Hole)  │
                         build_weekly_event_timeline()│
                         build_ict_time_map()         │
                         build_post_news_management()│
                         load_weekly_macro_sentiment()│
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
| `kb_context.py` | `scripts/knowledge_bridge/` | KB context retrieval (75 concept triggers + targeted query API) |
| `confluence_engine.py` | `scripts/knowledge_bridge/` | Runtime cross-domain confluence detection |
| `intraday_blocks.py` | `scripts/trader/signals/` | Per-session block builders (Asia/London/NY AM/Lunch/PM) |
| `econ_calendar.py` | `scripts/trader/signals/` | Economic event retrieval + US-only filter |
| `day_type.py` | `scripts/trader/signals/` | Day type classifier (clean/CPI/NFP/FOMC/Jackson Hole/special) |
| `narrative_stats.yaml` | `scripts/trader/config/` | Static config: day types, killzones, dead zones, no-trade rules |
| `weekly_macro_sentiment.yaml` | `config/` | Weekly curated macro theme + event sentiment (ISO week-keyed) |

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
2. `build_calendar_context_block()` queries KB with **targeted queries** based on today's calendar state (FOMC/CPI/NFP/Jackson Hole behavior, OPEX patterns, Kish macro windows, post-news candle management) — returns `(block, unit_ids)` tuple
3. `fetch_kb_context(cheat_sheet, exclude_ids=calendar_unit_ids)` scans the cheat sheet for 75 concept triggers (deduplicated against calendar block units):
   - 34 ICT setup triggers (FVG, CSD, MSS, Silver Bullet, OTE, killzone, etc.)
   - 23 conditional session/weekly triggers (asia, london, pre-ny, classification, macro, profile, opex, NWOG, day-of-week, etc.)
   - 18 calendar/event-specific triggers (Jackson Hole, Powell speech, Treasury auction, Kish's 6 macro windows, post-news candle management, manipulation/recovery/blackout windows)
4. Session-interplay + calendar triggers are **prioritized** (processed first)
5. KB API (port 8900) is queried for each trigger; results deduped by `unit_id`
6. Formatted as `# ICT KNOWLEDGE BASE CONTEXT` block with timeframes, sessions, instruments
7. Appended to the cheat sheet before the LLM call
8. Prompts instruct the LLM to USE the KB for inference, not just citation

### Two KB retrieval modes

| Mode | Function | Use case |
|---|---|---|
| **Cheat-sheet scan** | `fetch_kb_context(cheat_sheet, exclude_ids=)` | Scans full cheat sheet for concept triggers — generic setup definitions |
| **Targeted query** | `fetch_kb_context_for_queries(queries)` | Takes explicit `(label, query)` pairs — calendar/event-specific methodology |

The calendar block uses targeted queries (knows exactly what to ask for), then passes `exclude_ids` to the generic scan to avoid duplication.

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
| **Calendar & structural context** | `build_calendar_context_block()` | ✅ KB-distilled |
| **Weekly event timeline** | `build_weekly_event_timeline(mode=premarket)` | — (ICT knowledge) |
| **ICT intraday time map** | `build_ict_time_map(mode=premarket)` | — (ICT knowledge) |
| **Post-news candle management** | `build_post_news_management_block()` | ✅ KB-backed |
| **Weekly macro sentiment** | `load_weekly_macro_sentiment()` | — (curated config) |
| ICT KZ pivots + **session interplay** | `_format_kz_pivots_block()` | ✅ |
| IPDA 20/40/60 | `_format_ipda_block()` | — |
| Silver Bullet / macros | `_format_silver_bullet_block()` | — |
| Gaps | `_format_gaps_block()` | — |
| FTFC bias | `_format_ftfc_block()` | — |
| Herman Pre-NY sweep | `compute_herman_pre_ny_sweep()` | ✅ |
| Delivery triad | `_format_delivery_triad_1liner()` | — |
| **KB context (generic scan)** | `fetch_kb_context(exclude_ids=calendar_ids)` | ✅ |

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
| **Next week event timeline** | `build_weekly_event_timeline(mode=weekly)` |
| **KB context** | `fetch_kb_context()` |

### Per-mode calendar context injection

| Mode | Calendar block | Timeline | Time map | Post-news mgmt | Macro sentiment |
|---|---|---|---|---|---|
| **Premarket** | Full (CALENDAR & STRUCTURAL CONTEXT) | Full (WEEKLY EVENT TIMELINE) | Full (ICT INTRADAY TIME MAP) | ✅ (if event day) | ✅ (if configured) |
| **Open** | — | — | AM only (TODAY'S AM TIME WINDOWS) | ✅ (if event day) | — |
| **Intraday** | — | Position line only | PM only (PM TIME WINDOWS) | — | — |
| **Close** | — | Tomorrow preview (TOMORROW'S PREVIEW) | Tomorrow's key times | — | — |
| **Weekly** | — | Next week (NEXT WEEK EVENT TIMELINE) | — | — | ✅ (if configured) |

---

## 5. Calendar context, timeline & time map (2026-07-23)

### Calendar context block (`build_calendar_context_block`)

Queries the KB for event-specific ICT methodology based on today's calendar state. Uses `fetch_kb_context_for_queries()` with targeted queries — not the generic cheat-sheet scan.

| Day type | KB queries fired |
|---|---|
| FOMC | FOMC Day Behavior, FOMC Pre-PA, Kish Macro Windows, Post-News Candle Mgmt, News Manipulation Windows |
| CPI | CPI Day Behavior, CPI Liquidity Raid, Kish Macro Windows, Post-News, Manipulation Windows |
| NFP | NFP Day Behavior, NFP Liquidity Raid, Kish Macro Windows, Post-News, Manipulation Windows |
| Jackson Hole | Jackson Hole Behavior, Jackson Hole Pre-PA, Kish Macro Windows, Post-News, Manipulation Windows |
| Special (Treasury auction) | Treasury Auction, Kish Macro Windows |
| Clean | Kish Macro Windows only |

Week modifiers (OPEX, triple witching, FOMC week, CPI week, NFP week, Jackson Hole week, Treasury auction) add additional KB queries for weekly patterns.

### Weekly event timeline (`build_weekly_event_timeline`)

Day-by-day Mon-Fri expectations with **regime tags**. 7 week patterns encoded as structured data (ICT/Kish methodology):

| Pattern | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|
| FOMC | [CHOP] | [CHOP] | [CHOP→EXPANSION] | [EXPANSION] | [CHOP] |
| CPI | [CHOP] | [SWEEP→EXPANSION] | [EXPANSION] | [EXPANSION] | [CHOP] |
| NFP | [CHOP] | [EXPANSION] | [EXPANSION] | [CHOP→CAUTION] | [SWEEP→EXPANSION] |
| Jackson Hole | [CHOP] | [CHOP] | [CHOP] | [CHOP→CAUTION] | [SWEEP→EXPANSION] |
| OPEX | [EXPANSION] | [EXPANSION] | [EXPANSION↓] | [CHOP→EXPANSION] | [CHOP/PIN] |
| Triple Witching | [EXPANSION] | [EXPANSION] | [EXPANSION↓] | [CHOP/VOLATILE] | [CHOP/PIN] |
| Clean | [CHOP] | [EXPANSION] | [EXPANSION] | [EXPANSION] | [CHOP] |

Mode-filtered: premarket (full), intraday (position line), close (tomorrow preview), weekly (next week).

### ICT intraday time map (`build_ict_time_map`)

20-entry time map with regime tags. Kish's 6 intraday macros + ICT killzones + dead zones + post-close:

| Time | Window | Regime |
|---|---|---|
| 02:00-05:00 | London Open killzone | [SWEEP] |
| 08:15-09:45 | Liquidity Hunt Macro (Kish) | [SETUP] |
| 08:30 | NY Open / RTH open | [NO-TRADE] |
| 09:12 | 9:12 Macro (Kish) | [SETUP] |
| 08:35-09:20 | Manipulation Window (news days) | [NO-TRADE] |
| 09:45-10:00 | Offset Macro (Kish) | [SETUP] |
| 09:50-10:10 | MACRO WINDOW — MSS prime time | [SETUP] |
| 10:00-11:00 | SILVER BULLET window | [EXPANSION] |
| 11:00 | Rebalance Macro (Kish) | [DELIVERY] |
| 11:30-13:30 | NY LUNCH — dead zone | [CHOP] |
| 12:45 | 12:45 Macro (Kish) | [SWEEP] |
| 14:00-14:30 | FOMC statement (when scheduled) | [NO-TRADE] |
| 15:00-16:00 | POWER HOUR — distribution | [EXPANSION] |
| 15:59-16:00 | Last bar — prop-firm exit | [EXIT] |

Mode-filtered: premarket (full day), open (AM 09:30-11:30), intraday (PM 12:00-16:00), close (tomorrow's key times).

### Post-news candle management (`build_post_news_management_block`)

10 KB-backed rules for event days (CPI/NFP/FOMC/Jackson Hole/special). Examples:
- "Don't read the first M1 candle — statistically unreliable (except news days)" (conf 0.90)
- "First two M1 candles of a new M5 retrace (OLR) — third shows direction" (conf 0.90)
- "Require M5 candle close above 50% of order block before taking a trade" (conf 0.90)
- "Recovery: 80% of setups occur 20-60 min post-release" (ICT_CONCEPTS_KB §14)

### Weekly macro sentiment (`config/weekly_macro_sentiment.yaml`)

Curated current-week context that the KB cannot supply (KB = historical methodology, not current market narrative). ISO week-keyed (`YYYY-Www`). Provides:
- `macro_theme` — one-paragraph current-week narrative
- `event_sentiment` — per-event consensus + cooler/hotter scenarios
- `jackson_hole` — note for Jackson Hole weeks
- `treasury_auctions` — day/time/notes for auctions
- `intermarket_themes` — DXY, VIX term structure, etc.

Graceful absence: if file missing or week not configured, block is skipped (KB calendar context still provides methodology).

### Day type classifier enhancements

- `jackson_hole` added as dedicated day type (FOMC-class, 10:00 ET event, 50% sizing)
- `classify_day_type` now handles events with `time_et` string field (not just `datetime` epoch ms)
- `get_weekly_modifiers` detects CPI week, NFP week, Jackson Hole week, Treasury auctions

---

## 6. Known issues and open work

### GEX levels — macro vs daily + Expected Moves (OPEN, needs discussion + data pipeline fix)

The weekly briefing currently uses **daily/intraday GEX levels** from `unified_levels.json` (front-week weighted, 0D). The `macro_levels.json` / `macro_levels.txt` has **all-expiries weighted** (0-365 DTE) levels which are the correct view for a weekly horizon. The formats differ — need to unify before switching.

Both ES and NQ show "Expected High N/A <-> Expected Low N/A" in the weekly. The options EM pipeline isn't populating weekly EMs for ES/NQ. **The EM fix is related to the macro GEX level fix** — both depend on the same options data pipeline. These should be addressed together in a dedicated session.

| Level type | Source | Scope | ES CW | ES PW |
|---|---|---|---|---|
| Daily/intraday (current) | `unified_levels.json` | Front-week 0D | 7,550 | 7,425 |
| Macro (should use for weekly) | `macro_levels.txt` | All expiries 0-365 DTE | 7,538.50 | 7,357.00 |

### Weekly narrative JSON structure (OPEN, needs discussion)

The weekly narrative uses JSON slot-filling (not free-form prose like the daily narratives). This limits the LLM's ability to synthesize a cohesive "story of the week." The JSON structure forces a rigid section layout (Executive Risk Core, Economic Milestones, Earnings, Structural Sandbox, Trade Plan, etc.) rather than letting the LLM weave a narrative. A future refactor could:
- Switch the weekly to free-form prose like the daily narratives
- Or keep the JSON structure but make it more flexible (optional sections, free-text fields)
- This needs a design discussion before implementation

### Econ calendar data quality (OPEN, needs investigation)

The weekly cheat sheet generated on 2026-07-20 showed CPI m/m on Monday July 20 at 08:30 ET, but the user confirmed there was no CPI on Monday that week. The DB econ event data may have incorrect dates, or the events were from a previous CPI release cycle. The `get_weekly_modifiers` function scans ALL event names for "CPI" and sets `is_cpi_week = True` — this means any event with "CPI" in the name (including international CPI releases like "National Core CPI y/y") triggers the CPI week pattern. Need to:
- Verify the econ calendar data source is providing correct dates
- Filter `get_weekly_modifiers` to only match US CPI events (not international)
- Consider adding a date-range validation step

### Mid-week validation mode (BACKLOG — future feature)

A new narrative mode that runs mid-week (e.g. Wednesday evening) and:
1. **Validates** what the week was supposed to do (per the weekly event timeline pattern) against what actually happened
2. **Shows what to expect** for the rest of the week (remaining days' regime tags)
3. **Optionally generates** next week's narrative preview (if events are available)
4. **Configurable** — user can choose whether to show validation only, rest-of-week only, or both

This would be a new `--mode midweek` option in `trader_narrative.py` or a separate script. It would use:
- `build_weekly_event_timeline(mode="midweek")` — a new mode that highlights remaining days
- Comparison of the week's actual price action vs the expected pattern
- Next week's event timeline (if next week's events are available)

### Prior week trades (DISABLED)

Section 0 (Prior Week Review) was removed because trade generation is unreliable. Pending trade pipeline fix.

### Phase B-D: Historical replay (NOT STARTED)

See `docs/architecture/KB_NARRATIVE_REPLAY_ROADMAP.md` for the phased plan:
- Phase B: Historical day replay harness
- Phase C: Virtual trade execution + outcome eval
- Phase D: End-to-end day replay report

---

## 7. Prompt design principles (2026-07-23)

1. **No word limits** — 256K context, let the LLM write thorough narratives
2. **KB-aware jargon** — ICT terminology allowed when grounded in KB context, translate for reader
3. **Conditional session inference** — connect session outcomes to conditional rules from KB
4. **Timeframe annotation** — every FVG/CSD/level reference must state its timeframe
5. **Intermarket context** — reference VIX, DXY, yields, NQ/ES ratio
6. **Weekly profile** — map ICT archetype to day-by-day behavioral expectations
7. **US-only events** — filter international events, focus on what moves ES/NQ
8. **Index-moving earnings only** — filter to mega-caps that actually move the index
9. **Weekly timeline + time map usage** — cite specific time windows for entry timing and regime tags for expected behavior; frame the day in the context of the week
10. **Post-news candle management** — reference specific KB-backed rules for event days (M5 close, OLR retrace, recovery window)
11. **Tomorrow's preview** (close mode) — frame tomorrow in the context of the week with key time windows

---

## 8. Narrative goals (from brainstorming doc, still relevant)

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

## 9. Related docs

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