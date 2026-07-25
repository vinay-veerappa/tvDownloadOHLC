# Phase 5 Strategy-Specific Derived Data Roadmap

Status after latest work: **#2 IB Pullback Trigger Table implemented.**

This document lists all candidate Phase 5 derived-data products that consume the master IB confluence table (`data/derived/ib_confluence_{SYM}.parquet`) and produce smaller, strategy-ready feature sets.

---

## 1. IB Breakout Enhanced Filter Set ✅ DONE
**What it does**
Produces a strict/lenient entry filter table for the existing `IB Break` and `IB Breakout Modular` strategies. It joins the confluence flags (`trend_aligned_with_break`, `avwap_aligned`, `break_dir_matches_avwap0930`, `fail_setup_score`, news/OPEX) with the raw IB break facts. Walk-forward empirical calibration keyed by (session_slot, range_bucket_full, first_break_dir) estimates P(play3 win) for each cell.

**Why it matters**
Validation showed `trend_aligned_with_break` lifts `bias_correct_combined_05x` by ~13–17 percentage points across every instrument. A precomputed filter table lets the strategy skip low-probability breaks and bias size toward high-confluence ones. The walk-forward calibration provides an `expectation_bucket` (high/medium/low) that is monotonically predictive of actual play3 win rates across all six instruments (top quintile ~2x bottom quintile).

**Calibration details**
- Win = `play3_result > 0` (profitable trade outcome, ~15% base rate)
- Lag: `groupby(trading_day).shift(1)` prevents same-day session-slot leakage
- Shrinkage: Laplace blend `(n_obs * cell + k * prior) / (n_obs + k)` with `k=10`, `min_obs=20`
- Thresholds: `>=0.25` high, `>=0.18` medium, else low (calibrated to play3 base rate)
- Validated: correlation 0.07-0.10 across NQ1/ES1/YM1/RTY1/CL1/GC1; Q0→Q4 win rate spread 0.09→0.20

**Output**
- `data/derived/ib_breakout_filter_{SYM}.parquet`
- Columns: `break_direction`, `entry_side`, `filter_pass`, `confluence_score`, `recommended_target_multiple`, `recommended_stop_multiple`, `expectation_bucket`, `empirical_win_rate_strict`, `empirical_mean_mfe_strict`, `empirical_win_rate_lenient`, `empirical_mean_mfe_lenient`.

**Downstream strategy**
- [scripts/strategies/initial_balance/core/initial_balance_break.py](../scripts/strategies/initial_balance/core/initial_balance_break.py)
- [scripts/strategies/logic/ib_breakout_modular.py](../scripts/strategies/logic/ib_breakout_modular.py)
- [scripts/edgeful/universal_signal_classifier_input.py](../scripts/edgeful/universal_signal_classifier_input.py) (maps `expectation_bucket` → `signal_bucket`)

---

## 2. IB Pullback Trigger Table ✅ DONE
**What it does**
Computes Fib retracement depth, AVWAP re-entry alignment, midpoint retest speed, false-break components, and a composite `pullback_trigger_score` for fading or continuing after an IB break.

**Why it matters**
The existing `IB Pullback` strategy trades pullbacks to IB extremes. Precomputing the Fib level reached, whether price reclaims the 09:30 AVWAP, and whether the midpoint was retested gives the strategy a single table to scan instead of recomputing on every run.

**Output**
- `data/derived/ib_pullback_triggers_{SYM}.parquet` (45 cols)
- Key columns: `pullback_into_ib_pct`, `nearest_fib_level`, `deep_retrace_618`, `avwap_reclaim_aligned`, `mid_retest`, `false_break_any`, `pullback_trigger_score`, plus outcome labels.

**Downstream strategy**
- [scripts/strategies/initial_balance/core/initial_balance_pullback.py](../scripts/strategies/initial_balance/core/initial_balance_pullback.py)

---

