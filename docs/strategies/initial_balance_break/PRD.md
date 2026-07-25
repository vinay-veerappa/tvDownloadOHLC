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

## 10. Prop Trader Gap Analysis (2026-07-25 Review)

After generating the full 6-instrument `STRATEGY_STATISTICS.md` and inventorying the
trading framework's evaluation capabilities (`PropFirmSimulator`, `BacktestLoop`,
`RiskProfiler`, `tearsheet.py`), a prop-firm trader identified the following gaps.
These are grouped by theme and prioritized. Each gap references the framework
component that already exists but is **not yet wired to the IB pipeline**.

### 10.1 Dollar P&L, Account Sizing & Drawdown (CRITICAL)

The current report is entirely in **R-multiples**. A prop trader thinks in **dollars
and drawdown**. The `PropFirmSimulator` (ADR-021) computes all of this, but the IB
pipeline does not feed into it.

| Gap | Question | Framework asset that exists | IB pipeline status |
| :--- | :--- | :--- | :--- |
| **Dollar expectancy** | What is the dollar P&L per trade at 1 Micro on a $50K Apex account? | `PropFirmSimulator.run_deterministic` | ❌ Not wired |
| **Max losing streak** | What is the max consecutive losing streak per regime per play? | `RiskProfiler.print_report` | ❌ Not wired |
| **Risk of ruin** | What is RoR at each play's WR and R:R on a $50K account risking 1%? | `RiskProfiler` (`((1-edge)/(1+edge))^bankroll`) | ❌ Not wired |
| **Monte Carlo pass rate** | In 5,000 permutation simulations, what % pass Apex/TopStep/FTMO eval? | `PropFirmSimulator.run_monte_carlo` | ❌ Not wired |
| **Drawdown in dollars** | What is the 95th-percentile max drawdown in USD? | `MonteCarloSimulator` (`MDD_95%`) | ❌ Not wired |
| **Days to pass** | How many calendar days to reach the $3K/$6K profit target? | `MonteCarloResult.avg_days_to_pass` | ❌ Not wired |
| **Grade** | Does this strategy get an A (≥80% pass) or F (<30%)? | `MonteCarloResult.grade` | ❌ Not wired |

**Priority action:** Wire the IB param grid into `BacktestLoop` (see §10.7).

### 10.2 MAE Stop R:R Problem (BUG)

The Phase 5.1 `ib_mae_stops.py` computes `optimal_stop_r = p95_mae / median_mae`.
This is **wrong** — it normalizes the stop distance by the median MAE, not by the
target distance. The result: stops appear as 5R-20R from the target, which is
nonsensical for a 0.25x target trade.

**Current (broken):** `optimal_stop_r = p95_mae_winners / median_mae`
**Should be:** `optimal_stop_r = p95_mae_winners / target_r_value` (where
`target_r_value` is the R-multiple of the target level, e.g., 0.25, 0.5, 1.0).

A 5R stop on a 0.25x target means R:R is 1:20 — you'd need 95%+ WR to break even.
The report shows 73% WR at 0.25x target with a 4.96R stop → **negative edge**.
This must be fixed before any prop-firm evaluation.

### 10.3 Trade Frequency & Selectivity

| Gap | Question |
| :--- | :--- |
| **Per-day trade count** | N=166,016 for NQ1 Play 1 across 20 years × 6 sessions = ~8,000/year. But a prop trader takes 1-2 trades/day. How many are same-day duplicates? |
| **Skip-day profitability** | The "skip" regime still shows positive expectancy (NQ1: 0.08R). Either the skip filter is too aggressive or the regime label uses look-ahead. Is `ib_range_pct_of_daily` the realized value? |
| **Tradeable days/year** | After regime filtering, how many actual tradeable days remain? If <100, statistical significance per regime is questionable. |
| **Minimum N for viability** | What is the minimum trade count for a prop-viable strategy? 30? 50? 100? |

### 10.4 Entry Timing & Execution Realism

| Gap | Question |
| :--- | :--- |
| **Entry time distribution** | How many entries happen in the first 30 min (clean) vs after 13:00 (chop)? The time-decay curve (Phase 5.2) exists but isn't in the report. |
| **Stop mismatch** | `IBPullbackStrategy` uses `stop_loss_type=ib_opposite` (full IB range). But Phase 5.1 recommends P95 MAE (which could be wider). Which stop does the backtest actually use? |
| **Commissions & slippage** | `VALIDATION_RESULTS.md` shows +28% return on CL1 Tokyo. But no commissions ($2.25/round-turn per Micro) or slippage. On 800 trades, $3,600 in commissions could wipe out the edge. |
| **Session-boundary enforcement** | ADR-020 says exit by 16:00 ET. Does the `VectorizedBacktester` enforce this? Is there a 15:50 hard-exit flag? |

