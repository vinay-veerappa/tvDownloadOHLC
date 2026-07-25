# IB Strategy System — Product Requirements Document (PRD)

**Version:** 1.0.0
**Author:** Claude (GitHub Copilot)
**Last Updated:** 2026-07-25
**Source plan:** [`docs/plans/2026-07-24-ib-data-gathering-plan.md`](../../plans/2026-07-24-ib-data-gathering-plan.md)
**Supersedes / extends:** [`IB_STATS_PIPELINE_SPEC_v5.md`](./IB_STATS_PIPELINE_SPEC_v5.md), [`docs/plans/2026-06-04-ib-stats-pipeline.md`](../../plans/2026-06-04-ib-stats-pipeline.md)

---

## 1. Executive Summary

The **IB Strategy System** is a regime-switching trading framework for Initial Balance (IB) strategies across global futures (ES1, NQ1, YM1, RTY1, CL1, GC1). It is **not** a single strategy — it is a data pipeline, a validation harness, and a play router that selects the optimal entry/stop/take-profit configuration per day based on empirical filter effectiveness.

### 1.1 Core Goals

1. **Empirical, not asserted** — every filter weight is learned from 20+ years of data, not hand-tuned.
2. **Decomposable** — every signal is stored as its own column so filters can be tested individually and in combinations.
3. **Regime-aware** — a router classifies each day as trend / normal / range / skip and selects the appropriate play.
4. **Combinatorial** — 21 entry techniques × 17 stops × 20 take-profits = a large but tractable strategy space, swept per play per regime.
5. **Prop-firm viable** — all intraday strategies respect ADR-020 (exit by 16:00 ET) and are evaluated via `PropFirmSimulator` (ADR-021).

### 1.2 Target Path to 80% WR

The system does not seek a single 80% WR strategy. It seeks **per-regime plays that each hit 65–70% WR in their optimal regime**, combined with **MAE-calibrated stops** that lift R:R from 1:1 to 2:1, yielding expectancy of 0.8–1.2R. The regime router filters out non-tradeable days, so the *system* WR across traded days is ~65% while each individual play in its optimal regime is 65–70%.

---

## 2. User Personas

| Persona | Description | Key Need |
| :--- | :--- | :--- |
| **The Quant Researcher** | Tests filter effectiveness, builds strategy variants. | Filter-effectiveness tables, combinatorial sweep tools, clean derived data. |
| **The Discretionary Trader** | Trades IB setups daily on NQ/ES. | Daily regime classification, conviction score, suggested play + direction. |
| **The Algo Operator** | Runs validated strategies in live/prop-firm sim. | Calibrated stops, profit ladders, session-boundary exit rules, prop-firm metrics. |
| **The Newsletter Author** | Publishes daily IB briefings. | Pre-computed confluence snapshot, human-readable rationale. |

---

## 3. Scope

### 3.1 In Scope

- 6 Phases of derived-data pipeline (Phase 1–6) producing ~15 parquet tables in `data/derived/`.
- 83 testable strategies (3 existing core + 80 new) across 13 categories.
- 21 entry techniques, 17 stop techniques, 20 take-profit techniques (building blocks).
- Empirically-derived conviction score (`conviction_score_v2`) replacing the hand-tuned baseline.
- Regime-switching play router (trend / normal / range / skip).
- Prop-firm simulation validation per ADR-021.
- 14 Tier-3 strategies gated behind new data feeds (tick/breadth/VIX-futures) — stubbed, not blocked.

### 3.2 Out of Scope

- Live order execution (handled by NinjaTrader adapter / existing execution layer).
- Real-time streaming UI (handled by Next.js `web/` app separately).
- New data feed integrations themselves (Tier-3 strategies depend on those but this PRD does not specify the feed work).

---

## 4. Data Architecture

### 4.1 Existing Data (do NOT recreate)

