# Expected Volatility Zones — Quant Research & Data Plan

> Goal: determine **which volatility-implied levels actually matter** for intraday ES (and NQ) day trading, how to trade them, and whether the current zone construction (252 vs 365, multipliers, close-anchor) is optimal.
>
> Audience: quant trader building statistics → probabilities → rule set. Data-first, not opinion-first.
>
> **Rev 2026-08-30 (pass 2)** — addresses the 340-line review against `scripts/libs_py/expected_volatility/` and `data/*.parquet`. Blocking fixes: verification re-executed, upsert key unified, lookahead removed, geometry collapsed to one parameter, common-window re-scoped, and holdout discipline added. See §9.
>
> **§10 (measured baselines) supersedes several design choices in §2-§4** — the construction is ~50% too wide, the mirrored ladder is mis-specified, `scale_mode` should be a measurement not a horse race, and the fixed SD rungs should become a **percentile ladder** calibrated on the post-2022 0DTE regime. Read §10 before building.

---

## 1. Verification: Are Current Calculations Accurate?

### 1.1 Pine math (as ported — `core.py:36-40`)

```
a = VIX / sqrt(252) / 100        # trader-convention 1σ
b = VIX / sqrt(365) / 100        # calendar-year 1σ (CBOE basis, 525600 min)

for m in {1.0, 1.5, 0.5, 0.25}:
    R_top(m)    = S + S*a*m
    R_bottom(m) = S + S*b*m
    R_mid(m)    = (R_top + R_bottom)/2
    S_top(m)    = S - (R_bottom - S)   # mirror
    S_bottom(m) = S - (R_top - S)
    S_mid(m)    = (S_top + S_bottom)/2
```

`S` = settlement anchor (default: prior-day close < 16:00 ET, see `settlements.py:35`, `README.md:114`).

**Manual check — re-executed** `python -c "from scripts.libs_py.expected_volatility.core import compute_zone_ladders; print(compute_zone_ladders(6000,15))"`:

| | old doc | actual `compute_zone_ladders(6000,15)` |
|---|---|---|
| `R_top(1.0)` | 6056.69 | **6056.6947** ✓ |
| `R_bottom(1.0)` | 6048.08 | **6047.1082** |
| `S_top(1.0)` | 5951.92 | **5952.8918** |
| `S_bottom(1.0)` | 5943.31 | **5943.3053** ✓ |

The two middle values were a hand-arithmetic slip (mirror partners, so one error propagated to the other). `R_top` and `S_bottom` matched; `R_bottom`/`S_top` did not — the doc's line "Matches `compute_zone_ladders()` exactly" was false and has been corrected above. Vectorised path `compute_zone_dataframe()` is identical to the scalar path by construction (`core.py:82-146`).

§8's worked example (ES 7000 / VIX 15 → `ev_a ≈66.1`, `ev_b ≈54.9`) **is correct** and is retained.

### 1.2 Quant assessment

| Item | Verdict |
|---|---|
| `a = VIX/sqrt(252)/100` and `b = VIX/sqrt(365)/100` | **Both are rescalings of one forecast — neither is "correct" vs "approximate."** CBOE defines VIX with `T` in calendar-year fractions (365 days / 525600 min), so `b` is faithful to VIX's own definition. The `/sqrt(252)` trader convention reallocates calendar variance onto trading days (assumes weekends/holidays have near-zero variance). Algebraically `b = a * sqrt(252/365) = a * 0.830910`, so choosing 252 vs 365 is a **single-parameter fit** `σ = c·VIX/100` with `c=1/sqrt(252)` or `1/sqrt(365)`. Rank them by regressing `abs(return) ~ c·S·VIX/100` and reading off optimal `c` — Diebold-Mariano between two deterministic rescalings of one forecast is degenerate. The Pine author uses both to create a **zone** `[R_bottom,R_top]` of thickness `S·m·(a-b) = S·m·a·0.16909` ≈ 17% of the 1σ move. Treat as an intentional uncertainty band, not a formal DTE model. |
| `VIX/sqrt(252)` as "1σ RTH move" | **Overstates.** `VIX/sqrt(252)` is the σ of a **24h close-to-close** return (including overnight, by construction of VIX). Using it as an RTH-only (09:30–16:00, 390 min) forecast overstates systematically — measured on ES 2016–2025, RTH open→close variance is **56.8%** of close-to-close variance (RTH σ 0.722% vs c2c σ 0.958%) — i.e. the overstatement is larger than a hand-wave 2/3 would suggest. This collides with §2 Q17: if RTH=390 is the unscaled baseline, a full 24h trading day needs a factor >1. Fixed in §3.1 by making `scale_mode` include `1380` (full 23h trading day 18:00→17:00, see §3.3) and by treating the unscaled daily box as the 24h forecast. |
| Zone vs single level | The zone `[R_bottom,R_top]` is the calendar-vs-trading ambiguity. `R_mid` is the average of the two, not a separate vol model. See §1.3 for the collapse. |
| Arithmetic vs log levels | Pine uses **arithmetic** `S ± S·σ·m` (symmetric in points). A **log / geometric** variant is `S·exp(±σ·m)` (symmetric in log-returns, asymmetric in points). Gaps: at VIX 12–20 / m≤1, the log−arith gap is <1 pt at S=7000 (noise). At **VIX 30 / m=1.5, S=7000**: **arith ±198.4 pts symmetric; log up +201.3 / down −195.6 — a 5.6 pt up/down asymmetry, with the log up-leg +2.8 pts above arith.** The old doc's "up 198 vs down 194 — 4 pts wider" reported the *arithmetic* value as the log up-leg; §1.2's earlier "~3 pts" is the correct order (actual **+2.84 at VIX 30/m=1.5, S=7000**; at VIX 15/m=1.5 it is only +0.71) — the two sections disagreed and are now reconciled here. Log is theoretically cleaner for percentage SD (avoids negative-price pathology, respects compounding); whether it forecasts better is empirical — add as parallel columns and horse-race by VIX quintile (see §3.1). |
| DTE scaling | For a true DTE horizon `T` (trading days), `EV ≈ S·VIX/100·sqrt(T/252)` — or better, interpolated from the term structure (VIX1D=1d, VIX9D=9d, VIX=30d, VIX3M=90d). The indicator **fixes T=1**. For 0DTE intraday decay the static box overstates afternoon vol — should decay as `sqrt(remaining_session / session_length)` if you want an intraday clock. |
| VOLI / VIX1D reuse | `VOLI` and `VIX1D` are also **annualized** (CBOE/Nasdaq convention), so reusing `a,b` keeps magnitudes comparable. Verified locally on the README's own Dec-30 session (S=6955, VIX sources as of that close): **VIX 14.15 → σ=0.891%, VOLI 11.76 → σ=0.741%, VIX1D 8.83 → σ=0.556%** — all via `σ=VIX/sqrt(252)/100`. The old doc's 1.06%/0.88%/0.66% implied divisor √178.5 (neither 252 nor 365); ordering `VIX1D < VOLI < VIX` survives, percentages are now correct. |
| Settlement S | Pine `close_day = close[1]` (prior daily bar close). Equivalent is prior trading day's last print < 16:00 ET (our cutoff). The `toggle` variant (`open` of `session.isfirstbar_regular`) uses today's 09:30 regular open — a 17-hr fresher anchor. Neither is "right"; which forecasts better is an empirical question. |

**Bottom line:** arithmetic is faithfully ported and internally consistent. Whether the four multipliers are *optimal* is not a math question — see §1.3, which changes what you build.

### 1.3 Collapsed geometry — the ladder is one parameter

Verified: `b/a = sqrt(252/365) = 0.8309097177` exactly, `mid/a = (1+b/a)/2 = 0.9154548588` exactly.

Every one of the 12 "levels" (4 multipliers × 3 edges top/mid/bottom, per side) is `S·(1 ± c·a)` for a fixed constant:

```
c ∈ { 0.2077  0.2289  0.2500 | 0.4155  0.4577  0.5000 | 0.8309  0.9155  1.0000 | 1.2464  1.3732  1.5000 }
      \________ 0.25 ladder ________/  \________ 0.5 ladder ________/  \________ 1.0 ladder ________/  \________ 1.5 ladder ________/
```

Consequences:

- **Thickness is perfectly collinear with `S·VIX·m`** (`thickness = S·m·(a-b) = S·m·a·0.16909`). §2 Q3 as posed ("does thickness predict consolidation vs breakout?") cannot separate thickness from vol level — any answer is a statement about VIX. Replace with: does the *relative* position inside the zone matter?
- **"Does the zone add value over its mid?" (§4.2) is c=1.0 vs c=0.9155.** The clean experiment is a **continuous sweep of c** with hit-rate and reaction-rate as curves over c. That single chart subsumes Q1–Q3 and half of §4.2, and tells you where the ladder rungs *should* be instead of grading four inherited ones. Keep the four Pine rungs as markers on that curve, not as the hypothesis.

Build implication: emit `continuous_c` columns or at least the 12 `c` values above; analysis in §4.1/4.2 runs over `c` as a continuous variable.

---

## 2. What We Need to Answer (Prioritised Questions)

Group your research so every column in the parquet earns its keep.

### P0 — Does the construction work at all?
1. **Continuous c sweep** (replaces discrete hit-rate by rung and thickness questions): `P(touch)` and `P(reversal|touch)` as **curves over `c ∈ [0.1, 2.0]`** using the 12 constants above. The four Pine multipliers are markers on that curve. Reports where the ladder *should* be, and whether any discrete rung is special.
2. **Zone vs edge vs mid**: conditional on touch, does price *respect* `c=1.0` vs `c=0.9155` vs `inside zone` (`c ∈ [0.8309,1.0]`) differently? Metrics: reversal rate, median adverse excursion beyond level, time spent inside zone — now read off the same `c` sweep.
3. (Retired) Thickness utility — subsumed by (1); thickness cannot be separated from `S·VIX·m`.

### P1 — Is the anchor right?
4. **Close vs open anchor**: compare `S_close = close[1]` vs `S_open = today 09:30 open` vs `S_vwap = prior RTH VWAP`. Which anchor centres realized RTH range better? (mean absolute error, hit symmetry R vs S). Must be evaluated **per session's as-of time** (see §3.4).
5. **Prior-day vs overnight-inclusive settlement**: does including the 16:00–09:30 Globex drift in S improve or hurt? (Our current cutoff excludes it by design — test the alternative.)
6. **Intra-day re-anchor**: would a rolling anchor (e.g. overnight VWAP at 09:30) beat a static prior-close?