### 10.5 Regime Router Validity

| Gap | Question |
| :--- | :--- |
| **Look-ahead bias** | `ib_range_pct_of_daily` is only known post-close. The regime classifier uses the realized value. Are the trend/range/skip WR differences real or illusory? |
| **CL1 range regime** | CL1 "range" regime has Play 1 WR 41% / PF 1.14 (profitable). NQ1 "range" has WR 36% / PF 0.81 (losing). Why does range work for CL1 but not NQ1? |
| **News-day granularity** | "Skip" triggers on FOMC/NFP/CPI/ISM. But skip days are profitable. Are we leaving money on the table? What is WR on FOMC days specifically? |
| **Pre-trade regime estimate** | The PRD says "use trailing 60d distribution for pre-trade estimate." Is this implemented? If not, the regime router is post-hoc. |

### 10.6 Filter Effectiveness Concerns

| Gap | Question |
| :--- | :--- |
| **`break_vs_avwap_0930` artifact** | Top filter shows +55% lift but N=19,976 (12% of rows). Flag-off WR is 0.003. Is this a session-coverage artifact (flag only computed for NY AM IB)? |
| **Filter stack overfitting** | Phase 4c stacks have N=56-241 with 5 filters ANDed. Severe overfitting risk. What is the out-of-sample lift? (Report says "all in-sample.") |
| **Min-N guard** | `ib_news_distorted` shows +19% lift but N=15. PRD says min-N=20. This violated the guard. |
| **Walk-forward validation** | `ib_breakout_filter.py` has walk-forward calibration. Is it applied to all filter stacks or just the breakout filter? |

### 10.7 PropFirmSimulator Integration (THE critical gap)

The `BacktestLoop` harness in `scripts/knowledge_bridge/backtest_loop.py` is the
bridge. It already:
1. Resolves a strategy via the registry → `IBPullbackStrategy`
2. Runs `VectorizedBacktester` → gets `trades_detailed` (with `pnl_pct` + `exit_time`)
3. Iterates `FIRM_PROFILES` (Apex/TopStep/FTMO) running det + MC each
4. Auto-marks `VALIDATED/REJECTED` per `pass_threshold_pct`
5. Exports JSON via `export_backtest_results`

**What's needed:** Build 83 `StrategyCandidate` objects (one per param combo from
`IBPullbackStrategy.get_param_grid()`), set `strategy_key="ib_pullback"`, then
call `run_batch()`. This is ADR-021 compliant and produces the dollar-P&L, MC pass
rate, and grade that a prop trader needs.

### 10.8 Framework Enhancement Needs

| Gap | Framework asset | IB pipeline status |
| :--- | :--- | :--- |
| **Sharpe/Sortino/Calmar** | `tearsheet.py:compute_performance_metrics` | ❌ Not in IB report |
| **MDD_95% / MaxStreak_95%** | `monte_carlo.py:MonteCarloSimulator` | ❌ Not in IB report |
| **Daily trade cap per session** | `PropFirmSimulator` (max_trades_per_day) | ⚠️ Set to 999 (disabled) |
| **Consistency rule** | `PropFirmSimulator` (FTMO 30% rule) | ⚠️ Enabled for FTMO only |
| **Commission/slippage model** | Not in `VectorizedBacktester` | ❌ Missing entirely |

---

## 11. Empirical Target Framework (Gunship-Inspired)

### 11.1 Problem with Fixed-Multiple Targets

The current IB framework uses **fixed multiples** of the IB range as targets:
`0.25x, 0.5x, 0.75x, 1.0x`. This is rigid — it doesn't adapt to volatility regime,
session, or instrument personality. A 1.0x target on a quiet Globex day is very
different from 1.0x on a volatile NQ AM session.

The Gunship indicator (`DailyNYLevelsAnalytics.pine`, harmonized via
`gunship_consistency.md`) takes a fundamentally different approach: **empirical
percentiles of historical MFE/MAE distributions**, split by bull/bear side and
filtered by outcome (wins vs fakes).