| Store | Location | Use |
| :--- | :--- | :--- |
| `ib_facts_{SYM}.parquet` | `data/derived/` | Core IB stats, bias variants, play results, mid-lock, FVG timing |
| `ib_ext_detail_{SYM}.parquet` | `data/derived/` | Per-level×side extension hit bool + minutes |
| `ib_play_detail_{SYM}.parquet` | `data/derived/` | Per-play result, MFE, MAE, realized_r, timeout_loss, loss_reason |
| `ib_level_touch_detail_{SYM}.parquet` | `data/derived/` | Per-level×phase touch counts + timing |
| `daily_context_{SYM}.parquet` | `data/derived/` | VIX regime, ATR, gap stats, PDH/PDL, overnight range, OPEX |
| `web/prisma/dev.db` `EconomicEvent` | Prisma | 11,684 economic events with UTC timestamps (news timing) |
| `data/{SYM}_1m.parquet` | `data/` | 1m OHLCV with volume column (source for all Phase 2 derived fields) |
| `data/live/live_storage_-{ticker}.parquet` | `data/live/` | Live current-year storage (per ADR, use for live/current analysis) |

### 4.2 New Outputs (this PRD)

```
data/derived/
├── ib_agg_bias_compare.parquet          # Phase 1
├── ib_agg_timing.parquet                 # Phase 1
├── ib_agg_extension_ladder.parquet       # Phase 1
├── ib_agg_plays_by_regime.parquet        # Phase 1
├── ib_agg_bias_conflict.parquet          # Phase 1
├── ib_agg_no_signal.parquet              # Phase 1
├── ib_derived_{SYM}.parquet              # Phase 2 (+ §9.2, §9.5, §9.6, §9.8, §10.14 fields)
├── ib_news_opex_{SYM}.parquet            # Phase 2.5
├── ib_master_confluence_{SYM}.parquet   # Phase 3 — raw filter flags only
├── ib_filter_effectiveness.parquet       # Phase 4a
├── ib_filter_correlation.parquet         # Phase 4b
├── ib_filter_stacks.parquet              # Phase 4c
├── ib_conviction_weights.parquet         # Phase 4d
├── ib_empirical_baselines.json           # Phase 4 — no-filter reference distribution
├── ib_optimal_stops.parquet              # Phase 5.1
├── ib_time_decay_curves.parquet          # Phase 5.2
├── ib_optimal_ladders.parquet            # Phase 5.3
├── ib_break_speed_stats.parquet          # Phase 5.4
├── ib_regime_{SYM}.parquet               # Phase 6 — regime classifier
├── ib_entry_signals_{SYM}.parquet        # Phase 6 — entry module signals
├── ib_exit_signals_{SYM}.parquet         # Phase 6 — exit module signals
└── ib_pre_break_signals_{SYM}.parquet    # Phase 6 — contraction/expansion pre-break

config/
└── avwap_anchors.yaml                    # Phase 2.6
```

---

## 5. Functional Requirements

### FR-1: Aggregate Stats Builder (Phase 1)

**Script:** `scripts/edgeful/ib_aggregates.py`

Produce 6 aggregate parquet tables from existing `ib_facts` / `ib_play_detail` / `ib_ext_detail`:
- `ib_agg_bias_compare` — per-variant DIR% / HIT% at 0.25x–1x / LIFT / N
- `ib_agg_timing` — mode/median break time, extension timing, mid-retest timing (5-min buckets)
- `ib_agg_extension_ladder` — P(hit L+0.5 | hit L) per level
- `ib_agg_plays_by_regime` — play WR by range_bucket × VIX × DOW × bias agreement
- `ib_agg_bias_conflict` — pairwise conflict matrix
- `ib_agg_no_signal` — chop statistics for sparse variants

**Acceptance:** Every % cell includes N. Traffic-light coloring: ≥60% green, 50–60% orange, <50% red. Timing reported in 5-minute buckets.

### FR-2: IB Derived Fields Builder (Phase 2)

**Script:** `scripts/edgeful/ib_derived_fields.py`

Add to `ib_derived_{SYM}.parquet` (or merge into `ib_facts`):