### P2 — Is the vol input right?
7. **Vol source horse race — the ES question** (feasibility-corrected): `VIX` (30d) vs `VIX1D` (1d) vs `VOLI` vs `VIX9D` vs `VIX3M` vs term-interpolated IV vs realized 20d vol vs `VX1` futures-implied. Which `a` best predicts `|return|`? Use MAE/R² and hit-rate calibration (`P(|return| ≤ c·EV)` vs Normal `N(c)`). **Common window across the five cash sources is `2022-05-13 → 2026-08-28` (1,077 trading days)** — see §6.3. `VIX9D/VIX3M/VX1` extend further back; report both the common-window horse race and the longer-window pairwise races. Diebold-Mariano between two rescalings of one forecast is degenerate — use the single-parameter fit above.
7b. **Arithmetic vs log levels**: Pine is arithmetic `S·(1 ± σc)` (symmetric in points). Log variant is `S·exp(±σc)` (symmetric in returns, asymmetric in points: at VIX 30 / m=1.5 / S=7000, **log up +201.3 / down −195.6 vs arith ±198.4**). For VIX 12–20 / c≤1 the gap is <1 pt and irrelevant. Add choice `level_mode ∈ {arith, log}` as parallel columns (`R_top_arith_c` vs `R_top_log_c`) and horse-race by VIX quintile. Expect log to win marginally in high-vol regimes.
8. **252 vs 365 vs sqrt(DTE)**: since 252 vs 365 is a **fixed 0.8309 rescaling**, this is not model selection — just regress `|return| ~ k·S·VIX/100` and read off optimal `k` (see §1.2). Separate is `sqrt(remaining_time)` intraday decay: does `sqrt(remaining_minutes/session_length)` tighten levels usefully?
9. **Term-structure signal**: does `VIX − VIX1D` spread (contango/backwardation) or `VIX/VIX3M` ratio modulate zone reliability? E.g. backwardation → realized > implied → zones pierce more often.

### P3 — What is the *reaction* when price is mid-zone?
10. **Confluence premium** — when an EV `c`-level overlaps a:
    - **Quarter level** (00/25/50/75 per `QUARTERS_THEORY.md`),
    - **Fib of prior range** (38.2/50/61.8 of prior RTH or overnight range projected from S),
    - **Prior HOD/LOD / overnight H/L / VWAP / IB high-low**,
    
    does reaction probability jump? Quantify lift over baseline EV-only. The `c` sweep makes this a lift curve over `c`.
11. **Price-level vs zone-level**: mid-zone reactions — are they actually quarter/fib/VWAP levels *inside* the zone stealing the credit? Decompose via logistic regression with `dist_to_EV(c)` + quarter + fib distance as features.
12. **Reaction definition**: what counts as a reaction? Need operational thresholds: e.g. ≥ 0.25× zone thickness or ≥ 4 pts ES and hold ≥15 min, or failure to close beyond zone by >1× thickness. Pre-register one definition before looking at the data (see §4.5).

### P4 — Session & regime effects
13. **Session clock**: when do touches occur (09:30–10:30 vs 10:30–14:00 vs 14:00–16:00)? Does early touch fade → trade differently than late touch breakout? Now reported in **5-min buckets** (§3.3) with 15-min rollup.
14. **Overnight gap regime**: gap-up through R zones vs gap-down through S zones — does the *untouched opposite side* become a magnet later?
15. **Vol regime / trend vs range** (tie to `QUARTERS_THEORY.md` trending vs contradicting Asia/London combos, or VIX quintile): are EV zones mean-reverting in low vol and breakout in high vol?

### P5 — Multi-session & intraday split (Asia / London / NY AM vs NY PM)

The current indicator is RTH-only (09:30–16:00 ET). The research question generalizes: **does an EV-anchored zone work for any session, and should the anchor/vol scale with session length?**

16. **Session transfer**: do EV zones anchored at the *prior NY close* (16:00 ET) predict the subsequent **Asia** (18:00–03:00 ET) and **London** (03:00–09:30 ET) ranges with the same hit/reaction profile as RTH? Or does each session need its own anchor (Asia anchored at London close, London at Asia close)? Test both and compare MAE / `P(touch)` calibration — with **as-of correctness** (§3.4).
17. **Session-scaled EV**: for a shorter session of duration `T_sess`, expected move ≈ `S·σ·sqrt(T_sess / T_ref)` under GBM. Does scaling `a,b` by `sqrt(session_minutes / 1380)` (full 23h trading day) vs `sqrt(session_minutes / 390)` (RTH 390 min) vs `sqrt(session_minutes / 1440)` (calendar 24h) tighten Asia/London/NY-PM zones usefully vs unscaled? Treat `T_ref` as a tunable; note `unscaled` now means **24h close-to-close** (§1.2), not RTH.
18. **NY AM vs NY PM split**: is the morning (09:30–12:00) statistically different from afternoon (12:00–16:00) for EV utility? E.g. AM = high informed volume, more reversals at outer `c`; PM = drift/decay, more holds. Compute `P(touch)`, `P(reversal|touch)`, `max_pierce` separately.
19. **Mid-day re-anchor — should we recompute at 12:00 ET?** Two candidates to horse-race:
    - **Static** (Pine-faithful): one anchor at 09:30, one vol read, zones fixed all day.
    - **Rolling mid-day**: at 12:00 ET re-read `S_mid = 12:00 price`, `V_mid = VIX at 12:00` (or 5-min VWAP), and recompute *remaining-session* zones scaled by `sqrt(remaining_minutes / session_length)`.
    
    Question: does the re-anchored PM zone raise `P(reversal|touch)` or reduce `max_pierce` vs static? And does it help to also **condition on AM outcome** (e.g. AM already tagged `R_1.0` → PM fade the opposite side)? Measure lift and whether the improvement survives transaction-cost / whipsaw of the reset. **V1 scope note:** if `VIX_1m` remains stale past `2025-12-31` (see §6.3), `V_mid` and `vix_chg_intraday` cannot be computed — drop `NY_PM_midday` and Q27 from v1.

### P6 — VIX ecosystem pack (extends P2; shared across strategies)

VIX as a 30d annualized SPX vol is one projection — the surrounding VIX ecosystem tells you **whether to trust it and how wide to make it**. All features below are computable from already-captured parquets and are intentionally **strategy-agnostic** (reuse for mean-reversion, breakout, sizing, regime filters elsewhere). As-of rules in §3.4 apply — no feature may use data after the session's open.

20. **VIX percentile / rank**: `pctl_63d`, `pctl_252d` of VIX_T vs trailing history (as-of prior close). Filters every hit/reaction stat: does `P(reversal|touch)` at VIX p90 differ from p10?
21. **Term-structure slope** — `VIX - VIX9D`, `VIX - VIX3M`, `VIX1D - VIX`, `VIX/VIX3M` (local `VIX9D_1d`, `VIX3M_1d`, `VIX1D_1d` already captured). Contango (VIX < VIX3M) = complacent, zones hold; backwardation (VIX > VIX3M or VIX1D > VIX) = stress, outer `c` pierce — quantify the moderator effect on `P(close beyond | pierce)`.
22. **Vol-of-vol (VVIX)** — `VVIX_T` and `VVIX/VIX` (`VVIX_1d` holds 2006-03-06→2026-08-28; `VVIX_1m` is only 23 days 2025-12-09→2025-12-31 and is **not** the trading-day join). High VVIX → widen stop beyond zone top or shrink size; low VVIX → tighter fade.
23. **Variance risk premium (VRP)** — `VRP_T = VIX_T - RV20_T` where `RV20 = sqrt(252)*std(log ES returns, 20d)` from `ES1_1m`. VRP >0 (IV expensive) → fades at EV edges work; VRP <0 → vol expansion, favor breakout beyond 1σ.
24. **VIX momentum / change** — `Δ1d = VIX_T - VIX_{T-1}`, `Δintraday = VIX_midday - VIX_open` (intraday only for sessions that contain midday; see §3.4), 5d slope.
25. **Interpolated 1d IV** — variance-linear interpolation of the cash curve to exactly 1 trading day: `IV1d^2 = w*VIX1D^2 + (1-w)*VIX9D^2` (or VIX9D/VIX spline). Horse-races the single-VIX `a` as the *true* 1d forecast vs 30d proxy.
26. **VIX/SPX (or VIX/ES) correlation regime** — `corr(log ES returns, ΔVIX, 20d)` as-of prior close.
27. **Intraday VIX drift** — slope of VIX 09:30→16:00 vs `realized remaining range`. Tests §4.3 decay and is a standalone PM signal (intraday feature, not joined to overnight rows).
28. **VIX futures term premium (when futures feed lands — see §7)** — front-month basis `VX1 - VIX`, curve slope `VX2 - VX1`, roll cost. Data now live: `VX1_1d`/`VX2_1d` stitched from CFE (`fetch_cboe_vx_futures.py`, 2013→2026, 3438 rows). `vx_basis_spot` and `vx_curve_1_2` are the tradable expression of VRP.

---

## 3. Data Plan — Parquet Feature Store

**Three** derived parquets under `data/expected_volatility/` (derived domain per `CLAUDE.md`): `sessions.parquet` + `bars.parquet` + `coverage.parquet` (audit sidecar).

### 3.1 `sessions.parquet` — one row per session window (primary analysis table)

Granularity — **the row key is the 6-tuple** `(trading_day, session_id, ticker, vol_source, scale_mode, anchor_mode)`, and this is the *only* key statement in the doc (§3.5 repeats it verbatim; nothing else defines one). `level_mode` (arith vs log) is **not a key** — it is emitted as **parallel columns** `R_top_arith_c` / `R_top_log_c` per §2 Q7b (see schema). `anchor_mode` rows are emitted only where the anchor is **as-of valid** for that session (see §3.4); look-ahead combinations are not emitted.

Size, computed from this section's own catalog (**7** `session_id` values, **4** `scale_mode` values): `7 × 252 × 6 vol sources × 4 scale modes` ≈ **42k rows/year/ticker** before anchor variants (~**28×** the old doc's "~1.5k", which silently assumed the 4-tuple key). Over 20y × 2 tickers that is **~1.7M rows** at ~100 columns — large but well within parquet; partition by `ticker/year`. Anchor variants add ~1.6× on the ≥09:30 sessions only.

