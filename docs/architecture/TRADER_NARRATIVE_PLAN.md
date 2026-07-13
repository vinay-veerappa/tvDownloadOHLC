# Trader's Morning Narrative — Design Plan

> **Status:** v2 IMPLEMENTED + ICT Phase 1 COMPLETE — open, intraday, close, and premarket modes live. Intraday is session-adaptive (Asia, London, NY AM, NY Lunch, NY PM). Multi-timeframe range detection. ICT dealing range + liquidity map. ICT Phase 1 adds: killzone pivots, IPDA 20/40/60, Silver Bullet windows, ICT Macros, FVG+VI imbalances, NWOG/NDOG/RTH gaps with fill tracking. Unified `ict_engine` library (v1.3.0) is the canonical source for all ICT detection. Derived ICT parquets in `data/derived/ICT/`. Narrative data loader with freshness-aware auto-refresh.  
> **Date:** 2026-07-08 (last updated 2026-07-13)  
> **Goal:** A narrative system that reads like a trader thinking out loud. Runs at any time during any session. Eventually enables active trade creation and management from the data.

---

## 1. Problem Statement

### What we have today

Two separate systems produce morning output:

| System | What it does | What it lacks |
|---|---|---|
| `run_daily_prep.py` | Pulls ALN, classification, ICT context, profiler stats, calendar. Assembles a section-by-section newsletter. | Each section stands alone. ALN doesn't talk to classification. News doesn't connect to overnight price action. No intermarket comparison (NQ vs ES vs VIX). It's a data dump, not a narrative. |
| `daily_narrative.py` | Pulls GEX levels, regime, track mandates from Prisma DB. Sends compact JSON to Ollama. LLM fills structured JSON slots (entry/stop/target). | Trade-plan focused, not narrative focused. No overnight price context. No ALN/classification data. No intermarket read. Each ticker is a separate JSON block — no cross-ticker synthesis. |

### What the "Clean Read" does that we don't

1. **Bridges overnight → today**: Takes the Globex session and uses it to frame the RTH open. "NQ spent the night crashing through value, bottomed at 29,557."
2. **Intermarket synthesis**: Looks at ES, NQ, and VIX *together*. "NQ is leading the downside but ES isn't following, VIX is flat — this is NQ-specific, not broad risk-off."
3. **News interpretation**: Doesn't just list "CPI at 8:30" — says what it *means* for the session. "Clean calendar today" or "landmine at 8:30."
4. **Conflict detection**: If ALN says bullish but price is below London Low, it calls out the conflict instead of pretending everything aligns.

---

## 2. Design Constraints

### Token budget (local Ollama — `gemma4:latest`)

The local model has a 32K context window (`num_ctx: 32768`) and 16K output cap (`num_predict: 16384`). However, larger prompts = slower generation + higher risk of the model losing focus or hallucinating.

| Approach | Input Tokens | Output Tokens | Total | Risk |
|---|---|---|---|---|
| Current (raw TOON JSON) | ~3,000–4,000 | ~2,000 | ~5,000–6,000 | Model loses signal in JSON noise |
| **Cheat Sheet (pre-digested)** | **~800–1,200** | **~1,500–2,000** | **~2,300–3,200** | Minimal — Python does the heavy lifting |

The cheat sheet cuts input by **60–70%** because:
- No JSON syntax overhead (brackets, quotes, nesting)
- Python pre-computes the "so what" (distances, trajectory, intermarket comparison)
- Only the final synthesis goes to the LLM

### Data availability

| Data Source | Available? | Location | Notes |
|---|---|---|---|
| GEX levels (walls, flip, magnet, EM) | ✅ | `data/options/unified_levels.json` + `unified_levels_open.txt` | Updated by options pipeline |
| Economic calendar | ✅ | Prisma DB (`EconomicEvent` table) | Filtered by impact + keywords |
| ALN / NQStats | ✅ | `scripts/analysis/analyze_daily_nqstats.py` | Returns dict with bias, ALN, levels |
| Daily classification | ✅ | `scripts/analysis/analyze_daily_classification_bias.py` | Returns dict with overnight_key, probs |
| ICT context (PDH/PDL, midnight open) | ✅ | `scripts/trader/retrieve_ict_context.py` | Returns dict with PDH/PDL/midnight |
| VIX/VVIX (daily close) | ✅ | `data/derived/market_friction_matrix.parquet` | `vix_close`, `vvix_close` columns |
| VIX intraday (1m bars) | ✅ Checkpoint | `DataLoader.load_price("VIX")` | **Checkpoint:** Verify VIX 1m parquet exists. If not, fall back to daily close from friction matrix. RTD can provide real-time VIX during RTH. |
| Overnight/Globex session bars (NQ, ES) | ✅ Confirmed | NQ1/ES1 parquet includes full 23h session | Globex 18:00→08:30 ET is available |
| Prior EOD plan (continuity) | ✅ | Prisma DB (`Trade` + `TradePlan` tables) | `get_previous_eod_plan()` already exists |
| **TOS RTD real-time futures price** | ✅ | `scripts/streaming/options/tos_rtd/adapter.py` | Sub-second `/ES`, `/NQ` LAST price. Windows-only, TOS desktop required. |
| **TOS RTD real-time Greeks** | ✅ | `scripts/streaming/options/tos_rtd/adapter.py` | Native GAMMA, DELTA, OPEN_INT, VOLUME, LAST, MARK, IMPL_VOL |
| **Hybrid coordinator** | ✅ | `scripts/streaming/options/tos_rtd/hybrid_coordinator.py` | RTD first, Schwab fallback. `get_futures_price()` method. |
| Active trades (DB) | ✅ | Prisma DB (`Trade` table, `status` field) | PENDING, FILLED, CLOSED, WIN, LOSS, STOPPED |
| Trade legs (options) | ✅ | Prisma DB (`TradeLeg` table) | Per-leg Greeks, prices, P&L |
| Quote snapshots | ✅ | Prisma DB (`QuoteSnapshot` table) | Real-time unrealized P&L, VIX, GEX regime per snapshot |

---

## 3. Narrative Modes

The narrative system runs at multiple points, each with a different purpose:

| Mode | Time (ET) | Purpose | Key Data | Output |
|---|---|---|---|---|
| **Premarket** | ~07:00 | Early prep before GEX open snapshot | Globex, prior EOD classification, GEX levels | "Premarket Read" |
| **Open** | ~08:00-08:30 | Pre-market prep. Overnight → today bridge. Set the bias. | Globex OHLC, ALN, classification, calendar, GEX, ICT, Herman, Candle Science, Confluence | "Trader's Morning Narrative" |
| **Intraday** | Anytime (on-demand) | Session-adaptive update. Detects current session and adapts. | Session-specific blocks (see below) | "Intraday Update" |
| **Close** | ~16:00-16:15 | EOD review. What happened? What did we learn? | Full session OHLC, level outcomes, ICT dealing range outcome, trade outcomes | "Trader's EOD Narrative" |

### Intraday session-adaptive modes

The intraday mode detects the current session and assembles only relevant blocks:

| Session | Time (ET) | Blocks included |
|---|---|---|
| **ASIA** | 18:00-02:00 | Prior EOD, globex overnight, GEX, ICT dealing range, ICT KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps, Herman Asia range size, range stack, calendar |
| **LONDON** | 02:00-08:30 | Asia box, PL sweep, London box, London OR, ALN, GEX, ICT, ICT KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps, range stack, calendar, ICT liquidity map |
| **NY AM** | 09:30-11:30 | RTH session, Herman Pre-NY sweep, IB, ALN, GEX, ICT, ICT KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps, range stack, calendar, ICT liquidity map |
| **NY LUNCH** | 11:30-13:30 | Session so far, IB, lunch range, GEX, ICT, ICT KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps, range stack, calendar |
| **NY PM** | 13:30-16:00 | Session direction, noon curve, lunch breakout, GEX, ICT, ICT KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps, range stack, calendar, ICT liquidity map |

Weekend → "Markets closed. Run weekly narrative." After close (16:00-18:00) → "Session complete. Run EOD narrative."

### Intraday mode specifics

The intraday narrative is **session-adaptive** — it detects the current trading session and assembles only the blocks relevant to that session. It can be run manually at any time.

#### Session detection

| Session | Time (ET) | Key Focus |
|---------|------------|-----------|
| **ASIA** | 18:00 - 02:00 | Overnight globex, prior EOD levels, Herman Asia range size, what to watch for London |
| **LONDON** | 02:00 - 08:30 | Asia box complete, London forming, Herman OR breakout, PL sweep continuation, sweep-return |
| **NY AM** | 09:30 - 11:30 | RTH open, IB forming, Herman Pre-NY sweep (DOMINANT), ALN resolution |
| **NY LUNCH** | 11:30 - 13:30 | Lunch range forming, low volume, manipulation zone |
| **NY PM** | 13:30 - 16:00 | PM expansion, lunch range breakout, noon curve, trend close |

Weekend → graceful exit ("markets closed, run weekly narrative"). After close → defer to EOD narrative.

#### Modular architecture

The intraday cheat sheet is built from modular signal modules in `scripts/trader/signals/`:

| Module | File | What it provides |
|--------|------|-----------------|
| Session detection | `session_ranges.py` | `detect_session()`, `compute_all_session_ranges()`, `detect_sweep()` |
| Intraday blocks | `intraday_blocks.py` | Per-session block builders + 6 ICT feature blocks (KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps) |
| Range detection | `range_detection.py` | Multi-timeframe range stack (MICRO_5 through WEEKLY_2), compression detection, adaptive tightest-range scan |
| ICT data loader | `ict_data_loader.py` | Freshness-aware parquet loader with auto-refresh trigger + fallback to live compute. Reads from `data/derived/ICT/` parquets |
| ICT context | `ict_context.py` | Thin wrapper delegating to `ict_data_loader.load_ict_context()`. PDH/PDL/midnight open, premium/discount, BSL/SSL targets |
| ICT liquidity map | `liquidity_map.py` | Raid target identification based on bias + news tier |
| Candle science | `candle_science.py` | C1→C2→C3 daily candle pattern probabilities |
| Confluence | `confluence.py` | 3-signal confluence model (overnight + RTH open + daily chart) |
| Day type | `day_type.py` | CLEAN/CPI/NFP/FOMC/SPECIAL/HOLIDAY classification with killzones |
| Expected move | `expected_move.py` | Options-based expected move context |
| GEX regime | `gex_regime.py` | Gamma regime change detection |
| Volatility | `volatility.py` | VIX/VVIX regime classification |
| Weekly profile | `weekly_profile.py` | Weekly H/L, profile type, position |
| Caution score | `caution_score.py` | Composite risk posture score |

`build_intraday_context()` in `briefing_core.py` is a thin wrapper that delegates to `build_intraday_cheat_sheet()` in `intraday_blocks.py`, which detects the session and dispatches to the appropriate builder.

#### Multi-timeframe range detection

The range detection module (`range_detection.py`) computes active ranges at multiple timeframes simultaneously:

| TF Level | Lookback | Source | Used For |
|----------|----------|--------|----------|
| MICRO_5 | 5 min | 1m parquet | Scalp / micro chop |
| MICRO_15 | 15 min | 1m parquet | Short-term entry |
| MICRO_30 | 30 min | 1m parquet | Chop detection |
| SHORT_60 | 60 min | 1m parquet | Hourly range |
| SHORT_120 | 120 min | 1m parquet | Session chunk |
| SESSION | Session H/L | session_ranges | Current session range |
| RTH | Full day | session_ranges | Day range |
| DAILY_1 | 1 day | 1d parquet | EOD + weekly |
| DAILY_3 | 3 days | 1d parquet | EOD + weekly |
| DAILY_5 | 5 days | 1d parquet | EOD + weekly |
| WEEKLY | 1 week | 1W parquet | Weekly |
| WEEKLY_2 | 2 weeks | 1W parquet | Weekly |

Each range reports H/L/mid/width/position%/touches/classification(TIGHT/NORMAL/WIDE)/breakout status.
Compression detection compares 15m ATR vs 60m ATR. Adaptive auto-range finds the tightest window where price has spent the most time.

#### Bias source per session

The intraday bias is derived differently depending on the session:

| Session | Bias Source |
|---------|------------|
| ASIA | Overnight globex direction (up/down/flat vs prior close) |
| LONDON | Overnight direction + London OR breakout (once 03:00 hits) + PL sweep continuation |
| NY AM | Herman Pre-NY sweep (DOMINANT: 86.4% bullish / 77.9% bearish) + IB break + ALN resolution |
| NY LUNCH | AM session direction. Lunch fade reversals ~40% (low probability) |
| NY PM | Lunch range breakout direction + noon curve + IB break + session direction |

