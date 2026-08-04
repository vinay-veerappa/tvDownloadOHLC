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
| `weekly_macro_sentiment.yaml` | `scripts/config/` | Weekly curated macro theme + event sentiment (ISO week-keyed) |

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

### Weekly macro sentiment (`scripts/config/weekly_macro_sentiment.yaml`)

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

### Econ calendar data quality (FIXED 2026-07-23)

**Root causes found and fixed:**

1. **`country` field was null for all 11,662 events** — all three fetchers (Investing.com, ForexFactory, web app) were not writing the `country` field to the DB. Fixed in all fetchers; DB backfilled to `country='USD'`.

2. **International events mixed with US events** — the web app ForexFactory fetcher was fetching 8 currencies (USD, EUR, GBP, CAD, JPY, AUD, CHF, NZD) and inserting them all into the DB. Fixed to USD-only.

3. **`get_weekly_modifiers` over-broad CPI matching** — matched any event containing "CPI" including international releases like "National Core CPI y/y". Fixed to only match US CPI patterns (`CPI M/M`, `CPI Y/Y`, `Core CPI M/M`, etc.).

4. **`get_econ_releases` didn't filter by country at DB level** — relied on unreliable name-based filtering. Fixed to query `WHERE country='USD'`.

**Single-fetcher policy (Investing.com primary):**

| Fetcher | Role | Source | Future data? | Country stored? |
|---|---|---|---|---|
| `fetch_economic_calendar.py` | **PRIMARY** | Investing.com API (country_id=5) | ✅ 14 days ahead | ✅ `country='USD'` |
| `news_calendar_fetcher.py` | Fallback (NinjaTrader) | ForexFactory XML | ❌ Current week only | ✅ via Prisma |
| `web/lib/economic-calendar.ts` | Web app display | ForexFactory JSON | ❌ Current week only | ✅ (fixed) USD-only |
| `seed-economic-events.ts` | Historical seed (one-time) | CSV + TradingEconomics API | N/A | ✅ (fixed) `country='USD'` |

Investing.com is primary because it fetches 14 days ahead (solves the Friday/Saturday ForexFactory limitation where next week's data isn't available until Sunday). yfinance was tested as an alternative but lacks impact levels (HIGH/MEDIUM/LOW) and has abbreviated event names.

### GEX/EM enhancements (BACKLOG — 2026-07-23)

Three enhancements to make GEX/EM data more actionable in the narrative. Approved 2026-07-23; items 1–2 are backlog, item 3 is the immediate add.

#### 1. Intraday GEX drift block (BACKLOG)

**Problem:** The intraday cheat sheet reads `unified_levels.json` at narrative build time (a point-in-time snapshot). The narrative cannot tell the trader *how GEX has evolved intraday* — e.g. the zero gamma drifting up, the call wall pulling in, or a regime that is *about* to flip.

**What exists:** `GexSnapshot` is written to Prisma every ~60s by the options pipeline (`run_options_levels.py`), so the time-series is available. `compute_gex_verdict()` in `signals/gex_regime.py` already compares live vs. morning-open GEX to detect flips/wall shifts, but it is only invoked from the open-mode cheat sheet, not the intraday builder.

**Required:**
- New block in `build_intraday_context()` (briefing_core.py): **GEX DRIFT SINCE OPEN**
- Pull the morning-open `GexSnapshot` (first snapshot after 09:30 ET) and the latest snapshot from Prisma
- Surface deltas: zero gamma Δ, call wall Δ, put wall Δ, total GEX Δ
- Produce a read: "Pin weakening — flip approaching spot" / "Walls stable, regime holding" / "Regime flipped at 11:42 ET (positive → negative)"
- Reuse `compute_gex_verdict()` (already returns regime, bias, wall_shift_note, read)
- Add a "regime flip watch" alert when spot is within N points of the flip

**Depends on:** Options pipeline running intraday (it is, per `data_freshness.check_gex_levels()`)

#### 2. EM decay model (BACKLOG)

**Problem:** The cheat sheet reports the *morning* EM envelope (e.g. 300pt range). By 14:00 ET most of that envelope has been "used up" but the narrative still quotes the full range, making the "price at 93% of EM HI" read misleading late in the day.

**What exists:** `compute_weekly_ems()` already uses `√(time)` scaling for the weekly → daily EM progression. The same principle applies intraday: as the trading day elapses, the *remaining* expected move shrinks as `√(remaining_time / total_time)`.

