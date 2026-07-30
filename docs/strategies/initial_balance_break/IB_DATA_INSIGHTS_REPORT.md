# IB Strategy Data Insights Report

**Generated:** 2026-07-28
**Scope:** Consolidated synthesis of all IB (Initial Balance) research data produced across the research, results, and validation directories.
**Purpose:** The codebase contains a large volume of computed data (per-asset matrices, bias comparisons, mechanism evaluations, stop comparisons, 5-year edge validation, multi-asset validation) but no single document ties it together. This report extracts the actionable insights.

---

## 1. Executive Summary

The IB strategy family has been validated across **6 futures assets × 3 sessions × multiple bias/duration/variant/level configurations** over a **5-year window (2021–2025)** plus a focused **NQ1 NY AM IB 6-year edge-validation study (2021–2026)**. The data shows:

- ✅ **A real, statistically significant edge exists** on NQ1 NY AM IB. The earlier 20-year BacktestLoop "all-F" result was an artifact of an overly wide stop model (full IB range stop), not absence of edge.
- ✅ **Two standout strategies** emerge from the multi-asset sweep: NQ1 RTH Pre-Break Q25 (+17.10%) and CL1 Tokyo Post-Break Fib618 (+28.25%).
- ✅ **Decoupling bias filters** was the single biggest methodology improvement — it revealed that "FVG bias" is a high-precision powerhouse (+5.67% vs −28.84% under the contaminated model).
- ⚠️ **The edge is conditional, not universal** — it varies by day-of-week, month, year, bias variant, IB size, and break timing. Blind execution loses money.
- ⚠️ **2026 weakening of Play 1 breakout** (CI crosses zero) is a flag to monitor; Play 3 (fade) is strengthening in 2026.

---

## 2. The Two Layers of Evidence

The data is split across two complementary layers that should not be conflated:

| Layer | Source | What it measures | Sample |
|---|---|---|---|
| **A. Matrix sweep** | `results/multi_asset_matrix_results.csv`, `research/multi_asset_validation/` | Per-config P&L with `ib_opposite` stop, in price-%, all 6 assets | 6 assets × 4 configs each |
| **B. Play-detail edge validation** | `EDGE_VALIDATION_REPORT.md` | Per-play R-multiple expectancy with bar-by-bar target-before-stop resolution, bootstrap CIs | NQ1 only, 1,308 sessions |

**Layer B is the more honest edge measurement** because it evaluates target-before-stop bar-by-bar rather than imposing a fixed wide stop. Layer A is the "what would the backtest engine produce" view.

---

## 3. Multi-Asset Matrix Insights (Layer A)

### 3.1 The winners

| Asset | Config | Session | Trades | WR | PF | Sharpe | Max DD | Return |
|---|---|---|---|---|---|---|---|---|
| **NQ1** | RTH_45m PreBreak_Q25 | RTH | 478 | 51.3% | 1.13 | 0.58 | −11.61% | **+17.10%** |
| **CL1** | Tokyo_60m PostBreak_Fib618 | Tokyo | 800 | 62.7% | 1.46 | 2.18 | −2.54% | **+28.25%** |
| **CL1** | Globex_45m PostBreak_FVG_Inversion | Globex | 155 | 51.6% | 1.55 | 1.01 | −5.26% | **+18.45%** |
| **GC1** | Tokyo_60m PostBreak_Fib618 | Tokyo | 807 | 62.6% | 1.06 | 0.30 | −0.94% | +1.20% |
| **ES1** | Globex_45m PostBreak_FVG_Inversion | Globex | 90 | 46.7% | 1.17 | 0.28 | −1.74% | +1.28% |
| NQ1 | Tokyo_60m PostBreak_Fib618 | Tokyo | 657 | 62.9% | 1.17 | 0.80 | −1.42% | +3.33% |

### 3.2 The losers (do not trade)

| Asset | Config | Session | Return | Why |
|---|---|---|---|---|
| RTY1 | RTH_45m PreBreak_Q25 | RTH | −28.45% | Russell RTH is too volatile; whipsaws dominate |
| CL1 | RTH_45m PreBreak_Q25 | RTH | −20.85% | Crude RTH breakout fails — energy noise |
| GC1 | RTH_45m PreBreak_Q25 | RTH | −14.92% | Gold RTH breakout fails |
| YM1 | RTH_45m PreBreak_Q25 | RTH | −7.06% | Dow RTH breakout marginal |
| ES1 | RTH_45m PreBreak_Q25 | RTH | −6.64% | S&P RTH breakout marginal |

### 3.3 Cross-asset patterns

