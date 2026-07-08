# Narrative Engine v2 — Build Plan

> **Date**: 2026-07-08  
> **Status**: ACTIONABLE — ready for implementation  
> **Prerequisite**: `docs/architecture/NARRATIVE_ENGINE_V2_PLAN.md` (design doc)

---

## 0. Script Verification — Issues Found

Before building on existing scripts, we must fix/address these issues:

| # | Script | Issue | Severity | Fix |
|---|--------|-------|----------|-----|
| 1 | `data/derived/NQ1_herman_stats.parquet` | **STALE** — last date 2026-01-23, 166 days behind | 🔴 Critical | Must re-run `precompute_herman_stats.py` before using. Add a staleness check to the narrative pipeline. |
| 2 | `data/derived/NQ1_daily_classification.parquet` | **STALE** — last date 2026-01-23, 166 days behind | 🔴 Critical | Must re-run the classification batch job. Add staleness check. |
| 3 | `data/expected_moves.json` | **EMPTY** — `data: []`, no actual EM values | 🔴 Critical | Options pipeline must be running or EM computation needs to be triggered. Narrative should handle missing EM gracefully. |
| 4 | `load_fused_data()` | Returns **naive (tz=None)** index — NQStatsEngine expects tz-aware | 🟡 Medium | Engine internally localizes, but `build_overnight_context()` must also handle this. Currently works because it localizes internally. |
| 5 | `get_prior_classification()` | Requires `target_date` argument — not obvious from docs | 🟢 Low | Document in the narrative module. |
| 6 | `data/options/unified_levels.json` | Structure is `tickers: [list]` not `tickers: {dict}` — existing `_extract_gex_levels` expects dict | 🟡 Medium | Verify `_extract_gex_levels` handles list format. May need adapter. |
| 7 | `NQ1_1d.parquet` | UTC timezone, bars at 18:00 ET (22:00 UTC) — daily bar represents prior ET evening start | 🟢 Low | For PDH/PDL, use the ET date mapping, not the UTC timestamp directly. |
| 8 | `NQ1_1W.parquet` | UTC timezone, `_week_start` index — week starts Sunday 22:00 UTC | 🟢 Low | For weekly profile, convert to ET and use Monday-anchored weeks. |
| 9 | `retrieve_ict_context.py` `main()` | Prints to stdout + returns dict — noisy for pipeline use | 🟢 Low | Call helper functions directly, not `main()`. |
| 10 | `CandleScienceService` | Expects `filters` dict — need to build auto-detect filters from last 2 daily candles | 🟡 Medium | Write a helper `build_candle_science_auto_filters(ticker)` that reads 1d parquet and constructs filters. |
| 11 | ML model `data/ml_models/NQ1_binary_model.pkl` | No `predict()` helper — must manually build 16-feature row | 🟡 Medium | Write `build_ml_features(nq_status, herman, prior_type) -> np.ndarray`. BUT: ML was dropped from v2 per senior trader review. Only build if we re-add it. |
| 12 | NQStatsEngine session times | Engine uses Asia 18:00-02:00, London 03:00-08:00 (old spec). NQ_SESSIONS_SPEC.md now says Asia 20:00, London 02:00 | 🟡 Medium | Verify engine session definitions match the updated spec. If mismatched, update engine or document the discrepancy. |

---

## 1. Build Phases

### Phase A: Data Freshness & Staleness Guards (Day 1 morning)

**Goal**: Ensure all precomputed data is current and the pipeline fails gracefully when data is stale.

| Task | Details | Files |
|------|---------|-------|
| A1: Re-run Herman precompute | `python -m scripts.derived.precompute_herman_stats --ticker NQ1` | `data/derived/NQ1_herman_stats.parquet` |
| A2: Re-run classification batch | Run the classification pipeline to update through today | `data/derived/NQ1_daily_classification.parquet` |
| A3: Check EM pipeline | Verify `data/expected_moves.json` is being populated by the options pipeline. If empty, trigger a refresh. | `data/expected_moves.json` |
| A4: Add staleness guard module | Create `scripts/trader/data_freshness.py` — checks each Tier 1 data source for staleness. Returns `{source, last_date, days_stale, is_stale}`. Narrative pipeline calls this first and logs warnings for stale sources. | `scripts/trader/data_freshness.py` |
| A5: Verify NQStatsEngine session times | Check `scripts/libs_py/nqstats/sessions.py` for Asia/London start times. Compare with `NQ_SESSIONS_SPEC.md`. If mismatched, update or document. | `scripts/libs_py/nqstats/sessions.py` |