**Market Profile / TPO:**
- `ib_poc_price`, `ib_vah`, `ib_val`, `ib_tpo_skew`
- `ib_high_touch_count`, `ib_low_touch_count`

**Volume-weighted (§9.2):**
- `ib_vwap`, `ib_vol_at_high`, `ib_vol_at_low`, `ib_vol_poc_price`, `ib_vol_skew`

**Multi-day:**
- `ib_range_pct_of_daily`, `ib_range_5d_contracting`, `ib_range_5d_expanding`
- `ib_vs_overnight_ratio`, `ib_inside_outside`
- `ib_3day_composite_high`, `ib_3day_composite_low`

**Break characteristics:**
- `ib_break_speed`, `ib_open_drive_dir`
- `first_break_minutes_5min`, `mid_retest_minutes_5min`, `gap_fill_minutes_5min`, `ext_minutes_5min`

**Opening auction (§9.5):**
- `ib_or5_high`, `ib_or5_low`, `ib_or5_break_minutes`, `ib_or5_broken_in_15`, `ib_or5_ib_close_agree`

**80% rule (§9.6):**
- `ib_pct_time_above_mid`

**Pre-IB telegraph & post-break magnet (§9.8):**
- `ib_pre_telegraph_dir`
- `ib_mid_revisited_post_break`, `ib_mid_revisit_post_break_minutes`

**Day-type:**
- `ib_day_type_predicted` (categorical from `ib_range_pct_of_daily` buckets)

**Failure classification:**
- `ib_failure_mode_play1/2/3` ("fakeout" / "fade" / "chop" / "wrong_dir" / "none")

**External research (§10.14):**
- ACD: `ib_or_acd_a_up`, `ib_or_acd_a_down`, `ib_or_acd_c_level`, `ib_or_acd_a_held`
- VCP: `ib_vcp_3day_contracting`, `ib_vcp_volume_ratio`, `ib_vcp_setup`
- Single prints: `ib_has_upper_single_print`, `ib_has_lower_single_print`, `ib_single_print_high`, `ib_single_print_low`
- RVOL: `ib_rvol` (= VCP volume ratio), `ib_rvol_bucket`
- VIX term structure: `vix_term_structure`, `vix_regime_intraday` (Tier 1 if data loaded)
- Empirical: `ib_range_size_class`, `ib_break_urgency`, `ib_extension_expectation`
- Wicks/bodies: `ib_high_wick_pct`, `ib_low_wick_pct`, `ib_high_body_close`, `ib_low_body_close`
- Sweeps: `ib_high_swept`, `ib_low_swept`, `ib_sweep_reclaim_dir`

**Acceptance:** All computations vectorized (ADR-017). < 5 min per symbol runtime.

### FR-3: News & OPEX Impact Builder (Phase 2.5)

**Script:** `scripts/edgeful/ib_news_opex.py`

Produce `ib_news_opex_{SYM}.parquet` with:
- News: `news_0945_today`, `news_1000_today`, `news_1030_today`, `news_impact_level`, `news_release_name`, `ib_news_distorted`, `ib_news_break`, `minutes_since_news`
- OPEX: `is_opex_week`, `is_opex_friday`, `is_quarterly_opex`, `days_to_opex`, `opex_phase`, `opex_ib_range_pctile`

**Data source:** Reuse existing Prisma `EconomicEvent` table (do NOT recreate). Reuse `scripts/edgeful/calendar_generator.py` for OPEX logic.

### FR-4: Custom-Anchor VWAP & Trend Builder (Phase 2.6)

**Script:** `scripts/edgeful/ib_avwap_trend.py` + library `scripts/libs_py/avwap.py`

Precompute AVWAP for 7 anchors (09:30, 18:00, 00:00, 08:00, 09:00, 10:00, 13:30 ET). For each: price, deviation_pct, slope, above/below/touch counts, std bands, break_direction, distance_at_break_pct.

Simple trend confirmations: `ema_20_vs_ema_50`, `ema_slope_20`, `higher_highs_ib`, `lower_lows_ib`, `ib_close_vs_avwap_0930`, `break_vs_avwap_0930`, `avwap_confluence_score` (0–3).