## 3. OR / 9:30 Breakout Confluence Table
**What it does**
Maps the same confluence fields onto the 09:30 opening-range bar and the first N-minute OR. Adds OR-specific derived fields: OR range percentile relative to 20-day distribution, first extension beyond OR, time of first OR break, volume profile skew, and overlap with the Globex IB.

**Why it matters**
The 9:30 ORB is one of the most traded opening setups. Confluence with the broader IB trend, AVWAP, and news timing should improve the win rate beyond a raw ORB trigger.

**Output**
- `data/derived/orb_confluence_{SYM}.parquet`
- Columns: `or_range`, `or_break_dir`, `or_break_time`, `or_to_ib_overlap_pct`, `or_aligned_with_ib`, `news_0945_overlap_or`, `orb_confluence_score`.

**Downstream strategies**
- [scripts/strategies/nine_thirty_breakout/core/nine_thirty_strategy.py](../scripts/strategies/nine_thirty_breakout/core/nine_thirty_strategy.py)
- [scripts/orb_generic/strategy_validation/scripts/signal_generators.py](../scripts/orb_generic/strategy_validation/scripts/signal_generators.py)
- [scripts/strategies/framework/core/simulate_trades.py](../scripts/strategies/framework/core/simulate_trades.py)

---

## 4. ICT NY AM Confluence Table
**What it does**
Joins IB facts with NY killzone liquidity sweep detection, CISD displacement, market-structure break, and FVG rejection signals. Produces a table of ICT-style setups that only trigger when the IB context agrees (trend direction, range percentile, news/OPEX state).

**Why it matters**
ICT strategies often fail in isolation because they ignore session context. The IB confluence table already contains trend, range, AVWAP, and news fields, so an ICT confluence table can pre-filter setups to the higher-probability NY AM window.

**Output**
- `data/derived/ict_ny_confluence_{SYM}.parquet`
- Columns: `asian_range`, `london_extension_pct`, `ny_sweep_level`, `cisd_direction`, `mss_direction`, `fvg_rejection_aligned`, `ib_trend_agreement`, `killzone_valid`, `ict_signal_side`, `ict_confluence_score`.

**Downstream strategies**
- [scripts/strategies/ict/strategies/ict_ny_session.py](../scripts/strategies/ict/strategies/ict_ny_session.py)
- [scripts/strategies/ict/strategies/ict_fvg_cisd_rejection.py](../scripts/strategies/ict/strategies/ict_fvg_cisd_rejection.py)
- [scripts/strategies/ict/strategies/ict_liquidity_sweep.py](../scripts/strategies/ict/strategies/ict_liquidity_sweep.py)

---

## 5. Failed Auction / Box Reversion Derived Filter
**What it does**
Precomputes false-break probability scores and reversion-to-mid expectations from the confluence table. Uses `false_break_high`, `false_break_low`, `double_break`, `mid_lock_frac`, `front_run_active`, AVWAP disagreement, and range percentile to score how likely an IB extreme sweep is to reverse.

**Why it matters**
The `Box Reversion` and `Failed Auction` strategies already exist; they currently compute these components themselves. A shared derived table reduces duplication and lets multiple strategies use the same false-break score.

**Output**
- `data/derived/ib_reversion_score_{SYM}.parquet`
- Columns: `false_break_score`, `reversion_expected_target_pct`, `reversion_stop_pct`, `mid_distance_pct`, `box_status_agreement`, `reversion_signal_side`, `reversion_confidence`.

**Downstream strategies**
- [scripts/strategies/failed_auction/core/failed_auction.py](../scripts/strategies/failed_auction/core/failed_auction.py)
- [scripts/strategies/reversal/core/box_reversion.py](../scripts/strategies/reversal/core/box_reversion.py)
- [scripts/strategies/reversal/core/mean_reversion.py](../scripts/strategies/reversal/core/mean_reversion.py)

---