**Staleness guard design**:
```python
# scripts/trader/data_freshness.py
@dataclass
class FreshnessCheck:
    source: str
    last_date: str | None
    days_stale: int
    is_stale: bool  # > 3 days = stale
    warning: str | None

def check_all() -> list[FreshnessCheck]:
    checks = [
        check_herman("NQ1"),
        check_classification("NQ1"),
        check_em(),
        check_gex_levels(),
    ]
    return checks
```

**Verification**: Run `data_freshness.check_all()` and confirm all sources report fresh data.

---

### Phase B: Config & Static Data (Day 1 morning)

**Goal**: Create the YAML config file and verify all static probabilities.

| Task | Details | Files |
|------|---------|-------|
| B1: Create `narrative_stats.yaml` | All static probabilities from the plan: ALN, RTH breaks, Herman pre-NY, Asia range, sweep-return, IB, noon curve, hourly personalities, candle science, VIX/VVIX regimes, day types, day of week, killzones, dead zones, no-trade rules, weekly profiles, ICT liquidity rules | `scripts/trader/config/narrative_stats.yaml` |
| B2: Create config loader | `scripts/trader/config_loader.py` — loads YAML once, caches in module-level variable. All modules import from here. | `scripts/trader/config_loader.py` |
| B3: Verify unified_levels JSON structure | Confirm `_extract_gex_levels()` in `briefing_core.py` handles the `tickers: [list]` format. Fix if needed. | `scripts/trader/briefing_core.py` |

**Config design principles**:
- Single source of truth for all probabilities
- YAML (human-readable, easy to update)
- Loaded once at startup, cached
- Versioned (include a `version` field)
- Schema-validated on load (fail fast if missing required keys)

**Verification**: Load config, verify all sections present, print a summary.

---

### Phase C: Signal Modules — Build & Test Individually (Day 1 afternoon - Day 2)

Each signal module is built and tested in isolation. Each follows the same pattern:
1. Build the function
2. Test with live data
3. Verify output structure
4. Log any data issues

#### C1: VIX + VVIX Regime + Divergence (2h)

**File**: `scripts/trader/signals/volatility.py`

```python
def get_vix_vvix_checkpoint() -> dict:
    """Returns:
    {
        vix_close, vix_prev, vix_chg, vix_regime,  # QUIET/CALM/NORMAL/ELEVATED/HIGH/CRISIS
        vvix_close, vvix_prev, vvix_chg, vvix_regime,
        vvix_roc_regime,  # fear_building/caution/neutral/unwinding
        divergence_read,  # panic/hedging/complacency/smart_money/calm
        sizing_multiplier  # 1.0 / 0.75 / 0.5 / 0.25
    }
    """
```

**Data**: `data/live/live_storage_VIX.parquet`, `data/live/live_storage_VVIX.parquet`, `data/VIX_1d.parquet`, `data/VVIX_1d.parquet`

**Test**: Run function, verify VIX regime matches expected tier. Verify VVIX ROC direction. Verify divergence read. Cross-check: if VIX is ~14.8 and VVIX is ~88, regime should be CALM/NORMAL.

**Future-proofing**: Config thresholds in YAML. If VIX distribution shifts over time, update thresholds without code change.

---

#### C2: Expected Move Completeness (1h)

**File**: `scripts/trader/signals/expected_move.py`

```python
def get_em_context(spot: float, ticker: str = "NQ1") -> dict:
    """Returns:
    {
        em_upper, em_lower, em_range,
        price_position_pct,  # 0-100%
        read,  # "magnet/target" or "trend day signal" if exceeded
        is_exceeded  # bool
    }
    """
```

**Data**: `data/expected_moves.json` (currently empty — handle gracefully with `None` return + warning)

**Test**: With empty EM, verify function returns `{"read": "EM unavailable"}`. With valid EM, verify position computation.

**Future-proofing**: Store EM history in Prisma DB (new `ExpectedMove` table) for regime analysis. For now, JSON is sufficient.

---

#### C3: GEX Regime Change Detection (2h)

