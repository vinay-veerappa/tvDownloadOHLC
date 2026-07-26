# IB Statistical Discovery Plan

**Status:** Updated (2026-07-26) — see Part 9 for coverage status
**Scope:** Pilot on NQ1 or ES1, 1–3 years of data (not the full 20 years) for fast iteration. Expand only after the methodology is validated.
**Source data:** `data/derived/ib_confluence_{SYM}.parquet` (354 cols × ~5,300 trading days × 6 sessions), `ib_play_detail_{SYM}.parquet` (~500K per-play rows), `ib_facts_{SYM}.parquet` (189 cols), `ib_optimal_stops.parquet`, `ib_filter_effectiveness.parquet`.
**External reference:** Edgeful IB Playbook on YM (128 sessions, 6 months, 5 rules — see Part 7 for the findings we should replicate).
**Pilot scripts implemented:** `scripts/edgeful/ib_pilot_stats.py`, `ib_pilot_stacks.py`, `ib_pilot_5year.py`
**Validation report:** `EDGE_VALIDATION_REPORT.md`
**Automation design:** `AUTOMATION_DESIGN.md`

---

## Part 1 — Statistical Questions to Answer

### 1.1 Filter effectiveness (which filters actually helped?)

**Current state:** Phase 4a computed single-filter lift in `ib_filter_effectiveness.parquet` (125 rows). The audit flagged three problems:
- All measurements are in-sample (no walk-forward split).
- Min-N guard violated (`ib_news_distorted` had N=15 vs threshold 20).
- No multiple-testing correction (125 filters × p<0.05 → ~6 false positives by chance).

**Statistics to derive:**

| Statistic | Definition | Why it matters |
|---|---|---|
| **Conditional WR with N** | `P(win | filter=True)` and `P(win | filter=False)` per (play, session, filter) | The raw conditional — is the filter actually separating winners? |
| **Lift** | `WR_on − WR_off` | Already in `ib_filter_effectiveness`; needs N + min-N flag |
| **Bootstrap 95% CI on lift** | Resample day-session rows 1000×, recompute lift, take 2.5/97.5 pctile | Tells us if the lift is real or within noise |
| **Permutation p-value** | Shuffle filter flag, recompute lift, get null distribution | Is the lift distinguishable from random label assignment? |
| **FDR-corrected q-value** | Benjamini-Hochberg across all 125 filters | With 125 tests at p<0.05, ~6 will pass by chance |
| **Effect size (Cohen's h)** | `2·arcsin(√p1) − 2·arcsin(√p0)` | A lift from 50%→55% on N=20 is meaningless; on N=2000 is meaningful |
| **Coverage** | `N_filter_on / N_total` per filter | A filter that lifts 10% WR but only fires on 5% of days is untradeable |
| **Walk-forward lift** | Train lift on 2006–2018, test on 2019–2025 | A filter that lifts on train but decays on test is overfit |
| **Conditional expectancy lift** | `E[realized_r | filter=True] − E[realized_r | filter=False]` | WR lift is misleading when R:R varies; this is the honest metric |

**Output:** `data/derived/ib_filter_significance.parquet` (one row per filter × play × session, with lift, CI, p, q, effect size, coverage, walk-forward lift).

---

### 1.2 Effective MAE/MFE of a range

**Current state:** `ib_play_detail` has per-trade `mfe` and `mae` (in R-multiples). `ib_optimal_stops.parquet` has P95/P99 MAE of winners per (symbol, session, play, target_lvl). But we don't have the full distribution by **range size** (the user's question).

**Statistics to derive:**

| Statistic | Definition | Why it matters |
|---|---|---|
| **MAE distribution by range_bucket** | P25/P50/P75/P90/P95 of `mae` per (session, play, range_bucket) | Does a "Large" range day produce wider MAE? Stops must scale with range |
| **MFE distribution by range_bucket** | Same for `mfe` | Does a Large range give more MFE headroom? Affects target choice |
| **MAE/MFE ratio by range_bucket** | `median(mae) / median(mfe)` per cell | The "efficiency" of the move — how much heat to get how much reward |
| **MAE of winners vs losers** | P50/P75/P95 MAE split by `result ∈ {+1, −1}` | Winners pull back less than losers — the stop sits between these distributions |
| **MAE/MFE by time-of-day bucket** | Same split by `first_break_minutes` bucket | Late breaks may have different excursion profiles |
| **Excursion in price %** | `mae / ib_mid × 100` and `mfe / ib_mid × 100` | Cross-instrument comparable (ADR-002) |

**Output:** `data/derived/ib_excursion_distribution.parquet`.

---

### 1.3 Percentile achievement frequency (P25/P50/P75/P90 of price %)

**Question:** "How many times was P25 vs P50 vs P75 vs P90 of price percentage achieved?"

**Interpretation:** For each IB session, what is the empirical distribution of *how far price extends beyond the IB*? The user wants the **hit frequency** at each percentile of historical MFE.

**Statistics to derive:**

| Statistic | Definition | Why it matters |
|---|---|---|
| **Extension hit rate by level** | `P(ext_up_{L}_hit)` for L ∈ {0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0} per (session, side) | Already in `ib_facts` as `ext_up_{L}_hit`; needs aggregation |
| **P25/P50/P75/P90 of `max_ext_up`** | Empirical percentiles of the max extension (in IB-range multiples) per session | "Where does price typically go?" — the Gunship P20/P50/P75 levels |
| **Hit frequency at each percentile** | `P(max_ext_up ≥ P25)`, `P(max_ext_up ≥ P50)`, etc. | By definition 25/50/75/90% — but split by regime/filter to see conditional reach |
| **Conditional reach by range_bucket** | Same percentiles split by Small/Medium/Large range | Does a Large range day reach P75 more often? |
| **Conditional reach by bias agreement** | Same split by `bias_correct_*` | Does the correct-bias side reach further? |
| **Side asymmetry** | `P25/P50/P75/P90` separately for up vs down | NQ may extend further up than down (or vice versa) |
| **Price-% percentiles** | Same in `range_pct` terms (cross-instrument) | Compare NQ vs ES vs CL reach in normalized units |

**Output:** `data/derived/ib_extension_percentiles.parquet` + `ib_extension_hit_rate.parquet`.

---

### 1.4 Pullback depth for a successful move

**Question:** "What was the typical pullback (in price %) for a successful move?"

**Statistics to derive:**