**Config:** `config/avwap_anchors.yaml` controls which anchors are precomputed. Custom anchors testable via `--anchor HH:MM`.

### FR-5: Master Confluence Table (Phase 3)

**Script:** `scripts/edgeful/ib_master_confluence.py`

**Output:** `ib_master_confluence_{SYM}.parquet` — one row per `(symbol, trading_day, session_slot, time_basis)`.

**Critical constraint:** Store **raw filter flags only**. Do NOT compute a hand-tuned composite conviction score in this phase. The conviction score is the output of Phase 4, written back to this table after validation.

Schema includes ~150 columns: IB core, bias variants, play results, derived fields, daily context, classification, profiler, Herman, quarterly theory, SecondBrain rules, SDEV, news, OPEX, AVWAP, trend confirmations, and the two conviction columns added in Phase 4d:
- `conviction_score_naive` (baseline §7.3, for comparison only)
- `conviction_score_v2` (empirical, joined back from Phase 4d)
- `conviction_filters_active` (JSON list of which validated filters fired)

### FR-6: Validation Harness & Empirical Conviction (Phase 4)

**Script:** `scripts/edgeful/ib_validate_confluences.py`

This is the **core empirical engine**. Four sub-steps:

**4a — Single-filter effectiveness:** For each filter F and play P, split F=True/False, measure WR / expectancy / N / lift / significance (chi-square or bootstrap CI). Output `ib_filter_effectiveness.parquet`.

**4b — Independence & redundancy:** Pairwise activation correlations; drop filters with ρ > 0.85. Output `ib_filter_correlation.parquet`.

**4c — Combination search:** Greedy forward selection of non-redundant filters per play, bounded by min-N. Output `ib_filter_stacks.parquet` (optimal stack per play).

**4d — Empirical weights:** Weight each filter by validated lift (or logistic regression on P(win)). `conviction_score_v2 = Σ(filter_active × validated_lift) / Σ(validated_lift)`. Output `ib_conviction_weights.parquet`, then join `conviction_score_v2` + `conviction_filters_active` back to `ib_master_confluence`.

**Baseline reference:** `ib_empirical_baselines.json` — TrevorTrades 10-year ES probabilities (67.1% high-break, 94.9% low-break after below-mid close, 84% breaks in first 30 min, etc.) used as the no-filter reference distribution. Every lift is measured against THIS, not naive 50%.

**Acceptance:** The hand-tuned `conviction_score_naive` must be reported alongside `conviction_score_v2` as a sanity-check baseline; v2 must outperform naive on held-out data.

### FR-7: Strategy-Specific Derived Data (Phase 5)

| Sub-phase | Script | Output | Content |
| :--- | :--- | :--- | :--- |
| 5.1 | `ib_mae_stops.py` | `ib_optimal_stops.parquet` | P95/P99 MAE of winners per play, optimal_stop_r, WR & expectancy at optimal stop |
| 5.2 | `ib_time_decay.py` | `ib_time_decay_curves.parquet` | P(win \| elapsed_minutes) curve per play |
| 5.3 | `ib_ladder_optimizer.py` | `ib_optimal_ladders.parquet` | Optimal TP ladder (TP1% / TP2% / TP3% / runner%) maximizing expectancy |
| 5.4 | `ib_break_speed.py` | `ib_break_speed_stats.parquet` | Break speed distribution × outcomes |

### FR-8: Regime Classifier & Entry/Exit Modules (Phase 6)