**File**: `scripts/trader/signals/gex_regime.py`

```python
def get_gex_regime_change(today_gex: dict, yesterday_gex: dict | None) -> dict:
    """Returns:
    {
        flip_crossed: bool,
        wall_moved: str | None,  # "call_wall up 50pts" etc
        regime_change: str,  # "stable" / "flip crossed: neg→pos" / "call wall broken overnight"
    }
    """
```

**Data**: Today's GEX from `data/options/unified_levels.json`. Yesterday's from Prisma DB `MacroSnapshot` table (or from a simple JSON archive we write daily).

**Test**: Compare 2 consecutive days of GEX snapshots, verify delta computation.

**Long-term storage**: Write a daily GEX snapshot to `data/options/daily/gex_snapshots/{date}.json` for historical regime change analysis. Also store in Prisma DB if schema allows.

---

#### C4: ICT Context from HTF Parquet (2h)

**File**: `scripts/trader/signals/ict_context.py`

```python
def compute_ict_from_htf(df_1d: pd.DataFrame, df_1w: pd.DataFrame, overnight: dict) -> dict:
    """Returns:
    {
        pdh, pdl, pdc, midnight_open,
        pwh, pwl,  # prior week high/low
        dealing_range_pct,  # price position in PDH-PDL range
        premium_discount: str,  # "PREMIUM" / "DISCOUNT"
        bsl_target, ssl_target,  # liquidity targets
        weekly_range_pct  # price position in PWH-PWL range
    }
    """
```

**Data**: `data/NQ1_1d.parquet`, `data/NQ1_1W.parquet` (both UTC, need ET conversion)

**Test**: Load 1d/1W, compute PDH/PDL, verify against known values. Check midnight open computation.

**Future-proofing**: Use HTF parquet (fast, ~0.5s) instead of full 1m historical (~3-5s). If 1d parquet is stale (not updated by live pipeline), fall back to computing from 1m fused data.

---

#### C5: ICT Liquidity Map (1h)

**File**: `scripts/trader/signals/liquidity_map.py`

```python
def build_liquidity_map(bias: str, nq_status: dict, overnight: dict, ict: dict, news_tier: str) -> dict:
    """Returns:
    {
        bias: str,
        raid_target: str,  # "Asian low 25649" / "London high 29415" etc
        raid_target_level: float,
        level_equality: str,  # "equal" / "disparate"
        weekly_position: str,  # "discount" / "premium"
        entry_timing: str,  # "post-raid, not pre-raid"
    }
    """
```

**Data**: NQStatsEngine status (session H/L), overnight context, ICT levels, news tier from day-type classifier

**Test**: With known NQ status (ALN=LPED, London H=29415, London L=28910), verify raid target is correct for bearish bias.

---

#### C6: Weekly Profile (2h)

**File**: `scripts/trader/signals/weekly_profile.py`

```python
def compute_weekly_profile(df_1d: pd.DataFrame, df_1w: pd.DataFrame, today: date) -> dict:
    """Returns:
    {
        week_high, week_low, week_high_day, week_low_day,
        profile_type: str,  # bullish_run / bearish_run / inside / outside / balanced
        current_position: str,  # "near HOW" / "near LOW" / "mid-range"
        day_context: str,  # "LOW forming" / "inflection" / "HOW/LOW likely set"
        alignment: str,  # "ALIGNED" / "CONFLICTING" / "NEUTRAL"
    }
    """
```

**Data**: `data/NQ1_1d.parquet` (for current week H/L + timestamps), `data/NQ1_1W.parquet` (for prior week range)

**Test**: Load current week's daily bars, compute HOW/LOW with day-of-week, verify profile classification.

**Long-term storage**: Store weekly profile classifications in `data/derived/{ticker}_weekly_profiles.parquet` for backtesting profile accuracy.

---

#### C7: Day Type Classifier (2h)

**File**: `scripts/trader/signals/day_type.py`

```python
def classify_day_type(events: list[dict], today: date) -> dict:
    """Returns:
    {
        day_type: str,  # CLEAN / CPI / NFP / FOMC / SPECIAL / HOLIDAY
        sizing_multiplier: float,
        events_today: list,
        killzones: list[str],
        no_trade_zones: list[str],
        guidance: str,
    }
    """
```

