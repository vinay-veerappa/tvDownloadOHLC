# ICT Phase 2 — Implementation Plan

> **Date:** 2026-07-13
> **Status:** PLANNED — Phase 1 complete, Phase 2 in progress
> **Goal:** Complete the remaining ICT concepts (OB, Judas, MSS/BOS, DOL, Delivery Triad, SMT), add historical bias validation, and build a PineScript visualization indicator.

---

## Phase 1 Summary (COMPLETE ✅)

### Library (ict_engine v1.3.0)
- `detect_ipda_ranges()` — IPDA 20/40/60 rolling dealing ranges
- `SILVER_BULLETS` dict + `get_silver_bullet_data()` — Silver Bullet windows
- `detect_fvg()` rewritten as canonical FVG (merged `detect_fvgs_v5`)
- `detect_volume_imbalance()` enhanced with `resample_rule` + `vi_finalized_time`
- `detect_gap_fills()` — tracks when NWOG/NDOG/RTH gaps get filled
- `nqstats.ib.detect_fvgs_v5` now delegates to library

### Derived Data Pipeline (`scripts/context/compute_ict_features.py`)
- `{sym}_imbalance_{tf}.parquet` — FVG + VI at 4 timeframes
- `{sym}_gaps.parquet` — NWOG + NDOG + RTH gaps with fill tracking
- `{sym}_kz_pivots.parquet` — Killzone pivots (AS/LO/NYAM H/L/mid/range)
- `{sym}_ipda.parquet` — IPDA 20/40/60 rolling ranges
- `{sym}_htf_levels.parquet` — PDH/PDL/PWH/PWL/PMH/PML

### Narrative Integration
- `ict_data_loader.py` — freshness-aware parquet loader with auto-refresh
- 6 new ICT feature blocks in `intraday_blocks.py` (KZ pivots, IPDA, Silver Bullet, Macros, Imbalances, Gaps)
- ICT feature blocks added to all 4 narrative modes (premarket, open, intraday, close)
- `compute_ict_daily_bias()` — 7-model ICT bias synthesis

### ICT Daily Bias Models (7 implemented)
| # | Model | What it measures | Status |
|---|-------|-----------------|--------|
| A | Premium/Discount | Price position in PDH/PDL dealing range | ✅ |
| B | Draw on Liquidity | Proximity to BSL vs SSL | ✅ |
| C | IPDA Position | 20/40/60-day rolling range position | ✅ |
| D | HTF Structure | Price vs PWH/PWL | ✅ |
| E | Prior Day Candle | Close vs PDH/PDL | ✅ |
| F | Midnight Open | Price above/below midnight open | ✅ |
| G | London/Asia Sweep | London swept Asia H/L = continuation | ✅ |

---

## Phase 2 Scope

### 2A: ICT Pattern Detection (derived data + narrative blocks)

#### 2A.1: Order Blocks
- **Library:** `detect_orderblock()` already exists in `ict_engine.core.pa`
- **Derived data:** `{sym}_ob_{tf}.parquet` — order block events (per-bar, only OB-positive rows)
- **Narrative:** `_format_ob_block()` in `intraday_blocks.py` — today's active OBs near price
- **Effort:** Low — library ready, just needs pipeline + narrative wiring

#### 2A.2: Swings + Structure (MSS/BOS/CISD)
- **Library:** `detect_swings()`, `detect_structure_breaks()`, `detect_cisd()` all exist in `structure.py`
- **Note:** `detect_structure_breaks()` currently does basic breach detection — BOS vs MSS classification needs improvement (the comment says "This requires tracking the sequence of Highs/Lows")
- **Derived data:**
  - `{sym}_swings_{tf}.parquet` — swing high/low events (per-bar, only swing-positive rows)
  - `{sym}_structure_{tf}.parquet` — BOS/MSS/CISD events (per-bar, only event rows)
- **Narrative:** `_format_structure_block()` — recent BOS/MSS events, current trend direction
- **Bias model H:** Daily MSS/BOS — add as 8th model in `compute_ict_daily_bias()`
- **Effort:** Medium — library needs MSS classification improvement, then pipeline + narrative

#### 2A.3: Judas Swing Detection
- **Concept:** Sweep of Midnight Open during London/Pre-Market that reverses
- **Library:** Needs new function — `detect_judas_swing()` in `cycles.py` or `pa.py`
- **Logic:**
  1. Identify Midnight Open (00:00 ET open price)
  2. Track price during London session (02:00-08:30 ET)
  3. Sweep = price pierces above/below Midnight Open then closes back
  4. Judas Swing up = swept above Midnight Open, closed below → bearish bias confirmed
  5. Judas Swing down = swept below Midnight Open, closed above → bullish bias confirmed
- **Derived data:** Part of `{sym}_structure_{tf}.parquet` or separate `{sym}_judas.parquet`
- **Narrative:** `_format_judas_block()` — "Judas swing detected at HH:MM — bias confirmed"
- **Effort:** Medium — new library function needed

