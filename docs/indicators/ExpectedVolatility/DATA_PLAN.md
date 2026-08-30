# Expected Volatility Zones — Quant Research & Data Plan

> Goal: determine **which volatility-implied levels actually matter** for intraday ES (and NQ) day trading, how to trade them, and whether the current zone construction (252 vs 365, multipliers, close-anchor) is optimal.
>
> Audience: quant trader building statistics → probabilities → rule set. Data-first, not opinion-first.
>
> **Rev 2026-08-30** — addresses the 340-line review against `scripts/libs_py/expected_volatility/` and `data/*.parquet`. Blocking fixes: verification re-executed, upsert key unified, lookahead removed, geometry collapsed to one parameter, common-window re-scoped, and holdout discipline added. See §9.

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

The two middle values were a hand-arithmetic slip (mirror partners, so one error propagated to the other). `R_top` and `S_bottom` matched; `R_bottom`/`S_top` did not — the doc's line "Matches `compute_zone_ladders()` exactly" was false and has been corrected above. Vectorised path `compute_zone_dataframe()` is identical to the scalar path by construction (`core.py:92-110`).

§8's worked example (ES 7000 / VIX 15 → `ev_a ≈66.1`, `ev_b ≈54.9`) **is correct** and is retained.

### 1.2 Quant assessment

| Item | Verdict |
|---|---|
| `a = VIX/sqrt(252)/100` and `b = VIX/sqrt(365)/100` | **Both are rescalings of one forecast — neither is "correct" vs "approximate."** CBOE defines VIX with `T` in calendar-year fractions (365 days / 525600 min), so `b` is faithful to VIX's own definition. The `/sqrt(252)` trader convention reallocates calendar variance onto trading days (assumes weekends/holidays have near-zero variance). Algebraically `b = a * sqrt(252/365) = a * 0.830910`, so choosing 252 vs 365 is a **single-parameter fit** `σ = c·VIX/100` with `c=1/sqrt(252)` or `1/sqrt(365)`. Rank them by regressing `|return| ~ c·S·VIX/100` and reading off optimal `c` — Diebold-Mariano between two deterministic rescalings of one forecast is degenerate. The Pine author uses both to create a **zone** `[R_bottom,R_top]` of thickness `S·m·(a-b) = S·m·a·0.16909` ≈ 17% of the 1σ move. Treat as an intentional uncertainty band, not a formal DTE model. |
| `VIX/sqrt(252)` as "1σ RTH move" | **Overstates.** `VIX/sqrt(252)` is the σ of a **24h close-to-close** return (including overnight, by construction of VIX). Using it as an RTH-only (09:30–16:00, 390 min) forecast overstates systematically — RTH variance is ~65–75% of close-to-close variance empirically. This collides with §2 Q17: if RTH=390 is the unscaled baseline, a full 24h trading day needs a factor >1. Fixed in §3.1 by making `scale_mode` include `1380` (full 23h trading day 18:00→17:00, see §3.3) and by treating the unscaled daily box as the 24h forecast. |
| Zone vs single level | The zone `[R_bottom,R_top]` is the calendar-vs-trading ambiguity. `R_mid` is the average of the two, not a separate vol model. See §1.3 for the collapse. |
| Arithmetic vs log levels | Pine uses **arithmetic** `S ± S·σ·m` (symmetric in points). A **log / geometric** variant is `S·exp(±σ·m)` (symmetric in log-returns, asymmetric in points). Gaps: at VIX 12–20 / m≤1, |log−arith| <1 pt at S=7000 (noise). At **VIX 30 / m=1.5, S=7000**: **arith ±198.4 pts symmetric; log up +201.3 / down −195.6, spread 5.7 pts wider on the upside.** The old doc's "up 198 vs down 194 — 4 pts wider" reported the *arithmetic* value as the log up-leg; §1.2's earlier "~3 pts" is the correct order (actual 2.8 at VIX 15/m=1.5) — the two sections disagreed and are now reconciled here. Log is theoretically cleaner for percentage SD (avoids negative-price pathology, respects compounding); whether it forecasts better is empirical — add as parallel columns and horse-race by VIX quintile (see §3.1). |
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
4. **Close vs open anchor**: compare `S_close = close[1]` vs `S_open = today 09:30 open` vs `S_vwap = prior RTH VWAP`. Which anchor centres realized RTH range better? (mean absolute error, hit symmetry R vs S). Must be evaluated **per session's as-of time** (see §3.2).
5. **Prior-day vs overnight-inclusive settlement**: does including the 16:00–09:30 Globex drift in S improve or hurt? (Our current cutoff excludes it by design — test the alternative.)
6. **Intra-day re-anchor**: would a rolling anchor (e.g. overnight VWAP at 09:30) beat a static prior-close?