**Required:**
- New helper: `compute_decayed_em(em_upper, em_lower, spot, current_time, session="RTH")` in `signals/expected_move.py`
- Compute remaining EM width as `full_em_width × √(remaining_bars / total_bars)` where total = RTH 09:30–16:00 (390 1-min bars)
- Return decayed `em_upper_decay`, `em_lower_decay`, `remaining_em_pct`, `read`
- Surface in intraday cheat sheet: "EM (decay-adjusted, 14:00): 22,180–22,320 (47% remaining)"
- Combine with GEX regime for confluence (see item 3)

**Depends on:** RTH session clock (already available via `nqstats/sessions.py`)

#### 3. GEX × EM confluence verdict (IMMEDIATE — approved 2026-07-23)

**Problem:** The cheat sheet reports GEX regime and EM position as separate blocks. The *synthesis* — "what should I actually do given the regime and where price sits relative to EM" — is left to the LLM to infer each time, which is inconsistent.

**What exists:** `resolve_track()` already maps GEX regime → mandated execution track (Python-decided). But the track does not account for *where price is relative to EM* — e.g. a pinned regime with price at EM HI is a fade setup, while a pinned regime with price at the gamma magnet is "stay flat."

**Required — shared module:** `scripts/trader/signals/gex_em_confluence.py`
```python
def compute_gex_em_verdict(
    gex_regime: str,        # POSITIVE/NEGATIVE/NEUTRAL
    regime_label: str,      # PINNED/TRENDING/COILED/BATTLE ZONE
    em_upper: float,
    em_lower: float,
    spot: float,
    em85_upper: float | None = None,
    em85_lower: float | None = None,
    call_wall: float | None = None,
    put_wall: float | None = None,
) -> dict:
    """Return a single actionable verdict combining GEX regime + EM position.

    Returns: {verdict, setup, invalidation, confidence, read}
    """
```

**Logic matrix** (Python-decided, LLM narrates):

| GEX regime | EM position | Verdict | Setup |
|---|---|---|---|
| Pinned (positive + tight) | Near EM HI / call wall | Fade | Short near EM HI, target gamma magnet |
| Pinned | Near EM LO / put wall | Fade | Long near EM LO, target gamma magnet |
| Pinned | Mid-range (near magnet) | Neutral | Stay flat; wait for edge |
| Trending (negative + wide) | Above EM HI (broken) | Trend-follow | Long continuation, trail stops |
| Trending | Below EM LO (broken) | Trend-follow | Short continuation, trail stops |
| Trending | Inside EM | Wait | Wait for EM break, then join direction |
| Coiled (negative + tight) | Any | Breakout-wait | Wait for wall break + candle close |
| Battle zone (positive + wide) | Near wall | Wall-trade | Fade wall, target opposite wall |

**Integration:**
- Add to `build_premarket_context()` and `build_ticker_cheat_sheet()` as a new `== GEX × EM CONFLUENCE ==` block
- Add to intraday context with decay-adjusted EM (when item 2 lands)
- Add `confluence_verdict` field to the weekly briefing ticker block (so the weekly narrative can reference the bigger-picture regime posture)

**EM85 usage:** EM85 straddle bounds are NOT relied upon (per user preference 2026-07-24). Use the **full EM** calculations exclusively. The TOS-validated formula (`calculate_tos_expected_move()`) is the source of truth.

---

### IV investigation (2026-07-24)

**Root cause found**: `atm_iv` in `gex_calculator.py` (line ~2033) was set to the ATM **call-only** contract IV:
```python
atm_iv=_atm_contract(chain.calls, spot).iv  # call-only, ignores put skew
```
This understated ATM IV when there's a put skew (puts trade richer than calls), which is the normal state for equity index options.

**Fix committed** (`abde5ad0`): Blend call + put IV at the ATM strike:
```python
_atm_iv_val = (_atm_call.iv + _atm_put.iv) / 2.0
```

**Verification with live TOS values (2026-07-24)**:

| Ticker | Old (call-only) | New (blended) | TOS display | Gap (old) | Gap (new) | Status |
|---|---|---|---|---|---|---|
| NQ | 21.31% | 22.89% | 22.90% | 9.7% | **0.04%** | ✅ Fixed |
| ES | 12.10% | 13.01% | 13.92% | 13.1% | 6.5% | 🟡 Partial — put_25d (13.93%) matches TOS exactly |
| SPX/SPY | 17.49% (SPY atm_iv) | ~18-19% (est) | 20.98% | 16.6% | ~5-10% | 🟡 Partial — needs morning investigation |