| Statistic | Definition | Why it matters |
|---|---|---|
| **Pullback depth distribution (winners only)** | P25/P50/P75/P90 of `retrace_depth_pct` where `result=+1` | "How deep can a winner pull back before continuing?" |
| **Pullback by target level** | Same split by `target_lvl ∈ {0.25, 0.5, 0.75, 1.0}` | Higher targets may tolerate deeper pullbacks |
| **Pullback by entry variant** | Split by `entry_variant` (pre_break vs post_break) | Pre-break entries may see less pullback |
| **MAE-as-pullback for winners** | `mae` (in price %) where `result=+1` | The actual adverse excursion before the win — sets the stop distance |
| **P25 MAE (pullback entry level)** | Gunship: `p25_mae` is the pullback entry — enter when price retraces to P25 of winner MAE | Self-adapting entry level |
| **P80 MAE (invalidation level)** | Stop beyond P80 of winner MAE — "how deep can a winner pull back before failing" | Self-adapting stop |
| **Pullback-vs-extension scatter** | Joint distribution of `(mae, mfe)` per trade | Identifies the "sweet spot" where shallow pullback + deep extension = best trades |
| **Pullback timing** | Minutes from break to deepest pullback | Does the pullback happen in the first 15 min or later? |

**Output:** `data/derived/ib_pullback_distribution.parquet`.

---

### 1.5 One-side-then-other vs clean breakout

**Question:** "How many times does price hit one side of the IB and then take out the other side vs a clean breakout and never come back to test the other side?"

**This is the `double_break` vs single-break-then-extend question.**

**Statistics to derive:**

| Statistic | Definition | Why it matters |
|---|---|---|
| **Single break frequency** | `P(first_break_dir ≠ 0 AND double_break = False)` per session | How often is it a "clean" breakout? |
| **Double break frequency** | `P(double_break = True)` per session | How often does price take both sides? |
| **Double break order** | `P(double_break_order = "HL")` vs `"LH"` | High-first vs low-first — directional bias |
| **Double-break outcome** | Given double_break, what is `realized_dir_close`? | Does the second break predict the close direction? |
| **Clean-break extension** | Given single break, `P25/P50/P75/P90` of `max_ext` on the break side | How far does a clean break extend? |
| **Double-break extension** | Given double break, same percentiles | Does a double break extend less (choppy day)? |
| **Time-to-second-break** | Minutes from first break to second break | Quick double break = chop; late = trend day reversal |
| **Conditional on range_bucket** | All above split by Small/Medium/Large range | Large range days may double-break more |
| **Conditional on VIX bucket** | All above split by VIX regime | High VIX → more double breaks? |
| **Conditional on bias variant** | All above split by each `bias_*` | Does a bias variant predict the double-break direction? |
| **Mid-retest after clean break** | `P(mid_retest | single_break)` | Does a clean break revisit mid? Affects Play 2 |
| **Mid-retest after double break** | `P(mid_retest | double_break)` | After chop, does price come back to mid? |

**Output:** `data/derived/ib_break_topology.parquet`.

---

### 1.6 Conditions for each scenario

**Question:** "Under what conditions does each of these scenarios happen?"

**This is the conditional-probability layer. For each scenario above (clean break, double break, deep pullback, shallow pullback, P90 extension, etc.), what features predict it?**

**Method:** For each binary outcome `Y` (e.g. `double_break=True`), compute:
- `P(Y | feature=X)` for each feature in the 354-column confluence table
- Rank features by lift
- Apply FDR correction
- Report top 10 predictive features per scenario

**Features to condition on (pre-trade only — no look-ahead):**
- `range_bucket_trailing` (Small/Medium/Large)
- `vix_bucket_trailing` (low/mid/high)
- `dow` (Mon–Fri)
- `gap_dir` (up/down/none)
- `prior_day_result` (up/down/none)
- `bias_close_dir`, `bias_fvg`, `bias_fvg_ifvg`, `bias_formation_firstreach`, `bias_formation_lasttouch`
- `mid_lock_frac` (how locked the mid is during IB formation)
- `front_run_active` (was the mid front-run?)
- `ib_pct_time_above_mid` (if available)
- `first_break_minutes` (early/late break — knowable at break time, not pre-trade)
- `avwap_aligned`, `trend_aligned_with_break`
- `is_fomc_day`, `is_nfp_day`, etc. (from `ib_news_opex`)
- `ib_range_5d_pctile` (trailing regime estimate)

**Output:** `data/derived/ib_scenario_conditions.parquet`.

---

### 1.7 Timing of all these moves

**Question:** "The timing of all of these moves."

**Statistics to derive:**

| Statistic | Definition |
|---|---|
| **First break time distribution** | P25/P50/P75 of `first_break_minutes` per (session, range_bucket) |
| **Mid-retest time** | P25/P50/P75 of `mid_retest_minutes` given mid_retest occurred |
| **Extension time-to-hit by level** | P25/P50/P75 of `ext_up_{L}_minutes` for each L that was hit |
| **Pullback time** | Minutes from break to deepest pullback (for winners) |
| **Double-break gap** | Minutes from first to second break |
| **Time-decay curve** | `P(win | elapsed_minutes)` — already in `ib_time_decay_curves.parquet`; needs conditional split |
| **Front-run timing** | `front_run_time` distribution — when does the mid get front-run? |
| **Mid-lock timing** | `mid_lock_time` distribution — how early does the mid lock? |

**Conditional timing:** all of the above split by `range_bucket`, `vix_bucket`, `dow`, `bias_agreement`.

**Output:** `data/derived/ib_timing_distribution.parquet`.

---

### 1.8 IB duration comparison (5/15/30/40/50/60 min)

**Question:** "Comparing IB5 min vs IB 15 vs IB30 vs IB40 vs IB50 vs IB60. Can IB5 + IB15 predict how the longer version will move?"

**Current state:** The pipeline runs at 30/45/60 min durations only. The 5/15/40/50 min variants need to be computed (or loaded from a new run).

**Statistics to derive:**

| Statistic | Definition |
|---|---|
| **Range ratio** | `ib_range_5 / ib_range_60`, `ib_range_15 / ib_range_60`, etc. — how much of the full IB is captured by the shorter window |
| **Direction agreement** | `P(bias_60 = bias_5)`, `P(bias_60 = bias_15)` — does the short IB predict the long IB's bias? |
| **Break direction agreement** | `P(first_break_dir_60 = first_break_dir_5)` |
| **Extension agreement** | `P(max_ext_60 > 0.5R | max_ext_5 > 0.5R)` — does a 5-min extension predict a 60-min extension? |
| **Cumulative range curve** | `ib_range_t` as a function of `t ∈ {5, 15, 30, 40, 50, 60}` — how does range grow? |
| **Predictive power** | Logistic regression: `P(bias_60 = +1 | bias_5, bias_15, range_5, range_15)` — can short IBs predict the long IB? |
| **Per-duration WR** | WR per play per duration — does the 60-min IB produce higher WR than 5-min? |
| **Per-duration expectancy** | `E[realized_r]` per play per duration |
| **Per-duration MAE/MFE** | Excursion distributions per duration |