### Active trade management

The ultimate goal is for the narrative system to not just *describe* the market but to *inform trade decisions*. This means:

1. **Narrative → Trade Plan**: The open narrative feeds into `daily_narrative.py` which generates the trade plan (entry/stop/target). This already exists.
2. **Trade Plan → Active Trade**: `extract_and_save_trade_plan()` in `daily_narrative.py` already creates `Trade` rows in the DB with status PENDING.
3. **Active Trade → Monitoring**: The intraday narrative checks active trades against current price via RTD. If a trade's stop is within X points, flag it. If a trade's target is hit, flag it.
4. **Monitoring → Management**: Future: the system can update trade status (e.g., mark as STOPPED when stop is hit, mark as WIN when target is hit) using RTD price feeds. This closes the loop.

```
Morning Narrative → Trade Plan → DB Trade (PENDING)
                              ↓
                        RTD fills price → Trade triggers (FILLED)
                              ↓
                        Intraday Narrative → checks trade vs price
                              ↓
                        Stop hit → Trade closes (STOPPED/LOSS)
                        Target hit → Trade closes (WIN)
                              ↓
                        EOD Narrative → reviews outcome → tomorrow plan
```

This is a phased goal. v1 produces the narrative only. v2 adds active trade awareness (reading trades from DB). v3 adds trade management (writing trade status updates).

---

## 4. Architecture: Two-Phase Approach