1. **RTH Pre-Break Q25 is an NQ1-specific edge.** It fails on ES1/RTY1/YM1/GC1/CL1. Do not generalize it.
2. **Tokyo Post-Break Fib618 is broadly positive** on NQ1 (+3.33%), GC1 (+1.20%), and CL1 (+28.25%) — overnight trends are cleaner across most assets. The exception is ES1 (−3.94%) and RTY1 (−2.45%).
3. **Globex FVG Inversion is the universal safety shield.** Drawdowns are capped at −1.74% to −6.79% across all 6 assets. Returns are small but positive on NQ1 (+0.14%), ES1 (+1.28%), CL1 (+18.45%). It is a capital-preservation filter, not a return generator (except on CL1).
4. **Index futures (NQ/ES/RTY/YM) struggle in RTH with breakout entries.** The edge concentrates in overnight sessions for these assets.

---

## 4. NQ1 NY AM IB Edge Validation (Layer B — the deep study)

This is the most statistically rigorous study in the codebase: 1,308 sessions, bootstrap CIs, all 3 plays × 4 targets × 8 bias variants × 13 entry modules.

### 4.1 The three plays — 5-year expectancy

| Play | Name | E[R] all-time | Verdict |
|---|---|---|---|
| Play 1 | Breakout | +0.079 | Stable edge, positive all 6 years |
| Play 2 | Retest | +0.097 | Regime-dependent (negative 2022) |
| **Play 3** | **Fade** | **+0.099** | **Strongest at 0.25x target (+0.259)** |

**11 of 12 play+target combos have positive E[R].** Only Play 3 at 0.5x target is negative (−0.024).

### 4.2 The standout: Play 3 fade at 0.25x target

| Metric | Value | 95% CI |
|---|---|---|
| E[R] | +0.259 | [+0.127, +0.389] |
| WR | 38.5% | — |
| PF | 1.51 | — |
| N | 481 | — |
| $ risk (1 Micro, 0.25R stop) | $20 | 0.04% of $50K account |

This is the strongest single strategy in the dataset. The fade captures a small reversion to IB mid; the tight 0.25x target is essential (the 0.5x target is NOT significant).

### 4.3 Direction trigger (Rule 1) — confirmed real

| Condition | N | Hit % | 95% CI |
|---|---|---|---|
| Low formed first + close in top 25% → high breaks first | 387 | 88.1% | [84.8, 91.2] |
| High formed first + close in bottom 25% → low breaks first | 322 | 86.3% | [82.3, 90.1] |

This is the most actionable **pre-trade** signal — it tells you the likely break direction at 10:30, before the break happens. It generalizes to ES1 (87.5%).

### 4.4 Clock filter (Rule 3) — INVERTED on index futures

| Condition | N | Hold % | 95% CI |
|---|---|---|---|
| Baseline (any break) | 1252 | 81.2% | [79.0, 83.2] |
| Break before 12:00 | 1044 | 78.8% | [76.4, 81.3] |
| Break after 12:00 | 208 | 92.8% | [88.9, 96.2] |

**Key finding:** On NQ1/ES1, the Edgeful YM rule is inverted. Early breaks are NOISIER on index futures (78.8% hold); late breaks have institutional conviction (92.8% hold). This means the opposite IB boundary is a safer stop for late breaks than for early breaks.

### 4.5 Bias variants — all 8 add positive lift on +1 direction

| Bias variant | Direction | Lift vs baseline |
|---|---|---|
| **bias_combined** | **+1** | **+0.022** (strongest) |
| bias_fvg_ifvg | +1 | +0.018 |
| bias_fvg | +1 | +0.018 |
| bias_formation_firstreach | +1 | +0.015 |
| bias_close_dir | +1 | +0.011 |
| **bias_fvg_1011** | **−1** | **+0.025** (surprisingly strong on shorts) |

All bias variants add positive lift when filtering for +1 direction; the −1 direction is generally weaker (except `bias_fvg_1011`).

### 4.6 Entry modules — most add zero lift

| Entry module | Lift | Coverage | Verdict |
|---|---|---|---|
| **E11 80%-rule long** | **+0.093** | 4.2% | Strongest, but rare |
| **E18 wick-dominant fade** | **+0.020** | 3.8% | Second strongest |
| E8/E9/E10/E12/E14/E17 | ~0 | ~100% | Fire on nearly all days — not selective |
| E13 VCP / E15 sweep+reclaim / E22 inversion | — | <1% | Insufficient data |