Trading-day convention (your view — CME equity index futures day): a **trading day** runs **18:00 ET (T-1) → 17:00 ET (T)** and is filed under the **RTH date T** (so Mon 18:00 → Tue 17:00 = Tue trading day). All sessions below belong to the same `trading_day`.

Session catalog (window in `America/New_York`, inclusive start, exclusive end; windows **tile** the trading day):

| `session_id` | Window ET (on trading day T) | Duration | Typical anchor `S` (as-of) | Notes |
|---|---|---|---|---|
| `Asia` | 18:00 (T-1) → 03:00 (T) | 540 min | prior RTH close `S_T-1` (<16:00 T-1) | what was known at 18:00 T-1 |
| `London` | 03:00 (T) → 09:30 (T) | 390 min | same `S_T-1` (variant: Asia close as-of 03:00) | what was known at 03:00 T |
| `NY_AM` | 09:30 (T) → 12:00 (T) | 150 min | same `S_T-1` | |
| `NY_PM` | 12:00 (T) → 16:00 (T) | 240 min | same `S_T-1` (static) — midday variant is separate row (see below) | compare AM vs PM |
| `Settlement` | 16:00 (T) → 17:00 (T) | 60 min | same `S_T-1` | futures settlement hour; previously missing — now tiles to 1380 min |
| `RTH` | 09:30 (T) → 16:00 (T) | 390 min | same `S_T-1` | convenience rollup NY_AM+NY_PM |
| `Overnight` | 18:00 (T-1) → 09:30 (T) | 930 min | same `S_T-1` | Asia+London pooled — gap analysis |

`Asia 540 + London 390 + NY_AM 150 + NY_PM 240 + Settlement 60 = 1380 min` — the full trading day. `RTH` and `Overnight` are rollups for reporting, not separate tiling.

Time-bucket convention (see §3.3): primary bucket = **5 min** (`bucket_5m`), reporting rollup = **15 min** (`bucket_15m`). Both are derived from `minutes_since_trading_day_open` (0 at 18:00 T-1) and from `minutes_since_session_open` (0 at session start) — see schema below.

| Column | Source / Logic | Purpose |
|---|---|---|
| `trading_day` | ET date T of the RTH (the CME trading-day label) | key |
| `session_id` | one of the catalog above | key |
| `ticker` | `ES1!` / `NQ1!` etc. — **`vol_source` enum is per-family**: ES→ VIX, VOLI, VIX1D, VIX9D, VIX3M, VX1; NQ→ VXN; RTY→ RVX; CL→ OVX; GC→ GVZ (see `settlements.py:25-32`; `data/` has VXN 2001, RVX 2006, OVX 2007, GVZ 2008) | key |
| `vol_source` | For ES: `VIX` / `VOLI` / `VIX1D` / `VIX9D` / `VIX3M` / `VX1` / `term_interp` / `RV20`; for other tickers: their family vol (e.g. NQ→`VXN`) | key |
| `scale_mode` | `unscaled` (=24h close-to-close) / `sqrt_sess_over_1380` / `sqrt_sess_over_390` / `sqrt_sess_over_1440` | session-scaling horse race (§2 Q17) — **1380 is the trading-day length (§3.3)** |
| `settlement_close` | `close_day` (prior close <16:00 ET, `S_T-1`) | anchor (as-of) |
| `settlement_open` | first regular open ≥09:30 ET on T (only valid for sessions starting ≥09:30) | anchor variant — not emitted for Asia/London |
| `settlement_midday` | 12:00 ET price/VWAP on T (only for `NY_PM` midday re-anchor variant) | anchor for re-anchored PM — not emitted for Asia/London/Overnight |
| `open_session` | open of `session_id` window | gap & anchor comparison |
| `vix_close` | vol index **as-of prior close** (`vix_T-1`) — see §3.4 | vol input (as-of) |
| `ev_a`, `ev_b`, `ev_scaled` | `S·a`, `S·b`, `S·a·sqrt(T_sess/T_ref)` per `scale_mode` | base moves |
| For each `c` in the 12 constants (§1.3): `R_c`, `S_c` (arith) and `R_log_c`, `S_log_c` | `core.compute_zone_dataframe` with `level_mode` as **columns**, not rows; e.g. `R_top_arith_1.0`, `R_top_log_1.0`, `R_0.9155` etc. | zone geometry — continuous `c` sweep |
| `prior_rth_high/low/range`, `overnight_high/low/range` | from 1m OHLC as-of session open | fib base + gap regime |
| `fib_R_382/500/618`, `fib_S_382/500/618` | `S ± fib·prior_rth_range` | fib confluence; compare to EV |
| `q_up_1`, `q_dn_1`, `q_grid` | nearest quarter levels to S (per `QUARTERS_THEORY.md`) | quarter confluence |
| `session_high/low/close/range`, `session_vwap` | realised for `session_id` window | outcome |
| For each level (EV `c`, fibs, quarters): `touched`, `first_touch_min_session`, `first_touch_min_trading_day`, `first_touch_bucket_5m_session`, `first_touch_bucket_5m_trading_day`, `first_touch_bucket_15m_session`, `first_touch_bucket_15m_trading_day`, `max_pierce_pts`, `pierce_bars`, `close_beyond`, `reversal_pts_15m/60m`, `reversal_hit` | computed from 1m bars of `session_id` window | hit/reaction stats — **bucket ids are the primary time dimension** (§3.3) |
| `realized_move_abs`, `realized_vol_session` | `abs(close-open)/S`, `std(log returns)` over session | vol forecast calibration — denominator is session length |
| `regime_vix_quintile`, `regime_trend_range` | VIX percentile as-of prior close / Asia-London combo as-of session open | stratification |
| **VIX ecosystem pack** (§2 Q20–28, shared — strategy-agnostic, as-of) | | |
| `vix_pctl_63d`, `vix_pctl_252d` | percentile rank of `vix_T-1` vs trailing 63d / 252d | regime filter |
| `vix_term_slope_1d_30d` | `VIX_T-1 - VIX1D_T-1` | term slope — contango vs backwardation (as-of) |
| `vix_term_slope_9d_30d` | `VIX_T-1 - VIX9D_T-1` | 9d→30d slope (as-of) |
| `vix_term_slope_30d_90d` | `VIX_T-1 - VIX3M_T-1` | 30d→90d slope (as-of) |
| `vix_ratio_1d_30d` | `VIX1D_T-1 / VIX_T-1` | normalized term premium (as-of) |
| `vvix`, `vvix_vix_ratio` | `VVIX_T-1`, `VVIX_T-1 / VIX_T-1` from `VVIX_1d` | vol-of-vol (as-of) — `VVIX_1m` is intraday only, not the daily join |
| `vrp_20d` | `VIX_T-1 - RV20_T-1` (RV20 = `sqrt(252)*std(log ES ret, 20d)` as-of) | variance risk premium |
| `vix_chg_1d` | `VIX_T-1 - VIX_T-2` | momentum (as-of) |
| `vix_chg_intraday` | `VIX_midday - VIX_open` — **only for sessions containing 09:30→12:00** (NY_AM, RTH, NY_PM midday variant); `NULL` for Asia/London/Overnight | intraday drift (as-of within session) |
| `iv_1d_interp` | variance-linear interpolation to exactly 1 trading day | true 1d forecast (as-of) |
| `vix_spx_corr_20d` | `corr(log ES ret, ΔVIX, 20d)` as-of prior close | correlation regime |
| `rv20` | trailing 20d realized vol (annualized, as-of) | standalone RV input |
| `vx1_close`, `vx2_close`, `vx_basis_spot`, `vx_curve_1_2` | `VX1_T-1`, `VX2_T-1`, `VX1-VIX`, `VX2-VX1` from `VX1_1d`/`VX2_1d` (CFE, `fetch_cboe_vx_futures.py`) | futures term premium (as-of) |

*All VIX pack columns are `as-of prior close` (`T-1`) unless marked intraday — so a London touch on trading day T can be conditioned on `vix_term_slope_1d_30d` from `T-1`'s close without lookahead. The pack is computed once per trading day and joined to every `session_id` row for that day.*

### 3.2 `bars.parquet` — per-minute enriched tape (optional second table, for deeper work)

Granularity: 1 row per 1-min bar, filed under its **`trading_day`** (18:00 T-1 → 17:00 T). Partitioned by `ticker/trading_day` (or `ticker/year/month`) if needed. Each bar carries **both clocks**: `minutes_since_trading_day_open` (0 at 18:00 T-1) and `minutes_since_session_open` (0 at session start) plus their bucket ids (see §3.3). Overlapping rollup sessions (`RTH`, `Overnight`) are views over the tiled sessions, not duplicated bars.

| Column | Meaning |
|---|---|
| `ts` (UTC), `trading_day` (ET date T), `session_id` (derived from trading-day clock) | time — see §3.3 |
| `minutes_since_trading_day_open`, `bucket_5m_trading_day`, `bucket_15m_trading_day` | trading-day clock (0 at 18:00 T-1) |
| `minutes_since_session_open`, `bucket_5m_session`, `bucket_15m_session` | session clock (0 at session start) |
| `open/high/low/close/volume` | OHLCV |
| `dist_to_R_c` for each `c` (arith and log) | signed distance in points and in units of contemporary `ev_scaled` |
| `in_zone_c` (bool per `c`) | inside any EV band aligned to that bar's trading day |
| `dist_to_nearest_quarter`, `quarter_label` | per `QUARTERS_THEORY.md` |
| `dist_to_fib`, `dist_to_vwap`, `dist_to_overnight_HL` | competing levels |
| `confluence_score` | count of levels within ±X pts — the "stack" |

Use `bars.parquet` for: time-to-touch survival curves per 5-min bucket, intraday decay, and order-flow around levels. `sessions.parquet` alone answers most P0–P2 questions; `bars.parquet` makes P4–P5 granular.

### 3.3 Trading-day & bucket conventions (normative)

**Trading day.** A CME equity-index trading day **T** is `18:00 ET on calendar day T-1` (inclusive) → `17:00 ET on calendar day T` (exclusive, last bar 16:59 ET). Mon 18:00 → Tue 17:00 = Tue trading day (matches your desk convention). Holidays: if the 18:00 open is missing, the day still exists with fewer bars. The day length is **1380 min** (23h) — the gap 17:00→18:00 (60 min) is **outside** the trading day, not skipped within it. The old doc's "bucket ids skip it" was spurious.