```
┌──────────────────────────────────────────────────────────────┐
│                       EXISTING PIPELINE                        │
│                                                                │
│  run_daily_prep.py          daily_eod_update.py               │
│  ├─ ALN / NQStats           ├─ GEX levels from DB            │
│  ├─ Classification           ├─ Level interactions            │
│  ├─ ICT context              ├─ Track alignment               │
│  ├─ Profiler stats           └─ Saves to Prisma DB           │
│  └─ Calendar events                                          │
│                                                                │
│  TOS RTD (real-time, RTH only)                                 │
│  ├─ HybridCoordinator.get_futures_price("/ES", "/NQ")        │
│  ├─ Native Greeks (GAMMA, DELTA, OPEN_INT, VOLUME, LAST)     │
│  └─ GreeksValidationResult (RTD vs BSM drift)                │
│                                                                │
│  Prisma DB                                                     │
│  ├─ Trade (PENDING → FILLED → CLOSED/WIN/LOSS/STOPPED)       │
│  ├─ TradePlan (setup, entry/exit/risk plan)                  │
│  ├─ TradeLeg (per-leg Greeks, prices, P&L)                   │
│  ├─ QuoteSnapshot (real-time unrealized P&L, VIX, GEX)       │
│  └─ EconomicEvent (calendar with impact levels)              │
│                                                                │
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐            ┌──────────┐
        ▼            ▼            ▼            ▼          │
   ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
   │PREMARKET│ │  OPEN    │ │ INTRADAY  │ │  CLOSE   │    │
   │ ~07:00  │ │ ~08:00   │ │ ANYTIME   │ │ ~16:00   │    │
   │  ET     │ │  ET      │ │ on-demand │ │  ET      │    │
   └────┬────┘ └────┬─────┘ └─────┬────┘ └─────┬────┘    │
        │           │             │            │          │
        ▼           ▼             ▼            ▼          │
┌──────────────────────────────────────────────────────┐  │
│              TRADER NARRATIVE LAYER                   │  │
│                                                       │  │
│  Phase 1: Python Pre-Digestion (zero tokens)          │  │
│  ┌─────────────────────────────────────────────────┐  │  │
│  │ build_premarket_context()  [premarket mode]     │  │  │
│  │   Globex + prior EOD + GEX levels               │  │  │
│  ├─────────────────────────────────────────────────┤  │  │
│  │ build_ticker_cheat_sheet() [open mode]          │  │  │
│  │   Overnight + intermarket + ALN + classification│  │  │
│  │   + GEX + ICT + Candle Science + Confluence     │  │  │
│  │   + Day Type + Weekly Profile + Liquidity Map   │  │  │
│  │   + GEX Regime + EM + Prior EOD + Bias Grades   │  │  │
│  ├─────────────────────────────────────────────────┤  │  │
│  │ build_intraday_context()  [intraday mode]       │  │  │
│  │   → delegates to build_intraday_cheat_sheet()   │  │  │
│  │   → detects session (ASIA/LONDON/NY_AM/         │  │  │
│  │     NY_LUNCH/NY_PM)                             │  │  │
│  │   → dispatches to session-specific builder      │  │  │
│  │   → includes range stack + compression +        │  │  │
│  │     adaptive range from range_detection.py      │  │  │
│  ├─────────────────────────────────────────────────┤  │  │
│  │ build_eod_context()      [close mode]           │  │  │
│  │   Session summary + level outcomes + ALN        │  │  │
│  │   outcome + ICT dealing range outcome +         │  │  │
│  │   next session calendar + bias grade            │  │  │
│  └─────────────────────────────────────────────────┘  │  │
│                                                       │  │
│  Modular Signal Modules (scripts/trader/signals/):    │  │
│  ├─ session_ranges.py  → session detection + ranges   │  │
│  ├─ intraday_blocks.py → per-session block builders   │  │
│  ├─ range_detection.py → multi-TF range + compression │  │
│  ├─ ict_context.py     → PDH/PDL/midnight/prem-disc   │  │
│  ├─ liquidity_map.py   → ICT raid target map          │  │
│  ├─ candle_science.py  → C1→C2→C3 patterns            │  │
│  ├─ confluence.py      → 3-signal confluence model    │  │
│  ├─ day_type.py        → CLEAN/CPI/NFP/FOMC + KZ      │  │
│  ├─ expected_move.py   → options EM context           │  │
│  ├─ gex_regime.py      → gamma regime change          │  │
│  ├─ volatility.py      → VIX/VVIX regime              │  │
│  ├─ weekly_profile.py  → weekly H/L + profile type    │  │
│  └─ caution_score.py   → composite risk posture       │  │
│                                                       │  │
│  Phase 2: LLM Narrative (small token budget)          │  │
│  ┌─────────────────────────────────────────────────┐  │  │
│  │ trader_narrative.py --mode premarket|open|       │  │  │
│  │   intraday|close                                 │  │  │
│  │   Cheat sheet + mode-specific prompt → Ollama   │  │  │
│  │   Output: markdown narrative (~300-400 words)    │  │  │
│  └─────────────────────────────────────────────────┘  │  │
│                                                       │  │
└───────────────────────┬───────────────────────────────┘  │
                        │                                  │
                        ▼                                  │
┌──────────────────────────────────────────────────────────┘
│
│  Prompt Templates (scripts/trader/prompts/):
│  ├─ trader_premarket.md  → premarket (Globex + GEX + EOD)
│  ├─ trader_morning.md    → open (full cheat sheet + all guides)
│  ├─ trader_intraday.md   → session-adaptive (all session guides)
│  └─ trader_close.md      → close (EOD review + ICT outcome)
│
│  Run commands:
│  python -m scripts.trader.trader_narrative --mode premarket --ticker ES1
│  python -m scripts.trader.trader_narrative --mode open --ticker ES1
│  python -m scripts.trader.trader_narrative --mode intraday --ticker ES1
│  python -m scripts.trader.trader_narrative --mode close --ticker ES1
│
│  Output: data/options/daily/{date}_trader_narrative_{mode}_{ticker}.md
│          data/options/daily/latest_trader_narrative_{mode}_{ticker}.md
│
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Future TODOs

### ICT expansion — Phase 1 COMPLETE (2026-07-13)

**Completed items (library + derived data + narrative integration):**

- [x] ICT Killzone pivots: AS.H/AS.L, LO.H/LO.L, NYAM.H/NYAM.L — `detect_session_data()` in `ict_engine` + `{sym}_kz_pivots.parquet` + `_format_kz_pivots_block()`
- [x] ICT Silver Bullet windows: 10:00-11:00, 14:00-15:00, 03:00-04:00 — `SILVER_BULLETS` dict + `get_silver_bullet_data()` + `_format_silver_bullet_block()`
- [x] ICT Macros: 09:50-10:10, 10:50-11:10, 13:10-13:40, 15:15-15:45, 02:33-03:00, 04:03-04:30 — `MACROS` dict (already existed) + `_format_macro_block()`
- [x] ICT FVG (Fair Value Gap) detection — merged `detect_fvgs_v5` into canonical `detect_fvg()` in `ict_engine.core.pa` with `join_consecutive`, `require_candle_direction`, `resample_rule` params + `{sym}_imbalance_{tf}.parquet`
- [x] ICT Volume Imbalance detection — `detect_volume_imbalance()` enhanced with `resample_rule` + stored alongside FVG in imbalance parquet
- [x] ICT IPDA 20/40/60 ranges — `detect_ipda_ranges()` in `ict_engine.core.htf` + `{sym}_ipda.parquet` + `_format_ipda_block()`
- [x] NWOG/NDOG/RTH gap detection with fill tracking — `detect_gap_fills()` in `ict_engine.core.gaps` + `{sym}_gaps.parquet` + `_format_gaps_block()`
- [x] HTF levels (PDH/PDL/PWH/PWL/PMH/PML) — `detect_htf_levels()` (already existed) + `{sym}_htf_levels.parquet`
- [x] Unified library: `ict_engine` v1.3.0 is canonical source; `nqstats.ib.detect_fvgs_v5` is a wrapper
- [x] Derived data pipeline: `scripts/context/compute_ict_features.py` — batch generator with CLI + incremental updates
- [x] Narrative data loader: `scripts/trader/signals/ict_data_loader.py` — freshness-aware with auto-refresh

**Remaining items (Phase 2 — see [ICT_PHASE2_PLAN.md](file:///c:/Users/vinay/tvDownloadOHLC/docs/architecture/ICT_PHASE2_PLAN.md) for full details):**

- [ ] ICT Order Block detection — `detect_orderblock()` exists in library, needs derived data pipeline + narrative block
- [ ] ICT Judas Swing detection (sweep of Midnight Open during London/Pre-Market)
- [ ] ICT MSS/BOS — `detect_structure_breaks()` exists (needs MSS classification improvement), needs pipeline + narrative block
- [ ] ICT Draw on Liquidity (enhanced) — proximity to BSL/SSL pools with sweep tracking
- [ ] ICT Market Delivery Triad: I2E (fill FVG → seek external liquidity) vs E2I (sweep → revert to FVG)
- [ ] SMT Divergence — `detect_smt()` exists in library, needs paired-symbol pipeline + narrative block
- [ ] Historical bias validation — backtest each of the 7 bias models against historical data
- [ ] Bias model weighting — weight models by historical edge, disable negative-edge models
- [ ] Rolling per-model accuracy tracking in close narrative
- [ ] PineScript indicator for range stack + ICT features visualization

### Asia/London IB computation

- [ ] Compute Initial Balance during Asia and London sessions (currently only NY RTH IB via NQStats)
- [ ] Separate conversation — requires defining IB windows for each session

### Data freshness

- [ ] Herman stats parquet stale (last 2026-01-23, 171 days behind) — only used for static statistical references, not per-day data, so not blocking
- [ ] Daily classification parquet stale (last 2026-01-23) — same, used for sequential probabilities only

### Range detection expansion

- [ ] Integrate DAILY_3, DAILY_5, WEEKLY, WEEKLY_2 into EOD and weekly narratives
- [ ] PineScript indicator for range stack visualization

### Trade management (v3)

- [ ] Intraday narrative flags trade management actions (e.g., "stop 2 points away — manage now")
- [ ] Python updates Trade.status in DB via RTD price check

### Key principle: Nothing is replaced

The trader narrative is a **new layer** that sits on top of the existing pipeline. It runs *after* data is gathered but *alongside* (or before) the trade plan generator. The trade plan and the narrative are separate outputs with separate prompts.

---

## 5. The Cheat Sheet (Phase 1 — Python)

### Purpose

Python reads all the raw data and produces a pre-processed text block where the connections are already made. The LLM doesn't get raw JSON — it gets a pre-read summary with the "so what" already computed.

### Open mode cheat sheet

### Structure

```
== OVERNIGHT (Globex 18:00 → 08:30 ET) ==
NQ: Open 29,700 → Current 29,580 (down 0.40%)
    Session Low: 29,557 at 03:15 ET | Session High: 29,712 at 18:30 ET
    Trajectory: Sold off steadily after initial pop, bottomed pre-dawn