**Data**: Prisma DB `EconomicEvent` table (via `fetch_week_events` or direct query)

**Test**: Query today's events, classify day type, verify against calendar. Test with known CPI/NFP/FOMC dates.

---

#### C8: Candle Science Auto-Detect (2h)

**File**: `scripts/trader/signals/candle_science.py`

```python
def get_candle_science_read(ticker: str = "NQ1") -> dict:
    """Returns:
    {
        c1_dir: str, c2_dir: str,
        pattern_desc: str,
        n_matches: int,
        p_bull: float, p_bear: float,
        p_break_high: float, p_break_low: float,
        p_close_gt_c2c: float,
        edge: float,
        mfe: {p30, median, p70},
        mae: {p30, median, p70},
        rr_envelope: float,
        agrees_with_bias: str | None,
    }
    """
```

**Data**: `data/NQ1_1d.parquet` (for last 2 daily candles), `CandleScienceService.calculate_stats()` (for pattern match)

**Test**: Read last 2 daily candles, build auto-detect filters, call CandleScienceService, verify MFE/MAE percentiles are populated.

---

#### C9: Confluence Assessment (1h)

**File**: `scripts/trader/signals/confluence.py`

```python
def assess_confluence(signal_1: str, signal_2: str, signal_3: str) -> dict:
    """Returns:
    {
        overnight_signal: str,  # BULLISH / BEARISH / NEUTRAL
        rth_open_signal: str,
        daily_chart_signal: str,
        confluence: str,  # HIGH / MEDIUM / LOW
        sizing: float,  # 1.0 / 0.5-0.75 / 0.25
        conviction_note: str,
    }
    """
```

**Test**: Test all combinations (3/3 agree, 2/3 agree, conflict). Verify sizing multiplier.

---

### Phase D: Cheat Sheet Assembly (Day 2 afternoon)

**Goal**: Wire all signal modules into the unified cheat sheet builder.