**Key finding for ES**: TOS display IV (13.92%) matches the **put-side 25d IV** (13.93%) almost exactly, not the blended IV (13.01%). This suggests TOS may display the put-side IV (the peak of the volatility smile) for index products with strong put skew.

**Key finding for SPX/SPY**: TOS display IV (20.98%) is significantly higher than both the blended 25d IV (13.76%) and the stored `atm_iv` (17.49%). The SPY live GexSnapshot put 25d IV (19.17%) is closer. This suggests the ATM strike put IV (peak of the smile) is what TOS displays — it's always higher than the 25d IVs because the 25d strikes are away from ATM.

**Next steps (investigate when market is open)**:
1. Run the pipeline with the blending fix and compare the new `atm_iv` to TOS for all three tickers
2. Check if TOS displays the ATM strike put IV (not blended) for ES/SPX — if so, consider using put-side ATM IV for index products
3. Compare the actual ATM strike call/put IVs from the RTD chain (not 25d) to TOS display
4. The 25d IVs stored in DB are sampled at strikes away from ATM; the ATM strike IVs (used by the blending fix) should be higher and closer to TOS

**Important**: The `_expected_move()` and `_calculate_all_ems()` functions already blend call+put IV correctly — the bug was only in the `atm_iv` field that gets stored to DB and META_ fields. The EM calculations themselves were using the correct blended IV all along. The fix ensures `atm_iv` (used by the TOS formula fallback in `compute_weekly_ems()`) also uses the blended value.

**RTD pipeline metadata fix** (2026-07-24): NQ/ES entries in `intraday_levels.json` now have `translation_mode=rtd_direct`, `cash_spot`, and `futures_price` populated. Previously these were `None` because:
- `DealerLevels` dataclass was missing the translation metadata fields
- `file_writer.py` section 2 didn't include them in the output
- `dataclasses.replace()` dropped arbitrary attributes during EOD pinning
- The RTD OI scan couldn't handle both ES and NQ simultaneously (COM topic budget)
- Schwab NQ strikes at 100-pt intervals didn't match RTD 5-pt grid

**Fix**: Schwab's futures options chain API provides OI data (but not IV). The OI scan was replaced with direct Schwab OI data, and Schwab hint strikes are rounded to the RTD strike grid. NQ went from 19 → 420 contracts, ES from 154 → 814 contracts.

---

### TOS EM verification (2026-07-24)

**Context:** Today is Thursday 2026-07-24. The user captured TOS VxV ExpectedMove v3 values **last Friday (2026-07-17)** for **this week's expiry (2026-07-24)** — the Friday that is tomorrow. The scope capture date and expiry are correct for this week.

**User-provided TOS values** (captured 2026-07-17, expiry 2026-07-24, DTE=7 at capture):

| Ticker | Mon | Tue | Wed | Thu | Wkly/Fri |
|---|---|---|---|---|---|
| NQ (futures) | 412.25 | 567.5 | 688.21 | 816.4 | 916.9 |
| ES (futures) | 62.05 | 83.76 | 100.52 | 119.18 | 134.36 |
| SPX (index) | 60.89 | 82.14 | 99.64 | 117.78 | 132.16 |
| SPY (ETF) | 6.16 | 8.26 | 10.14 | 11.75 | 13.26 |

**Findings:**

1. **√(time) scaling is valid** — TOS daily values match `Wkly × √(day/5)` within 1–4%. Monday is consistently ~3% above the pure √ prediction (TOS uses calendar DTE, not fractional days). The per-day progression model in `compute_weekly_ems()` is sound.

2. **Scope expiry is CORRECT** — the scope captured 2026-07-24 (this Friday, DTE=7 at capture on 2026-07-17). This is the right expiry for this trading week. The earlier analysis that called it "wrong expiry" was incorrect — today is Thursday and the expiry is tomorrow.

3. **NQ/ES futures are NOT in `weekly_em_scope.json`** — the scope file has NDX/SPX (cash indices) and SPY/QQQ (ETFs) but not the futures contracts. NQ and ES are processed via the RTD-native path (`RTD_NATIVE_TICKERS = {"NQ", "ES"}`), and the scope capture happens on that path, but the scope file only contains the Schwab-path tickers.

   **Fix:** Ensure the RTD-native path writes NQ/ES scope entries to the same cache file. Verify `_save_weekly_scope_cache()` is called after the RTD path captures the weekly candidate.