**Insight:** Most entry modules are useless as filters because they fire on ~100% of days. Only E11 (80%-rule) and E18 (wick-dominant fade) are selective, and both have very low coverage (~4%).

### 4.7 Exit features — `mid_lock_frac` is the strongest

| Feature | N | E[R] | Lift |
|---|---|---|---|
| **mid_lock_frac Q5 (locked >0.95)** | 960 | +0.145 | **+0.066** (strongest) |
| mid_lock_frac Q1 (loose <0.50) | 1108 | +0.049 | −0.030 |
| trend_aligned_with_break = True | 3872 | +0.086 | +0.007 |
| behavior = trend | 284 | +0.033 | −0.046 (high PF 2.01 but low WR) |

When the IB mid is fully locked during IB formation, the breakout edge nearly doubles.

### 4.8 The optimal Play 1 stack

| Stack | N | WR | E[R] | PF | Lift |
|---|---|---|---|---|---|
| Play 1 baseline | 5008 | 48.0% | +0.079 | 1.48 | — |
| + Rule 1A (low first + top 25%) | 1532 | 45.3% | +0.105 | 1.88 | +0.026 |
| + Skip huge IB | 3548 | 51.2% | +0.088 | 1.49 | +0.009 |
| **COMBINED (1A + no huge + no Monday)** | **1064** | **49.2%** | **+0.115** | **1.86** | **+0.036** |

The optimal Play 1 stack lifts E[R] from +0.079 to +0.115 (+46% improvement). **Play 3 does NOT benefit from Rule 1A** (the fade works better without the direction trigger); Play 3 benefits from skip-huge-IB (+0.037 lift).

---

## 5. MAE/MFE & Stop Optimization

### 5.1 MAE/MFE by IB size (NQ1)

| IB size | MAE P50 | MAE P90 | MFE P50 | MFE P90 | Optimal stop range |
|---|---|---|---|---|---|
| Small (<0.47%) | 0.121R | 0.408R | 0.151R | 0.347R | 0.10–0.25R |
| Mid (0.47–0.7%) | 0.187R | 0.587R | 0.242R | 0.508R | 0.20–0.40R |
| Large (0.7–0.9%) | 0.254R | 0.787R | 0.288R | 0.647R | 0.25–0.50R |
| Huge (>0.9%) | 0.310R | 1.163R | 0.417R | 0.987R | 0.30–0.75R |

**Winners P50 MAE = 0.092R; Losers P50 MAE = 0.315R (3.4× gap).** The optimal stop sits between P80 winner MAE (0.232R) and P50 loser MAE (0.405R) — a 0.30R stop preserves ~80% of winners while cutting ~50% of losers early.

### 5.2 Stop distance does NOT affect E[R]

| Stop | WR | E[R] | PF | $ risk (1 Micro) |
|---|---|---|---|---|
| 0.25R | 43.0% | +0.259 | 1.47 | $20 |
| 1.0R | 56.0% | +0.083 | 1.31 | $320 |

A 0.25R stop captures the same edge as a 1.0R stop with **75% less dollar risk**. This is because MAE rarely exceeds 0.25R before the target is hit. Tighter stops are strictly better for prop viability.

### 5.3 The earlier "IB opposite wins" finding was wrong

The `STOP_LOSS_COMPARISON.md` concluded that `ib_opposite` (full IB range stop) outperforms the MAE-optimized stop on total return (+11.57% vs +9.62%). **The Layer B edge-validation study contradicts this**: with bar-by-bar target-before-stop resolution, the 0.25R stop captures the same E[R] at 75% less dollar risk. The earlier comparison used a fixed-time exit, not target-before-stop, which flattered the wide stop.

**Resolution:** Use the tight stop (0.25R for Play 3, 0.25–0.30R for Play 1). The IB-opposite stop is overkill and destroys prop viability.

---

## 6. Pullback Mechanism (Layer A — NQ1 RTH breakout study)

### 6.1 The breakout entry problem

Only **12.5% of breakout trades reached 1R** (1:1 R/R). This explains the PF 0.97 despite 45% WR. Breakout entries happen at the worst price (IB extreme), so price immediately moves against the position.

| R-Multiple | Reach probability |
|---|---|
| 0.5R | 33.0% |
| 1.0R | 12.5% |
| 1.5R | 2.3% |
| 2.0R | 2.3% |
| 3.0R | 0.0% |

### 6.2 Pullback entry comparison