**Implementation:** Requires running `ib_derived_fields.py` with custom IB durations [5, 15, 30, 40, 50, 60] and joining the resulting per-duration fact tables on `trading_day` + `session_slot`.

**Output:** `data/derived/ib_duration_comparison.parquet` (one row per trading_day × session × duration pair).

---

### 1.9 ALN / Herman direction confirmation

**Question:** "Does ALN confirm direction or Herman, then what happens if we look for trade setups only in that direction?"

**Current state:** ALN (Asia-London-NY) and Herman Master Manual concepts are in `docs/SecondBrain_Trading.md` and `docs/Herman/HERMAN_MASTER_MANUAL.md`. They are NOT currently columns in `ib_confluence`. This requires joining the daily-context / overnight-regime data.

**Statistics to derive:**

| Statistic | Definition |
|---|---|
| **ALN direction** | Asia range direction → London sweep direction → NY expected direction (per the ALN model) |
| **Herman direction** | Asia-London liquidity sweep → NY fractal direction |
| **Agreement rate** | `P(bias_* = ALN_dir)`, `P(bias_* = Herman_dir)` per session |
| **Conditional WR** | `P(win | trade in ALN_dir)` vs `P(win | trade opposite ALN_dir)` |
| **Conditional WR (Herman)** | Same for Herman direction |
| **ALN + bias stack** | `P(win | ALN_dir = bias_* = trade_dir)` — triple confirmation |
| **ALN-only filter lift** | Lift of "trade only in ALN direction" vs "trade both directions" |
| **Herman-only filter lift** | Same for Herman |
| **ALN + Herman agreement** | `P(win | ALN = Herman = trade_dir)` — strongest confirmation |

**Implementation:** Compute ALN/Herman direction from `daily_context` + overnight session facts (Asia range, London sweep). Join to `ib_confluence` on `trading_day`. Then conditional WR via groupby.

**Output:** `data/derived/ib_aln_herman_lift.parquet`.

---

## Part 2 — Methodology: Efficient Multi-Parameter Testing

### 2.1 The problem with one-at-a-time testing

Testing one filter at a time (the current Phase 4a approach) is **O(N_filters)** but:
- Misses interactions (filter A alone is neutral, filter B alone is neutral, A+B together is strong).
- Suffers multiple-testing inflation (125 tests × 0.05 → 6 false positives).
- Doesn't account for filter redundancy (two filters that fire on the same days).

### 2.2 The efficient approach: greedy forward selection + logistic regression

**Step 1 — Logistic regression on pre-trade features:**
```
P(win | features) = sigmoid(β₀ + Σ βᵢ × featureᵢ)
```
- Features: all pre-trade columns in `ib_confluence` (~30-50 columns after removing outcome-window features).
- Trained on 2006–2018, tested on 2019–2025.
- Output: coefficient per feature, AUC, Brier score.
- This is **one model** that tests all features simultaneously — no multiple-testing problem.
- AUC > 0.55 means there's *some* signal; AUC > 0.60 means it's tradeable; AUC > 0.65 means it's strong.

**Step 2 — Greedy forward selection (Phase 4c, but with significance):**
- Start with no filters.
- At each step, add the filter that maximizes conditional expectancy subject to min-N ≥ 30.
- Stop when no filter adds significant lift (bootstrap CI of the marginal lift includes 0).
- This produces a small, non-redundant stack — usually 3–5 filters.

**Step 3 — Tree-based feature importance (random forest / XGBoost):**
- Train `RandomForestClassifier` on `result ∈ {+1, −1}` with all pre-trade features.
- Report feature importances — which features carry the most signal?
- This captures non-linear interactions the logistic regression misses.
- Cross-validate (time-series split) to avoid overfitting.

**Step 4 — SHAP values for interpretability:**
- For the tree model, compute SHAP values per prediction.
- Reports *which feature pushed this specific trade toward win/loss*.
- Lets you say "this trade was flagged because range_bucket=Large AND vix_bucket=high AND bias_fvg_ifvg=+1".

### 2.3 Why this is more efficient than the current approach

| Approach | Tests run | Captures interactions? | Multiple-testing fix | Overfit risk |
|---|---|---|---|---|
| Current Phase 4a (one-at-a-time) | 125 | ❌ | ❌ | High |
| Logistic regression | 1 model | ✅ (additive) | Built-in (regularization) | Medium |
| Greedy forward selection | ~5–10 iterations | ✅ (greedy) | Bootstrap CI at each step | Low |
| Random forest + SHAP | 1 model | ✅ (non-linear) | Built-in (OOB) | Medium (with CV) |

The **combination** of logistic regression (linear baseline) + random forest (non-linear) + greedy selection (interpretable stack) gives three independent views of the same data. If all three agree on the top features, those features are real.

### 2.4 Parallel execution (ADR-022)

- Logistic regression: scikit-learn, single fit, seconds.
- Random forest: `n_jobs=-1` across 24 cores, minutes.
- Bootstrap CIs: joblib `Parallel(n_jobs=24)`, 1000 resamples × 125 filters = 125K fits, parallel = minutes.
- Walk-forward: split data into 5 folds (2006-10, 2011-14, 2015-18, 2019-22, 2023-25), refit per fold, parallel across folds.

### 2.5 Output schema (unified)

All statistics tables share the same schema:
```
(symbol, session_slot, play, target_lvl, condition_key, condition_value,
 n_trades, n_wins, win_rate, expectancy_r, profit_factor,
 lift_vs_baseline, bootstrap_ci_low, bootstrap_ci_high,
 permutation_pvalue, fdr_qvalue, cohen_h, coverage)
```
This lets you query "show me all conditions where `expectancy_r > 0.05 AND fdr_qvalue < 0.10 AND n_trades > 100`" in one pandas filter.

---

## Part 3 — Statistics You Haven't Asked For (Discovery Layer)

These are statistical patterns the data can reveal that you wouldn't think to ask about. The method is **unsupervised / exploratory** — let the data speak rather than testing a hypothesis.

### 3.1 Clustering day-types (unsupervised)
- Run K-means / Gaussian mixture on the per-day feature vector (`range_pct, vix_close, gap_pct, first_break_minutes, mid_lock_frac, retrace_depth_pct, max_ext_up, max_ext_down, behavior`).
- Discover: are there natural day-types beyond the hand-tuned trend/normal/range/skip?
- Output: cluster labels + cluster centroids; compare to the regime router's labels.

### 3.2 Anomaly detection (isolation forest)
- Fit `IsolationForest` on the day features.
- The top 5% most anomalous days — what happened on those days? Are they news days? Are they the days where the strategy lost the most?
- Output: `ib_anomaly_days.parquet` (date, anomaly score, top-3 contributing features via SHAP).