### 11.2 Gunship Percentile Target Model

| Level | Gunship variable | Percentile | Anchor | Filter | "What it answers" |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Cashflow (minimum target) | `p20_bo` → `y_cash` | P20 BO MFE | Breakout px | Wins | "Where will price at least reach?" |
| Median target | `p50_bo` | P50 BO MFE | Breakout px | Wins | "Where will price typically go?" |
| Confirm target | `p75_fake` → `y_conf` | P75 fakeout MFE | Breakout px | Fakes | "How far can a fake stretch?" |
| Pivot (fakeout reversal) | `p50_fake` → `pivot_px` | P50 fakeout MFE | Breakout px | Fakes | "Where do fakes typically reverse?" |
| Pullback entry | `p25_mae` → `pullback_px` | P25 MAE | Breakout px | Wins | "How much will it pull back before continuing?" |
| Invalidation (stop) | `p80_mae_wins` → `invalid_px` | P80 MAE | Breakout px | Wins | "How deep can a winner pull back before failing?" |
| Reversal zone | `rev_p25`, `rev_p50` | P25-P50 fake MAE | OR High/Low | Fakes | "Where will a fakeout reverse to?" |
| EV target (fixed) | `target_px` | `i_ev_target_pct` (0.30%) | Breakout px | — | "Minimum acceptable EV target" |

**Key difference:** Instead of asking "did price reach 1.0x IB range?", the
Gunship asks "did price reach the P75 of where winning breakouts typically go?"
This is **self-adapting** to each session's volatility.

### 11.3 Extensibility to Any Custom Time Range

The IB framework must be extensible beyond the 6 predefined IB sessions to **any
custom time range** (e.g., 18:00 break, 09:30 OR, a custom 2-hour window). The
infrastructure already exists:

| Component | File | Role |
| :--- | :--- | :--- |
| Custom range resolver | `scripts/indicators-pine/lib-pine/RangeSessionLib.pine` → `f_resolve_preset` | Supports Custom branch: `custom_start`, `custom_end`, `custom_cutoff` → builds session strings |
| Session helpers | `RangeSessionLib.pine` → `f_parse_hhmm`, `f_build_session_string`, `f_in_session_minutes` | Midnight-crossing aware, minute-of-day arithmetic |
| IB session config | `IB_Stats_Extensions.pine` → `input.session()` strings (6 presets) | Already editable; add a new preset or use Custom |
| MFE/MAE tracking | `StatsLib.pine` → `f_track_mfe`, `f_track_mae_abs`, `f_track_mae_pullback` | Anchor-agnostic — works off any breakout px |
| Percentile fallback | `DailyNYLevelsAnalytics.pine` → `f_get_pct_fallback` | Cold-start defaults when history < min-N |

### 11.4 FR-10: Empirical Target Engine (New Requirement)

**Requirement:** Add a Phase 5.5 module that computes Gunship-style percentile
targets for every `(symbol, session_slot, time_basis, play)` group, replacing
the fixed-multiple targets with empirical, self-adapting levels.

**Script:** `scripts/edgeful/ib_empirical_targets.py`

**Outputs:** `data/derived/ib_empirical_targets.parquet`

| Column | Description |
| :--- | :--- |
| `symbol, session_slot, time_basis, play` | Group keys |
| `p20_bo_mfe, p50_bo_mfe, p75_bo_mfe` | "How far can it go" percentiles (wins only) |
| `p50_fake_mfe, p75_fake_mfe` | Fakeout stretch percentiles (fakes only) |
| `p25_mae_entry, p80_mae_invalidation` | "How much can it pull back" percentiles |
| `p25_rev, p50_rev` | Reversal zone percentiles (fakes, anchored at OR boundary) |
| `bull_p50_bo, bear_p50_bo` | Side-split median targets |
| `n_wins, n_fakes, n_losses` | Sample counts per cell |
| `ev_target_pct` | Fixed minimum EV target (instrument-specific: 0.30% NQ, 0.20% ES) |

**Acceptance:**
- All percentiles computed from per-group historical MFE/MAE distributions
- Cold-start fallback: if group N < 30, fall back to session-level distribution; if session N < 50, fall back to symbol-level
- Side-split (bull/bear) for all MFE levels — NQ bull breakouts have different volatility than bear breakouts
- Must work for **any custom time range** — the group keys include `session_slot` which can be any custom range name (e.g., "Custom 1400-1600")