**Bucket ids.** For any timestamp `t` in `America/New_York`:
- `minutes_since_trading_day_open = floor((t - 18:00_{T-1}) / 1 min)`  (0 … 1379; 1380-min trading day)
- `bucket_5m_trading_day  = floor(minutes_since_trading_day_open / 5)`  (0 … 275, 5-min primary). Label: `"18:00-18:05"`, …, `"16:55-17:00"`.
- `bucket_15m_trading_day = floor(minutes_since_trading_day_open / 15)` (0 … 91, reporting rollup — exactly 3× the 5-min buckets).
- `minutes_since_session_open` / `bucket_5m_session` / `bucket_15m_session` are analogous with origin at the session window start (e.g. RTH 09:30 → 0).

Both clocks are stored so analysis can pivot either way: "5-min bucket across the trading day" (heatmap) and "5-min bucket within session" (session-relative).

**Reporting default:** 5-min buckets are the **stored truth**; initial reporting rolls them to 15-min (mean / sum) for readability. No information is lost.

**DST — no trading day is short or long.** US DST transitions occur at 02:00 ET on a **Sunday**, which falls inside the weekend closure (Fri 17:00 ET → Sun 18:00 ET). **Verified on `ES1_1m`: across all 42 US transitions 2006→2026, zero ES bars fall within ±3h of the transition instant.** Every trading day is therefore 1380 min and `minutes_since_trading_day_open` always runs 0…1379 — the earlier "22h/24h day, ~40 affected days" claim was wrong and is withdrawn.

What DST *does* change is the **UTC offset** of an ET-defined window (RTH opens 13:30 UTC in EST, 12:30 UTC in EDT). Since `bars.parquet` stores `ts` in UTC (§3.2) while every session boundary is defined in ET, bucketing on **UTC minutes would break alignment across the transition** — so the primary clock is **ET wall-clock** `minutes_since_trading_day_open`, computed by converting to `America/New_York` first. Do **not** derive buckets from UTC minutes; that is the inversion the previous revision recommended.

### 3.4 Leakage and as-of rules (normative — blocks §2 Q3 from being publishable without this)

**Principle:** no feature on a row may use data timestamped at or after the **decision time** for that row.

| Row type | Decision time | Allowed as-of | Forbidden |
|---|---|---|---|
| `Asia` (18:00 T-1→03:00 T) | 18:00 T-1 | `S_T-1` (prior RTH close <16:00 T-1), `vix_T-1`, `vrp_T-1`, `term slopes_T-1`, `pctl_T-1` | `vix_close_T`, `vix_open_T` (09:30), `vix_midday_T`, any `T`-day OHLC, `settlement_open_T`, `settlement_midday_T` |
| `London` (03:00→09:30 T) | 03:00 T | same as Asia (still `T-1` close) | same as Asia |
| `Overnight` (18:00 T-1→09:30 T) | **18:00 T-1** (its window *ends* at 09:30 T — that is the outcome, not a feature) | same as Asia (`T-1` pack only) | `open_09:30_T`, `vix_open_T`, `vix_close_T`, `vix_midday_T` |
| `NY_AM` (09:30→12:00), `RTH` (09:30→16:00) | 09:30 T | `S_T-1`, `vix_T-1`; `open_09:30_T` allowed as contemporaneous (gap) | `vix_close_T`, `vix_midday_T` for the static row |
| `NY_PM` static (12:00→16:00, anchor `S_T-1`) | 12:00 T (for the PM outcome, but features remain `T-1`) | same `S_T-1`/`vix_T-1` pack | `vix_close_T` |
| `NY_PM` midday re-anchored (12:00→16:00, anchor `S_midday_T`) | 12:00 T | `S_midday_T` (12:00 price), `vix_midday_T` (12:00 VIX) are allowed **only for this row variant** | not allowed for the static `NY_PM` row |

Consequences for the schema:

- The old doc's "VIX pack computed once per `trading_day` and joined to every `session_id` row for that day, so a London touch can be conditioned on the same trading day's open" **used future data** (`vix_close_T` for a session that ended at 09:30). Fixed: the pack is **as-of `T-1` close** for all sessions; the only `T`-day columns are `open_09:30_T` (gap) and, for the midday variant, `S_midday_T`/`vix_midday_T`.
- `vix_chg_intraday = VIX_midday - VIX_open` is **NULL** for Asia/London/Overnight/Settlement rows by construction — they do not contain 09:30→12:00. `Overnight` is the easy one to get wrong: it is a rollup that *terminates* at 09:30 T, so `open_09:30_T` is its outcome and must never be a feature on that row.
- `anchor_mode=open` (= today's 09:30 open) is **not emitted** for `Asia`/`London` rows — it would anchor a session on a price 6–15 hours after it ended.
- `anchor_mode=midday` and `NY_PM_midday` are **one variant**, not two encodings of the same fact. `session_id` stays `NY_PM` for both; the midday re-anchor is `anchor_mode=midday` + `scale_mode=sqrt_240_over_...` on that row. There is no separate `session_id=NY_PM_midday` key value — it is a row qualifier.

### 3.5 Build Logic & Dependencies

```
raw:  data/ES1_1m.parquet, data/NQ1_1m.parquet,
      data/VIX_1d.parquet, data/VOLI_1d.parquet, data/VIX1D_1d.parquet,
      data/VIX9D_1d.parquet, data/VIX3M_1d.parquet, data/VVIX_1d.parquet,
      data/VX1_1d.parquet, data/VX2_1d.parquet (CFE, fetch_cboe_vx_futures.py — Settle only, see §7 gate)
  │
  ├─► settlements.py :: build_daily_settlements() — 16:00 ET cutoff already handled,
  │                     daily-only vol via _settlements_from_daily()
  ├─► core.py        :: compute_zone_dataframe() — all m rungs + log variant + continuous c
  ├─► NEW: quarters.py :: quarter_grid(S)  (from QUARTERS_THEORY)
  ├─► NEW: fibs.py      :: fib_projection(S, prior_range)
  ├─► NEW: vix_features.py :: pctl, term slopes, VRP, VVIX ratio, iv_1d_interp (as-of T-1)
  └─► NEW: session_stats.py :: touches, pierces, reversals (extend backtest.zone_edges/box_sessions)
         │
         └─► data/expected_volatility/sessions.parquet (+ bars.parquet + coverage.parquet)
```

*Script location per repo standard* (`scripts/<domain>/`): `scripts/expected_volatility/build_features.py` (produces all three parquets, idempotent, append-friendly) and `scripts/expected_volatility/analyze.py` (reads parquets → stats).

*Implementation notes:*
- **Upsert key is the 6-tuple `(trading_day, session_id, ticker, vol_source, scale_mode, anchor_mode)`** — identical to §3.1's granularity statement, and the only key in this document. `level_mode` is **columns, not a key**. The pre-revision doc stated two different keys in the same section; the shorter 4-tuple `(trading_day, session_id, ticker, vol_source)` would silently collapse the scale-mode and anchor-mode rows that §4.2's horse races consume, and is removed. Upsert on rerun; backfill with `--from / --to`.
- Fuse `data/{ticker}_1m.parquet` (2006–2024) + `data/live/live_storage_-{ticker}.parquet` (2025→now) via `scripts/utils/fused_data_loader.py:load_fused_data()` for full history; for validation slices use live storage directly.
- Daily vol dailies are 16:00 ET close stamps → `build_daily_settlements` daily path handles normalization; intraday VIX uses 16:00 cutoff path.
- `VVIX` source is **`VVIX_1d.parquet` (2006-03-06→2026-08-28)** for the trading-day join; `VVIX_1m.parquet` is only 23 days (2025-12-09→2025-12-31) and is not used for the daily pack.
- `VIX_1m.parquet` is **stale past 2025-12-31** (last bar 2025-12-31, 8 months stale as of 2026-08-30) — any feature requiring intraday VIX (`vix_midday`, `vix_chg_intraday`, `NY_PM` midday re-anchor, §2 Q27) is **NULL for trading days after 2025-12-31** until the intraday feed is backfilled (see §6.3).
- Missing-data policy: require `settlement_close` and `vix_close_T-1` non-null to emit a session row; for `vol_source=VX1` additionally require `settle > 0` (95 rows fail — see §7); log gaps and keep `coverage.parquet` sidecar for audit.

---

## 4. Analysis Plan — From Parquet to Trading Rules

### 4.1 Descriptive statistics (continuous `c` sweep, per session)

For each **continuous `c`** (the 12 constants in §1.3, plus interpolated `c` values for the sweep curves), **per `session_id`** (Asia/London/NY_AM/NY_PM/Settlement/RTH/Overnight, plus pooled), reported in **both 5-min and 15-min buckets** (§3.3):
- **Touch rate** `P(touch at c)`, **time-to-touch** distribution (Kaplan-Meier), **first-touch clock** histogram — computed on `bucket_5m_trading_day` (primary) and rolled to `bucket_15m_trading_day` for reporting (mean/sum). Both `bucket_5m_session` (session-relative) and `bucket_5m_trading_day` (trading-day heatmap) views.
- **Reaction rate** `P(reversal ≥ k·ATR | touch at c, bucket)` for k ∈ {0.25,0.5,1.0} and horizons 15/60/240 min, **stratified by touch bucket**; **disposition** (reversal vs continuation vs hold) per bucket.
- **Pierce profile**: median `max_pierce`, `P(close beyond level | pierce)` — per bucket and per `c`.
- Calibration: scatter `predicted EV(c) = c·S·a·scale` vs `realized |session return|`; MAE, bias, R² by vol source and by session. This single sweep **replaces** the old discrete Q1–Q3 ladder grading.

Initial reporting rolls the 5-min truth to 15-min for readability; no information is lost — 5-min remains the join key.

### 4.2 Comparative / causal (all as-of, per §3.4)

- **Continuous `c` optimum**: read off `c*` maximizing `P(reversal|touch)` or Sharpe of the fade — the fitted rung. Compare Pine's four `m` markers to `c*`.
- **Anchor horse race**: paired test (close vs open vs vwap) on `|S - session_mid|` and `touch symmetry`; **single-parameter fit** `|return| ~ k·S·VIX/100` and report optimal `k` (see §1.2 — 252 vs 365 is not model selection).
- **Denominator / horizon**: the 252-vs-365 question is answered by the same `k` fit; intraday decay is separate: `sqrt(remaining_minutes/session_length)` tightening.
- **Vol source for ES (common-window + pairwise)**: `VIX` vs `VIX1D`/`VOLI`/`VIX9D`/`VIX3M`/`VX1`/`term_interp`/`RV20` — report **common-window (`2022-05-13→2026-08-28`, 1,077 trading days)** horse race *and* longer-window pairwise races where history exists (VIX 1990, VOLI 2013, VIX9D 2011, VIX3M 2009).
- **Arith vs log**: compare `R_log_c` vs `R_arith_c` on the same `c` sweep; stratify by VIX quintile (expect log edge only in high-vol tails; at VIX 30/c=1.5, log up +201.3 vs arith +198.4 and log down −195.6 vs arith −198.4).
- **Confluence lift**: `P(reaction | EV at c alone)` vs `P(reaction | EV at c ∧ quarter within d)` vs `P(reaction | EV at c ∧ fib within d)`. Lift = ratio; test with Fisher exact **with family-wise correction** (§4.5). Then joint model:
  ```
  logit(P(reaction)) ~ dist_to_EV(c) + dist_to_quarter + dist_to_fib + dist_to_vwap + vol_regime + gap_size
  ```
  Coefficients are attribution of reaction to each level type when mid-zone. Random forest / SHAP for non-linear interaction.
- **Term-spread moderator**: does `VIX − VIX1D` (or `VIX/VIX3M`, `VX1-VIX`) predict zone pierce rate? Test as interaction in the logit — **as-of `T-1`** slopes only.

### 4.3 Session & decay (covers §2 Q16–19)

- **Asia / London transfer**: fit `predicted EV(c)` with `S_T-1` vs alternative anchor as-of 18:00/03:00 (still `T-1` close) per session; report which wins on MAE/R² and `P(touch)` calibration. Expect Asia to be noisier — weekly `c` sweep will show a flatter touch curve without `scale_mode` correction.
- **Session scaling**: compare `unscaled` (24h close-to-close) vs `sqrt(session_minutes/1380)` (trading-day) vs `sqrt(session_minutes/390)` (RTH) vs `sqrt(session_minutes/1440)` (calendar) per session. Does scaling bring `P(|return| ≤ 1·EV)` back toward ~68% for short sessions? `scale_mode` now includes **1380** (the doc's own trading-day length, previously missing).
- **NY AM vs NY PM**: same `c` metrics split at 12:00 ET. Test `P(reversal|touch)` differs AM vs PM (χ² with correction); if AM is more mean-reverting and PM more trending, the rule sheet splits them.
- **Mid-day re-anchor (scope-gated)**: paired comparison `NY_PM` static (`S_T-1`) vs `NY_PM` midday re-anchored (`S_midday_T` at 12:00, `V_midday_T`, `sqrt(240/session_length)` scaling). Metrics: `P(reversal|touch)`, `max_pierce`, `P(close beyond)`. **Gated on `VIX_1m` intraday availability** — if the feed remains stale past 2025-12-31, this track is `NULL` and is dropped from v1 (see §6.3). Cost of the reset is whipsaw when AM already consumed the move — test conditional on AM outcome (`AM tagged at c=1.0` → fade-the-opposite-side in PM?).
- **Intraday decay (general)**: fit `realized_remaining_range ~ a·sqrt(remaining_minutes / session_length)` vs static `a` within any session.

### 4.4 From statistics to day-trading rules

Translate findings into a **condition → setup → invalidation** sheet **per session and per `c` band** (RTH/Asia/London/NY_AM/NY_PM), e.g.:

| Session | Condition | Setup | Invalidation | Expected R:R (from holdout) |
|---|---|---|---|---|
| `RTH` | Price enters `c≈0.5` band ∧ quarter level inside band ∧ first touch bucket `09:30-09:45` | Fade to `S` (mean reversion), target `R_mid` or `S`, stop beyond `R_c + buffer` | Close beyond `R_c` by >0.3× thickness | e.g. 62% reversal on test fold, median 8 pts adverse, 14 pts favorable |
| `RTH` | Close beyond `c=1.0` with volume expansion | Breakout continuation to `c=1.5` | Reclaim of `c=1.0` within 15 min | e.g. 54% continuation on test |
| `NY_PM` (midday re-anchored, when available) | AM already tagged `c=1.0` and PM re-anchored band re-tagged | Fade opposite side / mean reversion to `S_midday` | ... | ... |
| `Asia` / `London` | Gap through `c=1.0` pre-open, untagged `c=0.5` (session-scaled) | Magnet: drift to `c=0.5` by session end | ... | ... |

Every row must cite a parquet-derived probability **for its session and bucket on the holdout fold** (§4.5) — no cross-session intuition and no in-sample rule.

### 4.5 Holdout and multiple-testing discipline (normative)

- **Time-series holdout:** pre-register the P0 metrics (touch curve over `c`, reaction curve over `c`, pierce curve over `c`) and **hold out the last 20% of trading days chronologically** — computed from `VIX1D_1d`: the common window is **1,077** trading days (2022-05-13 → 2026-08-28), so the test fold is the last **215** days, **starting 2025-10-21**. (The previous revision's "~2024-06" was ~16 months too early — it split the *calendar* span, not the trading-day count.) All hyper-parameter choices (optimal `c`, regime thresholds) are fit on the train fold; §4.4's rule sheet is evaluated **once** on the test fold. No peeking.
- **Family-wise correction:** §4.1 stratifies `P(reversal|touch)` by 5-min bucket × `c` × vol source × regime. Note the bucket and session axes are **not independent** — the five tiled sessions *partition* the same 276 trading-day buckets, so `276 × 7` double-counts; the honest bucket count is **276** (plus the two rollups, which re-read buckets already counted). Within each **family** (e.g. "touch-rate by bucket"), correct `p`-values with **Benjamini-Hochberg FDR** (or Bonferroni for small families) and report `q`-values alongside raw `p`. Fisher exacts in §4.2 are subject to the same correction.
- **Cell-count floor:** do not report a probability for a stratum with fewer than **30 touches** (or fewer than 50 sessions for calibration) — mark as `insufficient N` in the tables. With a 1,077-day common window and 276 buckets, most bucket×level cells will be sparse; the 15-min rollup is the reporting floor for a reason.
- **Out-of-sample only where noted:** rolling 2-year windows in §6.3 are descriptive, not selective — selection is on the train fold.

---

## 5. Delivery Milestones

| Phase | Output | Effort |
|---|---|---|
| **A0. Measured baselines (DONE)** | `scripts/expected_volatility/measure_baselines.py` -> `data/expected_volatility/baselines_*.md` for ES/NQ/YM/RTY/GC. Answers P0 Q1-Q3 and §2 Q8/Q17 directly from disk. **See §10 — its findings change A-E below.** | done |
| **A1. Recalibrate & fit the ladder** | Percentile ladder (§10.5) fit on the 0DTE train fold, asymmetric up/dn, plus the `beta` exponent (§10.3) and the variance-share table (§10.7). Validate touch rates on the §4.5 holdout. | 1 session |
| **A. Verify & instrument** | This doc + `core.py`/`settlements.py` already validated (ES 6000→ `R` 6056.6947/6047.1082 etc., Dec-30 ES 6955.0 / VIX 14.15 → σ0.891% re-checked). Add quarter/fib helpers (reuse `QUARTERS_THEORY.md` grid) + `c` sweep columns. | 1 session |
| **B. Build `sessions.parquet`** | `scripts/expected_volatility/build_features.py` + `data/expected_volatility/sessions.parquet` for ES **common window `2022-05-13→present`** first (all vol sources comparable), then extend to full history with pairwise availability. Smoke-check vs existing `scan_expected_volatility`/`touch_stats`. | 1–2 sessions |
| **C. Build `bars.parquet` (optional)** | Same script, flag `--bars`. Needed for decay & microstructure questions. DST-aware (§3.3). | 0.5 session |
| **D. Analysis pack** | `scripts/expected_volatility/analyze.py` → markdown report + figures on the **holdout fold**: `c` sweep, anchor horse race (single `k` fit), vol source common-window + pairwise, arith vs log. | 1–2 sessions |
| **E. Confluence & intraday** | Logistic/SHAP model with FDR correction + decay fit → answers P3–P5; produces the per-session `c`-band rule sheet (§4.4) evaluated on holdout. | 1–2 sessions |
| **F. Live integration** | Wire selected `c` levels into the trader narrative / signal engine (e.g. `scripts/trader/`) only after D–E show holdout edge. | separate track |
| **G. Backfill gap** | Backfill `VIX_1m` past `2025-12-31` (8 months stale) via Schwab `pricehistory` or CBOE intraday, or formally drop `vix_midday` / `NY_PM` midday re-anchor / §2 Q27 from v1 scope. | 0.5 session decision |

Start with **ES × all vol sources** on `sessions.parquet` common window; expand to NQ/CL/RTY (family vol indices already in `data/` — VXN 2001, RVX 2006, OVX 2007, GVZ, VXSLV, VXD, VX1 2013) once the ES pattern is proven on holdout.

---

## 6. Open Decisions to Lock Before Building

1. **Reaction threshold**: fix now (e.g. reversal ≥ 0.5× thickness or ≥ 4 pts ES and hold ≥15 min) so analysis is comparable across `c`. Make it a parameter in the parquet builder, not hard-coded. Pre-register before the holdout.
2. **Quarter grid definition**: confirm tick size / quarter step per instrument (ES 1.00? NQ 1.00? Use the grid from `QUARTERS_THEORY.md` consistently).
3. **History depth for calibration**: use holdout split in §4.5 for selection; report descriptive rolling 2-year windows but **select on train only**. Common window for the 5-way vol horse race is `2022-05-13→2026-08-28` (1,077 trading days ≈ two 2-year windows). Longer histories are pairwise only, not 5-way.
4. **DTE ambition**: for v1 keep T=1 fixed (as Pine does); treat `sqrt(DTE)` scaling as a v2 experiment gated on P2 results. The 252-vs-365 question is answered by the single `k` fit, not by model selection.
5. **Intraday VIX freshness**: decide now whether `VIX_1m` will be backfilled past `2025-12-31` before v1. If not, `NY_PM_midday`, `vix_chg_intraday`, and §2 Q27 are out of v1 scope.

---

## 7. VIX Futures — CFE Scrape (now live)

VIX futures (CBOE/CFE: VX, front month VX1 / VX2 …) are the *tradable* term structure. Cash VIX term slopes (`VIX - VIX9D`) in §2 Q21/§3.1 use indicative CBOE indices; the futures curve (`VX1 - VIX` basis, `VX2 - VX1` slope) is the cleaner signal and the direct expression of variance risk premium.

Fetched via **CFE Price and Volume Detail per-expiry CSVs** (`cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_YYYY-MM-DD.csv`, ~618 expiries 2013→present, discovered via Playwright Year dropdown). Each CSV is one expiry (Wednesday) with `Trade Date,Open,High,Low,Close,Settle,Volume,OI`. Script `scripts/market_data/fetch_cboe_vx_futures.py` probes all Wednesdays 2013→2027 (HEAD → GET) and stitches **continuous `VX1_1d` / `VX2_1d`** at `16:00 ET → 20:00 UTC` (same anchor as `fetch_cboe_indices.py:47`).

Live on disk: `VX1_1d` 3438 rows `2013-01-02 → 2026-08-28` (last `Settle` 16.9353 for the `2026-09-02` expiry), `VX2_1d` same span. Join as `vx1_close = VX1 Settle`, `vx2_close`, `vx_basis_spot = VX1 - VIX`, `vx_curve_1_2 = VX2 - VX1` (all as-of `T-1` per §3.4).

> ⚠️ **The stitched VX OHLC is dirty — gate it before joining.** Measured on the files as built:
>
> | check | `VX1_1d` | `VX2_1d` |
> |---|---|---|
> | rows | 3438 | 3438 |
> | `low > high` | 304 | 350 |
> | `settle` outside `[low, high]` | 1078 (31%) | 1221 (36%) |
> | `open == 0` | 703 | 927 |
> | `high == 0` or `low == 0` | 189 | 226 |
> | `settle <= 0` | 95 | 95 |
>
> CFE per-expiry CSVs carry placeholder OHLC on thin/untraded days, so **only `Settle` is trustworthy** — use it and ignore `open/high/low/volume/open_interest` unless a row passes validation. Add a mandatory gate in `build_features.py`: drop rows with `settle <= 0`, and record the drop count in `coverage.parquet`. Any `vx_*` column derived from OHLC (rather than `Settle`) is out of scope until the scraper is fixed.

---

## 8. Quick Reference — Current Zone Geometry (for intuition)

For ES at 7000, VIX 15, `m=1.0`: `ev_a = 7000·15/√252/100 ≈ 66.1`, `ev_b = 7000·15/√365/100 ≈ 54.9`, zone `[54.9, 66.1]` above S (thickness 11.2). `m=0.25` zone is `[13.7, 16.5]` (thickness 2.8) — tight enough to be pierced by noise; its edge is less likely to be a clean reaction level unless reinforced by a quarter/fib. Under the §1.3 collapse this is `c=1.0` and `c=0.25` on the continuous `c` axis (with `c=0.8309` and `c=0.9155` for the `b` and `mid` edges).

---

## 9. Review Response (2026-08-30)

This revision addresses the 340-line verification against `scripts/libs_py/expected_volatility/` and `data/*.parquet`:

- **Blocking 1 (§1.1):** re-executed `compute_zone_ladders(6000,15)` — corrected `R_bottom 6047.1082` (was 6048.08) and `S_top 5952.8918` (was 5951.92); removed false "Matches exactly" claim.
- **Blocking 2 (§3.4 upsert key):** unified to the single key `(trading_day, session_id, ticker, vol_source, scale_mode, anchor_mode)` with `level_mode` as columns — removed contradictory 4-tuple bullet.
- **Blocking 3 (lookahead):** added §3.4 Leakage and as-of table; VIX pack is now as-of `T-1` (not `T`), `vix_chg_intraday` NULL for overnight rows, `anchor_mode=open/midday` not emitted for Asia/London.
- **Blocking 4 (feasibility):** scoped vol horse race to common window `2022-05-13→2026-08-28` (1,077 days, ≈ two 2-year windows) and flagged `VIX_1m` stale `2021-10-25→2025-12-31` gating `vix_midday`/`NY_PM_midday`/Q27.
- **Blocking 5 (VVIX file):** `VVIX_1d` is the daily join (2006-03-06→2026-08-28); `VVIX_1m` is 23 days intraday only.
- **Design 6 (one-parameter collapse):** §1.3 proves `b/a=0.830909…`, introduces 12 `c` constants and replaces discrete Q1–Q3 grading with a **continuous `c` sweep** (P0 now).
- **Design 7 (252 vs 365):** both defensible (CBOE calendar 365 vs trader 252); `b = a·0.8309` — single fit `k`, not DM.
- **Design 8 (close-to-close vs RTH):** noted 24h vs RTH overstatement; added `scale_mode` `sqrt_sess_over_1380` and `1380`-min trading day.
- **Design 9 (VIX percentages):** corrected `14.15→0.891%`, `11.76→0.741%`, `8.83→0.556%` (was 1.06%/0.88%/0.66% via √178.5).
- **Design 10 (log vs arith):** corrected VIX 30/m=1.5 to **arith ±198.4, log up +201.3 / down −195.6** (was up 198 / down 194).
- **Design 11 (holdout):** added §4.5 (20% chronological holdout, BH-FDR, N≥30 floor, pre-registration).
- **Smaller:** tiled sessions (added `Settlement` 16:00→17:00 → 1380 min), removed spurious maintenance-gap skip, de-duplicated `NY_PM_midday`/`anchor_mode` and `level_mode` key vs columns, expanded `vol_source` enum per family (VXN/RVX/OVX/GVZ etc.), added third parquet `coverage.parquet`, and corrected README ordering (now `VIX1D < VOLI < VIX`).

### 9.1 Second pass (same day) — defects introduced by the first revision

The first revision fixed all 11 findings but introduced eight of its own. Corrected here:

| # | Where | Defect | Now |
|---|---|---|---|
| 1 | §1.2 log row | "actual 2.8 at VIX **15**/m=1.5" — 2.84 is at VIX **30**; at VIX 15 it is 0.71 | measured both, stated with `S` |
| 2 | §1.2 log row | "spread 5.7 pts" — computed value is 5.63 | 5.6, and the +2.8 arith gap named separately |
| 3 | §1.2 | "RTH variance ~65–75% of close-to-close" asserted as empirical, never measured | **measured 56.8%** on ES 2016–2025 |
| 4 | §1.1 | `core.py:92-110` — `compute_zone_dataframe` starts at line **82** | `core.py:82-146` |
| 5 | 6 sites | as-of rules cited as **§3.2**; §3.2 is `bars.parquet`, the leakage table is **§3.4** | all 6 repointed |
| 6 | §3.1 / §3.5 | key stated **three** ways (5-tuple granularity, "7-tuple" size, 6-tuple + a phantom `level_mode_as_columns` member) — the same defect as Blocking 2, re-committed | **one** 6-tuple, stated twice verbatim |
| 7 | §3.1 | size used 6 sessions × 3 scale modes against a catalog with **7** and **4**; "understated by ~140×" vs its own 18× | **42k/yr/ticker, ~1.7M rows, ~28×** |
| 8 | §3.3 | DST rule was **wrong**: both US transitions fall inside the Fri 17:00→Sun 18:00 closure, so no trading day is 1320/1440 min — and the prescribed remedy (normalize to UTC minutes) is backwards for ET-defined sessions | verified 0 ES bars within ±3h of all 42 transitions 2006–2026; ET wall-clock is the primary clock |
| 9 | §3.4 | `Overnight` given decision time **09:30 T** — but its window *ends* at 09:30 T, so `open_09:30_T` is its outcome | own row, decision time **18:00 T-1** |
| 10 | §4.5 | holdout cut "~2024-06" — splits the calendar span, not the trading-day count | **2025-10-21** (last 215 of 1,077) |
| 11 | §4.5 | family size `276 buckets × 7 sessions` double-counts — the tiled sessions partition the same buckets | 276, with the overlap named |
| 12 | §3.1 | schema table row for `ticker` had an unescaped pipe breaking the 3-column table | escaped |
| 13 | §7 | `VX1_1d`/`VX2_1d` presented as join-ready; **31–36% of rows have `settle` outside `[low,high]`, 304/350 have `low > high`, 95 have `settle <= 0`** | measured table + mandatory `settle > 0` gate; OHLC declared untrustworthy |

Items 1–4, 7, 10 and 13 were verified by executing against `scripts/libs_py/expected_volatility/core.py` and `data/*.parquet`, not by re-reading the prose.

---

## 10. Measured Baselines (2026-08-30)

Everything below is **measured from data already on disk**, before the feature
store is built, by `scripts/expected_volatility/measure_baselines.py`
(`.\.venv\Scripts\python.exe -m scripts.expected_volatility.measure_baselines --ticker ES1 --write`).
Reports land in `data/expected_volatility/baselines_*.md`. Baseline:
**5,183 ES RTH sessions, 2006-01-06 → 2026-08-04**, anchor = prior close
<16:00 ET, vol = prior VIX close (as-of, per §3.4).

These results change what should be built, so they precede Phase B (§5).

### 10.1 The construction is not calibrated — the zones are ~50% too wide

| `c` | P(abs(close−S) ≤ c·EV) | Normal | gap |
|---|---|---|---|
| 0.25 | 37.2% | 19.7% | +17.5% |
| 0.50 | 62.1% | 38.3% | +23.8% |
| 0.8309 | 82.9% | 59.4% | +23.5% |
| **1.00** | **89.1%** | **68.3%** | **+20.8%** |
| 1.50 | 97.5% | 86.6% | +10.8% |

The single-parameter fit of §2 Q8 (`abs(return) ~ k·S·VIX/100`) gives
`k = 0.03346`, i.e. an implied divisor of **sqrt(569)** — not sqrt(252) (`a`)
and not sqrt(365) (`b`). **Realised RTH sigma is 0.666× the VIX-implied sigma.**
Two effects compound: the variance risk premium (~0.8×) and RTH capturing only
~55% of close-to-close variance (§10.7).

Consequence for the ladder: `c = 1.0` is touched on 19.6% of sessions and
**`c = 1.5` on 4.9%** — about 12 sessions a year. The outer rung is not a
tradeable level. §2 Q1 is answered.

### 10.2 The mirrored R/S ladder is mis-specified

Pine mirrors support and resistance exactly (`core.py:70-76`). ES does not:

| `c` | P(up touch) | P(dn touch) | ratio dn/up | z |
|---|---|---|---|---|
| 0.5000 | 34.07% | 32.55% | 0.96 | −1.6 |
| 0.8309 | 14.26% | 16.05% | 1.13 | +2.5 |
| **1.0000** | **8.06%** | **11.60%** | **1.44** | **+6.0** |
| **1.5000** | **1.14%** | **3.70%** | **3.25** | **+8.5** |

Symmetric at the inner rungs, strongly asymmetric in the tails — the signature
of index put skew. **The ladder must be asymmetric**, which §10.5 delivers for
free by taking up and down quantiles separately.

### 10.3 The 0DTE regime break is real, and it coincides with the VIX1D window

| regime | n | realised/implied sigma | P(abs(ret) ≤ 1 EV) | corr(excursion, VIX) |
|---|---|---|---|---|
| pre-0DTE 2006-2021 | 4,008 | 0.645 | 90.7% | +0.075 |
| **0DTE era 2022-05-13 →** | **1,084** | **0.746** | **84.4%** | **+0.113** |
| 0DTE mature 2023 → | 919 | 0.734 | 84.9% | +0.154 |
| recent 2024 → | 662 | 0.760 | 84.0% | +0.177 |

Two things follow. First, in the current regime the zones are *less* wrong
(0.746 vs 0.645) but still ~25% too wide — a pre-2022-calibrated ladder placed
today would sit too close. Second, `corr(excursion, VIX)` **more than doubles**
across the break: the fixed proportionality `EV ∝ VIX^1` is *more*
mis-specified now than it was, so fit an exponent `beta` in `EV ∝ VIX^beta`
rather than assuming `beta = 1`.

**This turns §6.3's feasibility limit into a feature.** The five-way vol-source
common window starts `2022-05-13` — the same date as the regime break, because
VIX1D was launched *for* the 0DTE regime. The window we are forced into is the
window we want to trade. Day-trading work should be calibrated on
`--regime odte`; the pre-2022 history is a separate regime, useful for
stability checks and nothing else.

### 10.4 Cross-instrument replication — promote to a core validation axis

Each instrument has its Pine-mapped vol index already on disk
(`settlements.py:25-32`), so replication costs one command per ticker. This is
a stronger overfitting defence than a single chronological ES holdout:

| pair | n | realised/implied sigma | P(abs(ret) ≤ 1 EV) | dn/up at `c`=1 |
|---|---|---|---|---|
| ES1 × VIX | 5,183 | 0.666 | 89.1% | 1.44 |
| NQ1 × VXN | 5,158 | 0.541 | 91.4% | 1.47 |
| YM1 × VXD | 4,626 | 0.773 | 85.6% | 1.17 |
| RTY1 × RVX | 2,242 | 0.819 | 82.1% | 1.09 |
| GC1 × GVZ | 4,479 | 0.608 | 88.0% | 1.03 |
| CL1 × OVX (rejected) | 4,495 | 2.386 | 66.4% | 1.04 |

**The "too wide" finding replicates across the entire equity complex**
(0.54–0.82, never near 1.0). The **skew** finding does *not* replicate
uniformly — strong in ES/NQ (1.44, 1.47), weak in YM/RTY (1.17, 1.09), absent
in GC (1.03). That is consistent with index put skew and is worth knowing
before assuming the asymmetry is universal.

⚠️ **The CL1 row is an artifact, not a result.** `abs_pct` reaches **8900%** and
`np.log` emits invalid-value warnings — the continuous CL1 series has roll gaps
and bad prints, and the script applies *equity-index* session and 16:00 ET
settlement conventions to a contract that settles 14:30 ET. CL and GC results
are not evidence until they get their own session catalog and a cleaned
continuous series. Do not quote the CL row.

### 10.5 Percentile ladder — replace fixed SD multiples with target `P(touch)`

Since every rung is `S(1 ± c·a)` (§1.3), `P(touch at c) = P(excursion ≥ c)`.
So **invert the empirical CDF**: choose the touch probability you want and read
off `c`. Each rung then carries a known probability *by construction*, the
miscalibration of §10.1 is absorbed automatically, and the skew of §10.2 is
handled by taking up and down quantiles separately.

| target P(touch) | pre-0DTE `c_up` | pre-0DTE `c_dn` | **0DTE `c_up`** | **0DTE `c_dn`** |
|---|---|---|---|---|
| 80% | 0.048 | −0.027 | 0.050 | −0.013 |
| 65% | 0.199 | 0.148 | 0.244 | 0.184 |
| 50% | 0.319 | 0.292 | **0.401** | **0.340** |
| 35% | 0.468 | 0.446 | 0.590 | 0.535 |
| 25% | 0.596 | 0.595 | **0.743** | **0.764** |
| 15% | 0.772 | 0.805 | 0.957 | 1.026 |
| 10% | 0.897 | 1.002 | **1.107** | **1.174** |
| 5% | 1.054 | 1.301 | **1.321** | **1.529** |

Read the asymmetry directly: at the 5% rung the downside level sits at
`c = 1.529` against `1.321` on the upside — **16% further out**. And the 0DTE
ladder is uniformly wider than the pre-2022 one, quantifying §10.3.

What Pine's inherited rungs actually deliver in the 0DTE era:

| `c` (Pine) | P(up touch) pre-0DTE | P(up touch) 0DTE | P(dn touch) 0DTE |
|---|---|---|---|
| 0.2077 | 64.0% | 67.7% | 62.9% |
| 0.2500 | 58.5% | 64.2% | 59.3% |
| 0.5000 | 32.3% | 41.0% | 37.5% |
| 0.8309 | 12.6% | 20.5% | 21.5% |
| 1.0000 | 6.6% | 13.7% | 16.1% |
| 1.5000 | 0.7% | 2.9% | 5.5% |

Probabilities spread from 68% to 3% with no even spacing in probability — which
is the whole argument for the percentile ladder. **It is a ladder; the fixed
multipliers are a zone with arbitrary rungs.**

⚠️ These quantiles are **in-sample by construction** — `P(touch)` landing on
target is not evidence. The ladder must be fit on the train fold and its touch
rates verified on the §4.5 holdout before any rule cites them.

### 10.6 Reaction per rung — and a metric that lies

| target | `c_up` | N | P(touch) | rel ≥50% (artifact) | **≥10 bps** | **≥0.25 EV** |
|---|---|---|---|---|---|---|
| 80% | 0.050 | 867 | 80.0% | 61.0% | 42.8% | 18.1% |
| 65% | 0.244 | 704 | 64.9% | 45.2% | 52.8% | 24.0% |
| 50% | 0.401 | 542 | 50.0% | 33.6% | **55.4%** | **26.6%** |
| 35% | 0.590 | 380 | 35.1% | 20.0% | **56.6%** | 22.1% |
| 25% | 0.743 | 271 | 25.0% | 10.0% | 50.9% | 18.8% |
| 15% | 0.957 | 163 | 15.0% | 4.3% | 55.2% | 19.6% |
| 10% | 1.107 | 109 | 10.1% | 4.6% | 56.0% | 17.4% |
| 5% | 1.321 | 55 | 5.1% | 5.5% | 49.1% | 23.6% |

⚠️ **The `rel` column is a trap and is retained only to show it.** Defining
reaction as "retraced ≥50% of the anchor→level distance" makes near rungs
trivially easy to satisfy, so the rate collapses from 61% to 4% purely as an
artifact of the definition. §6.1 must fix the reaction threshold in **bps or in
EV units**, never as a fraction of the level distance.

On the scale-free measures the reaction rate is **roughly flat** (~49–57% at
10 bps), with a mild peak at the **35–50% touch rungs, `c ≈ 0.40–0.59`**. That
is the first data-derived answer to "which levels matter": not the outer
1.0/1.5 sigma rungs the indicator emphasises, and not the inner noise rungs.
Note also that ~50–56% at 10 bps is close to a coin flip — the edge, if any,
has to come from the conditioning in P3/P4, not from the level alone.

### 10.7 Where variance realises — this replaces the `scale_mode` horse race

ES 1m realised variance, 2010→2026:

| session | minutes | % of clock | **% of variance** | per-min index | `sqrt(share)` | `sqrt(min/1380)` |
|---|---|---|---|---|---|---|
| Asia | 540 | 39.1% | 20.3% | 0.52 | 0.451 | 0.626 |
| London | 390 | 28.3% | 21.6% | 0.77 | 0.465 | 0.532 |
| NY_AM | 150 | 10.9% | 26.6% | **2.45** | 0.516 | 0.330 |
| NY_PM | 240 | 17.4% | 28.6% | 1.65 | 0.535 | 0.417 |
| Settlement | 60 | 4.3% | 2.7% | 0.63 | 0.166 | 0.209 |

Variance is **not uniform in clock time** — NY_AM carries 2.45× the average
per-minute variance, Asia 0.52×. So `sqrt(session_minutes / T_ref)` is wrong
for every session, by up to 1.56× (NY_AM: 0.516 vs 0.330).

**§2 Q17 and the `scale_mode` enum should be retired.** The correct session
scaling is `sqrt(measured variance share)` — a measurement, not a three-way
horse race between arbitrary denominators. Store the fitted share table and use
it; keep `scale_mode` only as a fallback for instruments without a fitted table.

### 10.8 Vol input, and what VIX does and does not get right

| input | `k` | R2 | MAE (%) |
|---|---|---|---|
| VIX (30d implied) | 0.03347 | 0.265 | 0.4146 |
| RV20 (realised) | 0.04681 | 0.218 | 0.4110 |
| 0.5·VIX + 0.5·RV20 | 0.04004 | **0.271** | **0.4103** |

VIX explains only ~27% of `abs(RTH move)`; a naive blend with trailing realised
vol already beats it on both R2 and MAE. Worth knowing before rules are built
on VIX alone.

The decomposition that matters — **VIX gets the shape right and the level
wrong**. `P(reversal | touch)` is essentially flat across VIX quintiles
(c=0.25: 37.8 / 38.1 / 37.8 / 40.2 / 40.9%; c=0.5: 15.0 / 14.9 / 15.4 / 15.2 /
18.5%), so the normalisation is correctly specified for *reaction*. But
`P(touch)` rises monotonically (c=0.5: **26.4% → 41.1%** from Q1 to Q5), so the
proportionality is not exact — excursions grow faster than VIX. This is the
`beta` exponent of §10.3, and it is the cleanest statement of what to fix.

### 10.9 What this changes, and what is still open

Changes to the plan:

1. **Recalibrate before building.** Apply the fitted `k` (or the §10.5 ladder) —
   the current geometry is ~50% too wide over the full sample, ~25% in the
   0DTE regime.
2. **Percentile ladder replaces the fixed multipliers** as the primary level
   set. Keep Pine's four `m` as markers on the curve (§1.3), not as the
   hypothesis.
3. **Asymmetric up/down ladders** for ES/NQ; check per instrument (§10.4) —
   the skew does not replicate on YM/RTY/GC.
4. **Calibrate on `--regime odte`** for day-trading use. The regime break and
   the vol-source common window are the same date.
5. **Fit `beta` in `EV ∝ VIX^beta`** rather than assuming proportionality.
6. **Retire `scale_mode`** in favour of the measured variance-share table.
7. **Fix the reaction threshold in bps or EV units** (§6.1), never as a
   fraction of the level distance.

Still open, in rough value order:

- **A clean placebo.** "Does the EV level beat an arbitrary level at the same
  distance" is the negative control the whole plan rests on. The naive version
  is confounded (the two ladders select different day-populations conditional
  on touch); §10.8's invariance test is the properly specified partial answer.
  A full answer needs a within-day matched design.
- **HAR-RV as a `vol_source`.** With 1m bars, Corsi's daily/weekly/monthly
  realised-variance model is the standard benchmark and routinely beats implied
  vol at forecasting realised vol. §2 Q7 currently omits the model most likely
  to win.
- **Better RV estimators.** `RV20 = std(daily closes)` wastes the 1m data.
  Parkinson / Garman-Klass / Yang-Zhang (which handles the overnight jump
  explicitly — directly relevant given §10.7) are strictly more efficient.
- **Block bootstrap for every standard error.** Sessions are not independent
  and volatility clusters hard; every Fisher exact and chi-square in §4.2/§4.5
  is anti-conservative without blocking. Interacts with the BH-FDR correction.
- **Day-of-week / 0DTE-expiry / OPEX conditioning.** SPX 0DTE expiries land
  Mon/Wed/Fri; the repo already has OPEX validation work (see the `video2pdf`
  handover §21).
- **CL/GC session catalogs and a cleaned continuous series**, before either is
  quoted (§10.4).

### 10.10 Note on build state

`data/expected_volatility/sessions.parquet` was rebuilt 2026-08-30 and is now
**1,451,136 rows × 41 columns** (192 per `(trading_day, session_id)` = 4
`scale_mode` × 12 `c` × 2 `level_mode` × 2 `side`), keyed `(trading_day,
session_id, ticker, vol_source, anchor_mode, scale_mode, c, level_mode, side)`.
The pre-fix artifact is retained as `sessions_pre_sidefix.parquet.bak`; **do not
join against it** — see §10.13 for what was wrong with it.

It uses a **long** layout (`c`, `level_mode` and `side` as columns of values)
rather than the wide layout §3.1 specifies. That is the better shape for the
§1.3 continuous-`c` sweep, but §3.1 and §3.5 describe the wide one —
**reconcile the doc with the artifact before extending either.**

---

### 10.11 The anchor is the variable that matters — and it overturns §10.6

Every level in this plan is measured from the **prior settlement close**,
inherited from the Pine indicator. That is the wrong origin for a day trader,
and the size of the error is measurable. In EV units the ES overnight gap runs:

| | p5 | p25 | p50 | p75 | p95 | mean abs |
|---|---|---|---|---|---|---|
| gap / EV | −0.77 | −0.22 | +0.04 | +0.28 | +0.70 | 0.335 |

**The gap alone already exceeds `c=0.25` on 49.1% of sessions, `c=0.4155` on
29.4%, and `c=0.50` on 21.6%.** On half of all days a prior-close ladder has
spent its inner rungs before the opening bell.

Re-running the identical ladder, bracket and days from the **09:30 open**
(`build_playbook.py --anchor rth_open`) collapses the continuation result that
§10.6 and the research report carried as their headline:

| fold | anchor | rungs N≥30 | mean E per trade (EV) | rungs positive | mean win |
|---|---|---|---|---|---|
| train | prev_close | 15 | **+0.0534** | 15/15 | 58.0% |
| train | rth_open | 16 | +0.0093 | 12/16 | 51.7% |
| holdout | prev_close | 10 | **+0.0666** | 9/10 | 58.9% |
| holdout | rth_open | 11 | **−0.0016** | 6/11 | 49.7% |

The mechanism is not subtle. Median minutes from 09:30 to first touch, holdout,
upper rungs:

| target P | `c` prev | prev_close | `c` open | rth_open |
|---|---|---|---|---|
| 80% | 0.055 | **0 min** | 0.124 | 10 min |
| 65% | 0.246 | **0 min** | 0.222 | 27 min |
| 50% | 0.390 | 8 min | 0.340 | 79 min |
| 35% | 0.578 | 30 min | 0.497 | 134 min |

The two rungs carrying the whole result — win 69.3% and 66.9% — have a median
first touch of **zero minutes**. The trade was never a level touch; it was *buy
the open on a gap-up day and hold*, with the level acting only as a filter on
which days qualified. **This is the confound §10.9 listed as an open item. It is
now closed, against the finding.**

Note what this says about method: the holdout was honest, the ladder was never
fit on it, and the result replicated cleanly across both folds. A holdout
cannot detect a confound in the **definition of the event**, because the
confound is present identically in both folds. Only the control caught it.

**Consequences for this plan.** `anchor_mode` must stop being a v1 stub. Emit at
least `close` and `rth_open`; `§3.2`'s open/midday gating is not a nice-to-have,
it is the axis that decides whether any §4.4 rule means anything. The
`open` anchor is also the correct frame for every intraday rule in §4.

### 10.12 Vol input: HAR-RV forecasts better, but the ladder does not care

`compare_variants.py` races 2 anchors × 4 vol inputs, scored on the holdout by
mean |realised touch rate − target| across the 16 ladder rungs.

| anchor | vol input | mean rung cal. error | CV of excursion/EV | QLIKE |
|---|---|---|---|---|
| rth_open | vix_prev_close | **1.45%** | 0.556 | 1.9397 |
| rth_open | har_rv | 1.67% | 0.550 | 1.4309 |
| rth_open | vix_open | 1.70% | 0.558 | 1.9618 |
| rth_open | blend | 1.79% | **0.527** | **1.3844** |
| prev_close | vix_open | 2.39% | 0.569 | 1.6709 |
| prev_close | vix_prev_close | 2.46% | 0.571 | 1.6454 |
| prev_close | blend | 2.55% | 0.540 | 1.8150 |
| prev_close | har_rv | 2.55% | 0.556 | 1.9294 |

**Every `rth_open` row beats every `prev_close` row, with no overlap.** Within an
anchor the four vol inputs span 0.34 pp and their ranking *flips* between
anchors — that is noise.

HAR-RV (Corsi 2009) on log realised RTH variance, 5-minute sampling, fit on the
train fold only: `const −0.6032`, `daily +0.4304`, `weekly +0.3073`, `monthly
+0.1462`. Decaying, summing to 0.884 (mean-reverting) — textbook, which is a
sanity check on the estimator rather than a finding. It **does** forecast better:
QLIKE 1.94 → 1.43 on the open anchor (−26%). The OLS blend of `log VIX` and
`log HAR` is better still (QLIKE 1.3844, CV 0.527) with near-equal weights
(`+0.618` / `+0.596`), so the two carry genuinely different information.

Why the better forecast does not produce a better ladder: **the ladder is built
by inverting the empirical CDF, so it absorbs any systematic mis-scaling of its
input.** A vol source running 30% hot is corrected by the fit itself. What the
ladder cannot absorb is an origin in the wrong place, because that changes what
is being measured, not just its scale. Practical rule: **fix the anchor; the vol
input is close to a free choice.** Prefer the blend where the EV *magnitude* is
used (position sizing), not just the rank.

`VIX_1m.parquet` cannot support an intraday-VIX variant: it starts at **09:31
ET on 913 of 1049 days** and holds a pre-open print on 12. The daily bar's
`open` is the usable pre-RTH read, and it differs from the prior close by >2% on
40% of days and >5% on 12%.

### 10.13 `build_features.py` review — adjudicated 2026-08-30

An external review of `build_features.py` + the 544k-row artifact was checked
claim by claim against code and data.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Only `R` levels emitted, all `S` dropped | **CONFIRMED** | `level_price > settlement_close` on **100.0%** of 544,176 rows. `compute_ev_levels` builds `S_arith_*`/`S_log_*`; the writer read only `R_{mode}_{label}` |
| 2 | `sqrt_sess_over_1440` promised, not built | **CONFIRMED** | `scale_mode` held exactly 3 values; the dict declaring the 4th was never iterated |
| 3 | Upsert key ambiguous, doc vs code | **CONFIRMED, and worse than stated** | The review called it "actually the correct behavior". It is not: the code key **omits `anchor_mode`**, so emitting the §10.11 open anchor would have silently overwritten every close-anchor row via `keep="last"` |
| 4 | Dead code (`C_VALUES`, `daily_S`, `scale_modes`) | **CONFIRMED** | all three assigned and never read |
| 6 | Intraday-VIX staleness not surfaced | **CONFIRMED** | and see §10.12 — the file is worse than stale, it has almost no pre-open coverage at all |
| 7 | `bars.parquet` reintroduces the lookahead | **CONFIRMED** | read `vol_daily` (unshifted) where the sessions builder reads `vol_daily_asof` |
| 8 | Settlement touch rate low "expected given low volume" | **REFUTED — it was a bug symptom** | see below |

**The review missed the defect that produced the symptom it explained away.**
Touch was tested as `sess_high >= lvl >= sess_low` — *the level lies inside the
session range* — which scores `False` when a session opens entirely **beyond**
the level. That is a level exceeded, not a level unreached. It mislabelled
**48,078 rows (8.84%)**, concentrated exactly where sessions do not straddle the
prior close:

| session | P(touch) as built | corrected | understated by |
|---|---|---|---|
| Settlement | 7.4% | 37.7% | **30.3 pp** |
| NY_PM | 24.3% | 37.7% | 13.4 pp |
| NY_AM | 31.5% | 40.1% | 8.6 pp |
| RTH | 34.3% | 39.3% | 5.1 pp |
| **overall** | **21.4%** | **30.2%** | **+41% relative** |

Settlement was not quiet. It was the session most often entirely on one side of
the prior close, so it collected the most false negatives. Two further defects
the review did not raise: the reversal threshold was a **fixed 4 ES points**
(9 bps at ES 4400, 6 bps at ES 6800 — the exact scale-dependence §10.6 warns
about), and `max_pierce` was emitted only in points, against ADR-002.

All of the above are fixed; `reversal_bps` and `max_pierce_bps` are now emitted
alongside, and the threshold is derived from `REVERSAL_BPS` rather than baked
into a literal.