| Task | Details |
|------|---------|
| D1: Create `signals/__init__.py` | Package init, exports all signal functions |
| D2: Refactor `build_trader_cheat_sheet()` | Replace existing implementation with 12-block structure. Each block calls the corresponding signal module. Graceful degradation: if a signal module fails, log warning and skip that block (don't crash the whole narrative). |
| D3: Add error handling | Each block wrapped in try/except. Failed blocks return `"== [BLOCK NAME] ==\nData unavailable: [error]"`. Narrative continues with remaining blocks. |
| D4: Add staleness check | Call `data_freshness.check_all()` at the start. Log warnings for stale sources. Don't skip stale sources — use them but note the staleness in the output. |
| D5: Test full cheat sheet | Run `build_trader_cheat_sheet(mode="open")`, verify all 12 blocks populated, verify token count < 2000. |

**File**: `scripts/trader/briefing_core.py` (modified) + `scripts/trader/signals/` (new package)

---

### Phase E: Prompt Template Update (Day 2 afternoon)

| Task | Details |
|------|---------|
| E1: Update `trader_morning.md` | Add confluence model rules, ICT liquidity raid rules, weekly profile rules, day type rules, VIX/VVIX interpretation rules, EM interpretation rules, ES divergence rules |
| E2: Remove old ALN/RTH rules from prompt | These are now in the cheat sheet data blocks + config. The prompt should have interpretation RULES, not probabilities. |
| E3: Test with Ollama | Run full narrative with `trader_narrative.py --mode open`, verify ~400 word output covers all key blocks. |

**File**: `scripts/trader/prompts/trader_morning.md`

---

### Phase F: Bias Grade Feedback Loop (Day 3)

| Task | Details |
|------|---------|
| F1: Create bias grade storage | `data/options/daily/bias_grades.jsonl` — append-only. Each entry: `{date, morning_bias, actual_outcome, correct, pattern, confluence_level}` |
| F2: Add grading to close mode | At 16:05, compare morning bias to actual session outcome. Write grade to JSONL. |
| F3: Add recent accuracy to open cheat sheet | Read last 5 entries, compute accuracy %. Include in Block 12 (Prior EOD Plan). |

---

### Phase G: Integration & Scheduling (Day 3)

| Task | Details |
|------|---------|
| G1: Wire into `run_options_levels.py` | Add narrative generation at 08:00 (open), 12:00 (intraday — v1.5), 16:05 (close — v1.5) |
| G2: Discord webhook routing | Open narrative → trading channel. Trade plan → trade-alerts channel. |
| G3: End-to-end test | Full pipeline run during live session. Verify all blocks populate, narrative generates, output saves to disk + Discord. |

---

## 2. Long-Term Data Storage Design

Data that should be persisted for future analysis:

| Data | Storage | Purpose | Update Frequency |
|------|---------|---------|------------------|
| Herman stats | `data/derived/{ticker}_herman_stats.parquet` | Precomputed session stats | Daily (after 16:00 ET) |
| Daily classification | `data/derived/{ticker}_daily_classification.parquet` | R1/R2/DWP/DNP labels | Daily (after 16:00 ET) |
| Weekly profiles | `data/derived/{ticker}_weekly_profiles.parquet` | Weekly profile classification | Weekly (Friday after 16:00) |
| GEX snapshots | `data/options/daily/gex_snapshots/{date}.json` | Historical GEX regime changes | Daily (from live pipeline) |
| Bias grades | `data/options/daily/bias_grades.jsonl` | Narrative accuracy tracking | Daily (at close) |
| Narrative outputs | `data/options/daily/{date}_trader_narrative_{mode}.md` | Historical narrative archive | Per narrative run |
| Config version | `scripts/trader/config/narrative_stats.yaml` (versioned) | Probabilities may change over time | Manual updates |

**Future**: Move GEX snapshots and bias grades to Prisma DB tables for queryability. For v2, files are sufficient.

---

## 3. Performance Targets

| Metric | Target | Strategy |
|--------|--------|----------|
| Cheat sheet build time | < 4s | Tier 1 reads (~0.4s) + live compute (~3s) |
| LLM generation time | < 30s | gemma4:latest, ~2500 input tokens, ~500 output tokens |
| Total narrative time | < 35s | Build + LLM + save + Discord |
| Memory | < 500 MB | Load 10-day 1m window only (~9K rows), not full history |
| Error rate | < 5% per block | Graceful degradation — failed blocks skipped, not fatal |

---

## 4. Verification Checklist

Each signal module must pass before integration:

- [ ] **C1 VIX/VVIX**: Returns correct regime for known VIX/VVIX values. Divergence read is directionally correct.
- [ ] **C2 EM**: Handles missing EM gracefully. Position computation correct when EM available.
- [ ] **C3 GEX regime**: Detects flip crossing correctly. Wall movement delta accurate.
- [ ] **C4 ICT**: PDH/PDL match known daily highs/lows. Midnight open correct. Premium/discount classification correct.
- [ ] **C5 Liquidity map**: Raid target matches bias direction. Level equality check works.
- [ ] **C6 Weekly profile**: Profile type classification correct for known week patterns. HOW/LOW timestamps accurate.
- [ ] **C7 Day type**: CPI/NFP/FOMC correctly identified. Clean days not misclassified.
- [ ] **C8 Candle Science**: Auto-detect filters match last 2 candles. MFE/MAE percentiles populated.
- [ ] **C9 Confluence**: All 3 signals correctly classified. Sizing multiplier correct for each confluence level.
- [ ] **D4 Error handling**: Simulate each signal module failure, verify cheat sheet still generates with remaining blocks.
- [ ] **D5 Full cheat sheet**: All 12 blocks populated. Token count < 2000. No crashes.
- [ ] **E3 LLM test**: Narrative covers key blocks. ~400 words. No hallucinated prices.
- [ ] **G3 End-to-end**: Full pipeline runs in < 35s. Output saved to disk + Discord.

---

## 5. Timeline

| Day | Phase | Deliverable |
|-----|-------|-------------|
| Day 1 AM | A + B | Fresh data + config YAML + staleness guards |
| Day 1 PM | C1-C4 | VIX/VVIX, EM, GEX regime, ICT context modules tested |
| Day 2 AM | C5-C9 | Liquidity map, weekly profile, day type, candle science, confluence modules tested |
| Day 2 PM | D + E | Cheat sheet assembly + prompt update + LLM test |
| Day 3 AM | F | Bias grade feedback loop |
| Day 3 PM | G | Integration + scheduling + end-to-end test |

**Total: 3 days.** Each signal module is independently testable. The system degrades gracefully if any module fails.