### 11.5 FR-11: Custom Range Support (New Requirement)

**Requirement:** The IB pipeline must accept a custom time range definition
(start time, end time, cutoff/outcome window) and produce the full Phase 1-6
derived data for that range, using the same percentile target engine.

**Config:** `config/ib_custom_ranges.yaml`

```yaml
custom_ranges:
  - name: "1400-1600 Range"
    start: "1400"
    end: "1600"
    cutoff: "1800"      # outcome evaluation window end
    timezone: "America/New_York"
    days: "12345"        # Mon-Fri
  - name: "Overnight Break 1800"
    start: "1800"
    end: "1815"
    cutoff: "0300"
    timezone: "America/New_York"
    days: "12345"
```

**Implementation:**
- `scripts/edgeful/ib_session_config.py` reads the YAML and produces `RangeSpec` objects
- Each custom range gets its own `session_slot` label in all derived parquet files
- The `ib_derived_fields.py` `_session_cfg()` function already accepts arbitrary `session_slot` strings — no change needed to the compute path
- The regime classifier, entry/exit modules, and empirical target engine all group by `session_slot` — custom ranges flow through automatically

**Acceptance:**
- A user can define a custom range in YAML and run `ib_derived_fields --custom-ranges config/ib_custom_ranges.yaml`
- All downstream phases (aggregates, confluence, validation, regime, entry, exit, empirical targets) produce outputs for the custom range
- The `STRATEGY_STATISTICS.md` report includes the custom range in all breakdown tables

### 11.6 Target Model Comparison

| Dimension | Fixed-Multiple (current) | Empirical Percentile (Gunship-inspired) |
| :--- | :--- | :--- |
| Target basis | `ibH + mult * ibRange` | P20/P50/P75 of historical BO MFE |
| Pullback | `ibH - 0.25 * ibRange` (fixed) | P25 MAE (empirical entry), P80 MAE (invalidation) |
| Anchor | IB High/Low | Breakout px (self-adapting) |
| Direction split | Symmetric | Bull/bear split (different volatility) |
| Sample filter | All sessions | Wins for MFE, Fakes for pivot, Wins for MAE |
| Reversal target | IB Mid | P25-P50 fake MAE, anchored at OR boundary |
| Volatility adaptivity | ❌ Fixed | ✅ Self-adapting per session/symbol |
| Custom range support | ✅ (via input.session) | ✅ (anchor-agnostic) |

---

## 12. Framework Audit (Pre-Integration, 2026-07-25)

Before wiring IB strategies into `BacktestLoop`, the full pipeline was audited end-to-end:
`StrategyCandidate` → `registry.get_strategy()` → `HunterStrategyAdapter.generate_signals()` →
`VectorizedBacktester.run()` → `PropFirmSimulator.run_deterministic()` / `run_monte_carlo()`.

### 12.1 Integration Contract — CONFIRMED WORKING

| Layer | Component | Interface | Status |
|---|---|---|---|
| Registry | `STRATEGY_FACTORY_REGISTRY["ib_pullback"]` | `HunterStrategyAdapter(IBPullbackStrategy(ticker=ticker), "IB Pullback")` | ✅ Registered |
| Adapter | `HunterStrategyAdapter.generate_signals(df, config)` | Delegates to `IBPullbackStrategy.hunt(df, params=config)` | ✅ Interface matches |
| Strategy | `IBPullbackStrategy.hunt()` returns | DataFrame[signal_time, direction, entry_price, stop_price, target1_price] | ✅ Matches `_standard_signal_columns()` |
| Backtester | `VectorizedBacktester.run(signals_df, data, risk_params)` | `_run_standardized_matches` path — expects exactly those 5 columns | ✅ Contract matches |
| Backtester output | `trades_detailed` columns | `pnl_pct, mae_pct, mfe_pct, mfe_wick_pct, mfe_close_pct, exit_time` | ✅ All 6 columns produced |
| PropFirmSimulator input | `run_deterministic(trades_detailed, profile)` | Needs `pnl_pct` + `exit_time` minimum — both present | ✅ Minimum satisfied |
| PropFirmSimulator output | `det.passed`, `det.final_equity_delta`, `mc.pass_rate_pct`, `mc.grade` | Consumed by `ProfileResult` | ✅ All fields mapped |
| Profiles | `FIRM_PROFILES` | apex_50k, apex_100k, topstep_50k, topstep_100k, ftmo_50k, generic_50k | ✅ All 6 configured |
| Config | `sessions.yaml` `prop_firm.run_profiles` | `["apex_50k", "topstep_50k", "ftmo_50k"]` | ✅ Resolved by `_ensure_loaded()` |