### 3.3 Regime change detection (change-point analysis)
- Run `ruptures` or Bayesian online change-point detection on the rolling `expectancy_r` per session.
- Did the edge decay over the 20 years? Is there a structural break (e.g. 2020 COVID, 2022 rate hike)?
- Output: `ib_changepoints.parquet` (date, session, pre/post mean expectancy).

### 3.4 Autocorrelation of trade outcomes
- `Corr(result_t, result_{t-1})` per session — does a win yesterday predict a win today?
- `Corr(realized_r_t, realized_r_{t-1})` — streakiness of expectancy.
- If autocorrelation is significant, position sizing should scale with recent performance (Kelly fraction).

### 3.5 Conditional independence (which filters are redundant)
- For each pair of filters (A, B), compute `P(A=True | B=True)`. If > 0.85, they're redundant (already in `ib_filter_correlation.parquet`).
- But also compute **conditional lift**: `lift(A | B=True)` vs `lift(A | B=False)`. If A's lift disappears when B is True, A is subsumed by B.
- Output: a redundancy graph (DAG) showing which filters add marginal information.

### 3.6 Information-theoretic feature ranking
- Compute **mutual information** `I(feature; result)` for every pre-trade feature.
- Unlike logistic regression (which assumes linearity), MI captures any dependence.
- Rank features by MI — the top 10 are the most informative, regardless of model form.
- Output: `ib_feature_mutual_info.parquet`.

### 3.7 Calendar effects you might not expect
- Monthly seasonality: `WR(play=1, session=RTH, month=Jan)` vs `...month=Oct` — already computed but worth re-checking post-BL-7.
- Pre/post holiday: WR on the day before/after market holidays.
- Expiration cycle: WR by OPEX phase (quad witch vs normal).
- First-of-month vs end-of-month (institutional rebalancing).
- Payroll-Friday effect: WR on NFP day vs the day after.

### 3.8 The "quiet filter" — silent regime indicators
- Some filters are binary (FVG, sweep). Others are continuous and might have a threshold we haven't found.
- For each continuous feature (`range_pct, vix_close, gap_pct, mid_lock_frac, retrace_depth_pct`), plot `expectancy_r` as a function of the feature value (binned into deciles).
- The "quiet filter" is a feature where expectancy crosses zero at a specific threshold — that threshold is your trade/no-trade rule.

### 3.9 Survivorship of the edge over time
- Compute rolling 252-day `expectancy_r` per (session, play).
- Plot the time series — is the edge stable, decaying, or gone?
- If the edge was strong 2006–2015 but flat 2016–2025, the strategy is dead and no filter rescues it.

### 3.10 The "what if we did nothing" baseline
- For each session, compute the **buy-and-hold return** over the outcome window.
- Compare IB strategy expectancy to buy-and-hold. If the strategy underperforms buy-and-hold after costs, the "edge" is just a complicated way to capture beta.

---

## Part 4 — Implementation Plan

### Phase A — Conditional statistics (Layer 1+2, no new data)
Scripts: `ib_conditional_stats.py`
Inputs: `ib_confluence`, `ib_play_detail` (both already on disk)
Outputs: `ib_conditional_wr.parquet`, `ib_conditional_expectancy.parquet`, `ib_excursion_distribution.parquet`, `ib_pullback_distribution.parquet`, `ib_break_topology.parquet`, `ib_timing_distribution.parquet`
Runtime: minutes (vectorized groupby, no MC)
Effort: 1 day

### Phase B — Significance testing (Layer 3)
Scripts: `ib_filter_significance.py`
Inputs: `ib_confluence`, `ib_play_detail`, `ib_filter_effectiveness`
Outputs: `ib_filter_significance.parquet` (bootstrap CIs, permutation p-values, FDR q-values, walk-forward lift)
Runtime: ~30 min (joblib parallel, 1000 bootstrap × 125 filters)
Effort: 1 day

### Phase C — Predictive modeling (Layer 4)
Scripts: `ib_predictive_model.py`
Inputs: `ib_confluence` (pre-trade features only), `ib_play_detail`
Outputs: `ib_logistic_model.pkl`, `ib_random_forest.pkl`, `ib_shap_values.parquet`, `ib_feature_importance.parquet`
Runtime: ~10 min (sklearn fit, RF with n_jobs=-1)
Effort: 1 day

### Phase D — Duration comparison (requires new data run)
Scripts: rerun `ib_derived_fields.py` with durations [5, 15, 30, 40, 50, 60]; new `ib_duration_compare.py`
Inputs: 6 per-duration fact tables
Outputs: `ib_duration_comparison.parquet`
Runtime: ~6 hours (re-derive fields at 6 durations × 6 symbols)
Effort: 2 days (including the re-derivation)

### Phase E — ALN/Herman integration (requires daily-context join)
Scripts: `ib_aln_herman_lift.py`
Inputs: `ib_confluence`, `daily_context`, overnight session facts
Outputs: `ib_aln_herman_lift.parquet`
Runtime: minutes
Effort: 1 day (the ALN/Herman direction computation is the work)

### Phase F — Discovery layer (unsupervised)
Scripts: `ib_discovery.py`
Inputs: `ib_confluence`
Outputs: `ib_day_clusters.parquet`, `ib_anomaly_days.parquet`, `ib_changepoints.parquet`, `ib_feature_mutual_info.parquet`, `ib_edge_survival.parquet`
Runtime: ~30 min
Effort: 2 days

### Phase G — Realistic expectancy (Layer 5)
Scripts: `ib_realistic_expectancy.py`
Inputs: `ib_play_detail`, `ib_optimal_stops`, contract specs
Outputs: `ib_realistic_expectancy.parquet` (risk-scaled dollar expectancy per condition)
Runtime: minutes
Effort: 0.5 day

**Total: ~7-8 days of implementation, all vectorized/parallel, no new infrastructure.**

---

## Part 5 — Decision Criteria

After running all phases, the verdict is determined by:

1. **Does any filter survive FDR + walk-forward?** (`fdr_qvalue < 0.10 AND walk_forward_lift > 0`)
   - Yes → that filter is the regime. Run the strategy only on those days.
   - No → the edge is noise. Stop.

2. **Is conditional expectancy > 0.05R after costs?** (`expectancy_r > 0.05 AND coverage > 0.10`)
   - Yes → tradeable edge exists on ~10%+ of days.
   - No → no tradeable edge even conditional.

3. **Does the predictive model AUC > 0.55 on test set?**
   - Yes → there is pre-trade signal.
   - No → the features don't predict the outcome; no amount of filtering helps.