#### 2A.4: Draw on Liquidity (Enhanced)
- **Current:** Model B in bias uses simple proximity (nearest BSL vs SSL)
- **Enhancement:** Add "magnet strength" — percent distance to target, and rank multiple liquidity pools
- **Also:** Track which pools have been swept today vs which are still untaken
- **Library:** `detect_liquidity()` already exists — returns BSL/SSL/EQH/EQL
- **Derived data:** `{sym}_liquidity_{tf}.parquet` — liquidity pool events
- **Narrative:** `_format_dol_block()` — ranked liquidity targets with sweep status
- **Effort:** Medium — library ready, needs pipeline + enhanced narrative block

#### 2A.5: Market Delivery Triad (I2E vs E2I)
- **Concept:** 
  - I2E (Internal to External): price just filled/mitigated an FVG → next draw is external liquidity (BSL/SSL)
  - E2I (External to Internal): price just swept external liquidity → next draw is internal imbalance (FVG)
- **Library:** Needs new function — `detect_delivery_triad()` combining FVG mitigation + liquidity sweep data
- **Depends on:** FVG mitigation tracking (`check_fvg_mitigation()` exists) + liquidity sweep detection
- **Derived data:** Part of `{sym}_structure_{tf}.parquet`
- **Narrative:** `_format_delivery_triad_block()` — "E2I mode: liquidity swept, next target is FVG at X"
- **Bias model I:** Delivery Triad — add as 9th model in `compute_ict_daily_bias()`
- **Effort:** High — requires combining multiple data sources

#### 2A.6: SMT Divergence
- **Library:** `detect_smt()` already exists in `correlation.py`
- **Derived data:** `{sym}_smt.parquet` — SMT divergence events (requires NQ+ES pair)
- **Narrative:** `_format_smt_block()` — "Bearish SMT: NQ made HH but ES made LH → bearish"
- **Bias model J:** SMT Divergence — add as 10th model in `compute_ict_daily_bias()`
- **Effort:** Medium — library ready, needs paired-symbol pipeline + narrative

---

### 2B: Historical Bias Validation

**Goal:** Backtest each of the 7+ ICT daily bias models against historical data to determine which models are predictive and which are noise.