**Conclusion: No interface mismatch. The pipeline is wireable as-is.** The `HunterStrategyAdapter`
already bridges `hunt()` → `generate_signals()`, and all DataFrame schemas line up.

### 12.2 Issues Found (No Blockers)

#### NOTE N1: `DataLoader.load_enriched()` reads historical parquet only — BY DESIGN

- `backtest_loop.py` line 181: `self._df = loader.load_enriched(self.ticker)`.
- `loader.py` `_price_path()` resolves to `data/{symbol}_1m.parquet` (historical archive, 2006 → 2025-12-31).
- This is **correct for backtesting** — deep history (20 years) is what we want for strategy verification.
- **Live storage** (`data/live/live_storage_-{ticker}.parquet`, 2025-01-01 → current) is a **separate forward-validation step**, intentionally separate from the backtest.
- **Two-phase workflow**: (1) Backtest on historical to verify strategies → (2) Forward-validate survivors on live storage recent price action.
- **No fix needed for the backtest phase.** The `data_override` parameter on `BacktestLoop.__init__()` is still useful for the forward-validation phase (inject live/fused data), but it is not a blocker for the initial backtest integration.
- **Forward-validation hook**: When ready to validate on live data, add `data_override` param to `BacktestLoop.__init__()` and pass `load_fused_data(ticker)` output (which merges historical + live storage).

#### BLOCKER B2: `IBPullbackStrategy.hunt()` requires §9.2+ derived columns that are missing for 5 of 6 instruments

- `hunt()` reads bias source, CISD, regime, and other §9.2/9.5/9.6/9.8/10.14 columns from the input DataFrame.
- These columns are currently only populated for NQ1 (the async job for ES1/YM1/RTY1/CL1/GC1 is in progress).
- **Impact**: `hunt()` will either crash or produce 0 signals for 5 instruments.
- **Fix needed**: Wait for the `ib_derived_fields` async job to complete for all 6 symbols, then run BacktestLoop.

#### ISSUE I1: `VectorizedBacktester` commission model is flat slippage, not per-contract

- `backtest_engine.py` line 26: `commission: float = 2.05, slippage_pct: float = 0.0001`.
- `commission` is set but **never used** in `_run_standardized_matches()`. Only `slippage_pct` (0.01% per trade) is deducted.
- This is a flat % deduction, not a per-contract dollar commission ($2.05/round-turn per Micro).
- **Impact**: Low-expectancy plays (0.25x targets) may look profitable when they're not after real commissions.
- **Severity**: Medium — documented in PRD §10.1, affects all prop-firm dollar P&L outputs. Not a blocker for initial integration but must be addressed before trusting grade A/B results.

#### ISSUE I2: No ADR-020 enforcement in backtester or simulator

- `PropFirmSimulator` docstring says "All exits are assumed to already comply with ADR-020 (16:00 ET hard exit)."
- `VectorizedBacktester._run_standardized_matches()` uses `MAX_SEARCH = 1440` (24 hours of 1-min bars) — it will hold trades overnight if neither TP nor SL is hit.
- **Impact**: Trades that don't hit TP/SL within RTH will be carried past 16:00, violating ADR-020.
- **Severity**: Medium — affects any trade that doesn't hit TP or SL within the session. Needs a time-based exit filter in the backtester or a forced 16:00 close. For IB Pullback (entries at 10:30+), the 1440-bar search window extends to next day's 10:30+.

#### ISSUE I3: `max_trades_per_day=999` (disabled) in all profiles

- All 6 `FIRM_PROFILES` have `max_trades_per_day=999`, which effectively disables the daily trade count limit.
- Real prop firms (Apex, TopStep) enforce max trades per day (e.g., TopStep = unlimited but with daily loss limit).
- **Impact**: No constraint on trade frequency. For IB Pullback (1-2 trades/day), this is fine. For high-frequency strategies, this would overstate pass rates.
- **Severity**: Low for IB integration, but should be parameterized for future strategies.

#### ISSUE I4: `BacktestResult.to_dict()` uses `asdict()` which may not serialize nested dataclasses