4. **SPX EM is 13.3% below TOS** — pipeline scope SPX EM = 114.60 vs TOS SPX EM = 132.16 (same instrument, same expiry, same capture date). Reverse-engineering shows the pipeline SPX IV = 13.34% but TOS-implied IV = 15.38%. **The IV source for SPX is wrong**, not the formula.

5. **SPY EM is only 3.6% below TOS** — pipeline scope SPY EM = 12.79 vs TOS SPY EM = 13.262. Pipeline SPY IV = 14.91% vs TOS-implied IV = 15.46%. The SPY IV is much closer to TOS (3.6% gap vs 13.3% for SPX).

6. **Internal inconsistency confirms the SPX IV bug** — TOS SPX/SPY EM ratio = 9.97 (matches the ~10x price ratio). Pipeline scope SPX/SPY EM ratio = 8.97 (broken). SPX and SPY track the same underlying — their EM ratio should equal their price ratio. The pipeline SPX IV is understated, producing a too-narrow SPX EM.

7. **NQ/ES futures EM** — NDX scope (882.81) vs NQ TOS (916.9) = -3.7% (index vs futures, expected gap from basis). SPX scope (114.60) vs ES TOS (134.36) = -14.7% (index vs futures + the SPX IV bug). If SPX IV were correct, ES futures EM computed via TOS formula would match TOS much more closely.

8. **RTD chain for NQ/ES has only 2 expiries** — NQ has 2026-07-24 (0DTE) + 2026-08-21 (28DTE monthly). Neither has the weekly expiry that TOS displays (though the scope capture on Friday EOD would use the front expiry which IS the weekly).

**Root cause summary:**

| Issue | Root cause | Impact |
|---|---|---|
| SPX EM 13.3% too low | Pipeline SPX IV (13.34%) is below TOS SPX IV (15.38%) — Schwab API IV differs from TOS display IV for SPX | All SPX-derived levels understated |
| SPY EM 3.6% low | Minor IV gap (14.91% vs 15.46%) — acceptable tolerance | Minor |
| NQ/ES not in scope | RTD-native path scope capture not persisted to scope file | No futures-native weekly EM |
| NQ pipeline IV 21.5% vs TOS 27% | RTD IV source may differ from TOS display IV | NQ EM understated by ~16% |

**User directive:** NQ/ES must use the **futures TOS EM** (computed from futures spot + futures IV via `calculate_tos_expected_move(is_futures=True)`), NOT the SPY/QQQ translated values. The `basis_ratio` translation from ETF to futures introduces a spot mismatch that compounds the IV discrepancy.

**User preference:** Use **full EM** calculations only — do not rely on EM85 straddle bounds.

**IV time-drift caveat:** The IV gap analysis above is valid because both the pipeline scope and the user's TOS values were captured at the **same time** (Friday 2026-07-17 EOD, DTE=7). Comparing today's live pipeline EM (Thursday, DTE=1) against Friday's TOS values would NOT be a fair comparison — IV drifts over the week as market conditions change, and DTE shrinks. The 13.3% SPX IV gap and 3.6% SPY IV gap are real discrepancies at the same snapshot time, not time-drift artifacts. Any future re-verification should capture TOS values at the same timestamp the pipeline runs (e.g., both on Friday EOD, or both intraday at a specific time).

**Action items (producer side — `scripts/streaming/options/`):**

| # | Fix | File | Status |
|---|---|---|---|
| A | Ensure RTD-native path (NQ/ES) writes scope entries to `weekly_em_scope.json` | `run_options_levels.py` RTD path + `_save_weekly_scope_cache()` | ✅ Done — RTD path already saves to cache; added TOS formula fallback |
| B | When weekly expiry missing from RTD chain, compute EM via TOS formula with futures IV | `run_options_levels.py` `_compute_tos_em_fallback()` | ✅ Done — added `_compute_tos_em_fallback()` + `_next_friday()` |
| C | Investigate SPX IV discrepancy (pipeline 13.34% vs TOS 15.38%) — check Schwab API IV source for SPX | `options_fetcher.py` + `gex_calculator.py` | 🟡 In progress — see IV investigation below |
| D | Investigate NQ IV discrepancy (pipeline 21.5% vs TOS 27%) — check RTD IV source | `tos_rtd/adapter.py` + `gex_calculator.py` | ✅ Fixed — call-only → blended IV (see below) |
| E | Add NQ/ES futures EM directly to `weekly_em_scope.json` (not just NDX/SPX) | `run_options_levels.py` | ✅ Done — RTD path + TOS fallback now writes NQ/ES to scope |

