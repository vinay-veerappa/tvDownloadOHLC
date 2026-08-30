# Expected Volatility Zones — Quant Research & Data Plan

> Goal: determine **which volatility-implied levels actually matter** for intraday ES (and NQ) day trading, how to trade them, and whether the current zone construction (252 vs 365, multipliers, close-anchor) is optimal.
>
> Audience: quant trader building statistics → probabilities → rule set. Data-first, not opinion-first.

---

## 1. Verification: Are Current Calculations Accurate?

### 1.1 Pine math (as ported — `core.py:36-40`)

```
a = VIX / sqrt(252) / 100        # "trading-day" 1σ
b = VIX / sqrt(365) / 100        # "calendar-day" 1σ

for m in {1.0, 1.5, 0.5, 0.25}:
    R_top(m)    = S + S*a*m
    R_bottom(m) = S + S*b*m
    R_mid(m)    = (R_top + R_bottom)/2
    S_top(m)    = S - (R_bottom - S)   # mirror
    S_bottom(m) = S - (R_top - S)
    S_mid(m)    = (S_top + S_bottom)/2
```

`S` = settlement anchor (default: prior-day close < 16:00 ET, see `settlements.py:35`, `README.md:114`).

**Manual check** (S=6000, VIX=15): `R_top(1.0)=6056.69`, `R_bottom(1.0)=6048.08`, `S_top(1.0)=5951.92`, `S_bottom(1.0)=5943.31`. Matches `compute_zone_ladders()` exactly. Vectorised path `compute_zone_dataframe()` identical.

### 1.2 Quant assessment