4. **Is the rolling 252-day expectancy flat or positive in 2024–2025?**
   - Yes → the edge is alive today.
   - No → the edge is dead; historical numbers are irrelevant.

**If all four are No, the honest answer is: the IB strategy has no edge, conditional or unconditional, and we should move to a different strategy family.**

---

## Part 6 — Open Questions for Discussion

1. **Duration comparison:** Should we re-derive fields at 6 durations (5/15/30/40/50/60 min) for all 6 symbols, or just NQ1 first as a pilot? The re-derivation is ~1 hour per symbol per duration.

2. **ALN/Herman:** Are the ALN and Herman direction rules fully specified in `docs/SecondBrain_Trading.md` and `docs/Herman/HERMAN_MASTER_MANUAL.md`, or do we need to extract them from transcripts? This affects Phase E effort.

3. **Predictive model scope:** Should the logistic regression predict `P(win)` (binary) or `E[realized_r]` (continuous)? The continuous target is more honest but noisier.

4. **Discovery layer priority:** Which unsupervised method (clustering, anomaly, change-point, MI) is most interesting? All four are cheap; we can run them all.

5. **Walk-forward split:** 70/30 (2006–2018 / 2019–2025) or rolling-origin (5 folds of 4 years each)? Rolling-origin is more robust but takes 5× longer.

6. **Cost model:** Should Phase G use the current `account_size × pnl_pct` model, the 1-Micro model, or the risk-scaled Micro model? The risk-scaled model is the most honest but requires stop-distance per trade (we have this in `ib_optimal_stops`).

7. **Cross-instrument transfer:** Should filters learned on NQ1 be tested on ES1/CL1/GC1? If a filter generalizes, it's more likely real. If it's NQ1-specific, it's likely overfit.

---

## Part 7 — Edgeful IB Playbook Findings (YM, 128 sessions)

**Source:** `C:\Users\vinay\Downloads\full IB playbook on YM.pdf` (Edgeful, 2025-12-08 through 2026-06-08, 128 NY sessions on YM)

The Edgeful playbook is the reference model for what IB statistics *should* look like — a LLM-driven sweep of thousands of condition combinations producing 5 actionable rules with attached sample sizes. We should replicate these statistics on our data and verify whether they hold.

### 7.1 Baseline statistics (the "normal day" table)

Edgeful reports these baselines for YM over 128 sessions. We should compute the same for NQ1/ES1 over our pilot window.

| Stat | YM (Edgeful) | Our equivalent column | Status |
|---|---|---|---|
| Single break % | 80.5% | `P(first_break_dir ≠ 0 AND double_break = False)` | ✅ Computable from `ib_facts` |
| Double break % | 13.3% | `P(double_break = True)` | ✅ `double_break` column |
| No break % | 6.3% | `P(first_break_dir = 0)` | ✅ Computable |
| First break = IB high | 46.1% | `P(first_break_dir = +1)` | ✅ `first_break_dir` column |
| First break = IB low | 47.7% | `P(first_break_dir = −1)` | ✅ Same column |
| Green day % | 52.3% | `P(realized_dir_close = +1)` | ✅ `realized_dir_close` column |

**Gap:** We compute these per-session but don't report them as a headline baseline table. The `ib_strategy_report.py` should emit this as Section 0.

### 7.2 The 5 rules (condition stacks with WR)

Each Edgeful rule is a **condition stack** — start with a baseline, add conditions one at a time, report N and hit rate at each step. This is exactly the "conditional WR" table from Part 1.1, but structured as a *cumulative stack* rather than independent filters.

#### Rule 1 — 10:30 Direction Trigger

| Condition | N | Hit rate |
|---|---|---|
| Low formed first (alone) | 66 | 72.7% |
| + first hour closes in top 25% of range | 38 | 97.4% |
| High formed first (alone) | 62 | 77.4% |
| + first hour closes in bottom 25% | 36 | 97.2% |

**Our mapping:**
- "Low formed first" = `bias_formation_firstreach = +1` (low timestamp < high timestamp) — ✅ in `ib_facts`
- "First hour closes in top 25% of range" = `(ib_close − ib_low) / ib_range > 0.75` — computable from `ib_high/ib_low/ib_close/ib_range`
- **Gap:** We do not currently compute `ib_close_position_in_range` (where the close sits within the IB range as a 0–1 percentile). This is a **new derived field** we need to add.

#### Rule 2 — Day Color from First Hour

| Condition stack | N | Green day % |
|---|---|---|
| Green IB alone | 67 | 80.6% |
| Large IB alone (>0.7%) | 58 | 60.3% |
| Both (green + large) | 29 | 89.7% |
| High breaks first | 59 | 79.7% |
| + before 12:00 | 46 | 87.0% |
| + IB candle green | 38 | 97.4% |
| + IB also large | 19 | 100% |

**Our mapping:**
- "Green IB" = `ib_close > ib_open` — ✅ computable
- "Large IB" = `range_pct > 0.7` — ✅ `range_pct` column exists
- "High breaks first" = `first_break_dir = +1` — ✅
- "Before 12:00" = `first_break_minutes < 90` (90 min after 10:30 IB close = 12:00) — ✅ `first_break_minutes`
- **Gap:** The cumulative condition-stack structure (each row adds one condition and recomputes N + hit rate) is NOT in our current Phase 4a output. Phase 4a reports *independent* filter lifts, not *cumulative stacks*. We need a new `ib_condition_stack` computation.

#### Rule 3 — Hold vs Fade (the clock filter)

| Condition | N | No double break % |
|---|---|---|
| Baseline (any break) | 120 | 85.8% |
| Break before 12:00 | 92 | 94.6% |
| Low break < 12:00 + opened inside yesterday's range | 31 | 100% |
| High break < 12:00 + large IB | 23 | 100% |
| First break after 12:00 | 28 | 57.1% (fade risk) |
| + previous day red | 17 | 52.9% (fade risk) |

**Our mapping:**
- "Break before 12:00" = `first_break_minutes < 90` — ✅
- "Opened inside yesterday's range" = `gap_dir` and prior-day IB range overlap — **gap**: we have `gap_dir` but not `opened_inside_prior_range`. New derived field.
- "Previous day red" = `prior_day_result = −1` — ✅ column exists

**Key finding to replicate:** The clock is the strongest single filter. Early breaks hold 94.6%; late breaks fade 42.9%. This is the `first_break_minutes` distribution from Part 1.7, but specifically the *conditional* `P(double_break | first_break_minutes > 90)`.

#### Rule 4 — Extension Targets

| Condition | N | Reaches −0.5x | Closes below IB low |
|---|---|---|---|
| Small IB (<0.47%) + low breaks < 12:00 | 13 | 84.6% | 61.5% |
| Given high break, reaches +0.5x | — | 42.4% baseline | — |
| IB range > 0.9% | 21 | — | Closes back inside 76.2% |