### P2 — Is the vol input right?
7. **Vol source horse race — the ES question** (feasibility-corrected): `VIX` (30d) vs `VIX1D` (1d) vs `VOLI` vs `VIX9D` vs `VIX3M` vs term-interpolated IV vs realized 20d vol vs `VX1` futures-implied. Which `a` best predicts `|return|`? Use MAE/R² and hit-rate calibration (`P(|return| ≤ c·EV)` vs Normal `N(c)`). **Common window across the five cash sources is `2022-05-13 → present` (~1,070 trading days)** — see §6.3. `VIX9D/VIX3M/VX1` extend further back; report both the common-window horse race and the longer-window pairwise races. Diebold-Mariano between two rescalings of one forecast is degenerate — use the single-parameter fit above.
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

16. **Session transfer**: do EV zones anchored at the *prior NY close* (16:00 ET) predict the subsequent **Asia** (18:00–03:00 ET) and **London** (03:00–09:30 ET) ranges with the same hit/reaction profile as RTH? Or does each session need its own anchor (Asia anchored at London close, London at Asia close)? Test both and compare MAE / `P(touch)` calibration — with **as-of correctness** (§3.2).
17. **Session-scaled EV**: for a shorter session of duration `T_sess`, expected move ≈ `S·σ·sqrt(T_sess / T_ref)` under GBM. Does scaling `a,b` by `sqrt(session_minutes / 1380)` (full 23h trading day) vs `sqrt(session_minutes / 390)` (RTH 390 min) vs `sqrt(session_minutes / 1440)` (calendar 24h) tighten Asia/London/NY-PM zones usefully vs unscaled? Treat `T_ref` as a tunable; note `unscaled` now means **24h close-to-close** (§1.2), not RTH.
18. **NY AM vs NY PM split**: is the morning (09:30–12:00) statistically different from afternoon (12:00–16:00) for EV utility? E.g. AM = high informed volume, more reversals at outer `c`; PM = drift/decay, more holds. Compute `P(touch)`, `P(reversal|touch)`, `max_pierce` separately.
19. **Mid-day re-anchor — should we recompute at 12:00 ET?** Two candidates to horse-race:
    - **Static** (Pine-faithful): one anchor at 09:30, one vol read, zones fixed all day.
    - **Rolling mid-day**: at 12:00 ET re-read `S_mid = 12:00 price`, `V_mid = VIX at 12:00` (or 5-min VWAP), and recompute *remaining-session* zones scaled by `sqrt(remaining_minutes / session_length)`.
    
    Question: does the re-anchored PM zone raise `P(reversal|touch)` or reduce `max_pierce` vs static? And does it help to also **condition on AM outcome** (e.g. AM already tagged `R_1.0` → PM fade the opposite side)? Measure lift and whether the improvement survives transaction-cost / whipsaw of the reset. **V1 scope note:** if `VIX_1m` remains stale past `2025-12-31` (see §6.3), `V_mid` and `vix_chg_intraday` cannot be computed — drop `NY_PM_midday` and Q27 from v1.

### P6 — VIX ecosystem pack (extends P2; shared across strategies)

VIX as a 30d annualized SPX vol is one projection — the surrounding VIX ecosystem tells you **whether to trust it and how wide to make it**. All features below are computable from already-captured parquets and are intentionally **strategy-agnostic** (reuse for mean-reversion, breakout, sizing, regime filters elsewhere). As-of rules in §3.2 apply — no feature may use data after the session's open.