## 6. Universal Signal Filter / Classifier Input ✅ DONE
**What it does (detailed)**
Builds a single, normalized feature matrix that can train a LightGBM classifier (`SignalClassifier`) to filter false-positive signals across **all** strategies. It merges the IB confluence table with strategy signal timestamps from any of the Phase 5 tables and labels each signal row as positive outcome (>0) or not.

**Why it matters (detailed)**
Every Pillar-2 hunter currently emits signals, but none share a single ML-based false-positive filter. By materializing a `features + target` parquet once per instrument, we can:
1. Train one classifier per instrument instead of one per strategy.
2. Use the same features (IB confluence + AVWAP + news/OPEX) for breakout, pullback, reversion, and ICT strategies.
3. Evaluate feature importance across strategies to find which confluence factors actually predict success in each regime.
4. Plug directly into `scripts/trading_framework/ml/signal_classifier.py`, which expects a DataFrame of features and a binary target.

**Proposed feature set**
| Feature group | Columns |
|---------------|---------|
| IB structure | `ib_range`, `range_pct`, `range_atr`, `range_bucket_full`, `range_bucket_trailing` |
| Break context | `first_break_dir`, `first_break_minutes`, `break_speed_bars`, `realized_dir_break` |
| Trend / AVWAP | `trend_aligned_with_break`, `avwap_aligned`, `avwap_mixed`, `avwap_0930_deviation_pct`, `break_dir_matches_avwap0930`, `avwap_confluence_score` |
| Mid / Retest | `mid_lock_frac`, `mid_retest`, `retrace_depth_pct` |
| False-break | `false_break_high`, `false_break_low`, `double_break` |
| News / OPEX | `news_high_impact_present`, `ib_news_distorted`, `ib_news_break`, `is_opex_week`, `is_quarterly_opex`, `opex_ib_range_pctile` |
| Session / calendar | `dow`, `dst_regime`, `us_dst`, `uk_dst`, `early_mid_event` |
| Strategy-specific | `signal_side`, `entry_bucket`, `target_distance_pct`, `stop_distance_pct` |

**Proposed target columns**
- Binary: `target_positive = (play3_result > 0)`
- Optional ordinal: `target_outcome_5class` mapping `{-1,0,1}` × `{timeout, normal}`.

**Output**
- `data/derived/universal_signal_classifier_input_{SYM}.parquet`
- A single row per candidate signal with all features and labels.

**Downstream harness**
- [scripts/trading_framework/ml/signal_classifier.py](../scripts/trading_framework/ml/signal_classifier.py)
- [scripts/trading_framework/research/lifecycle_runner.py](../scripts/trading_framework/research/lifecycle_runner.py)

**Implementation notes**
- Must respect ADR-017: fully vectorized join and feature construction.
- Must use PurgedKFold from [scripts/trading_framework/ml/walk_forward.py](../scripts/trading_framework/ml/walk_forward.py) for time-series cross-validation.
- Should read signal timestamps from Phase 5 tables (#1–#5) rather than recomputing signals.

---

## Recommended Build Order
1. ✅ #2 IB Pullback Trigger Table
2. **#1 IB Breakout Enhanced Filter Set** — fastest win-rate impact per validation.
3. **#6 Universal Signal Filter / Classifier Input** — enables one ML filter for every strategy.
4. #3 OR / 9:30 Breakout Confluence Table
5. #4 ICT NY AM Confluence Table
6. #5 Failed Auction / Box Reversion Derived Filter

---

## Architecture Reminders
- Source data: `data/derived/ib_confluence_{SYM}.parquet` (306 cols, unique key on `symbol, session_slot, time_basis, trading_day`).
- Validation evidence: [data/reports/ib_confluence_validation.csv](../data/reports/ib_confluence_validation.csv).
- ADR-017: no per-row Python loops in calculation paths; vectorized NumPy/Pandas only.
- ADR-020: intraday positions hard-liquidated by 16:00 ET; derived targets should respect this.
- ADR-021: prop-firm evaluation uses only `scripts/trading_framework/ml/prop_firm_simulator.py`.