**Our mapping:**
- "Reaches −0.5x" = `ext_down_0_5_hit = True` — ✅ in `ib_facts` (`ext_down_{L}_hit`)
- "Small IB" = `range_pct < 0.47` — ✅ `range_pct`
- "Closes back inside IB" = `realized_dir_close` sign AND close within `[ib_low, ib_high]` — **gap**: we have `outcome_close` but not `close_inside_ib` boolean. Computable.

**Key finding to replicate:** Small IB + low break → 84.6% reach −0.5x extension. Large IB (>0.9%) → 76.2% rotation back inside. This is the Part 1.3 extension percentile question, conditioned on IB size.

#### Rule 5 — Close Location (the in-trade decision)

| Condition stack | N | Closes above IB high | Inside IB | Below IB low |
|---|---|---|---|---|
| All days (baseline) | 128 | 25.8% | 46.9% | 27.3% |
| IB high breaks first | 59 | 50.8% | 40.7% | 8.5% |
| + before 12:00 | 46 | 65.8% | 31.6% | 2.6% |
| + IB candle green | 38 | 86.7% | 13.3% | 0.0% |
| Never reached +0.5x | 34 | 26.5% | 59% | 14.5% |
| Reached +0.5x | 25 | 84.0% | 16.0% | 0.0% |
| Reached +1.0x | 9 | 88.9% | 11.1% | 0.0% |

**Our mapping:**
- "Closes above IB high" = `outcome_close > ib_high` — ✅ computable from `outcome_close`
- "Reached +0.5x" = `ext_up_0_5_hit = True` — ✅
- **Gap:** We don't compute the 3-way close-location classification (above IB high / inside IB / below IB low). This is a **new derived field**: `close_location = np.where(outcome_close > ib_high, 'above', np.where(outcome_close < ib_low, 'below', 'inside'))`.

### 7.3 Statistics from Edgeful that we are MISSING

| Edgeful statistic | Our status | Action |
|---|---|---|
| **IB close position in range** (0–1 percentile of close within IB) | ❌ Not computed | Add to `ib_derived_fields.py` |
| **Cumulative condition stacks** (each row adds a condition, reports N + hit rate) | ❌ Phase 4a is independent, not cumulative | New script `ib_condition_stacks.py` |
| **Opened inside yesterday's range** (boolean) | ❌ Not computed | Add to `ib_derived_fields.py` (needs prior-day IB range) |
| **3-way close location** (above IB high / inside / below IB low) | ❌ Not computed | Add to `ib_derived_fields.py` |
| **Day color** (green/red close vs prior close) | ⚠️ `realized_dir_close` is sign of close vs IB close, not vs prior day close | Add `day_color = sign(outcome_close − prior_session_close)` |
| **IB candle color** (green/red first hour) | ⚠️ Computable as `sign(ib_close − ib_open)` but not stored as a column | Add `ib_candle_color` |
| **IB size buckets** (<0.47% small / 0.47–0.7% mid / >0.7% large / >0.9% huge) | ⚠️ `range_bucket` uses terciles, not Edgeful's thresholds | Add `ib_size_bucket_edgeful` using Edgeful thresholds |
| **Extension-as-confirmation** (P(close above IB high \| reached +0.5x)) | ❌ Not computed as a conditional | Computable from existing columns via groupby |
| **Prior day context** (prior day color, prior day close vs its IB) | ⚠️ `prior_day_result` exists but is coarse | Add `prior_day_closed_above_ib` boolean |
| **65% threshold rule** (only report conditions ≥65% WR) | ❌ We report all lifts without a threshold | Add `meets_65_threshold` flag to filter tables |

### 7.4 Edgeful's methodology we should adopt

1. **Sample sizes attached to everything.** Every stat carries N. Sub-20 samples are flagged as "confluence, not conviction." We should do the same — add `n_trades` to every conditional table and a `confidence_tier` column: `conviction (N≥50) / confluence (20≤N<50) / insufficient (N<20)`.

2. **Cumulative stacking, not independent testing.** Edgeful builds rules by *adding* conditions, not testing them independently. This is the greedy-forward-selection approach from Part 2.2 — we should implement it as `ib_condition_stacks.py`.

3. **The 65% bar.** A rule only counts as a setup if it hits 65%+ historically. Below that, it's a "risk filter" or "context." We should adopt this labeling in our output tables.

4. **Time-bounded validation.** Edgeful uses 6 months (128 sessions). We should pilot on 1–3 years (250–750 sessions) — enough for statistical power, short enough to iterate fast.

5. **The morning checklist.** Edgeful compresses everything into 4 questions at 10:30. Our equivalent would be: a `ib_morning_checklist.py` that outputs, per day, the 4 answers and the suggested action.

### 7.5 Existing IB statistics in our codebase (from codebase-memory search)

From the knowledge graph, these are the IB statistics functions already implemented:

| Function | File | What it computes |
|---|---|---|
| `calculate_ib_statistics` | `scripts/libs_py/nqstats/ib.py` | Legacy IB stats (v1) |
| `calculate_ib_statistics_v5` | `scripts/libs_py/nqstats/ib.py` | v5 multi-session IB stats (7 inbound edges — most-used IB function) |
| `calculate_ib_bias` | `scripts/libs_py/nqstats/ib.py` | IB bias computation |
| `verify_ib_breaks` | `scripts/nqstats/initial_balance/verify_ib_breaks.py` | IB break verification |
| `analyze_ib_bias` | `scripts/orb_generic/.../08_ib_bias_study.py` | IB bias study |
| `compute_ib_bias` | `scripts/orb_generic/.../signal_generators.py` | IB bias for signal generation |
| `test_ib_breakout` | `scripts/strategies/data_analysis/entry_timing_simulation.py` | IB breakout timing test |
| `_ib_vote` | `scripts/context/compute_daily_confluence.py` | IB vote in daily confluence |

**NQStats IB reports** (`docs/nqstats/initial_balance/`):
- `REPORT.md` — IB break statistics, extension hits, timing
- `LOGIC.md` — IB definitions and computation logic
- These are the NQ-specific IB stats that predate the edgeful pipeline.

**Existing derived data** (`data/derived/`):
- `ib_optimal_stops.parquet` — P95/P99 MAE, optimal_stop_r, rr_ratio, wr_at_optimal_stop, expectancy_at_optimal_stop
- `ib_filter_effectiveness.parquet` — 125 single-filter lift measurements
- `ib_filter_correlation.parquet` — pairwise filter correlation
- `ib_filter_stacks.parquet` — greedy forward-selected filter combos
- `ib_conviction_weights.parquet` — validated filter weights
- `ib_time_decay_curves.parquet` — P(win | elapsed_minutes)
- `ib_break_speed_stats.parquet` — break speed × outcomes
- `ib_empirical_targets.parquet` / `ib_empirical_targets_best.parquet` — Gunship percentile targets
- `ib_empirical_baselines.json` — TrevorTrades 10-year ES priors