#### 2B.1: Bias Backtest Framework
- **New file:** `scripts/context/validate_ict_bias.py`
- **Pattern:** Similar to existing `scripts/strategies/ict/archive/bias_*.py` but using our derived parquets
- **Method:**
  1. For each trading day in history (e.g., last 2 years):
     - Compute each bias model's signal at a fixed time (e.g., 09:30 ET open)
     - Record the directional prediction (BULLISH/BEARISH/NEUTRAL)
     - Record the actual outcome (close > open = bullish, close < open = bearish)
  2. Compute per-model statistics:
     - Win rate (% of days the model's direction matched the close direction)
     - Coverage (% of days the model produced a non-NEUTRAL signal)
     - Edge (win rate minus 50% baseline)
     - Profit factor (avg win magnitude / avg loss magnitude)
  3. Compute composite statistics:
     - All-models-agree win rate
     - N-models-agree win rate (for N=2,3,4,5)
     - Confidence bucket win rates (0-30%, 30-60%, 60-80%, 80-100%)
  4. Per-ticker breakdown (NQ1 vs ES1 vs CL1 vs GC1)
  5. Per-day-type breakdown (R1/R2/DWP/DNP days)
  6. Per-session breakdown (does the model work better on certain days?)
- **Output:** `data/derived/ICT/bias_validation_{sym}.parquet` + summary JSON
- **CLI:** `python -m scripts.context.validate_ict_bias --symbols NQ1,ES1 --lookback 500`
- **Effort:** Medium — needs historical parquet reads + bias computation at each date

#### 2B.2: Bias Model Weighting
- After validation, weight each model by its historical edge
- Models with negative edge → weight to 0 (disabled)
- Models with high edge → higher weight in composite score
- Store weights in `scripts/trader/config/bias_weights.yaml`
- `compute_ict_daily_bias()` loads weights and applies them
- **Effort:** Low — once validation data exists, this is config + formula change

#### 2B.3: Rolling Bias Accuracy Tracking
- **Existing:** `get_recent_bias_accuracy()` in `briefing_core.py` tracks last N bias grades
- **Enhancement:** Track per-model accuracy, not just the composite
- Show in the close narrative: "This week: Model A 60% accurate, Model B 45% accurate, ..."
- **Effort:** Low — extend existing tracking

---

### 2C: PineScript Visualization

#### 2C.1: Range Stack Indicator
- Multi-timeframe range stack visualization for TradingView
- Shows MICRO_5 through DAILY_1 ranges as horizontal lines
- Color-coded by status (in range, broke out up/down)
- **Effort:** Medium — PineScript development

#### 2C.2: ICT Features Dashboard
- KZ pivots + IPDA levels + Silver Bullet windows + Macros as visual levels
- FVG/VI zones shaded on chart
- Gap levels with fill status
- **Effort:** High — comprehensive PineScript

---

## Implementation Order (Priority)

```
Phase 2A (pattern detection):
  Step 1: Order Blocks (low effort, library ready)
  Step 2: Swings + Structure (medium, library needs MSS improvement)
  Step 3: SMT Divergence (medium, library ready)
  Step 4: Judas Swing (medium, new function needed)
  Step 5: DOL Enhanced (medium, library ready)
  Step 6: Delivery Triad (high, depends on 1+2)

Phase 2B (validation):
  Step 7: Bias Backtest Framework (can start in parallel with 2A)
  Step 8: Bias Model Weighting (after Step 7)
  Step 9: Rolling Accuracy Tracking (after Step 8)

Phase 2C (visualization):
  Step 10: Range Stack Indicator (can start in parallel)
  Step 11: ICT Features Dashboard (after 2A complete)
```

### New Bias Models to Add (Phase 2A)

| # | Model | Source | Data needed | Effort |
|---|-------|--------|-------------|--------|
| H | Daily MSS/BOS | §2.1-2.2 ICT KB | Swings + structure breaks | Medium |
| I | Delivery Triad | §2.3 bias doc | FVG mitigation + sweeps | High |
| J | SMT Divergence | §4 ICT KB | NQ+ES paired swings | Medium |
| K | Judas Swing | §5.3 ICT KB | Midnight open + London session | Medium |
| L | DOL Enhanced | §5.5 ICT KB | Liquidity pools + sweep tracking | Medium |

### New Derived Parquets (Phase 2A)

```
data/derived/ICT/
├── {sym}_ob_{tf}.parquet         — Order blocks (per-bar)
├── {sym}_swings_{tf}.parquet     — Swing highs/lows (per-bar)
├── {sym}_structure_{tf}.parquet  — BOS/MSS/CISD events (per-bar)
├── {sym}_liquidity_{tf}.parquet  — BSL/SSL/EQH/EQL pools (per-bar)
├── {sym}_smt.parquet             — SMT divergence events (per-bar, NQ+ES pair)
└── {sym}_judas.parquet            — Judas swing events (per-day)
```

### New Narrative Blocks (Phase 2A)

| Block | Function | Sessions |
|-------|----------|----------|
| Order Blocks | `_format_ob_block()` | All intraday |
| Structure | `_format_structure_block()` | All intraday |
| DOL Enhanced | `_format_dol_block()` | All intraday + close |
| Delivery Triad | `_format_delivery_triad_block()` | All intraday |
| SMT Divergence | `_format_smt_block()` | All intraday |
| Judas Swing | `_format_judas_block()` | London + NY AM |

---

## Existing Infrastructure (Reusable)

| Component | Location | Status |
|-----------|----------|--------|
| `detect_swings()` | `ict_engine/core/structure.py` | ✅ Ready |
| `detect_structure_breaks()` | `ict_engine/core/structure.py` | ⚠️ Basic (needs MSS classification) |
| `detect_cisd()` | `ict_engine/core/structure.py` | ✅ Ready |
| `detect_orderblock()` | `ict_engine/core/pa.py` | ✅ Ready |
| `detect_liquidity()` | `ict_engine/core/pa.py` | ✅ Ready |
| `detect_smt()` | `ict_engine/core/correlation.py` | ✅ Ready |
| `check_fvg_mitigation()` | `ict_engine/core/pa.py` | ✅ Ready |
| `detect_breaker()` | `ict_engine/core/pa.py` | ✅ Ready |
| `compute_ict_features.py` | `scripts/context/` | ✅ Ready (extend for new parquets) |
| `ict_data_loader.py` | `scripts/trader/signals/` | ✅ Ready (extend for new parquets) |
| `get_recent_bias_accuracy()` | `briefing_core.py` | ✅ Ready (extend for per-model tracking) |
| Bias backtest archive | `scripts/strategies/ict/archive/` | ✅ Reference patterns |

---

## Session Definitions Reference (Do NOT Harmonize)

| Regime | Source | Asia | London | Pre-NY/NY AM | Purpose |
|--------|--------|------|--------|-------------|---------|
| ICT | `ict_engine.sessions.KILLZONES` | 20:00-00:00 | 02:00-05:00 | 08:30-11:00 | ICT killzone pivots, Silver Bullets, macros |
| NQStats/ALN | `nqstats.sessions` | 18:00-02:00 | 03:00-08:00 | 08:00-09:30 | ALN pattern detection |
| Herman | `narrative_stats.yaml` | 20:00-00:00 | 02:00-05:00 | 05:00-08:00 | Liquidity sweep probabilities |
| Narrative | `session_ranges.py` | 18:00-02:00 | 02:00-08:30 | 09:30-11:30 | Cheat-sheet routing |

These are intentionally different. Each serves its own purpose with its own probabilities.