| Item | Verdict |
|---|---|
| `a = VIX/sqrt(252)/100` | **Correct** for 1 trading-day expected move. VIX is quoted annualized to 30-day SPX vol on a 252-trading-day year. 1σ RTH move ≈ `S * VIX / sqrt(252) / 100`. |
| `b = VIX/sqrt(365)/100` | **Approximate / heuristic.** Dividing an *annualized trading-day* vol by `sqrt(365)` mixes bases. True calendar-day vol ≈ `a * sqrt(252/365)` only if variance were uniform across calendar days (it isn't — weekends/holidays have near-zero variance). The Pine author uses `b` to create a **zone between trading-day and calendar-day attenuation** — thickness ≈ `S*m*(a-b)` ≈ 17% of the expected move. Treat as an intentional uncertainty band, not a formal DTE model. |
| Zone vs single level | The zone `[R_bottom, R_top]` *is* the DTE ambiguity. Top = aggressive (1 trading-day vol), bottom = conservative (1 calendar-day vol). Mid is an artifact of averaging the two, not a separate vol model. |
| Arithmetic vs log levels | Pine uses **arithmetic** `S ± S*σ*m` (symmetric in points). A **log / geometric** variant would be `S*exp(±σ*m)` (symmetric in log-returns). For typical ES conditions (VIX 12–20, m≤1) the gap is <1 pt — noise. At VIX 30 / m=1.5 the gap widens to ~3 pts on the far side and introduces **asymmetry** (up move > down move in points). Log is theoretically cleaner for percentage-based SD (avoids negative-price pathology, respects compounding). Whether it forecasts better is empirical — add as a parallel column set and horse-race it; see §3.1. |
| DTE scaling | For a true DTE horizon `T` (in trading days), expected move ≈ `S * VIX / 100 * sqrt(T/252)` — or better, interpolated from the term structure (VIX1D=1d, VIX9D=9d, VIX=30d, VIX3M=90d). The indicator **fixes T=1**. For 0DTE intraday decay the static box overstates afternoon vol — should decay as `sqrt(remaining_session / RTH_duration)` if you want an intraday clock. |
| VOLI / VIX1D reuse | `VOLI` and `VIX1D` are also **annualized** (CBOE/Nasdaq convention), so reusing `a,b` keeps magnitudes comparable. If you wanted a *true* 1-day forecast from VIX1D, it would be `S * VIX1D/100 / sqrt(252)` only if VIX1D is quoted on 252 base (CBOE docs: yes, same annualisation). Verified locally: Dec-30 ES session VIX=14.15 → 1σ ≈ 1.06%, VOLI=11.76 → 0.88%, VIX1D=8.83 → 0.66% — ordering sensible. |
| Settlement S | Pine `close_day = close[1]` (prior daily bar close). Equivalent is prior trading day's last print < 16:00 ET (our cutoff). The `toggle` variant (`open` of `session.isfirstbar_regular`) uses today's 09:30 regular open — a 17-hr fresher anchor. Neither is "right"; which forecasts better is an empirical question. |

**Bottom line:** arithmetic is faithfully ported and internally consistent. Whether 365-denominator, fixed T=1, or the 4 multipliers are *optimal for trading* is not a math question — needs the hit/reversal statistics below.

---

## 2. What We Need to Answer (Prioritised Questions)

Group your research so every column in the parquet earns its keep.

### P0 — Does the construction work at all?
1. **Hit rate by rung**: P(touch during RTH | m) for m ∈ {0.25,0.5,1.0,1.5,2.0?}. Is 0.25 noise, 1.5 unattainable?
2. **Zone vs edge vs mid**: conditional on touch, does price *respect* top/bottom/mid differently? Metrics: reversal rate, median adverse excursion beyond level, time spent inside zone.
3. **Thickness utility**: does staying *inside* the zone predict consolidation vs breakout? Or should we collapse each zone to a single level (`mid` or `a`-leg)?

### P1 — Is the anchor right?
4. **Close vs open anchor**: compare `S_close = close[1]` vs `S_open = today 09:30 open` vs `S_vwap = prior RTH VWAP`. Which anchor centres realized RTH range better? (mean absolute error, hit symmetry R vs S).
5. **Prior-day vs overnight-inclusive settlement**: does including the 16:00–09:30 Globex drift in S improve or hurt? (Our current cutoff excludes it by design — test the alternative.)
6. **Intra-day re-anchor**: would a rolling anchor (e.g. overnight VWAP at 09:30) beat a static prior-close?

### P2 — Is the vol input right?
7. **Vol source horse race — the ES question**: `VIX` (30d) vs `VIX1D` (1d) vs `VOLI` (Nasdaq SPX vol) vs `VIX9D` (9d) vs `VIX3M` (90d) vs term-interpolated IV (e.g. `sqrt((1/30)*VIX^2)`-family or CBOE term-structure fit) vs realized 20d vol — which `a` best predicts `|RTH return|`? Use MAE/R², hit-rate calibration (`P(|return| ≤ m·EV)` vs Normal `N(m)`), and Diebold-Mariano on forecast errors. Control for denominator (§1.2) by holding it fixed; then swap denominators. Data note: local `VIX1D_1d`/`VOLI_1d` are daily-only (fine — anchor is daily); `VIX9D_1d`/`VIX3M_1d` already captured as `_1d.parquet` — extend the `vol_source` enum accordingly.
7b. **Arithmetic vs log levels**: Pine is arithmetic `S*(1 ± σm)` (symmetric in points). Log variant is `S*exp(±σm)` (symmetric in returns, asymmetric in points: at VIX 30 / m=1.5, up 198 pts vs down 194 pts — 4 pts wider). For VIX 12–20 / m≤1 the gap is <1 pt and irrelevant. Add choice `level_mode ∈ {arith, log}` as a parallel column set in `sessions.parquet` (`R_top_arith_m` vs `R_top_log_m`) and horse-race on §4.1 metrics. Expect log to win marginally in high-vol regimes and when measuring thin near-the-money reaction precision.
8. **252 vs 365 vs sqrt(DTE)**: calibrate denominator / horizon scaling. Does `sqrt(1/365)` add value over `sqrt(1/252)`? Does `sqrt(remaining_time)` intraday decay tighten levels?
9. **Term-structure signal**: does VIX − VIX1D spread (contango/backwardation) or VIX/VIX1D ratio modulate zone reliability? E.g. backwardation → realized > implied → zones pierce more often.

### P3 — What is the *reaction* when price is mid-zone?
10. **Confluence premium** — when an EV zone overlaps a:
    - **Quarter level** (00/25/50/75 per `QUARTERS_THEORY.md` — the "psychological" grid),
    - **Fib of prior range** (38.2/50/61.8 of prior RTH or overnight range projected from S),
    - **Prior HOD/LOD / overnight H/L / VWAP / IB high-low**,
    
    does reaction probability jump? Quantify lift over baseline EV-only.
11. **Price-level vs zone-level**: mid-zone reactions — are they actually quarter/fib/VWAP levels *inside* the zone stealing the credit? Decompose via logistic regression with zone + quarter + fib distance as features.
12. **Reaction definition**: what counts as a reaction? Need operational thresholds: e.g. ≥ 0.25R reversal and hold ≥15 min, or failure to close beyond zone by >1× zone thickness.

### P4 — Session & regime effects
13. **Session clock**: when do touches occur (09:30–10:30 vs 10:30–14:00 vs 14:00–16:00)? Does early touch fade → trade differently than late touch breakout?
14. **Overnight gap regime**: gap-up through R zones vs gap-down through S zones — does the *untouched opposite side* become a magnet later?
15. **Vol regime / trend vs range** (tie to `QUARTERS_THEORY.md` trending vs contradicting Asia/London combos, or VIX quintile): are EV zones mean-reverting in low vol and breakout in high vol?

### P5 — Multi-session & intraday split (Asia / London / NY AM vs NY PM)

The current indicator is RTH-only (09:30–16:00 ET). The research question generalizes: **does an EV-anchored zone work for any session, and should the anchor/vol scale with session length?**

16. **Session transfer**: do EV zones anchored at the *prior NY close* (16:00 ET) predict the subsequent **Asia** (18:00–03:00 ET) and **London** (03:00–09:30 ET) ranges with the same hit/reaction profile as RTH? Or does each session need its own anchor (Asia anchored at London close, London at Asia close)? Test both and compare MAE / `P(touch)` calibration.
17. **Session-scaled EV**: VIX-implied daily move is for ~24h (or RTH 6.5h, depending on interpretation). For a shorter session of duration `T_sess`, expected move ≈ `S * σ * sqrt(T_sess / T_daily)` under GBM. Does scaling `a,b` by `sqrt(session_minutes / 390)` (RTH 390 min) or `sqrt(session_minutes / 1440)` (calendar) tighten Asia/London/NY-PM zones usefully vs unscaled daily boxes? Treat scaling base as a tunable and horse-race it.
18. **NY AM vs NY PM split**: is the morning (09:30–12:00) statistically different from afternoon (12:00–16:00) for EV utility? E.g. AM = high informed volume, more reversals at outer rungs; PM = drift/decay, more holds. Compute `P(touch)`, `P(reversal|touch)`, `max_pierce` separately.
19. **Mid-day re-anchor — should we recompute at 12:00 ET?** Two candidates to horse-race:
    - **Static** (Pine-faithful): one anchor at 09:30, one vol read, zones fixed all day.
    - **Rolling mid-day**: at 12:00 ET re-read `S_mid = 12:00 price`, `V_mid = VIX at 12:00` (or 5-min VWAP), and recompute *remaining-session* zones scaled by `sqrt(remaining_minutes / 390)`. This decays the PM box and re-centres on the realized AM drift.
    
    Question: does the re-anchored PM zone raise `P(reversal|touch)` or reduce `max_pierce` vs static? And does it help to also **condition on AM outcome** (e.g. AM already tagged `R_1.0` → PM fade the opposite side)? Measure lift and whether the improvement survives transaction-cost / whipsaw of the reset.

### P6 — VIX ecosystem pack (extends P2; shared across strategies)

VIX as a 30d annualized SPX vol is one projection — the surrounding VIX ecosystem tells you **whether to trust it and how wide to make it**. All features below are computable from already-captured parquets and are intentionally **strategy-agnostic** (reuse for mean-reversion, breakout, sizing, regime filters elsewhere).

20. **VIX percentile / rank**: `pctl_63d`, `pctl_252d` of VIX_T vs trailing history. Filters every hit/reaction stat: does `P(reversal|touch)` at VIX p90 differ from p10? Is outer 1.5σ only fadeable when VIX is mid-rank?
21. **Term-structure slope** — `VIX - VIX9D`, `VIX - VIX3M`, `VIX1D - VIX`, `VIX/VIX3M` (local `VIX9D_1d`, `VIX3M_1d`, `VIX1D_1d` already captured). Contango (VIX < VIX3M) = complacent, zones hold; backwardation (VIX > VIX3M or VIX1D > VIX) = stress, outer rungs pierce — quantify the moderator effect on `P(close beyond | pierce)`.
22. **Vol-of-vol (VVIX)** — `VVIX_T` and `VVIX/VIX` (`VVIX_1m` already local). High VVIX = VIX itself jumpy → widen stop beyond zone top or shrink size; low VVIX → tighter fade. Test VVIX as interaction in `logit(P(reaction))`.
23. **Variance risk premium (VRP)** — `VRP_T = VIX_T - RV20_T` where `RV20 = sqrt(252)*std(log ES returns, 20d)` from `ES1_1m`. VRP >0 (IV expensive) → fades at EV edges work; VRP <0 → vol expansion, favor breakout beyond 1σ. Shared signal for any IV-vs-realized strategy.
24. **VIX momentum / change** — `Δ1d = VIX_T - VIX_{T-1}`, `Δintraday = VIX_midday - VIX_open`, 5d slope. Session tilt: VIX spiking into London predicts larger NY realized and lower `P(reversal|touch)` in AM.
25. **Interpolated 1d IV** — variance-linear interpolation of the cash curve to exactly 1 trading day: `IV1d^2 = w*VIX1D^2 + (1-w)*VIX9D^2` (or VIX9D/VIX spline). Horse-races the single-VIX `a` as the *true* 1d forecast vs 30d proxy — directly answers §2 Q7 with a more accurate numerator.
26. **VIX/SPX (or VIX/ES) correlation regime** — `corr(log ES returns, ΔVIX, 20d)`. Normally ≈ -0.8 to -0.9; breakdown flags vol-regime shift where EV zones lose calibration.
27. **Intraday VIX drift** — slope of VIX 09:30→16:00 vs `realized remaining range`. Tests §4.3 decay: does VIX bleeding through the day make static AM zones overstate PM? Also a standalone signal for PM drift.
28. **VIX futures term premium (when futures feed lands — see §6)** — front-month basis `VX1 - VIX`, curve slope `VX2 - VX1`, roll cost. Futures basis is a cleaner term-structure than cash indices and the tradable expression of VRP. Planned column family `vx_basis_*` gated on futures capture.

---

## 3. Data Plan — Parquet Feature Store

Two derived parquets under `data/expected_volatility/` (derived domain per `CLAUDE.md`):

### 3.1 `sessions.parquet` — one row per session window (primary analysis table)

Granularity: `trading_day × session_id × ticker × vol_source × anchor_variant`. One trading day emits **multiple rows** (RTH, Asia, London, NY_AM, NY_PM, and an optional `NY_PM_midday` re-anchored row). ~5–6× the RTH-only row count, still cheap (~1.5k rows/year/ticker/source).

Trading-day convention (your view — CME equity index futures day): a **trading day** runs **18:00 ET (T-1) → 17:00 ET (T)** and is filed under the **RTH date T** (so Mon 18:00 → Tue 17:00 = Tue trading day). All sessions below belong to the same `trading_day`; `session_date` in earlier drafts is renamed `trading_day` for clarity.

Session catalog (window in `America/New_York`, inclusive start, exclusive end; all windows tile the trading day without gaps):

| `session_id` | Window ET (on trading day T) | Duration | Typical anchor `S` | Vol scaling question |
|---|---|---|---|---|
| `Asia` | 18:00 (T-1) → 03:00 (T) | 540 min | prior RTH close <16:00 ET (T-1) *and* variant: prior session close | does NY close predict Asia? |
| `London` | 03:00 (T) → 09:30 (T) | 390 min | same two anchor variants | does NY/Asia close predict London? |
| `NY_AM` | 09:30 (T) → 12:00 (T) | 150 min | same `S` as RTH | AM slice of RTH |
| `NY_PM` | 12:00 (T) → 16:00 (T) | 240 min | same `S` as RTH (static) | PM slice — compare AM vs PM |
| `NY_PM_midday` | 12:00 (T) → 16:00 (T) | 240 min | `S_mid = 12:00 price` + `V_mid` re-read, scaled by `sqrt(240/390)` | mid-day re-anchor candidate (§2 Q19) |
| `RTH` | 09:30 (T) → 16:00 (T) | 390 min | prior close <16:00 ET (`settlement_close`) | baseline — no scaling |
| `Overnight` | 18:00 (T-1) → 09:30 (T) | 930 min | same as RTH anchor | Asia+London pooled — overnight drift vs EV |

`Overnight` is a convenience rollup (Asia+London combined) for gap analysis; Asia and London remain separately queryable.

Time-bucket convention (see §3.4): primary bucket = **5 min** (`bucket_5m`), reporting rollup = **15 min** (`bucket_15m`). Both are derived from `minutes_since_trading_day_open` (0 at 18:00 T-1) and from `minutes_since_session_open` (0 at session start) — see schema below.

| Column | Source / Logic | Purpose |
|---|---|---|
| `trading_day` | ET date T of the RTH (the CME trading-day label) | key — replaces earlier `session_date` |
| `session_id` | one of the catalog above | key |
| `ticker` | `ES1!` / `NQ1!` | key |
| `vol_source` | `VIX` / `VOLI` / `VIX1D` / `VIX9D` / `VIX3M` / `term_interp` | key |
| `level_mode` | `arith` / `log` | level construction (§1.2 Q7b) |
| `scale_mode` | `unscaled` / `sqrt_sess_over_RTH` / `sqrt_sess_over_1440` | session-scaling horse race (§2 Q17) |
| `anchor_mode` | `close` / `open` / `midday` / `vwap_rth` | anchor horse race (§2 Q4, Q19) |
| `settlement_close` | `close_day` (prior close <16:00 ET, T-1) | anchor A |
| `settlement_midday` | 12:00 ET price/VWAP on T (only for `NY_PM_midday`) | anchor for re-anchored PM |
| `settlement_open` | first regular open ≥09:30 ET (toggle path) | anchor B for Q4 |
| `settlement_vwap_rth` | prior RTH VWAP (optional) | anchor C |
| `open_session` | open of `session_id` window | gap & anchor comparison |
| `vix_close`, `vix_midday` | vol index settlement analogues (`vix_midday` only for re-anchored) | vol source comparison |
| `ev_a`, `ev_b`, `ev_scaled` | `S*a`, `S*b`, scaled variant | base moves |
| For each `m∈{0.25,0.5,1.0,1.5,2.0}`: `R_top_m`, `R_bot_m`, `R_mid_m`, `S_top_m`, `S_bot_m`, `S_mid_m` | `core.compute_zone_dataframe` (with chosen `level_mode` and `scale_mode`) | zone geometry — two parallel sets arith/log |
| `prior_rth_high/low/range`, `overnight_high/low/range` | from 1m OHLC | fib base + gap regime |
| `fib_R_382/500/618`, `fib_S_382/500/618` | `S ± fib * prior_rth_range` | fib confluence; compare to EV |
| `q_up_1`, `q_dn_1`, `q_grid` | nearest quarter levels to S (per `QUARTERS_THEORY.md`) | quarter confluence |
| `session_high/low/close/range`, `session_vwap` | realised for `session_id` window | outcome |
| For each level (EV edges, fibs, quarters): `touched`, `first_touch_min_session`, `first_touch_min_trading_day`, `first_touch_bucket_5m_session`, `first_touch_bucket_5m_trading_day`, `first_touch_bucket_15m_session`, `first_touch_bucket_15m_trading_day`, `max_pierce_pts`, `pierce_bars`, `close_beyond`, `reversal_pts_15m/60m`, `reversal_hit` | computed from 1m bars of `session_id` window | hit/reaction stats — **bucket ids are the primary time dimension** (§3.4) |
| `realized_move_abs`, `realized_vol_session` | `|close-open|/S`, `std(log returns)` over session | vol forecast calibration — denominator is session length |
| `regime_vix_quintile`, `regime_trend_range` | VIX percentile / Asia-London combo | stratification |
| **VIX ecosystem pack** (§2 Q20–Q28, shared — strategy-agnostic) | | |
| `vix_pctl_63d`, `vix_pctl_252d` | percentile rank of `vix_close` vs trailing 63d / 252d | regime filter for any strategy |
| `vix_term_slope_1d_30d` | `VIX - VIX1D` | term slope — contango vs backwardation |
| `vix_term_slope_9d_30d` | `VIX - VIX9D` | 9d→30d slope |
| `vix_term_slope_30d_90d` | `VIX - VIX3M` | 30d→90d slope |
| `vix_ratio_1d_30d` | `VIX1D / VIX` | normalized term premium |
| `vvix`, `vvix_vix_ratio` | `VVIX_T`, `VVIX_T / VIX_T` | vol-of-vol |
| `vrp_20d` | `VIX_T - RV20_T` (RV20 = `sqrt(252)*std(log ES ret, 20d)`) | variance risk premium |
| `vix_chg_1d` | `VIX_T - VIX_{T-1}` | momentum |
| `vix_chg_intraday` | `VIX_midday - VIX_open` (or close) | intraday drift |
| `iv_1d_interp` | variance-linear interpolation to exactly 1 trading day (w*VIX1D² + (1-w)*VIX9D², etc.) | true 1d forecast |
| `vix_spx_corr_20d` | `corr(log ES ret, ΔVIX, 20d)` | correlation regime |
| `rv20` | trailing 20d realized vol (annualized) | standalone RV input for Q7 horse race |

*These VIX columns are computed once per `trading_day` and joined to every `session_id` row for that day — so a London touch can be conditioned on `vix_term_slope_1d_30d` from the same trading day's open without re-scanning. Reusable by any downstream strategy (sizing, regime filter, breakout vs fade selector).*

*Key change:* `sessions.parquet` is trading-day-centric and multi-session. Every analysis in §4 runs **per `session_id`** (and pooled), so we can answer "does 0.5σ mean the same thing in Asia as in RTH?" directly.

### 3.2 `bars.parquet` — per-minute enriched tape (optional second table, for deeper work)

Granularity: 1 row per 1-min bar, filed under its **`trading_day`** (18:00 T-1 → 17:00 T). Partitioned by `ticker/trading_day` (or `ticker/year/month`) if needed. Each bar carries **both clocks**: `minutes_since_trading_day_open` (0 at 18:00 T-1) and `minutes_since_session_open` (0 at session start) plus their bucket ids (see §3.4). Overlapping sessions are not duplicated — the bar lives once; session membership is a filter on `minutes_since_trading_day_open`.

| Column | Meaning |
|---|---|
| `ts` (UTC), `trading_day` (ET date T), `session_id` (derived from trading-day clock) | time — see §3.4 |
| `minutes_since_trading_day_open`, `bucket_5m_trading_day`, `bucket_15m_trading_day` | trading-day clock (0 at 18:00 T-1) |
| `minutes_since_session_open`, `bucket_5m_session`, `bucket_15m_session` | session clock (0 at session start) |
| `open/high/low/close/volume` | OHLCV |
| `dist_to_R_top_1.0`, `dist_to_S_bot_1.0`, … (all EV edges, both arith/log) | signed distance in points and in units of contemporary ATR/EV |
| `in_zone_m` (bool per m) | inside any EV box aligned to that bar's trading day |
| `dist_to_nearest_quarter`, `quarter_label` | per `QUARTERS_THEORY.md` |
| `dist_to_fib`, `dist_to_vwap`, `dist_to_overnight_HL` | competing levels |
| `confluence_score` | count of levels within ±X pts — the "stack" |

Use `bars.parquet` for: time-to-touch survival curves per 5-min bucket, intraday decay, and order-flow around levels. `sessions.parquet` alone answers most P0–P2 questions; `bars.parquet` makes P4–P5 granular.

### 3.3 Trading-day & bucket conventions (normative)

**Trading day.** A CME equity-index trading day **T** is `18:00 ET on calendar day T-1` (inclusive) → `17:00 ET on calendar day T` (exclusive, last bar 16:59 ET). Mon 18:00 → Tue 17:00 = Tue trading day (matches your desk convention). Holidays: if the 18:00 open is missing, the day still exists with fewer bars.

**Bucket ids.** For any timestamp `t` in `America/New_York`:
- `minutes_since_trading_day_open = floor((t - 18:00_{T-1}) / 1 min)`  (0 … 1379; 23h trading day = 1380 min; 17:00–18:00 is the 60-min maintenance gap — no bars, bucket ids skip it).
- `bucket_5m_trading_day  = floor(minutes_since_trading_day_open / 5)`  (0 … 275, 5-min primary). Label: `"18:00-18:05"`, …, `"16:55-17:00"`.
- `bucket_15m_trading_day = floor(minutes_since_trading_day_open / 15)` (0 … 91, reporting rollup — exactly 3× the 5-min buckets).
- `minutes_since_session_open` / `bucket_5m_session` / `bucket_15m_session` are analogous with origin at the session window start (e.g. RTH 09:30 → 0).

Both clocks are stored so analysis can pivot either way: "5-min bucket across the trading day" (0900 heatmap) and "5-min bucket within session" (session-relative).

**Reporting default:** 5-min buckets are the **stored truth**; initial reporting rolls them to 15-min (mean / sum) for readability. No information is lost.

### 3.4 Build Logic & Dependencies

```
raw:  data/ES1_1m.parquet, data/NQ1_1m.parquet,
      data/VIX_1m.parquet, data/VOLI_1d.parquet, data/VIX1D_1d.parquet,
      data/VIX9D_1d.parquet, data/VIX3M_1d.parquet, data/VVIX_1m.parquet,
      (later: VIX futures — see §6)
  │
  ├─► settlements.py :: build_daily_settlements() — 16:00 ET cutoff already handled,
  │                     daily-only vol via _settlements_from_daily()
  ├─► core.py        :: compute_zone_dataframe() — all m rungs + log variant
  ├─► NEW: quarters.py :: quarter_grid(S)  (from QUARTERS_THEORY)
  ├─► NEW: fibs.py      :: fib_projection(S, prior_range)
  ├─► NEW: vix_features.py :: pctl, term slopes, VRP, VVIX ratio, iv_1d_interp
  └─► NEW: session_stats.py :: touches, pierces, reversals (extend backtest.zone_edges/box_sessions)
         │
         └─► data/expected_volatility/sessions.parquet (+ bars.parquet)
```

*Script location per repo standard* (`scripts/<domain>/`): `scripts/expected_volatility/build_features.py` (produces both parquets, idempotent, append-friendly) and `scripts/expected_volatility/analyze.py` (reads parquets → stats).

*Implementation notes:*
- Trading-day key is `(trading_day, session_id, ticker, vol_source, level_mode, scale_mode, anchor_mode)` — upsert on rerun; backfill with `--from / --to`.
- Fuse `data/{ticker}_1m.parquet` (2006–2024) + `data/live/live_storage_-{ticker}.parquet` (2025→now) via `scripts/utils/fused_data_loader.py:load_fused_data()` for full history; for validation slices use live storage directly.
- Daily vol dailies are 16:00 ET close stamps → `build_daily_settlements` daily path handles normalization; intraday VIX uses 16:00 cutoff path.
- Missing-data policy: require `settlement_close` and `vix_close` non-null to emit a session row; log gaps and keep a `coverage.parquet` sidecar for audit.
- Idempotency: keyed by `(trading_day, session_id, ticker, vol_source)` — upsert on rerun; backfill with `--from / --to`.

---

## 4. Analysis Plan — From Parquet to Trading Rules

### 4.1 Descriptive statistics (per Q1–Q3, per session)

For each level (EV edge, mid, quarter, fib), **per `session_id`** (RTH/Asia/London/NY_AM/NY_PM/Overnight, plus pooled), reported in **both 5-min and 15-min buckets** (§3.3):
- **Touch rate** `P(touch)`, **time-to-touch** distribution (Kaplan-Meier), **first-touch clock** histogram — computed on `bucket_5m_trading_day` (primary) and rolled to `bucket_15m_trading_day` for reporting (mean/sum). Both `bucket_5m_session` (session-relative) and `bucket_5m_trading_day` (trading-day heatmap) views.
- **Reaction rate** `P(reversal ≥ k×ATR | touch, bucket)` for k ∈ {0.25,0.5,1.0} and horizons 15/60/240 min, **stratified by touch bucket** (e.g. touches in bucket `09:30-09:35` vs `14:00-14:05`); **disposition** (reversal vs continuation vs hold) per bucket.
- **Pierce profile**: median `max_pierce`, `P(close beyond level | pierce)` — per bucket to see if late-session pierces hold more often.
- Calibration: scatter `predicted EV (scaled by session length)` vs `realized |session return|`; MAE, bias, R² by vol source/denominator **and by session**.

Initial reporting rolls the 5-min truth to 15-min for readability; no information is lost — 5-min remains the join key.

### 4.2 Comparative / causal

- **Zone vs single level**: compare `P(reaction)` at `R_top` vs `R_mid` vs `inside zone` (any point within `[R_bot,R_top]`). Does the zone add value over its mid?
- **Anchor horse race**: paired test (close vs open vs vwap) on `|S - session_mid|` and `touch symmetry`; Diebold-Mariano for forecast MAE.
- **Denominator horse race**: `252` vs `365` vs `252*sqrt(T/30)` vs term-interpolated — which `a` best predicts realization? Use out-of-sample rolling window.
- **Vol source for ES (§2 Q7)**: repeat calibration per `vol_source ∈ {VIX,VIX1D,VOLI,VIX9D,VIX3M,term_interp}`; report R² lift over 30d VIX baseline.
- **Arith vs log (§2 Q7b)**: compare `R_top_arith` vs `R_top_log` on the same metrics; stratify by VIX quintile (expect log edge only in high-vol tails).
- **Confluence lift**: `P(reaction | EV alone)` vs `P(reaction | EV ∧ quarter within d)` vs `P(reaction | EV ∧ fib within d)`. Lift = ratio; test with Fisher exact. Then joint model:
  ```
  logit(P(reaction)) ~ dist_to_EV + dist_to_quarter + dist_to_fib + dist_to_vwap + vol_regime + gap_size
  ```
  Coefficients = attribution of reaction to each level type when mid-zone. Random forest / SHAP for non-linear interaction.
- **Term-spread moderator**: does VIX − VIX1D (or VIX/VIX1D) predict zone pierce rate? Test as interaction in the logit.

### 4.3 Session & decay (now covers §2 Q16–Q19)

- **Asia / London transfer (§2 Q16)**: fit `predicted EV` with `S = prior NY close` vs `S = prior session close` per session; report which anchor wins per session on MAE/R² and `P(touch)` calibration. Expect Asia to be noisier (fewer informed participants) — zones may be wider than needed without the `sqrt(T_sess/T_daily)` scaling.
- **Session scaling (§2 Q17)**: compare `unscaled daily EV` vs `sqrt(session_minutes/390)` vs `sqrt(session_minutes/1440)` per session. Does scaling bring `P(|return| ≤ 1σ)` back toward ~68% for short sessions?
- **NY AM vs NY PM (§2 Q18)**: same metrics split at 12:00 ET. Test `P(reversal|touch)` differs AM vs PM (χ²); if AM is more mean-reverting and PM more trending, the rule sheet should split them.
- **Mid-day re-anchor (§2 Q19)**: paired comparison `NY_PM` (static anchor) vs `NY_PM_midday` (re-anchored at 12:00 with `S_mid`, `V_mid`, `sqrt(240/390)` scaling). Metrics: `P(reversal|touch)`, `max_pierce`, `P(close beyond)`. Cost of the reset is whipsaw when AM already consumed the move — test conditional on AM outcome (`AM tagged R_1.0` → fade-the-opposite-side in PM?).
- **Intraday decay (general)**: fit `realized_remaining_range ~ a * sqrt(remaining_minutes / 390)` vs static `a` within any session. Does time-scaled EV tighten levels usefully as the close approaches?
- **Session archetypes**: cluster sessions by gap size, overnight range, VIX quintile; compute `P(touch)` and `P(reversal|touch)` per cluster **per session** → adaptive rule (e.g., "in high-VIX gap-down London, fade S_1.5 is weak; trade breakouts").

### 4.4 From statistics to day-trading rules

Translate findings into a **condition → setup → invalidation** sheet **per session** (RTH/Asia/London/NY_AM/NY_PM), e.g.:

| Session | Condition | Setup | Invalidation | Expected R:R (from data) |
|---|---|---|---|---|
| `RTH` | Price enters `R_0.5` zone ∧ quarter level inside zone ∧ first touch before 11:00 ET | Fade to `S` (mean reversion), target `R_mid` or `S`, stop beyond `R_top + buffer` | Close beyond `R_top` by >0.3× zone thickness | e.g. 62% reversal, median 8 pts adverse, 14 pts favorable |
| `RTH` | Close beyond `R_1.0` with volume expansion | Breakout continuation to `R_1.5` | Reclaim of `R_1.0` within 15 min | e.g. 54% continuation |
| `NY_PM` (mid-day re-anchored) | AM already tagged `R_1.0` and PM re-anchored zone re-tagged | Fade opposite side / hold for mean reversion to `S_mid` | ... | ... |
| `Asia` / `London` | Gap through `S_1.0` pre-open, untagged `R_0.5` (session-scaled) | Magnet: drift to `R_0.5` by session end | ... | ... |

Every row must cite a parquet-derived probability **for its session** — no cross-session intuition.

---

## 5. Delivery Milestones

| Phase | Output | Effort |
|---|---|---|
| **A. Verify & instrument** | This doc + `core.py`/`settlements.py` already validated (Dec-30 ES 6955.0, VIX 14.15 etc.). Add quarter/fib helpers (reuse `QUARTERS_THEORY.md` grid). | 1 session |
| **B. Build `sessions.parquet`** | `scripts/expected_volatility/build_features.py` + `data/expected_volatility/sessions.parquet` for ES 2006→present (fused + live). Smoke-check vs existing `scan_expected_volatility`/`touch_stats`. | 1–2 sessions |
| **C. Build `bars.parquet` (optional)** | Same script, flag `--bars`. Needed for decay & microstructure questions. | 0.5 session |
| **D. Analysis pack** | `scripts/expected_volatility/analyze.py` → markdown report + figures answering P0–P2 (hit rates, anchor/vol horse races). Answers which levels to keep. | 1–2 sessions |
| **E. Confluence & intraday** | Logistic/SHAP model + decay fit → answers P3–P4; produces the rule sheet. | 1–2 sessions |
| **F. Live integration** | Wire selected levels into the trader narrative / signal engine (e.g. `scripts/trader/`) only after D–E show edge. | separate track |

Start with **ES × VIX/VOLI/VIX1D** on `sessions.parquet`; expand to NQ/CL/RTY once the pattern is proven.

---

## 6. Open Decisions to Lock Before Building

1. **Reaction threshold**: fix now (e.g. reversal ≥ 0.5× zone thickness or ≥ 4 pts ES and hold ≥15 min) so analysis is comparable across rungs. Make it a parameter in the parquet builder, not hard-coded.
2. **Quarter grid definition**: confirm tick size / quarter step per instrument (ES 1.00? NQ 1.00? Use the grid from `QUARTERS_THEORY.md` consistently).
3. **History depth for calibration**: use full 2006→present but report rolling 2-year windows (regime changes — vol regime in 2020/2022 vs 2024/2025 differ markedly).
4. **DTE ambition**: for v1 keep T=1 fixed (as Pine does); treat sqrt(DTE) scaling as a v2 experiment gated on P2 results.

---

## 7. VIX Futures — Next Exploration

VIX futures (CBOE/CFE: VX, front month VX1 / VX2 …) are the *tradable* term structure. Cash VIX term slopes (`VIX - VIX9D`) in §2 Q21/§3.1 use indicative CBOE indices; the futures curve (`VX1 - VIX` basis, `VX2 - VX1` slope) is the cleaner signal and the direct expression of variance risk premium.

**Why it matters for this project:**
- Cash indices are computed from SPX options; futures embed financing/carry and settlement timing — the futures basis is what vol desks actually trade to express contango/backwardation.
- `VX1 - VIX` (spot–front basis) and `VX2 - VX1` (front curve slope) as interaction terms in §4.2 improve the zone-pierce model beyond cash `VIX - VIX9D`.
- Futures settlement times differ (VIX futures settle Wed 08:00 ET) — futures-implied expected move needs expiry-aware scaling.

**Data to source from CBOE/CFE endpoints (to investigate):**

| Source | What | Endpoint / note |
|---|---|---|
| CBOE Delayed Quotes API | VX futures OHLCV (1m or daily) for `VX1`, `VX2` continuous | `https://cdn.cboe.com/api/global/delayed_quotes/...` (check `tradingview` or `cboe.com` delayed chart API — same family used for cash indices) |
| CFE Historical Data | Daily settlement CSVs for VX futures (all expiries) | `https://www.cboe.com/us/futures/market_statistics/historical_data/` — bulk download, stitch continuous front-month series |
| CBOE VIX Central | VIX futures term structure snapshot (daily) | `http://vixcentral.com/` (scrapable) or CBOE `https://ir.cboe.com/...` file |

**Proposed columns (when feed lands, gated):** `vx1_close`, `vx2_close`, `vx_basis_spot = VX1 - VIX`, `vx_curve_1_2 = VX2 - VX1`, `vx_basis_roll_cost`. Join on `trading_day` same as cash VIX pack; analysis per §4.2 adds them as moderator columns — no change to the EV zone construction itself, purely a signal layer.

**Next step:** probe the three endpoints above (confirm delay, history depth, 1m vs daily granularity), pick the one covering 2006→present with minimal stitching, and extend `scripts/expected_volatility/build_features.py` to optionally ingest `data/VX_1m.parquet` continuous series (same fusion + 16:00 ET cutoff logic as cash).

---

## 8. Quick Reference — Current Zone Geometry (for intuition)

For ES at 7000, VIX 15, `m=1.0`: `a=0.0595%`? Let's anchor: `ev_a = 7000*15/ sqrt(252)/100 ≈ 66.1 pts`, `ev_b = 7000*15/ sqrt(365)/100 ≈ 54.9 pts`, zone `[54.9, 66.1]` above S (thickness 11.2 pts). `m=0.25` zone is `[13.7, 16.5]` (thickness 2.8 pts) — tight enough to be pierced by noise; its edge is less likely to be a clean reaction level unless reinforced by a quarter/fib.