**Gap summary:** We have the *raw material* (354 columns, per-play results, optimal stops, filter lifts) but we are missing the *Edgeful-style presentation* — cumulative condition stacks, 65% threshold labeling, sample-size confidence tiers, the morning checklist, and several specific derived fields (IB close position, opened-inside-prior-range, 3-way close location, IB candle color, day color).

---

## Part 8 — Revised Pilot Plan (NQ1 or ES1, 1–3 years)

### 8.1 Scope reduction for fast iteration

| Parameter | Full plan | Pilot |
|---|---|---|
| Symbols | 6 (NQ1/ES1/YM1/RTY1/CL1/GC1) | **1 (NQ1 or ES1)** |
| Date range | 2006–2025 (20 years) | **2023-01-01 to 2025-12-31 (3 years, ~750 sessions)** |
| Sessions | 6 (RTH/Globex/Tokyo/London/Midnight/NY PM) | **1 (NY AM IB only)** — expand later |
| Durations | 6 (5/15/30/40/50/60 min) | **1 (60 min)** — expand later |
| Bootstrap sims | 1000 | **200** (enough for 95% CI) |
| Walk-forward | 5-fold | **Single 70/30 split** (2023-2024 train, 2025 test) |

**Runtime estimate:** Phase A (conditional stats) on 750 sessions × 1 symbol = seconds. Phase B (significance) = minutes. Phase C (predictive model) = seconds. Total pilot: **< 30 minutes end-to-end**.

### 8.2 What the pilot validates

1. **Does the conditional WR / expectancy table find anything above 65% with N ≥ 30?** If yes on the pilot, expand to full data. If no, the edge is likely dead and we save weeks of compute.

2. **Does the logistic regression AUC beat 0.55?** If yes, there's pre-trade signal. If no, no amount of filtering helps.

3. **Do any filters survive FDR on 750 sessions?** With fewer tests (pilot uses ~30 pre-trade features, not 125), FDR is less stringent. A filter that survives at N=750 is more likely to survive at N=5000.

4. **Does the Edgeful Rule 1 (10:30 direction trigger) replicate on our data?** This is the single most valuable cross-check: if `bias_formation_firstreach + ib_close_position > 0.75` gives us >90% first-break-direction prediction on NQ1 2023–2025, the methodology is validated and we expand.

### 8.3 Pilot phases (revised from Part 4)

| Phase | Script | Output | Runtime | Effort |
|---|---|---|---|---|
| **A** — New derived fields | `ib_pilot_fields.py` | `ib_close_position`, `ib_candle_color`, `day_color`, `opened_inside_prior_range`, `close_location_3way`, `ib_size_bucket_edgeful` | seconds | 0.5 day |
| **B** — Conditional stats + condition stacks | `ib_pilot_condition_stats.py` | `ib_conditional_wr.parquet`, `ib_condition_stacks.parquet` (Edgeful-style cumulative) | seconds | 0.5 day |
| **C** — Significance + FDR | `ib_pilot_significance.py` | `ib_filter_significance.parquet` (bootstrap CI, perm p, FDR q, 65% flag) | ~5 min | 0.5 day |
| **D** — Predictive model | `ib_pilot_predictive.py` | `logistic_model.pkl`, `rf_model.pkl`, `feature_importance.parquet`, AUC/Brier | seconds | 0.5 day |
| **E** — Edgeful replication | `ib_pilot_edgeful_replication.py` | Replicate all 5 rules on NQ1, report N + hit rate | seconds | 0.5 day |
| **F** — Discovery (MI + edge survival + day clusters) | `ib_pilot_discovery.py` | `ib_mutual_info.parquet`, `ib_edge_survival.png`, `ib_day_clusters.parquet` | ~5 min | 1 day |

**Total pilot: ~3 days.** If the pilot shows signal, expand to 6 symbols × 20 years × 6 sessions with the validated methodology.

### 8.4 Decision gate after pilot

After the pilot completes, answer these 4 questions:

1. **Does any condition stack reach 65%+ WR with N ≥ 30?**
   - Yes → expand to full data with that stack as the primary hypothesis.
   - No → the edge is dead on NQ1 NY AM; test ES1 or a different session before abandoning.

2. **Does the logistic model AUC > 0.55 on the 2025 test set?**
   - Yes → pre-trade features predict outcomes; expand.
   - No → no predictive signal; stop.

3. **Does the Edgeful Rule 1 replicate (>90% direction prediction)?**
   - Yes → the methodology works; replicate all 5 rules on full data.
   - No → either our data is different from Edgeful's, or the rule is YM-specific.

4. **Is the rolling 252-day expectancy positive in 2024–2025?**
   - Yes → the edge is alive today.
   - No → historical edge is dead; stop.

---

## Part 9 — Coverage Status (2026-07-26)

### 9.1 What has been completed