ES: Open 5,540 → Current 5,535 (down 0.09%)
    Session Low: 5,531 | Session High: 5,548
    Trajectory: Flat — barely participating in NQ's move
VIX: 14.82 (prev close 14.75) — slightly higher despite risk-off overnight

== INTERMARKET READ ==
NQ is leading the downside but ES is not following. VIX is flat.
This looks like NQ-specific weakness (tech rotation), not a broad risk-off.
The "flush" in NQ overnight may be an overshoot since ES and VIX aren't confirming.

== TODAY'S CALENDAR ==
08:30 ET [HIGH] CPI — This is the landmine. Expect volatility spike.
    No entries 15 min before. Wait for post-news settlement.
(Or: No market-moving events today. Clean session.)

== GEX STRUCTURE (NQ) ==
Call Wall: 29,800 (+0.37% from spot) — overhead resistance
Put Wall: 29,500 (-0.27% from spot) — below current price, close
Gamma Flip: 29,650 — we're below it (negative gamma, amplification regime)
Magnet: 29,600 — pulling price toward it

== GEX STRUCTURE (ES) ==
Call Wall: 5,580 | Put Wall: 5,500 | Flip: 5,545
ES is near its flip — less directional pressure than NQ.

== ALN / SESSION PATTERNS ==
Pattern: LPEU (London Partially Engulfs Up)
London High: 29,680 | London Low: 29,590 | Mid: 29,635
Bias: STRONG BULLISH (78% continuation probability)
CONFLICT: Price is already below London Low (29,590) — the bullish setup is under pressure

== CLASSIFICATION ==
Yesterday: R2 (Expansion)
Overnight Key: Bearish | Bullish
Most Likely Today: R2 (62%) — expansion day
But: If CPI breaks the put wall, this flips to R1 (reversal)

== KEY LEVELS TO WATCH ==
Overhead: 29,650 (flip) → 29,680 (London High) → 29,800 (call wall)
Support: 29,590 (London Low) → 29,557 (overnight low) → 29,500 (put wall)

== PRIOR EOD PLAN (overnight continuity) ==
Yesterday's EOD planned: MNQ long at 29,650, stop 29,580, target 29,800
Current price 29,580 — sitting right on the stop. Plan is in jeopardy.
```

### Intraday mode cheat sheet

```
== MID-DAY UPDATE (12:00 ET) ==

== MORNING BIAS (from 08:00 narrative) ==
Bias was: NQ-specific weakness, possible overshoot. Bullish ALN under pressure.
Key levels: flip 29,650 overhead, put wall 29,500 support.

== CURRENT PRICE (RTD real-time) ==
NQ: 29,720 (up 0.47% from open) — recovered from overnight lows
ES: 5,548 (up 0.24% from open) — catching up to NQ
VIX: 14.65 (down from 14.82 open) — fear is fading

== PLAN STATUS ==
Morning narrative said: "flush may be an overshoot, watch for recovery"
What happened: NQ recovered from 29,557 to 29,720 — the overshoot call was correct.
The CPI event at 08:30 caused a spike down to 29,540 (below put wall) then V-recovery.

== LEVEL INTERACTIONS SINCE OPEN ==
Call Wall 29,800: not tested
Gamma Flip 29,650: TESTED and BROKEN (price now above it — back to positive gamma)
Put Wall 29,500: tested at 08:35 (CPI spike), HELD
London High 29,680: BROKEN — price is above it now

== ACTIVE TRADES ==
MNQ Long: Entry 29,650 | Stop 29,580 | Target 29,800 | Status: FILLED
  Current price 29,720 → +70 pts unrealized | Stop 140 pts below | Target 80 pts above
  R:R now 1:0.5 (was 1:2 at entry) — reward shrinking, risk is the stop getting hit
  ASSESSMENT: Trade is winning. Consider trailing stop to 29,680 (London High, now support)

MES Long: Entry 5,540 | Stop 5,525 | Target 5,580 | Status: FILLED
  Current price 5,548 → +8 pts unrealized | Stop 23 pts below | Target 32 pts above
  ASSESSMENT: Trade is alive but ES is lagging. Still valid.

== CALENDAR UPDATE ==
08:30 CPI: PASSED — caused a spike but market recovered. No more events today.

== WHAT CHANGED ==
The overnight "NQ-specific weakness" read was correct — NQ recovered and is now
leading ES higher. The put wall held during the CPI spike. We're back above
the flip (positive gamma). The morning bias is still valid but has strengthened.
```

### Close mode cheat sheet

```
== EOD REVIEW (16:00 ET) ==

== TODAY'S SESSION ==
NQ: Open 29,580 → Close 29,850 (up 0.91%)
    High: 29,870 (14:22 ET) | Low: 29,540 (08:35 ET — CPI spike)
    Body: Bullish — strong recovery from overnight lows
ES: Open 5,535 → Close 5,565 (up 0.54%)
    High: 5,572 | Low: 5,528
    Body: Bullish but lagged NQ all day
VIX: Open 14.82 → Close 14.45 (down 2.5%) — fear unwound

== LEVEL OUTCOMES ==
Call Wall 29,800: TESTED and BROKEN (close above — bullish)
Gamma Flip 29,650: BROKEN upward (positive gamma confirmed)
Put Wall 29,500: TESTED at CPI, HELD — strong support confirmed
London High 29,680: BROKEN upward — continuation confirmed

== ALN OUTCOME ==
Pattern was LPEU (bullish, 78% continuation)
Result: NQ broke London High — CONTINUATION confirmed. ALN was correct.

== CLASSIFICATION OUTCOME ==
Predicted: R2 (Expansion, 62%)
Result: R2 confirmed — strong trend day with range expansion.

== TRADE OUTCOMES ==
MNQ Long: Entry 29,650 → Exit 29,850 (target hit) | P&L: +$400 | WIN
MES Long: Entry 5,540 → Exit 5,565 (still open, near target) | P&L: +$125 | OPEN

== DRAWDOWN STATUS ==
Cumulative P&L: +$525 today | Trailing DD remaining: $2,000 (full)
Account in profit — no DD pressure.

== TOMORROW'S CALENDAR ==
10:00 ET [MEDIUM] ISM Services — could move ES.
No HIGH impact events.