**Action items (consumer side — `scripts/trader/`):**

| # | Fix | File | Status |
|---|---|---|---|
| F | `expected_move.py` should read `cash_spot` (populated) not `price` (empty) from `market_structure[]` | `signals/expected_move.py` | ✅ Done — `market_structure[]` entries use `cash_spot`; EM values are read from `expected_moves[]` not `price` |
| G | `expected_move.py` should prefer NQ/ES futures EM when available (check `translation_mode == "rtd_direct"`) | `signals/expected_move.py` | ✅ Done — futures-native lookup priority + `is_rtd_native` skip of `basis_ratio` scaling |
| H | Weekly briefing should use futures-native EM for NQ/ES, not ETF-translated | `weekly_briefing.py` `build_ticker_block()` | 🟡 Pending |

---

### RTD pipeline fixes (2026-07-24)

**Problem:** NQ/ES entries in `intraday_levels.json` had `translation_mode=None`, `cash_spot=None`, `futures_price=None` — the narrative layer couldn't tell they were RTD-direct futures options data. The pipeline was falling back to SPY/QQQ ETF-translated values, which use a different IV source.

**Root causes found and fixed:**

| # | Bug | File | Fix |
|---|---|---|---|
| 1 | `DealerLevels` dataclass missing `futures_symbol`, `translation_mode`, `basis_ratio`, `basis_spread`, `futures_price` fields | `gex_calculator.py` | Added as proper dataclass fields so `dataclasses.replace()` preserves them |
| 2 | `file_writer.py` section 2 (translated levels) missing translation metadata in output dict | `file_writer.py` | Added `futures_symbol`, `translation_mode`, `basis_ratio`, `futures_price`, `cash_spot` |
| 3 | EOD parquet pinning used `_replace()` which dropped arbitrary attributes | `run_options_levels.py` | Re-apply translation metadata after `_replace()` |
| 4 | RTD OI scan couldn't handle both ES and NQ simultaneously (COM topic budget exhausted) | `hybrid_coordinator.py` | Skip RTD OI scan entirely — use Schwab futures chain OI data directly |
| 5 | Schwab NQ strikes at 100-pt intervals didn't match RTD 5-pt grid | `hybrid_coordinator.py` | Round Schwab hint strikes to RTD strike grid |
| 6 | QQQ→NQ ETF translation for OI hints was unreliable (ratio errors miss NQ strike grid) | `hybrid_coordinator.py` | Use direct Schwab futures options chain instead of ETF proxy |

**Key insight:** Schwab's futures options chain API (`fetch_futures_option_chain_data`) returns OI data but **not IV** (IV=0.0 for all contracts). This is by design:
- **Schwab** → OI data for cache/strike selection
- **RTD** → live IV streaming for Greeks and EM calculation

**Result after fixes:**

| Metric | Before | After |
|---|---|---|
| NQ contracts in RTD chain | 19 (4 calls, 15 puts) | **420** (210 calls, 210 puts) |
| ES contracts in RTD chain | 154 (62 calls, 92 puts) | **814** (407 calls, 407 puts) |
| NQ `translation_mode` | `None` | `rtd_direct` |
| ES `translation_mode` | `None` | `rtd_direct` |
| NQ `cash_spot` | `None` | `28,468` |
| ES `cash_spot` | `None` | `7,470` |

**Remaining issue:** The RTD `IMPL_VOL` values (NQ ~11%, ES ~6%) are significantly lower than TOS display (NQ 26.18%, ES 15.25%). The RTD returns IV in percentage format (e.g. `'13.58%'` parsed to `0.1358`), but the values don't match TOS UI. This is a separate investigation — the RTD `IMPL_VOL` field may use a different pricing model or sample a different snapshot than TOS display.

### Weekly narrative — bigger picture (approved 2026-07-23)

**Problem:** The weekly narrative currently frames the week as a *scaled-up day* — per-ticker walls, zero gamma, intraday invalidation, mandated track. It does not answer the macro question the weekly brief should answer: *what kind of week is this, what is the multi-week positioning context, and what is the structural regime?*

**Current weekly focus (day-trading lens):**
- Per-ticker: call wall, put wall, zero gamma, gamma magnet, pin strike
- Weekly EM envelope (Friday EM HI/LO as risk boundary)
- Mandated execution track (Track A/B/C from GEX regime)
- Account invalidation (bullish/bearish model-break levels)
- Scenarios (bullish/bearish/range per ticker)