- `to_dict()` at line 111: `d = asdict(self); d["profiles"] = [p.to_dict() for p in self.profiles]`.
- `asdict()` recursively converts dataclass fields, but `profiles` is a list of `ProfileResult` — already handled explicitly.
- However, if any field contains a pandas Timestamp or Path, JSON export via `json.dumps(default=str)` will work but lose type info.
- **Severity**: Low — cosmetic, not a blocker.

### 12.3 Items Requiring Fixes Before Integration

| ID | Severity | Fix | Effort |
|---|---|---|---|
| N1 | **Note (not a blocker)** | Historical-only data is correct for backtest. Add `data_override` param later for forward-validation phase only. | 0 min (now) |
| B2 | ~~Blocker~~ ✅ **Cleared** | All 6 `ib_derived_{SYM}.parquet` files now exist with 69 cols, fully populated. | Done |
| I1 | Medium | Add per-contract commission to `VectorizedBacktester._run_standardized_matches()` | 30 min |
| I2 | Medium | Add 16:00 ET forced exit to backtester (ADR-020 enforcement) | 1 hr |
| I3 | Low | Parameterize `max_trades_per_day` in `sessions.yaml` overrides | 15 min |
| I4 | Low | Add `default=str` to JSON export (already present) | 0 |

### 12.4 Recommended Integration Plan

1. **Run initial backtest** — No blockers remain. `BacktestLoop` as-is works with historical data (2006–2025). Build IB candidate grid, run `run_batch()`, export results.
2. **Fix I1 + I2** — After smoke test, add commission and ADR-020 enforcement, re-run, and compare grades.
3. **Build IB candidate grid** — Expand `IBPullbackStrategy.get_param_grid()` into 83 `StrategyCandidate` objects (3 sessions × 3 durations × 2 entries × 6 pullbacks × 3 stops × ... → filter to 83 viable combos).
4. **Run `run_batch()`** for each ticker × profile combo. Export results via `export_backtest_results()` to `results/ib_backtest/`.
5. **Forward-validation phase** — After backtest verification, add `data_override` param to inject `load_fused_data()` for live-storage validation of surviving strategies.

### 12.5 Integration Results (2026-07-25)

**Status: Pipeline fully operational. NQ1 moderate grid (432 candidates) complete.**

#### Pipeline components built
- `ib_backtest_runner.py` — original runner using `BacktestLoop` (slow: ~10s/candidate)
- `ib_backtest_fast.py` — optimized runner with `CachedIBHunter` (9x faster: ~1s/candidate)
  - Splits `hunt()` into `_precompute(session, duration)` (cached) + `generate_signals(params)` (lightweight)
  - 4 unique (session, duration) precomputations instead of 432 full recomputations
- Fixes applied: import path (`config_loader`), VIX dtype mismatch (`merge_asof`), emoji encoding (Windows cp1252)

#### NQ1 moderate grid results (432 candidates, 200 MC sims)
- **Grade distribution**: 429 F, 3 D (all on TopStep 50K)
- **Positive return**: 62/432 (14.4%)
- **Det PASS on ≥1 profile**: 16/432 (3.7%)
- **Best MC pass rate**: 41.0% (Grade D, TopStep 50K)
- **Top performer**: RTH 60m post_break ib_edge ib_opposite confluence tp2.0 → +16.2% return, 46.4% WR, 261 trades
- **Key pattern**: post_break + ib_edge pullback + ib_opposite stop + tp2.0 dominates; confluence bias cuts trades ~90% and improves quality

#### BL-2 Fix (MAE stop R:R bug)
- `optimal_stop_r = p95_mae / target_lvl` (was `p95 / median_mae`)
- Now correct: 0.25R target → 1.24R stop (R:R 0.20:1); 1.0R target → 0.30R stop (R:R 3.31:1)

#### BL-3 New (empirical target engine)
- `ib_empirical_targets.py` — Gunship-style percentile targets (P20/P50/P75/P90 MFE, P25/P50/P80 MAE)
- 4 selection modes: best_expectancy, balanced, aggressive, conservative
- **Finding**: all NQ1 expectancies negative — raw IB Pullback has no edge even with empirical targets

#### Speed comparison
| Runner | Grid | Time | Per-candidate | Speedup |
|---|---|---|---|---|
| Original (`BacktestLoop`) | 432 | 70 min | ~10s | 1x |
| Fast (`CachedIBHunter`) | 432 | 7.8 min | ~1s | 9x |