20. **VIX percentile / rank**: `pctl_63d`, `pctl_252d` of VIX_T vs trailing history (as-of prior close). Filters every hit/reaction stat: does `P(reversal|touch)` at VIX p90 differ from p10?
21. **Term-structure slope** — `VIX - VIX9D`, `VIX - VIX3M`, `VIX1D - VIX`, `VIX/VIX3M` (local `VIX9D_1d`, `VIX3M_1d`, `VIX1D_1d` already captured). Contango (VIX < VIX3M) = complacent, zones hold; backwardation (VIX > VIX3M or VIX1D > VIX) = stress, outer `c` pierce — quantify the moderator effect on `P(close beyond | pierce)`.
22. **Vol-of-vol (VVIX)** — `VVIX_T` and `VVIX/VIX` (`VVIX_1d` holds 2006-03-06→2026-08-28; `VVIX_1m` is only 23 days 2025-12-09→2025-12-31 and is **not** the trading-day join). High VVIX → widen stop beyond zone top or shrink size; low VVIX → tighter fade.
23. **Variance risk premium (VRP)** — `VRP_T = VIX_T - RV20_T` where `RV20 = sqrt(252)*std(log ES returns, 20d)` from `ES1_1m`. VRP >0 (IV expensive) → fades at EV edges work; VRP <0 → vol expansion, favor breakout beyond 1σ.
24. **VIX momentum / change** — `Δ1d = VIX_T - VIX_{T-1}`, `Δintraday = VIX_midday - VIX_open` (intraday only for sessions that contain midday; see §3.2), 5d slope.
25. **Interpolated 1d IV** — variance-linear interpolation of the cash curve to exactly 1 trading day: `IV1d^2 = w*VIX1D^2 + (1-w)*VIX9D^2` (or VIX9D/VIX spline). Horse-races the single-VIX `a` as the *true* 1d forecast vs 30d proxy.
26. **VIX/SPX (or VIX/ES) correlation regime** — `corr(log ES returns, ΔVIX, 20d)` as-of prior close.
27. **Intraday VIX drift** — slope of VIX 09:30→16:00 vs `realized remaining range`. Tests §4.3 decay and is a standalone PM signal (intraday feature, not joined to overnight rows).
28. **VIX futures term premium (when futures feed lands — see §7)** — front-month basis `VX1 - VIX`, curve slope `VX2 - VX1`, roll cost. Data now live: `VX1_1d`/`VX2_1d` stitched from CFE (`fetch_cboe_vx_futures.py`, 2013→2026, 3438 rows). `vx_basis_spot` and `vx_curve_1_2` are the tradable expression of VRP.

---

## 3. Data Plan — Parquet Feature Store

**Three** derived parquets under `data/expected_volatility/` (derived domain per `CLAUDE.md`): `sessions.parquet` + `bars.parquet` + `coverage.parquet` (audit sidecar).

### 3.1 `sessions.parquet` — one row per session window (primary analysis table)