| Script | Output | Content |
| :--- | :--- | :--- |
| `ib_regime_classifier.py` | `ib_regime_{SYM}.parquet` | `ib_regime` (trend/normal/range/skip), `ib_regime_confidence`, `suggested_play`, `suggested_direction`, `suggested_expectancy` |
| `ib_entry_modules.py` | `ib_entry_signals_{SYM}.parquet` | Scale-in ladder, time-qualified, 80%-rule, failed-breakout, opening-drive, two-timeframe, ACD, VCP, sweep+MSS signals |
| `ib_exit_modules.py` | `ib_exit_signals_{SYM}.parquet` | Trailing-by-IB-fractions, session-boundary, VWAP-cross, liquidity-target, time-decay, partial-ladder signals |
| `ib_pre_break.py` | `ib_pre_break_signals_{SYM}.parquet` | 5-day contraction pre-break, VCP contraction break |

**Regime router logic (§9.9):**

| Regime | Trigger | Play | Target WR |
| :--- | :--- | :--- | :--- |
| Trend day | `ib_range_pct_of_daily` <30% (trailing est) + fast break + POC near extreme | Play 1 breakout, full size | 65–70% |
| Normal day | 30–50% + moderate break + POC near mid | Play 2 retest, half→full | 60–65% |
| Range day | >50% + slow/no break + POC centered | Play 3 fade | 60–70% |
| Skip day | FOMC/NFP/CPI/ISM, contradictory overnight, late mid-lock | No trade | — |

### FR-9: Strategy Catalog (reference)

83 testable strategies across 13 categories (§10.1–10.14 of the plan). Built from:
- **21 entry techniques** (§10.15): E1 break-close ... E21 post-news entry
- **17 stop techniques** (§10.16): S1 opposite boundary ... S17 liquidity-stop
- **20 take-profit techniques** (§10.17): T1 fixed extensions ... T20 runner after partial

The full combinatorial space is 21 × 17 × 20 = 7,140 theoretical combinations; the catalog lists validated configurations and Phase 4 sweeps the compatible subset per play per regime.

---

## 6. Non-Functional Requirements

| NFR | Requirement | Source |
| :--- | :--- | :--- |
| NFR-1 | Zero-loop in calculation paths (vectorized NumPy/Pandas) | ADR-017 |
| NFR-2 | Parallel & GPU for sweeps ≥32 arms (joblib + Numba + CuPy) | ADR-022 |
| NFR-3 | Intraday positions exit by 16:00 ET | ADR-020 |
| NFR-4 | Prop-firm viability via `PropFirmSimulator` only | ADR-021 |
| NFR-5 | Performance metrics as % gains, not absolute points | ADR-002 |
| NFR-6 | Timezone: UTC storage, ET session windows, UTC epoch | ADR-001 |
| NFR-7 | Phase 1–2 runtime < 5 min/symbol; Phase 4 sweep via joblib | Plan §7.4 |
| NFR-8 | Filter testability: every filter stored as own column (never collapsed before Phase 4) | §11 of plan |

---

## 7. Execution Order & Dependencies

```
Phase 1 (ib_aggregates.py)
    ↓ reads ib_facts + ib_play_detail + ib_ext_detail
Phase 2 (ib_derived_fields.py)
    ↓ reads ib_facts + 1m data (+ §9.2, §9.5, §9.6, §9.8, §10.14 fields)
Phase 2.5 (ib_news_opex.py)
    ↓ reads ib_facts + Prisma EconomicEvent + calendar_generator
Phase 2.6 (ib_avwap_trend.py)
    ↓ reads 1m data + avwap_anchors.yaml
Phase 3 (ib_master_confluence.py)
    ↓ joins ALL fields; raw filter flags only (no composite)
Phase 4 (ib_validate_confluences.py)
    ↓ 4a single-filter → 4b independence → 4c stacks → 4d weights → conviction_score_v2
Phase 5 (ib_mae_stops / time_decay / ladder_optimizer / break_speed)
    ↓ exit mechanics
Phase 6 (ib_regime_classifier + entry_modules + exit_modules + pre_break)
    ↓ regime router + entry/exit modules
Validation: PropFirmSimulator (ADR-021) across all §10 strategies
```

---

## 8. Success Criteria

After all phases, the system must answer:

1. **Which bias variant is most accurate?** → `ib_agg_bias_compare.parquet`
2. **When should I enter?** → `ib_agg_timing.parquet` + `ib_entry_signals_{SYM}.parquet`
3. **Which play for today's regime?** → `ib_regime_{SYM}.parquet` (`suggested_play`)
4. **What's my optimal stop?** → `ib_optimal_stops.parquet`
5. **When should I exit if target not hit?** → `ib_time_decay_curves.parquet`
6. **What's my conviction score today?** → `ib_master_confluence` (`conviction_score_v2`)
7. **Which filters actually improve WR?** → `ib_filter_effectiveness.parquet`
8. **Can I get to 80% WR?** → Per-regime plays at 65–70% + MAE stops → 0.8–1.2R expectancy
9. **How does 9:45/10:00 news affect IB breaks?** → `ib_news_opex_{SYM}.parquet` sliced by `ib_news_distorted` / `ib_news_break`
10. **Should I skip OPEX weeks?** → `ib_agg_plays_by_regime.parquet` sliced by `opex_phase`
11. **Does AVWAP(09:30) direction improve break accuracy?** → `ib_filter_effectiveness.parquet` testing `break_vs_avwap_0930`
12. **Does empirical conviction beat the hand-tuned baseline?** → Compare `conviction_score_v2` vs `conviction_score_naive` as predictors of play outcomes
13. **Are news-distorted IBs tradeable?** → Separate stats "clean IB" vs "news IB" WRs
14. **Does the regime router outperform always-trade-Play-1?** → Backtest comparison via PropFirmSimulator

---

## 9. Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| Filter overfitting (Phase 4 finds spurious combos) | Bootstrap CIs on lift; require min-N per cell; out-of-sample validation split |
| Tier-3 strategies blocked on missing data feeds | Stubbed in catalog; gated behind Phase 6+; do not block Phases 1–5 |
| `ib_range_pct_of_daily` only knowable post-close | Use trailing 60d distribution for *pre-trade* estimate; flag as estimated vs realized |
| Conviction score collapse before validation | NFR-8: store raw flags only in Phase 3; v2 joined back only after Phase 4d |
| VIX futures data may not be loaded | `vix_term_structure` degrades gracefully to Tier 3; `vix_regime_intraday` from existing `daily_context.vix_regime` is Tier 1 |
| Comb. explosion (7,140) | Phase 4 sweeps compatible subset only; greedy forward selection bounds the search |

---

## 10. Open Questions

1. **VIX futures data availability** — is VIX9D vs VIX (or VIX front-month vs back-month) already loaded anywhere, or does `vix_term_structure` need a new feed? (Affects Tier 1 vs Tier 3 for strategies 76–78.)
2. **Tick / bid-ask volume** — does `data/{SYM}_1m.parquet` have an up/down volume split, or is delta/CVD entirely Tier 3? (Affects strategies 67–70.)
3. **NYSE breadth feed** — is the TOS RTD feed from `OPTIONS_INVENTORY.md` wired to capture intraday A/D ratio? (Affects strategies 74–75.)

---

## 11. References

- Source plan: [`docs/plans/2026-07-24-ib-data-gathering-plan.md`](../../plans/2026-07-24-ib-data-gathering-plan.md)
- Prior pipeline spec: [`IB_STATS_PIPELINE_SPEC_v5.md`](./IB_STATS_PIPELINE_SPEC_v5.md)
- Prior implementation plan: [`docs/plans/2026-06-04-ib-stats-pipeline.md`](../../plans/2026-06-04-ib-stats-pipeline.md)
- Existing README: [`README.md`](./README.md)
- ADRs: [`docs/architecture/ADR.md`](../../architecture/ADR.md) (ADR-001, 002, 017, 020, 021, 022)
- Prop-firm spec: `scripts/trading_framework/ml/prop_firm_simulator.py` (`PropFirmSimulator`, `FIRM_PROFILES`)
- Economic events source: `web/prisma/dev.db` `EconomicEvent` table, accessed via `scripts/edgeful/lib/context.py` (`_load_events_by_date`)
- OPEX calendar: `scripts/edgeful/calendar_generator.py`