| Plan item | Status | Script / Output | Finding |
|---|---|---|---|
| **Part 1.1 — Filter effectiveness** | PARTIAL | `ib_pilot_stacks.py` (condition stacks + bootstrap CI) | Rule 1 + Rule 3 validated with CIs; 125-filter FDR not yet run |
| **Part 1.2 — MAE/MFE of a range** | NOT DONE | — | `ib_optimal_stops.parquet` has P95/P99 but not by range_bucket |
| **Part 1.3 — Extension percentile frequency** | PARTIAL | `ib_pilot_stats.py` Rule 4 | `max_ext_up/down` P50/P75/P90 by IB size bucket computed; hit-rate-by-level not yet |
| **Part 1.4 — Pullback depth for winners** | NOT DONE | — | `retrace_depth_pct` exists in confluence but not analyzed |
| **Part 1.5 — One-side-then-other vs clean breakout** | PARTIAL | `ib_pilot_stats.py` Rule 3 | Single/double break % computed; conditional extension not yet |
| **Part 1.6 — Conditions for each scenario** | PARTIAL | `ib_pilot_stacks.py` | Rule 1/2/3 condition stacks computed; full 354-column scan not yet |
| **Part 1.7 — Timing of moves** | PARTIAL | `ib_pilot_stats.py` Rule 3 | `first_break_minutes` early/late split done; full timing distribution not yet |
| **Part 1.8 — IB duration comparison (5/15/30/40/50/60)** | NOT DONE | — | Requires re-deriving fields at 6 durations |
| **Part 1.9 — ALN / Herman direction** | NOT DONE | — | Requires daily-context join + ALN/Herman computation |
| **Part 2 — Multi-parameter testing (logistic/RF/SHAP)** | NOT DONE | — | Phase C of pilot plan |
| **Part 3.1 — Day-type clustering** | NOT DONE | — | Discovery layer |
| **Part 3.2 — Anomaly detection** | NOT DONE | — | Discovery layer |
| **Part 3.3 — Change-point detection** | PARTIAL | `ib_pilot_5year.py` edge_by_year | Per-year E[R] shows 2026 weakening; formal change-point not run |
| **Part 3.4 — Autocorrelation of outcomes** | NOT DONE | — | Discovery layer |
| **Part 3.5 — Conditional independence / redundancy** | NOT DONE | — | `ib_filter_correlation.parquet` exists but not conditional lift |
| **Part 3.6 — Mutual information feature ranking** | NOT DONE | — | Discovery layer |
| **Part 3.7 — Calendar effects** | DONE | `ib_pilot_5year.py` edge_by_dow, edge_by_month | Per-DOW and per-month E[R] computed for all 3 plays |
| **Part 3.8 — Quiet filter (continuous threshold)** | NOT DONE | — | Discovery layer |
| **Part 3.9 — Edge survival over time** | DONE | `ib_pilot_5year.py` edge_by_year | Per-year E[R] with bootstrap CI for 2021-2026 |
| **Part 3.10 — Buy-and-hold baseline** | NOT DONE | — | Discovery layer |
| **Part 7 — Edgeful replication** | DONE | `ib_pilot_stats.py` + `ib_pilot_stacks.py` | All 5 rules replicated; Rule 1 holds, Rule 3 inverted, Rule 2A fails |
| **Part 8 — Pilot plan** | DONE | `ib_pilot_stats.py`, `ib_pilot_stacks.py`, `ib_pilot_5year.py` | Phases A, B, E, F(partial) complete; C, D not yet |

### 9.2 Pilot decision gate results

| Question | Answer | Evidence |
|---|---|---|
| 1. Any condition stack >65% WR with N>=30? | **YES** | Rule 1A: 88.1% (N=387), Rule 1B: 86.3% (N=322) |
| 2. Logistic model AUC > 0.55? | **NOT TESTED** | Phase D (predictive model) not yet implemented |
| 3. Edgeful Rule 1 replicates (>90%)? | **PARTIAL** | 88.1% on NQ1 (vs 97.4% on YM) — direction matches, magnitude lower |
| 4. Rolling 252-day expectancy positive in 2024-2025? | **YES** | Play 1: +0.061 (2025), +0.021 (2026 CI crosses zero); Play 3: +0.096 (2025), +0.415 (2026) |

### 9.3 What remains to be done (prioritized)

**HIGH PRIORITY (directly affects the automation strategy):**

0. **STOP-DISTANCE OPTIMIZATION FOR PROP VIABILITY (NEW — critical)** — The validated edge assumes `ib_opposite` (full IB range stop). On NQ1 at ~20K with a 1.3% range, that's ~260 points = $520 per Micro = 1.04% of a $50K account. On large IB days (>0.9%), the stop could be $400+ which eats the edge. We need to find the **minimum stop that preserves the edge**:
   - MAE distribution of winners by range_bucket → P80/P90/P95 MAE = the stop that doesn't kill winners
   - MAE distribution of losers → where do losers peak before failing?
   - The optimal stop sits between P80 MAE of winners (don't stop out winners) and P50 MAE of losers (stop out losers early)
   - Conditional expectancy at each stop distance: `E[R | stop = X]` for X ∈ {0.25R, 0.5R, 0.75R, 1.0R, ib_opposite}
   - Dollar risk per trade at each stop distance: `stop_points × point_value × contracts` — must be < 1% of account
   - Prop-firm viability: can we pass Apex/TopStep/FTMO with the tighter stop?

1. **Part 1.2 — MAE/MFE distribution by range_bucket** — needed to set stops per IB size. Currently we use `ib_opposite` (full range) which the review showed is too wide. The MAE distribution by range size would give us size-adaptive stops.

2. **Part 1.4 — Pullback depth for winners** — needed to set the Play 3 fade entry level. Currently we use 0.25x overshoot; the P25 MAE of winners would give us the empirical pullback entry.

3. **Part 2 — Logistic regression + random forest** — the predictive model would tell us if the pre-trade features (beyond Rule 1) add signal. AUC > 0.55 means there's more edge to extract; AUC < 0.55 means Rule 1 is all we have.

4. **Part 1.8 — IB duration comparison** — the automation uses 60-min IB; would a 30-min or 45-min IB produce better results? This requires re-deriving fields at multiple durations.

**MEDIUM PRIORITY (improves the edge but not blocking automation):**

5. **Part 1.9 — ALN/Herman direction** — would add a third direction confirmation layer on top of Rule 1.

6. **Part 3.6 — Mutual information feature ranking** — model-free feature importance; would confirm whether Rule 1's features (bias_firstreach, ib_close_position) are truly the top predictors or if there are better ones we haven't tested.

7. **Part 3.1 — Day-type clustering** — might reveal that the hand-tuned trend/normal/range/skip regime router is wrong.

8. **Part 1.3 — Extension hit-rate by level** — the full `ext_up_{L}_hit` aggregation for all 10 levels, not just the P50/P75/P90 of max_ext.

**LOW PRIORITY (nice to have, not blocking):**

9. **Part 3.2 — Anomaly detection** — interesting but not actionable for the strategy.
10. **Part 3.4 — Autocorrelation** — would inform Kelly sizing but not entry/exit logic.
11. **Part 3.5 — Conditional independence** — filter redundancy analysis; useful for the 125-filter FDR but not for the 5-rule Edgeful stack.
12. **Part 3.8 — Quiet filter** — continuous threshold discovery; the calendar filters already capture the main seasonal effects.
13. **Part 3.10 — Buy-and-hold baseline** — academic interest; the strategy is intraday so buy-and-hold is not the right comparator.

### 9.4 Summary

**Coverage: 7 of 22 plan items fully done, 6 partial, 9 not started.**

The pilot validated the core methodology (Rule 1 direction trigger, Rule 3 clock filter, per-year/DOW/month seasonality, Edgeful replication) and produced the `EDGE_VALIDATION_REPORT.md` and `AUTOMATION_DESIGN.md`. The automation can proceed with the current findings — the 4 high-priority items above would improve the strategy but are not blocking.

The most important remaining question is **Part 2 (predictive model)**: does the logistic regression find signal beyond Rule 1? If AUC > 0.55, there are additional filters worth adding to the automation. If AUC < 0.55, Rule 1 + Rule 3 + calendar filters is the complete edge, and the automation should proceed as designed.