**Missing — the bigger-picture lens the weekly should provide:**

| Dimension | What it answers | Data source | Status |
|---|---|---|---|
| **GEX regime persistence** | Is this a 1-day flip or a multi-week regime? Compare this week's net GEX to prior 2–4 weeks | `GexSnapshot` history (Prisma) | 🔴 Not built |
| **Vol term structure** | Is vol expanding or compressing? Compare 0DTE vs weekly vs monthly EM width | `daily_levels.json` `expected_moves[]` (multi-expiry) | 🟡 Data exists, not surfaced |
| **Wall migration** | Are the call/put walls drifting? Compare this week's walls to prior weeks | `MacroSnapshot` history (Prisma) | 🔴 Not built |
| **Intermarket divergence** | Are NQ and ES in the same regime? Is VIX diverging from GEX? | `unified_levels.json` + `get_intermarket_quotes()` | 🟡 Intermarket matrix exists but not as a *divergence* read |
| **Weekly range statistics** | What is the typical weekly range vs the current EM? Is this week coiled or expanded? | Live storage parquet (weekly bars) | 🔴 Not built |
| **Regime stability score** | How stable is the current GEX regime? (low stability = expect regime change) | `GexSnapshot` time-series | 🔴 Not built |
| **Multi-week EM term structure** | Are front-week EMs wider than back-week (backwardation = vol event priced in)? | `expected_moves[]` across expiries | 🟡 Data exists, not surfaced |

**Required changes:**

1. **New `build_weekly_macro_context()` block** in `briefing_core.py`:
   - Pull 4 weeks of `GexSnapshot` from Prisma for each ticker
   - Compute: regime persistence (% of days in same regime), wall migration (Δ call/put wall over 4 weeks), total GEX trend (rising/falling)
   - Pull multi-expiry EM from `daily_levels.json` → term structure (0DTE vs weekly vs monthly width)
   - Compute weekly range stats from live storage (prior 4 weeks actual range vs EM-implied range)
   - Produce a `WEEKLY MACRO CONTEXT` block: "GEX regime: 3 weeks negative → trending. Walls stable. Vol term structure: backwardation (0DTE EM wider than monthly — event risk priced in)."

2. **Add to weekly briefing JSON** (`build_ticker_block()` in `weekly_briefing.py`):
   - `macro_context: {regime_persistence, wall_migration, vol_term_structure, range_stats, regime_stability}`
   - This feeds the LLM's `executive_risk_core` slot

3. **Update weekly prompt** (`prompts/weekly_briefing.md`):
   - Add instruction: "The `executive_risk_core` must frame the week in the context of the multi-week regime (is this a continuation or inflection?) and the vol term structure (is vol expanding or compressing?), not just today's GEX read."
   - Add a new slot `{{MACRO_REGIME_ASSESSMENT}}` for the bigger-picture synthesis

4. **Add intermarket divergence read**:
   - Compare NQ vs ES GEX regime (same or divergent)
   - Compare VIX level vs GEX regime (VIX high + positive GEX = divergence, vol event not yet priced)
   - Already have `get_intermarket_quotes()` — just need a `compute_intermarket_divergence()` helper

**Data freshness prerequisite (verified 2026-07-24):**
- `macro_levels.json` — EXISTS but `market_structure[].price` field is empty (spot lives in `cash_spot` which IS populated — consumer bug). EM85 fields are empty but **not needed** (user preference: use full EM only).
- `weekly_em_scope.json` — EXISTS but captured the **wrong expiry** (2026-07-24, the immediate next Friday at capture, not the forward week 2026-07-31). NQ/ES futures are **missing** from the scope entirely — only NDX/SPX/SPY/QQQ and single-name stocks are present. See TOS EM verification section above.
- `daily_levels.json` — STALE (2026-07-10, 13 days old). Superseded by `intraday_levels.json` (no longer written as a separate file per `run_options_levels.py` line 1305 comment).
- `unified_levels.json` — FRESH (today). Tokens populated but `spot` top-level field is empty string.

**Action:** before building the bigger-picture block, the options pipeline needs investigation: why `daily_levels.json` is stale, why `price`/`spot` fields are empty in `macro_levels.json`/`unified_levels.json`, and why NQ/ES futures are missing from `weekly_em_scope.json`. The empty `price`/`spot` is a consumer-side bug (should read `cash_spot`), not a producer gap.

---

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