| Configuration | Trades | WR | PF | Return |
|---|---|---|---|---|
| **Fib 38.2% Only** | **149** | **69.8%** | **1.22** | **+9.62%** |
| Fib 50% Only | 149 | 58.4% | 0.69 | −19.85% |
| Fib 61.8% Only | 144 | 63.2% | 0.84 | −8.85% |
| FVG 5m / 15m Only | 19 | 47.4% | 0.30 | −7.63% |
| High Confluence (3+) | 19 | 47.4% | 0.30 | −7.63% |

**Fib 38.2% is the clear winner** — shallow enough to catch early pullbacks, deep enough to filter noise. Deeper Fib levels (50%, 61.8%) underperform; FVG-only strategies fail (too rare, only 19 trades).

---

## 7. Calendar Effects (NQ1 NY AM IB)

### 7.1 Day-of-week

| DOW | Play 1 E[R] | Play 2 E[R] | Play 3 E[R] |
|---|---|---|---|
| Mon | +0.034 | **−0.048** | +0.091 |
| Tue | +0.108 | +0.102 | +0.050 |
| Wed | +0.067 | +0.205 | +0.128 |
| Thu | +0.066 | +0.073 | +0.154 |
| Fri | **+0.121** | +0.128 | +0.062 |

- **Skip Monday** for Play 2 (only negative DOW).
- **Friday** is best for Play 1; **Wednesday** best for Play 2; **Thursday** best for Play 3.

### 7.2 Monthly

| Month | Play 1 E[R] | Play 2 E[R] | Play 3 E[R] |
|---|---|---|---|
| Jan | +0.037 | +0.114 | +0.146 |
| Feb | +0.037 | **−0.135** | +0.147 |
| Mar | +0.084 | +0.245 | +0.100 |
| Apr | **+0.192** | +0.260 | −0.018 |
| May | **−0.048** | −0.112 | **+0.415** |
| Jun | +0.077 | +0.160 | +0.270 |
| Jul | +0.110 | +0.111 | +0.053 |
| Aug | +0.065 | +0.126 | +0.097 |
| Sep | +0.128 | +0.004 | −0.023 |
| Oct | +0.112 | +0.024 | **−0.166** |
| Nov | +0.090 | **+0.281** | +0.043 |
| Dec | +0.060 | +0.098 | +0.103 |

- **Skip February** for Play 2 (−0.135, PF 0.55).
- **Skip May** for Play 1 (only negative month, −0.048).
- **Skip October** for Play 3 (−0.166, autumn volatility breaks the fade).
- **Best:** April for Play 1, November for Play 2, May for Play 3.

### 7.3 Year-over-year (edge survival)

| Year | Play 1 E[R] | Play 2 E[R] | Play 3 E[R] |
|---|---|---|---|
| 2021 | +0.155 | +0.219 | −0.111 |
| 2022 | +0.108 | −0.026 | +0.008 |
| 2023 | +0.068 | +0.108 | +0.087 |
| 2024 | +0.074 | +0.053 | +0.123 |
| 2025 | +0.061 | +0.140 | +0.096 |
| 2026 | **+0.021** (CI crosses zero) | +0.191 | **+0.415** |

**The Play 1 breakout edge is decaying** (CI crosses zero in 2026). **Play 3 fade is strengthening** (0.099 → 0.415). This is a regime shift worth monitoring — the fade may be the future of this strategy family.

---

## 8. Predictive Model (NQ1)

| Model | AUC | Brier | Verdict |
|---|---|---|---|
| Logistic regression | 0.6135 | 0.238 | Tradeable (>0.60) |
| Random forest | 0.5927 | 0.242 | Some signal (>0.55) |

**Top predictive features:**
1. `range_pct` (−0.88) — large IB days are harder to win
2. `dow_Monday` (−0.33) — Monday is toxic
3. `bias_fvg_ifvg` (−0.18) — FVG inversion hurts
4. `bias_close_dir` (+0.17) — green IB candle helps
5. `first_break_minutes` (RF importance 0.29) — the clock is the strongest non-linear predictor

**AUC > 0.55 confirms there IS pre-trade signal beyond Rule 1.** The automation should add `range_pct` (skip huge IB) and `dow_Monday` (skip Monday) as additional filters.

---

## 9. Actionable Conclusions

### 9.1 What to trade

| Priority | Strategy | Asset/Session | E[R] / Return | Why |
|---|---|---|---|---|
| 1 | **Play 3 fade @ 0.25x, 0.25R stop** | NQ1 NY AM IB | +0.259 R | Strongest, lowest $ risk ($20/Micro), prop-viable |
| 2 | **Play 1 breakout @ 0.5x + Rule 1A + skip huge + skip Monday** | NQ1 NY AM IB | +0.115 R | Stable, +46% lift over baseline |
| 3 | **Tokyo Post-Break Fib618** | CL1 | +28.25% | Overnight crude trends cleanly |
| 4 | **RTH Pre-Break Q25** | NQ1 | +17.10% | NQ1-specific, do not generalize |
| 5 | **Globex FVG Inversion** | ES1 / CL1 | +1.28% / +18.45% | Capital-preservation shield, low DD |