== TOMORROW'S SETUP ==
NQ closed at call wall (29,800) — this is resistance for tomorrow.
If we break above 29,800, next target is 29,900+ (no wall until then).
If we reject 29,800, expect pullback to 29,650 (old flip, now support).
ES is lagging — if it catches up, 5,580 (call wall) is the target.
```

### What Python pre-computes (so the LLM doesn't have to)

| Computation | Source | Output | Mode |
|---|---|---|---|
| Overnight session OHLC + trajectory | DataLoader 1m bars, filtered 18:00–08:30 ET | "Sold off steadily after initial pop, bottomed pre-dawn" | Open |
| Intermarket divergence | NQ vs ES vs VIX overnight moves | "NQ leading downside, ES not following, VIX flat" | Open |
| Calendar interpretation | EconomicEvent DB + impact level | "Landmine at 8:30" or "Clean session" | Open/Intraday/Close |
| GEX distances from spot | unified_levels + spot price | "+0.37% from spot" | All |
| ALN vs price conflict | ALN bias + current price vs London levels | "CONFLICT: price below London Low" | Open |
| Classification vs ALN agreement | Classification most_likely + ALN bias | "Agreement: both bullish" or "Conflict: ALN bullish, classification says R1" | Open |
| Prior EOD plan proximity | DB Trade + TradePlan + current price | "Sitting right on the stop" | Open |
| Key levels hierarchy | All sources merged + sorted by distance | Overhead/support ladder | All |
| **RTD real-time price** | `HybridCoordinator.get_futures_price()` | "NQ: 29,720 (up 0.47% from open)" | Intraday |
| **Active trade status** | DB `Trade` where status PENDING/FILLED + RTD price | "MNQ Long: +70 pts unrealized, stop 140 pts below" | Intraday |
| **Level interactions since open** | Morning levels vs current RTD price | "Gamma Flip: TESTED and BROKEN" | Intraday |
| **Plan vs reality check** | Morning narrative bias vs actual price action | "The overshoot call was correct — NQ recovered" | Intraday |
| **Trade outcomes** | DB Trade where status CLOSED + P&L | "MNQ: +$400 WIN" | Close |
| **Drawdown status** | Cumulative P&L from all closed trades | "Trailing DD remaining: $2,000" | Close |
| **Tomorrow's calendar** | EconomicEvent DB, next trading day | "10:00 ISM Services [MEDIUM]" | Close |
| **Session OHLC** | DataLoader 1m bars, filtered 09:30–16:00 ET | "High: 29,870 at 14:22 ET" | Close |
| **ALN/Classification outcome** | Actual price action vs predicted bias | "ALN was correct — continuation confirmed" | Close |

---

## 6. The LLM Prompts (Phase 2)

### File: `scripts/trader/prompts/trader_morning.md` (Open mode)

```markdown
You are a trader writing your morning prep notes. Below is a pre-processed
cheat sheet with all the data already connected. Write a narrative that:

1. Opens with the overnight story — what happened and what it means for the open
2. Notes the calendar risk — what could change the picture today
3. Describes the GEX structure in plain English — where is price trapped or free
4. Reads the ALN pattern and classification together — do they agree or conflict?
5. Ends with "What I'm watching" — 2-3 specific levels and what they mean

Rules:
- Plain English. No jargon. Talk like you're explaining to a friend.
- If the data conflicts (e.g., ALN says bullish but price is below London Low),
  call it out. Don't pretend everything aligns.
- Keep it under 400 words.
- Use the numbers from the cheat sheet. Don't invent prices.
- Don't give trade recommendations. This is a read, not a plan.

== CHEAT SHEET ==
{{INSERT_CHEAT_SHEET}}
```

### File: `scripts/trader/prompts/trader_intraday.md` (Intraday mode)

```markdown
You are a trader doing a mid-day check. The morning narrative set a bias.
Now you're checking: is the market following the plan? Write a narrative that:

1. Restates the morning bias in one sentence
2. Compares current price (via RTD) to the morning levels — what's been tested/broken?
3. Checks active trades — are they winning, losing, or in jeopardy?
4. Notes what changed since open (news, regime shifts, level breaks)
5. Ends with "Adjustment" — should we be more aggressive, defensive, or neutral?

Rules:
- Plain English. No jargon.
- If the morning bias is wrong, say so clearly. Don't double down on a bad call.
- If a trade is in jeopardy (stop close), flag it explicitly.
- Keep it under 300 words. This is a quick check, not a full essay.
- Use the numbers from the cheat sheet. Don't invent prices.

== CHEAT SHEET ==
{{INSERT_CHEAT_SHEET}}
```

### File: `scripts/trader/prompts/trader_close.md` (Close mode)

```markdown
You are a trader writing your end-of-day review. Write a narrative that:

1. Summarizes today's session — what happened from open to close
2. Grades the morning bias — was the read correct, partially correct, or wrong?
3. Reviews trade outcomes — what won, what lost, and why
4. Notes level accuracy — which walls held, which broke
5. Ends with "Tomorrow's setup" — based on today's close, what's the initial read?

Rules:
- Plain English. No jargon.
- Be honest about mistakes. If the morning bias was wrong, own it.
- Keep it under 400 words.
- Use the numbers from the cheat sheet. Don't invent prices.