Granularity: **`trading_day × session_id × ticker × vol_source × scale_mode`** — each `(trading_day, session_id, ticker, vol_source)` emits one row per `scale_mode` value. `level_mode` (arith vs log) is **not a key** — it is emitted as **parallel columns** `R_top_arith_c` / `R_top_log_c` per §1.2 Q7b (see schema). `anchor_mode` variants are rows only where the anchor is **as-of valid** for that session (see §3.2); combinations that look ahead are not emitted. Expected size under the 7-tuple key: ~6 sessions × 252 trading days × 6 vol sources × 3 scale modes ≈ **27k rows/year/ticker** before anchor variants — not "~1.5k". Over 20y × 2 tickers at ~100 columns, plan for **~1.1M rows and ~8–9M cell families** (previous doc understated by ~140×).

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
| `ticker` | `ES1!` / `NQ1!` etc. — **vol_source enum is per-family**: ES→ VIX/VOLI/VIX1D/VIX9D/VIX3M/VX1 | `VX1`; NQ→ VXN; RTY→ RVX; CL→ OVX; GC→ GVZ (see `settlements.py:25-32`, `data/` has VXN 2001, RVX 2006, OVX 2007) | key |
| `vol_source` | For ES: `VIX` / `VOLI` / `VIX1D` / `VIX9D` / `VIX3M` / `VX1` / `term_interp` / `RV20`; for other tickers: their family vol (e.g. NQ→`VXN`) | key |
| `scale_mode` | `unscaled` (=24h close-to-close) / `sqrt_sess_over_1380` / `sqrt_sess_over_390` / `sqrt_sess_over_1440` | session-scaling horse race (§2 Q17) — **1380 is the trading-day length (§3.3)** |
| `settlement_close` | `close_day` (prior close <16:00 ET, `S_T-1`) | anchor (as-of) |
| `settlement_open` | first regular open ≥09:30 ET on T (only valid for sessions starting ≥09:30) | anchor variant — not emitted for Asia/London |
| `settlement_midday` | 12:00 ET price/VWAP on T (only for `NY_PM` midday re-anchor variant) | anchor for re-anchored PM — not emitted for Asia/London/Overnight |
| `open_session` | open of `session_id` window | gap & anchor comparison |
| `vix_close` | vol index **as-of prior close** (`vix_T-1`) — see §3.2 | vol input (as-of) |
| `ev_a`, `ev_b`, `ev_scaled` | `S·a`, `S·b`, `S·a·sqrt(T_sess/T_ref)` per `scale_mode` | base moves |
| For each `c` in the 12 constants (§1.3): `R_c`, `S_c` (arith) and `R_log_c`, `S_log_c` | `core.compute_zone_dataframe` with `level_mode` as **columns**, not rows; e.g. `R_top_arith_1.0`, `R_top_log_1.0`, `R_0.9155` etc. | zone geometry — continuous `c` sweep |
| `prior_rth_high/low/range`, `overnight_high/low/range` | from 1m OHLC as-of session open | fib base + gap regime |
| `fib_R_382/500/618`, `fib_S_382/500/618` | `S ± fib·prior_rth_range` | fib confluence; compare to EV |
| `q_up_1`, `q_dn_1`, `q_grid` | nearest quarter levels to S (per `QUARTERS_THEORY.md`) | quarter confluence |
| `session_high/low/close/range`, `session_vwap` | realised for `session_id` window | outcome |
| For each level (EV `c`, fibs, quarters): `touched`, `first_touch_min_session`, `first_touch_min_trading_day`, `first_touch_bucket_5m_session`, `first_touch_bucket_5m_trading_day`, `first_touch_bucket_15m_session`, `first_touch_bucket_15m_trading_day`, `max_pierce_pts`, `pierce_bars`, `close_beyond`, `reversal_pts_15m/60m`, `reversal_hit` | computed from 1m bars of `session_id` window | hit/reaction stats — **bucket ids are the primary time dimension** (§3.3) |
| `realized_move_abs`, `realized_vol_session` | `|close-open|/S`, `std(log returns)` over session | vol forecast calibration — denominator is session length |
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

**DST.** ET wall-clock days are 23h (1380 min) normally, but **22h (1320 min) on the spring-forward Sunday and 24h (1440 min) on the fall-back Sunday**. On those two dates `minutes_since_trading_day_open` runs 0…1319 or 0…1439 and bucket ids stop aligning across days. For the primary join key, use **`minutes_since_trading_day_open` as stored** and a derived **`bucket_5m_et_wall`** that is DST-aware; or normalize to **UTC minutes** (`minutes_since_trading_day_open_utc`) for cross-day alignment. Document which is used per analysis. ~40 trading days over 2006→present are affected.

### 3.4 Leakage and as-of rules (normative — blocks §2 Q3 from being publishable without this)

**Principle:** no feature on a row may use data timestamped at or after the **decision time** for that row.