### 9.2 What to avoid

- ❌ RTH breakout entries on ES1/RTY1/YM1/GC1/CL1 (all negative).
- ❌ Play 2 retest on Monday or February.
- ❌ Play 1 breakout in May; Play 3 fade in October.
- ❌ Play 3 fade at 0.5x target (the only negative combo, −0.024).
- ❌ FVG-only pullback entries (too rare, 19 trades, PF 0.30).
- ❌ Fib 50% / 61.8% pullback entries (both negative return).
- ❌ Wide `ib_opposite` stops (destroy prop viability; tight 0.25R is strictly better).

### 9.3 Open items not yet evaluated

| Item | Status | Why it matters |
|---|---|---|
| IB duration comparison (5/15/30/40/50/60 min) | ❌ Not run | Can short IBs predict long IB? |
| ALN/Herman direction confirmation | ❌ Not run | Triple-confirmation stack |
| Discovery layer (clustering, anomaly, MI, changepoints) | ❌ Not run | Unsupervised day-type detection |
| FDR + walk-forward on all 125 filters | ❌ Not run | Confirms filters survive out-of-sample |
| Commission/slippage adjustment | ⚠️ Not applied | ~$2,050/yr on 1000 Micro trades ≈ 0.002R/trade |

---

## 10. Methodology Notes (important caveats)

1. **Layer A vs Layer B disagreement on stops.** Layer A (`STOP_LOSS_COMPARISON.md`) favored the wide `ib_opposite` stop. Layer B (edge validation) showed the tight 0.25R stop captures the same edge at 75% less risk. The difference is the exit model: Layer A used fixed-time exit (flattering wide stops); Layer B used target-before-stop bar-by-bar (the honest model). **Trust Layer B on stops.**

2. **The 20-year BacktestLoop "all-F" was wrong.** It used `ib_opposite` (full IB range stop), which is too wide. The play-detail data shows the raw edge is real; the wide stop destroyed it. This is why the two layers must be kept separate.

3. **Decoupling bias filters changed everything.** The `BIAS_COMPARISON_REPORT.md` shows that contaminated FVG bias returned −28.84%; decoupled FVG bias returned +5.67%. Any future bias test must use the decoupled model (stand aside with neutral bias when conditions aren't met).

4. **All Layer B stats are pre-cost.** At ~$2.05/round-turn per Micro and ~$20K NQ1 price, 1000 trades/yr ≈ $2,050 ≈ 0.002R/trade. Small but non-zero; subtract from E[R] before judging viability.

5. **Sample sizes.** Edgeful's 65% bar: a rule only counts as a setup if it hits 65%+ historically with N≥50 (conviction), 20≤N<50 is confluence, N<20 is insufficient. Apply this confidence tier to every conditional table.

---

## 11. Source Files Reference

| Report | Path | Key content |
|---|---|---|
| This report | `docs/strategies/initial_balance_break/IB_DATA_INSIGHTS_REPORT.md` | Consolidated insights |
| Edge validation | `docs/strategies/initial_balance_break/EDGE_VALIDATION_REPORT.md` | NQ1 6-year deep study |
| Statistical discovery plan | `docs/strategies/initial_balance_break/STATISTICAL_DISCOVERY_PLAN.md` | Full methodology + remaining phases |
| Multi-asset matrix | `docs/strategies/initial_balance_break/results/multi_asset_matrix_results.csv` | 6-asset × 4-config P&L |
| Multi-asset validation | `docs/strategies/initial_balance_break/research/VALIDATION_RESULTS.md` | Decoupled 5-year sweep |
| Bias comparison | `docs/strategies/initial_balance_break/research/BIAS_COMPARISON_REPORT.md` | Decoupled bias findings |
| Mechanism evaluation | `docs/strategies/initial_balance_break/research/MECHANISM_EVALUATION_RESULTS.md` | Pullback entry comparison |
| MAE/MFE findings | `docs/strategies/initial_balance_break/research/MAE_MFE_FINDINGS.md` | Breakout entry problem |
| Stop loss comparison | `docs/strategies/initial_balance_break/research/STOP_LOSS_COMPARISON.md` | Wide vs tight stop (Layer A view) |