== CHEAT SHEET ==
{{INSERT_CHEAT_SHEET}}
```

### Why no `<analysis_json>` extraction

The current `daily_narrative.py` forces the LLM to output structured JSON that Python slots into a template. This is necessary for trade plans (entry/stop/target need to be machine-readable).

The trader narrative is **for human consumption only**. The output is markdown. No JSON parsing, no slot filling, no template rendering. The LLM writes freely, and that's the final output.

This also saves tokens — no JSON structure overhead in the output.

---

## 7. Implementation Components

### New files

| File | Purpose | Status |
|---|---|---|
| `scripts/trader/trader_narrative.py` | Main script. `--mode open\|intraday\|close`. Calls cheat sheet builder, calls Ollama, saves output. | ✅ Created |
| `scripts/trader/prompts/trader_morning.md` | Open mode narrative prompt. | ✅ Created |
| `scripts/trader/prompts/trader_intraday.md` | Intraday mode narrative prompt. | ⏳ v2 |
| `scripts/trader/prompts/trader_close.md` | Close mode narrative prompt. | ⏳ v1.5 |

### New functions in `briefing_core.py`

| Function | Purpose | Mode | Status |
|---|---|---|---|
| `build_overnight_context(loader, ticker)` | Pull 1m bars via fused data loader, filter to Globex session (18:00–08:30 ET), compute OHLC + trajectory. Returns dict. | Open | ✅ |
| `build_intermarket_read(nq_ctx, es_ctx, vix_ctx)` | Compare NQ/ES/VIX overnight moves. Detect divergence. Returns text string. | Open | ✅ |
| `build_intraday_context(morning_narrative, rtd_prices, active_trades)` | Compare morning bias to current RTD price. Check active trades vs levels. Returns dict. | Intraday | ⏳ v2 |
| `build_eod_context(loader, morning_narrative, closed_trades)` | Full session OHLC, trade outcomes, level accuracy. Returns dict. | Close | ⏳ v1.5 |
| `build_trader_cheat_sheet(mode, ...)` | Mode-specific assembly of all data sources into the cheat sheet text block. Returns string (~800-1200 tokens). | All | ✅ (open) |
| `get_active_trades()` | Query DB for PENDING/FILLED trades with entry/stop/target. Returns list. | Intraday | ⏳ v2 |
| `compute_trade_proximity(trade, current_price)` | Compute unrealized P&L, distance to stop, distance to target. Returns dict. | Intraday | ⏳ v2 |
| `get_vix_checkpoint()` | Check if VIX 1m parquet exists. If yes, use intraday VIX. If no, fall back to daily close from friction matrix. Log which source was used. | All | ✅ |
| `_extract_gex_levels(unified_entry, ticker)` | Parse call wall, put wall, flip, magnet from unified_levels tokens. Translate SPY/QQQ proxy → futures scale. | All | ✅ |
| `_format_aln_block(aln_data, spot)` | Format ALN/session pattern data with conflict detection (price vs London levels). | Open | ✅ |
| `_format_gex_block(ticker_label, levels, spot)` | Format GEX structure with distances from spot. | All | ✅ |
| `_format_classification_block(class_data)` | Format daily classification probabilities. | Open | ✅ |
| `_format_key_levels_hierarchy(nq_gex, es_gex, aln_data, nq_spot)` | Merge all level sources into overhead/support ladder. | All | ✅ |
| `_format_calendar_for_cheat_sheet(events)` | Format economic events with impact interpretation. | All | ✅ |

### Existing files — changes

| File | Status |
|---|---|
| `briefing_core.py` | Extended (new functions appended, `asyncio` import added, `get_dataloader()` date_end fixed to `now + 1 day`) |
| `daily_narrative.py` | Unchanged — still generates trade plans |
| `daily_eod_update.py` | Unchanged — still populates DB |
| `run_daily_prep.py` | Unchanged — still generates charts + ICT newsletter |
| `weekly_narrative.py` | Unchanged |

---

## 8. Execution Flow

### Open routine (08:00 ET)

```
1. run_daily_prep.py --newsletter --tickers NQ1 ES1
   → Gathers ALN, classification, ICT, charts
   → Outputs newsletter to Discord (existing behavior)

2. daily_eod_update.py --session open
   → Populates Prisma DB with GEX levels + interactions (existing behavior)

3. trader_narrative.py --mode open
   → NEW: Reads all data sources (overnight bars, GEX, ALN, classification, calendar)
   → Builds cheat sheet (Python pre-digestion)
   → Calls Ollama with cheat sheet + morning prompt
   → Outputs markdown narrative to disk + Discord + DB

4. daily_narrative.py --session open
   → Reads DB, generates trade plan (existing behavior)
   → Creates Trade rows (PENDING) in DB
```

### Intraday routine (12:00 ET or on-demand)

```
1. trader_narrative.py --mode intraday
   → Reads morning narrative from disk/DB
   → Gets current price via RTD (HybridCoordinator) or DataLoader fallback
   → Queries active trades from DB (PENDING/FILLED)
   → Computes level interactions since open
   → Builds intraday cheat sheet
   → Calls Ollama with intraday prompt
   → Outputs mid-day update to disk + Discord

   FUTURE (v2/v3):
   → If trade stop is within X points → flag for management
   → If trade target is hit → update Trade.status in DB
```

### Close routine (16:00 ET)

```
1. daily_eod_update.py --session eod
   → Updates DB with full session OHLC + level interactions (existing)

2. trader_narrative.py --mode close
   → Reads full session bars, trade outcomes, drawdown status
   → Builds close cheat sheet
   → Calls Ollama with close prompt
   → Outputs EOD narrative to disk + Discord + DB

3. daily_narrative.py --session eod
   → Generates tomorrow's trade plan (existing)
   → Creates Trade rows (PENDING) for tomorrow