| Row type | Decision time | Allowed as-of | Forbidden |
|---|---|---|---|
| `Asia` (18:00 T-1→03:00 T) | 18:00 T-1 | `S_T-1` (prior RTH close <16:00 T-1), `vix_T-1`, `vrp_T-1`, `term slopes_T-1`, `pctl_T-1` | `vix_close_T`, `vix_open_T` (09:30), `vix_midday_T`, any `T`-day OHLC, `settlement_open_T`, `settlement_midday_T` |
| `London` (03:00→09:30 T) | 03:00 T | same as Asia (still `T-1` close) | same as Asia |
| `NY_AM` (09:30→12:00), `RTH` (09:30→16:00), `Overnight` (18:00 T-1→09:30) | 09:30 T | `S_T-1`, `vix_T-1`, `open_09:30_T` is allowed as contemporaneous (gap), but not `vix_close_T` | `vix_close_T`, `vix_midday_T` for the static row |
| `NY_PM` static (12:00→16:00, anchor `S_T-1`) | 12:00 T (for the PM outcome, but features remain `T-1`) | same `S_T-1`/`vix_T-1` pack | `vix_close_T` |
| `NY_PM` midday re-anchored (12:00→16:00, anchor `S_midday_T`) | 12:00 T | `S_midday_T` (12:00 price), `vix_midday_T` (12:00 VIX) are allowed **only for this row variant** | not allowed for the static `NY_PM` row |

Consequences for the schema:

- The old doc's "VIX pack computed once per `trading_day` and joined to every `session_id` row for that day, so a London touch can be conditioned on the same trading day's open" **used future data** (`vix_close_T` for a session that ended at 09:30). Fixed: the pack is **as-of `T-1` close** for all sessions; the only `T`-day columns are `open_09:30_T` (gap) and, for the midday variant, `S_midday_T`/`vix_midday_T`.
- `vix_chg_intraday = VIX_midday - VIX_open` is **NULL** for Asia/London/Overnight/Settlement rows by construction — they do not contain 09:30→12:00.
- `anchor_mode=open` (= today's 09:30 open) is **not emitted** for `Asia`/`London` rows — it would anchor a session on a price 6–15 hours after it ended.
- `anchor_mode=midday` and `NY_PM_midday` are **one variant**, not two encodings of the same fact. `session_id` stays `NY_PM` for both; the midday re-anchor is `anchor_mode=midday` + `scale_mode=sqrt_240_over_...` on that row. There is no separate `session_id=NY_PM_midday` key value — it is a row qualifier.

### 3.5 Build Logic & Dependencies

```
raw:  data/ES1_1m.parquet, data/NQ1_1m.parquet,
      data/VIX_1d.parquet, data/VOLI_1d.parquet, data/VIX1D_1d.parquet,
      data/VIX9D_1d.parquet, data/VIX3M_1d.parquet, data/VVIX_1d.parquet,
      data/VX1_1d.parquet, data/VX2_1d.parquet (CFE, fetch_cboe_vx_futures.py)
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
- **Upsert key is the 7-tuple** `(trading_day, session_id, ticker, vol_source, scale_mode, anchor_mode, level_mode_as_columns)` — but `level_mode` is **columns, not a key** (see §3.1). The old doc listed both the 7-tuple and a contradictory 4-tuple `(trading_day, session_id, ticker, vol_source)`; the 4-tuple would silently collapse the scale/anchor/mode experiment and is removed. Use the 7-tuple (with `level_mode` collapsed to columns) — i.e. **`(trading_day, session_id, ticker, vol_source, scale_mode, anchor_mode)`** — and upsert on rerun; backfill with `--from / --to`.
- Fuse `data/{ticker}_1m.parquet` (2006–2024) + `data/live/live_storage_-{ticker}.parquet` (2025→now) via `scripts/utils/fused_data_loader.py:load_fused_data()` for full history; for validation slices use live storage directly.
- Daily vol dailies are 16:00 ET close stamps → `build_daily_settlements` daily path handles normalization; intraday VIX uses 16:00 cutoff path.
- `VVIX` source is **`VVIX_1d.parquet` (2006-03-06→2026-08-28)** for the trading-day join; `VVIX_1m.parquet` is only 23 days (2025-12-09→2025-12-31) and is not used for the daily pack.
- `VIX_1m.parquet` is **stale past 2025-12-31** (last bar 2025-12-31, 8 months stale as of 2026-08-30) — any feature requiring intraday VIX (`vix_midday`, `vix_chg_intraday`, `NY_PM` midday re-anchor, §2 Q27) is **NULL for trading days after 2025-12-31** until the intraday feed is backfilled (see §6.3).
- Missing-data policy: require `settlement_close` and `vix_close_T-1` non-null to emit a session row; log gaps and keep `coverage.parquet` sidecar for audit.

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
- **Vol source for ES (common-window + pairwise)**: `VIX` vs `VIX1D`/`VOLI`/`VIX9D`/`VIX3M`/`VX1`/`term_interp`/`RV20` — report **common-window (`2022-05-13→present`, ~1,070 trading days)** horse race *and* longer-window pairwise races where history exists (VIX 1990, VOLI 2013, VIX9D 2011, VIX3M 2009).
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

- **Time-series holdout:** pre-register the P0 metrics (touch curve over `c`, reaction curve over `c`, pierce curve over `c`) and **hold out the last 20% of trading days chronologically** (`~2024-06→present`, ~214 of the ~1,070 common-window days) as the test fold. All hyper-parameter choices (optimal `c`, regime thresholds) are fit on the train fold; §4.4's rule sheet is evaluated **once** on the test fold. No peeking.
- **Family-wise correction:** §4.1 stratifies `P(reversal|touch)` by ~276 five-minute buckets × 7 sessions × 12 `c` values × 6 vol sources × regime. Within each **family** (e.g. "touch-rate by bucket"), correct `p`-values with **Benjamini-Hochberg FDR** (or Bonferroni for small families) and report `q`-values alongside raw `p`. Fisher exacts in §4.2 are subject to the same correction.
- **Cell-count floor:** do not report a probability for a stratum with fewer than **30 touches** (or fewer than 50 sessions for calibration) — mark as `insufficient N` in the tables. With a ~1,070-day common window and 276 buckets, most bucket×level cells will be sparse; the 15-min rollup is the reporting floor for a reason.
- **Out-of-sample only where noted:** rolling 2-year windows in §6.3 are descriptive, not selective — selection is on the train fold.

---

## 5. Delivery Milestones

| Phase | Output | Effort |
|---|---|---|
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
3. **History depth for calibration**: use holdout split in §4.5 for selection; report descriptive rolling 2-year windows but **select on train only**. Common window for the 5-way vol horse race is `2022-05-13→present` (~1,070 trading days ≈ two 2-year windows). Longer histories are pairwise only, not 5-way.
4. **DTE ambition**: for v1 keep T=1 fixed (as Pine does); treat `sqrt(DTE)` scaling as a v2 experiment gated on P2 results. The 252-vs-365 question is answered by the single `k` fit, not by model selection.
5. **Intraday VIX freshness**: decide now whether `VIX_1m` will be backfilled past `2025-12-31` before v1. If not, `NY_PM_midday`, `vix_chg_intraday`, and §2 Q27 are out of v1 scope.

---

## 7. VIX Futures — CFE Scrape (now live)

VIX futures (CBOE/CFE: VX, front month VX1 / VX2 …) are the *tradable* term structure. Cash VIX term slopes (`VIX - VIX9D`) in §2 Q21/§3.1 use indicative CBOE indices; the futures curve (`VX1 - VIX` basis, `VX2 - VX1` slope) is the cleaner signal and the direct expression of variance risk premium.

Fetched via **CFE Price and Volume Detail per-expiry CSVs** (`cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_YYYY-MM-DD.csv`, ~618 expiries 2013→present, discovered via Playwright Year dropdown). Each CSV is one expiry (Wednesday) with `Trade Date,Open,High,Low,Close,Settle,Volume,OI`. Script `scripts/market_data/fetch_cboe_vx_futures.py` probes all Wednesdays 2013→2027 (HEAD → GET) and stitches **continuous `VX1_1d` / `VX2_1d`** at `16:00 ET → 20:00 UTC` (same anchor as `fetch_cboe_indices.py:47`).

Live on disk (just built): `VX1_1d` 3438 rows `2013-01-02 → 2026-08-28` (`last Settle 16.9353` for `2026-09-02` expiry), `VX2_1d` same. Join as `vx1_close = VX1 Settle`, `vx2_close`, `vx_basis_spot = VX1 - VIX`, `vx_curve_1_2 = VX2 - VX1` (all as-of `T-1` per §3.4).

---

## 8. Quick Reference — Current Zone Geometry (for intuition)

For ES at 7000, VIX 15, `m=1.0`: `ev_a = 7000·15/√252/100 ≈ 66.1`, `ev_b = 7000·15/√365/100 ≈ 54.9`, zone `[54.9, 66.1]` above S (thickness 11.2). `m=0.25` zone is `[13.7, 16.5]` (thickness 2.8) — tight enough to be pierced by noise; its edge is less likely to be a clean reaction level unless reinforced by a quarter/fib. Under the §1.3 collapse this is `c=1.0` and `c=0.25` on the continuous `c` axis (with `c=0.8309` and `c=0.9155` for the `b` and `mid` edges).

---

## 9. Review Response (2026-08-30)

This revision addresses the 340-line verification against `scripts/libs_py/expected_volatility/` and `data/*.parquet`:

- **Blocking 1 (§1.1):** re-executed `compute_zone_ladders(6000,15)` — corrected `R_bottom 6047.1082` (was 6048.08) and `S_top 5952.8918` (was 5951.92); removed false "Matches exactly" claim.
- **Blocking 2 (§3.4 upsert key):** unified to the single key `(trading_day, session_id, ticker, vol_source, scale_mode, anchor_mode)` with `level_mode` as columns — removed contradictory 4-tuple bullet.
- **Blocking 3 (lookahead):** added §3.4 Leakage and as-of table; VIX pack is now as-of `T-1` (not `T`), `vix_chg_intraday` NULL for overnight rows, `anchor_mode=open/midday` not emitted for Asia/London.
- **Blocking 4 (feasibility):** scoped vol horse race to common window `2022-05-13→present` (~1,070 days, ≈ two 2-year windows) and flagged `VIX_1m` stale `2021-10-25→2025-12-31` gating `vix_midday`/`NY_PM_midday`/Q27.
- **Blocking 5 (VVIX file):** `VVIX_1d` is the daily join (2006-03-06→2026-08-28); `VVIX_1m` is 23 days intraday only.
- **Design 6 (one-parameter collapse):** §1.3 proves `b/a=0.830909…`, introduces 12 `c` constants and replaces discrete Q1–Q3 grading with a **continuous `c` sweep** (P0 now).
- **Design 7 (252 vs 365):** both defensible (CBOE calendar 365 vs trader 252); `b = a·0.8309` — single fit `k`, not DM.
- **Design 8 (close-to-close vs RTH):** noted 24h vs RTH overstatement; added `scale_mode` `sqrt_sess_over_1380` and `1380`-min trading day.
- **Design 9 (VIX percentages):** corrected `14.15→0.891%`, `11.76→0.741%`, `8.83→0.556%` (was 1.06%/0.88%/0.66% via √178.5).
- **Design 10 (log vs arith):** corrected VIX 30/m=1.5 to **arith ±198.4, log up +201.3 / down −195.6** (was up 198 / down 194).
- **Design 11 (holdout):** added §4.5 (20% chronological holdout, BH-FDR, N≥30 floor, pre-registration).
- **Smaller:** tiled sessions (added `Settlement` 16:00→17:00 → 1380 min), removed spurious maintenance-gap skip, added DST rule (~40 days), de-duplicated `NY_PM_midday`/`anchor_mode` and `level_mode` key vs columns, corrected size to ~27k rows/year/ticker (≈1.1M rows / 8–9M cells), expanded `vol_source` enum per family (VXN/RVX/OVX/GVZ etc.), fixed cross-refs (§3.4→§3.3 etc.), added third parquet `coverage.parquet`, and corrected README ordering (now `VIX1D < VOLI < VIX`).