---

## 13. Backlog

| ID | Item | Source | Priority | Status |
|---|---|---|---|---|
| BL-1 | Report format & storage — IB stats reports are currently scattered as individual parquet/csv files in `results/ib_stats/`. Consolidate into a structured directory with a manifest, and add a summary HTML/MD dashboard. | User request 2026-07-25 | Medium | Open |
| BL-2 | Fix MAE stop R:R bug in `ib_mae_stops.py` — `optimal_stop_r = p95_mae / target_r` (not `median_mae`). Currently shows 5R-20R stops on 0.25x targets. | PRD §10.2 | High | ✅ Done (2026-07-25) |
| BL-3 | Implement FR-10 empirical target engine (`ib_empirical_targets.py`) — Gunship-style percentile targets. | PRD §11 | High | ✅ Done (2026-07-25) |
| BL-4 | Implement FR-11 custom range support (`config/ib_custom_ranges.yaml`). | PRD §11 | Medium | ✅ Done (2026-07-25) |
| BL-5 | Fix `VectorizedBacktester` commission model (I1) — add per-contract dollar commission. | PRD §12.2 | Medium | ✅ Done (2026-07-25) |
| BL-6 | Add ADR-020 16:00 ET forced exit to `VectorizedBacktester` (I2). | PRD §12.2 | Medium | ✅ Done (2026-07-25) |
| BL-7 | Verify regime router look-ahead (Q4) — is `ib_range_pct_of_daily` using realized same-day value? | PRD §12 Q4 | High | ✅ Done (2026-07-25) |

---

## 14. Open Questions

1. **VIX futures data availability** — is VIX9D vs VIX (or VIX front-month vs back-month) already loaded anywhere, or does `vix_term_structure` need a new feed? (Affects Tier 1 vs Tier 3 for strategies 76–78.)
2. **Tick / bid-ask volume** — does `data/{SYM}_1m.parquet` have an up/down volume split, or is delta/CVD entirely Tier 3? (Affects strategies 67–70.)
3. **NYSE breadth feed** — is the TOS RTD feed from `OPTIONS_INVENTORY.md` wired to capture intraday A/D ratio? (Affects strategies 74–75.)
4. **Regime router look-ahead** — is `ib_range_pct_of_daily` in the regime classifier using the realized same-day value or a trailing 60-day estimate? (Affects validity of all regime stats.) **Answer (BL-7): Was using realized same-day value (look-ahead bias). Fixed to use trailing 5d percentile (`ib_range_5d_pctile`) for pre-trade regime estimation. Also fixed the `ib_range_pct_of_daily` computation itself — was `ib_range/ib_mid` (mislabeled proxy), now correctly `ib_range / (daily_high - daily_low)` from 1m data. Regime distribution shifted: range 2,056 → 6,251 (5% → 15%), trend 21,579 → 19,632.**
5. **Commission model** — does `VectorizedBacktester` deduct $2.25/round-turn per Micro? If not, what is the impact on low-expectancy plays? **Answer (§12.2 I1): No — only 0.01% flat slippage. `$2.05` commission is stored but never applied.**
6. **Stop mismatch** — does the `IBPullbackStrategy` backtest use `ib_opposite` stop or the Phase 5.1 P95 MAE stop? (Affects whether backtest results match report recommendations.)

---

## 15. References

- Source plan: [`docs/plans/2026-07-24-ib-data-gathering-plan.md`](../../plans/2026-07-24-ib-data-gathering-plan.md)
- Prior pipeline spec: [`IB_STATS_PIPELINE_SPEC_v5.md`](./IB_STATS_PIPELINE_SPEC_v5.md)
- Prior implementation plan: [`docs/plans/2026-06-04-ib-stats-pipeline.md`](../../plans/2026-06-04-ib-stats-pipeline.md)
- Existing README: [`README.md`](./README.md)
- ADRs: [`docs/architecture/ADR.md`](../../architecture/ADR.md) (ADR-001, 002, 017, 020, 021, 022)
- Prop-firm spec: `scripts/trading_framework/ml/prop_firm_simulator.py` (`PropFirmSimulator`, `FIRM_PROFILES`)
- Economic events source: `web/prisma/dev.db` `EconomicEvent` table, accessed via `scripts/edgeful/lib/context.py` (`_load_events_by_date`)
- OPEX calendar: `scripts/edgeful/calendar_generator.py`