```

### Data source priority by mode

| Data | Open | Intraday | Close |
|---|---|---|---|
| Overnight bars (Globex) | DataLoader 1m parquet | — | — |
| Current price | DataLoader (pre-open) | **RTD** (real-time) | DataLoader (post-close) |
| GEX levels | unified_levels_open.txt | unified_levels.json (live) | unified_levels_close.txt |
| ALN/classification | run_daily_prep modules | Morning narrative (cached) | Actual outcome vs prediction |
| Active trades | Prior EOD plan (DB) | **DB Trade query + RTD price** | DB Trade outcomes (CLOSED) |
| Calendar | Today's events | Events passed since open | Tomorrow's events |

---

## 9. Output

### File output
```
data/options/daily/
├── latest_trader_narrative_open.md      ← always overwritten
├── latest_trader_narrative_intraday.md  ← always overwritten
├── latest_trader_narrative_close.md     ← always overwritten
├── 2026-07-08_trader_narrative_open.md  ← dated archive
├── 2026-07-08_trader_narrative_intraday.md
├── 2026-07-08_trader_narrative_close.md
```

### Discord output
Sent to `macro-alerts` webhook (same as existing narratives). Intraday mode could use a separate `intraday-alerts` webhook to avoid noise.

### DB storage
Store in `DailyEodUpdate.summaryMd` (existing field) for close mode. For open/intraday, either:
- New field on `DailyEodUpdate` (e.g., `openNarrativeMd`, `intradayNarrativeMd`)
- Or new table `TraderNarrative` with (date, mode, contentMd, createdAt)

This enables the web UI to display historical narratives and the intraday mode to read the morning narrative from DB instead of disk.

---

## 10. Token Efficiency Strategy

### Principle: Python digests, LLM writes

The LLM should never see raw data. It should only see pre-digested, pre-connected summaries. This means:

| Task | Who does it | Why |
|---|---|---|
| Reading JSON/files | Python | Free (no tokens) |
| Computing distances | Python | Free + deterministic |
| Detecting conflicts | Python | Free + deterministic |
| Comparing NQ vs ES vs VIX | Python | Free + deterministic |
| Interpreting what it all means | LLM | This is the actual value of the LLM |
| Writing the narrative | LLM | This is what LLMs are good at |

### Fallback: If data is too large

If the cheat sheet exceeds 1,500 tokens (e.g., many tickers, many events), we have two options:

1. **Truncate**: Drop lower-priority tickers (keep only NQ + ES + VIX). Drop low-impact events.
2. **Two-call split**: Call 1 = overnight + calendar + GEX. Call 2 = ALN + classification + levels. Merge in Python. (More complex, but keeps each call small.)

For v1, we start with option 1 (truncate to NQ + ES + VIX only).

---

## 11. Open Questions

1. **VIX intraday checkpoint**: We need to verify if VIX 1m parquet exists. The `get_vix_checkpoint()` function will check at runtime and log which source was used. During RTH, RTD can provide real-time VIX. Outside RTH, fall back to daily close from friction matrix. — **Action: Add checkpoint function, don't block on this.**

2. **DB storage**: New `TraderNarrative` table with `(id, date, mode, contentMd, createdAt)`. Clean separation from `DailyEodUpdate`. — **Decision: Confirmed. New table.** Will be added in v2 when DB storage is needed. v1 uses file + Discord only.

3. **Scheduler vs. on-demand**: For open/close, a scheduler (Windows Task Scheduler or a simple Python loop) makes sense. For intraday, on-demand is more flexible (triggered manually or by a webhook). — **Recommend: start with on-demand (CLI), add scheduler later.**

4. **Weekly version**: Should the weekly briefing also shift to this cheat-sheet approach? — **Recommend: keep weekly as-is for now. The weekly is a macro horizon briefing, different purpose. Focus on daily first.**

5. **Trade management scope**: v1 reads trades for awareness. v2 flags management actions. v3 writes trade status updates. Where do we draw the line for the first implementation? — **Decision: v1 = open mode only, file + Discord output, no DB storage, no RTD. Fine-tune the system before adding complexity.**

---

## 12. Phased Delivery

| Phase | Scope | Deliverable |
|---|---|---|
| **v1** | Open mode only. Cheat sheet + LLM narrative. File + Discord output. No DB storage. No RTD. | "Trader's Morning Narrative" — the basic read. **✅ DONE (2026-07-08)** |
| **v1.5** | Add close mode. Same cheat sheet approach but with session OHLC + trade outcomes. | "Trader's EOD Narrative" — the review. |
| **v2** | Add intraday mode. RTD real-time price. Active trade awareness (read from DB). DB storage for all modes. | "Mid-Day Update" — are we on track? |
| **v3** | Trade management. Intraday narrative flags management actions. Python updates Trade.status when stop/target hit via RTD price check. | Active trade management loop. |
| **v4** | Web UI integration. Display narratives in Next.js frontend. Historical narrative browser. | Visual narrative dashboard. |

---

## 13. Future Extensions (out of scope for v1)

- **Multi-ticker**: Extend beyond NQ + ES to include individual stocks (AAPL, NVDA, etc.).
- **Confidence scoring**: Python computes a confidence score for the narrative (how much do the data sources agree?).
- **Backtesting**: Run the cheat sheet builder on historical dates to test narrative quality.
- **Web UI**: Display the narrative in the Next.js frontend alongside the trade plan.

---

## 14. v1 Implementation Notes (2026-07-08)

### Performance (ADR-017 compliance)

The cheat sheet builder was profiled and optimized:

| Section | Before | After | Fix |
|---|---|---|---|
| Overnight NQ | 2.25s | 2.20s | Uses `load_fused_data` (live only) |
| Overnight ES | 2.15s | 2.02s | Same |
| VIX checkpoint | 0.01s | 0.01s | Already fast |
| Calendar (Prisma DB) | 2.16s | 2.11s | DB query, no change |
| GEX levels | 0.00s | 0.00s | File parse |
| Load fused NQ | 2.52s | 0.21s | `require_historical=False` (was True) |
| **NQStats engine** | **116.75s** | **0.26s** | **Filter to last 10 days (was full 6.5M rows)** |
| **TOTAL** | **125.84s** | **6.80s** | **15x speedup** |

Key fix: the NQStats engine is vectorized (ADR-017 compliant) but was processing the entire 6.5M-row fused dataset. Filtering to the last 10 days (~9K rows) gives identical results in 0.26s — a 449x speedup on that section alone.

### Data source fixes

1. **Fused data loader**: `build_overnight_context()` uses `load_fused_data` from `scripts/utils/fused_data_loader.py` instead of `DataLoader.load_price()`. The DataLoader only reads historical parquet (ends 2025-12-31); the fused loader includes live storage with current data.

2. **ALN engine**: Uses `scripts.libs_py.nqstats.engine.NQStatsEngine.get_latest_status()` directly instead of the `analyze_daily_nqstats.py` CLI script. The CLI script has a stale column name mismatch (`asia_quadrant` vs the engine's `asiabox_status`) that causes a `KeyError` on every run.

3. **1677 timestamp fix**: Dropped 1 corrupt row from `data/live/live_storage_-NQ.parquet` (row 0 had `time = -9223372036854.775` — an int64-min sentinel value that converted to 1677-09-21 and caused pandas `OutOfBoundsDatetime` overflow in the NQStats engine).

### End-to-end test result

```
python -m scripts.trader.trader_narrative --mode open
```

Output: ~400-word morning narrative written to `data/options/daily/latest_trader_narrative_open.md` + dated archive. Sent to Discord `macro-alerts` webhook.

The narrative correctly synthesized:
- Overnight story (NQ -1.65%, ES -0.95%, VIX up — broad risk-off)
- Calendar risk (3 high-impact events: Crude, 10Y Auction, FOMC Minutes)
- GEX structure (bearish trending regime, negative gamma)
- ALN + classification agreement (LPED continuation, R1 most likely — "everything aligned on the downside")
- Key levels to watch (London High, Magnet, Put Wall)