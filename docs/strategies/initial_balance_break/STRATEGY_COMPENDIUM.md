# IB Time-Range Strategy Compendium

Each strategy is listed as: **name**, **preconditions**, **IF/THEN/ELSE algorithm**.
All time ranges are configurable via `config/ib_custom_ranges.yaml`.

**Label convention** (from `docs/plans/2026-07-24-ib-data-gathering-plan.md §10.15–10.17`):

| Prefix | Meaning | Range | Tested in backtest? |
|---|---|---|---|
| **E#** | Entry technique (building block) | E1–E21 | Subset (E5, E6, E8–E22 used in `ib_entry_modules.py`); grid uses `entry_variant`+`pullback_level` params |
| **S#** | Stop-loss technique (building block) | S1–S17 | Subset (S2 in `ib_optimal_stops.parquet`); grid uses `stop_loss_type` param (ib_opposite, ib_edge, fixed_pct) |
| **T#** | Take-profit technique (building block) | T1–T20 | Subset (T4, T5, T6, T14, T15 in `ib_exit_modules.py`); grid uses `tp_r_mult` param |
| **Play 1/2/3** | Canonical plays (breakout/retest/fade) | 1–3 | ✅ Yes — `ib_play_detail_{SYM}.parquet` |
| **bias_{name}** | Bias variant (spec column name) | 8 variants in §2.5 | 4 tested: `ib_close`, `fvg`, `fvg_inversion`, `confluence` (the `bias_source` param values) |

**Building block → backtest param mapping** (for evaluating test results):

| Building block | Backtest param value | Notes |
|---|---|---|
| E1/E2 break entries | `entry_variant="post_break"` | Combined under post_break |
| E3/E4 retest entries | `entry_variant="post_break"` + `pullback_level="fib_*"` | Pullback to fib level |
| E17 body-close | `entry_variant="post_break"` + `pullback_level="ib_edge"` | IB edge pullback |
| Pre-break #17/#63/#64 | `entry_variant="pre_break"` | Pre-break contraction |
| `pullback_level` | `fib_382`, `fib_50`, `fib_618`, `q_25`, `q_75`, `ib_edge` | Direct param |
| S1 opposite | `stop_loss_type="ib_opposite"` | Default |
| S2 MAE-calibrated | (in `ib_optimal_stops.parquet`, not in grid stops) | Reference only |
| `bias_close_dir` (B3) | `bias_source="ib_close"` | ✅ Tested |
| `bias_fvg` (B4) | `bias_source="fvg"` | ✅ Tested |
| `bias_fvg_ifvg` (B5) | `bias_source="fvg_inversion"` | ✅ Tested |
| `bias_combined`/confluence (B8/B9) | `bias_source="confluence"` | ✅ Tested |

**Untested building blocks** (in spec/code, not in backtest grid): E5–E22 entry modules (standalone), S2–S17 stops (except via `ib_optimal_stops` reference), T4/T5/T6/T14 exits (in `ib_exit_signals`, not wired to backtest grid), `bias_formation_firstreach`/`lasttouch`, `bias_fvg_rth`, `bias_fvg_1011`.

---

## Play 1 — IB Breakout (Continuation)

**Preconditions:** IB window closed; `ib_high`, `ib_low`, `ib_range` defined.

```
IF  bar closes above ib_high
THEN enter LONG at ib_high
     stop = ib_low
     target = ib_high + 1.0 × ib_range
     IF target hit (touch) THEN Win
     ELSE IF stop hit (touch) THEN Loss
     ELSE IF 16:00 ET THEN exit at close (timeout loss)

ELSE IF bar closes below ib_low
THEN enter SHORT at ib_low
     stop = ib_high
     target = ib_low − 1.0 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN exit at close (timeout loss)

ELSE  No-Setup
```

---

## Play 2 — IB Retest-Continuation (Mid Pullback)

**Preconditions:** First break has occurred (`first_break_dir ≠ 0`).

```
IF  first_break_dir = +1
    AND price touches ib_mid
THEN enter LONG at ib_mid
     stop = ib_low
     target = ib_high + 0.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF first_break_dir = −1
    AND price touches ib_mid
THEN enter SHORT at ib_mid
     stop = ib_high
     target = ib_low − 0.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## Play 3 — IB Fade-to-Mid (Mean Reversion)

**Preconditions:** IB window closed; `ib_mid` defined.

```
IF  price overshoots ib_high by 0.25 × ib_range (touch)
    AND a later bar closes back below ib_high
THEN enter SHORT at ib_high
     stop = ib_high + 0.5 × ib_range
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF price never returns to ib_high before 16:00 THEN No-Setup
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF price overshoots ib_low by 0.25 × ib_range (touch)
    AND a later bar closes back above ib_low
THEN enter LONG at ib_low
     stop = ib_low − 0.5 × ib_range
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF price never returns to ib_low before 16:00 THEN No-Setup
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## Pre-Break #17 — 5-Day Contraction Breakout

**Preconditions:** `ib_range_5d_contracting = True`; `pre_break_direction ≠ 0`.

```
IF  ib_range_5d_contracting = True
    AND pre_break_direction = +1
THEN enter LONG at first touch of ib_high
     stop = ib_low
     target = ib_high + 1.0 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_range_5d_contracting = True
    AND pre_break_direction = −1
THEN enter SHORT at first touch of ib_low
     stop = ib_high
     target = ib_low − 1.0 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## Pre-Break #63 — VCP 3-Day Contraction

**Preconditions:** `ib_vcp_3day_contracting = True`; `ib_vcp_setup = True`.

```
IF  ib_vcp_3day_contracting = True
    AND ib_vcp_setup = True
    AND pre_break_direction = +1
THEN enter LONG at VCP breakout
     stop = contraction low
     target = ib_high + 1.0 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_vcp_3day_contracting = True
    AND ib_vcp_setup = True
    AND pre_break_direction = −1
THEN enter SHORT at VCP breakout
     stop = contraction high
     target = ib_low − 1.0 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## Pre-Break #64 — VCP Volume Dry-Up

**Preconditions:** `ib_vcp_volume_ratio < 0.6`; (`ib_vcp_setup` OR `ib_vcp_3day_contracting`).

```
IF  ib_vcp_volume_ratio < 0.6
    AND (ib_vcp_setup OR ib_vcp_3day_contracting)
    AND pre_break_direction = +1
THEN enter LONG at the break
     stop = contraction low
     target = ib_high + 1.0 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_vcp_volume_ratio < 0.6
    AND (ib_vcp_setup OR ib_vcp_3day_contracting)
    AND pre_break_direction = −1
THEN enter SHORT at the break
     stop = contraction high
     target = ib_low − 1.0 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

**Pre-break direction rule:**
```
IF  ib_pre_telegraph_dir ≠ 0
THEN pre_break_direction = ib_pre_telegraph_dir
ELSE  pre_break_direction = ib_open_drive_dir
```

---

## E6 — Time-Qualified Sizing

**Preconditions:** `first_break_minutes` computed.

```
IF  first_break_minutes ≤ 15  THEN size = 1.0
ELSE IF first_break_minutes ≤ 75  THEN size = 0.5
ELSE IF first_break_minutes ≤ 210 THEN size = 0.0
ELSE IF first_break_minutes ≤ 270 THEN size = 0.5
ELSE  size = 0.0
```

---

## E8 — Failed-Breakout Reversal

**Preconditions:** `ib_high_swept` or `ib_low_swept` detected.

```
IF  ib_high_swept = True
    AND a later bar closes back below ib_high
THEN enter SHORT at ib_high
     stop = sweep high + 0.25 × ib_range
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_low_swept = True
    AND a later bar closes back above ib_low
THEN enter LONG at ib_low
     stop = sweep low − 0.25 × ib_range
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## E9 — Opening Drive

**Preconditions:** `ib_or5_broken_in_15` computed.

```
IF  ib_or5_broken_in_15 = True
    AND OR5 broke UP
THEN take Play 1 LONG (size = 1.0)
ELSE IF ib_or5_broken_in_15 = True
    AND OR5 broke DOWN
THEN take Play 1 SHORT (size = 1.0)
ELSE  skip Play 1
```

---

## E10 — Pre-IB Telegraph Filter

**Preconditions:** `ib_pre_telegraph_dir` computed.

```
IF  ib_pre_telegraph_dir = +1
THEN take only LONG breakouts; skip SHORT breakouts
ELSE IF ib_pre_telegraph_dir = −1
THEN take only SHORT breakouts; skip LONG breakouts
ELSE  trade both directions
```

---

## E11 — 80% Rule

**Preconditions:** `ib_pct_time_above_mid` computed; `first_break_dir` known.

```
IF  ib_pct_time_above_mid > 0.80
    AND first_break_dir = +1
THEN enter LONG on high break
     stop = ib_low
     target = ib_high + 1.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_pct_time_above_mid < 0.20
    AND first_break_dir = −1
THEN enter SHORT on low break
     stop = ib_high
     target = ib_low − 1.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  use standard Play 1
```

---

## E12 — ACD Hold

**Preconditions:** `ib_or_acd_a_held` computed.

```
IF  ib_or_acd_a_held = True
    AND ACD direction = +1
THEN take Play 1 LONG
     stop = ACD A-level
     target = ib_high + 1.0 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_or_acd_a_held = True
    AND ACD direction = −1
THEN take Play 1 SHORT (mirror)
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  skip
```

---

## E13 — VCP Setup

**Preconditions:** `ib_vcp_setup = True`.

```
IF  ib_vcp_setup = True
    AND break direction = +1
THEN enter LONG at VCP breakout
     stop = VCP contraction low
     target = ib_high + 1.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_vcp_setup = True
    AND break direction = −1
THEN enter SHORT at VCP breakout
     stop = VCP contraction high
     target = ib_low − 1.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## E14 — Single-Print Reclaim

**Preconditions:** `ib_has_upper_single_print` or `ib_has_lower_single_print` set.

```
IF  ib_has_upper_single_print = True
    AND price reclaims the single-print zone (close back above)
THEN enter LONG at the single-print zone
     stop = below single print
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_has_lower_single_print = True
    AND price reclaims the single-print zone (close back below)
THEN enter SHORT at the single-print zone
     stop = above single print
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## E15 — Sweep + Reclaim

**Preconditions:** `ib_sweep_reclaim_dir` computed.

```
IF  ib_sweep_reclaim_dir = +1
THEN enter LONG at the reclaimed level
     stop = sweep low
     target = ib_high + 0.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_sweep_reclaim_dir = −1
THEN enter SHORT at the reclaimed level
     stop = sweep high
     target = ib_low − 0.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## E17 — Body-Close Break

**Preconditions:** `ib_high_body_close` or `ib_low_body_close` computed.

```
IF  ib_high_body_close = True
THEN take Play 1 LONG with full size
     stop = ib_low
     target = ib_high + 1.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_low_body_close = True
THEN take Play 1 SHORT with full size
     stop = ib_high
     target = ib_low − 1.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  standard Play 1
```

---

## E18 — Wick-Dominant Fade

**Preconditions:** `ib_high_wick_pct` or `ib_low_wick_pct` computed.

```
IF  ib_high_wick_pct > 20
THEN enter SHORT at ib_high (fade the rejection)
     stop = ib_high + 0.25 × ib_range
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_low_wick_pct > 20
THEN enter LONG at ib_low (fade the rejection)
     stop = ib_low − 0.25 × ib_range
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

---

## E22 — CISD Confirmation

**Preconditions:** `ib_cisd_dir` and `first_break_dir` computed.

```
IF  ib_cisd_dir = +1
    AND first_break_dir = +1
THEN take Play 1 LONG with full size
     stop = ib_low
     target = ib_high + 1.5 × ib_range
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_cisd_dir = −1
    AND first_break_dir = −1
THEN take Play 1 SHORT with full size (mirror)
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_cisd_dir = +1
    AND first_break_dir = −1
THEN CISD inversion — take Play 3 fade LONG
     stop = ib_low − 0.5 × ib_range
     target = ib_mid
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE IF ib_cisd_dir = −1
    AND first_break_dir = +1
THEN CISD inversion — take Play 3 fade SHORT (mirror)
     IF target hit THEN Win
     ELSE IF stop hit THEN Loss
     ELSE IF 16:00 ET THEN timeout loss

ELSE  No-Setup
```

**Entry priority (when multiple fire):**
```
1. E22 CISD break confluence
2. E11 80% rule long/short
3. E15 sweep + reclaim
4. E13 VCP setup
5. E8 failed-breakout reversal
6. E12 ACD hold
7. E9 opening drive
8. E10 pre-IB telegraph
9. E14 single-print reclaim
10. E17 body-close break
11. E18 wick-dominant fade
12. E22 CISD standalone confirm
```

---

## S2 — MAE-Calibrated Stop

**Preconditions:** `ib_optimal_stops` row exists for this (symbol, session, play, target_lvl).

```
IF  target_lvl = 0.25R
THEN stop = 1.24 × ib_range  (R:R 0.20:1)
ELSE IF target_lvl = 0.50R
THEN stop = 0.66 × ib_range  (R:R 0.75:1)
ELSE IF target_lvl = 0.75R
THEN stop = 0.44 × ib_range  (R:R 1.71:1)
ELSE IF target_lvl = 1.00R
THEN stop = 0.30 × ib_range  (R:R 3.31:1)
ELSE  stop = ib_opposite (default)
```

---

## S15 — Trailing by IB Fractions

**Preconditions:** position is open.

```
IF  price moves +0.5 × ib_range favorable
THEN trail stop to entry + 0.25 × ib_range

ELSE IF price moves +1.0 × ib_range favorable
THEN trail stop to entry + 0.50 × ib_range

ELSE IF price moves +1.5 × ib_range favorable
THEN trail stop to entry + 0.75 × ib_range
```

---

## T4 — Partial Ladder Exit

**Preconditions:** position is open.

```
IF  price reaches +0.5 × ib_range favorable
THEN sell 1/3 at +0.5R, move stop to breakeven

IF  price reaches +1.0 × ib_range favorable
THEN sell 1/3 at +1.0R, move stop to +0.5R

IF  price reaches +1.5 × ib_range favorable
THEN let runner ride with trailing stop (S15)
```

---

## T5 — VWAP Cross Exit

**Preconditions:** `ib_vwap` exists for the session.

```
IF  position = LONG
    AND bar closes below ib_vwap
THEN exit at the VWAP cross

ELSE IF position = SHORT
    AND bar closes above ib_vwap
THEN exit at the VWAP cross
```

---

## T6 — Liquidity Target Exit

**Preconditions:** `pdh`/`pdl`/`p12_high`/`p12_low` in daily_context.

```
IF  position = LONG
    AND price touches the nearest upper liquidity level (pdh or p12_high)
THEN exit at the liquidity level

ELSE IF position = SHORT
    AND price touches the nearest lower liquidity level (pdl or p12_low)
THEN exit at the liquidity level
```

---

## T14 — Time-Decay Ladder Exit (also covers mid-magnet fast)

**Preconditions:** time-decay curve exists for this (symbol, session, play).

```
IF  elapsed_minutes > P50(expected time-to-target)
    AND target not yet hit
THEN exit 50% at market

IF  elapsed_minutes > P75(expected time-to-target)
    AND target not yet hit
THEN exit remaining at market

IF  ib_mid_revisited_post_break = True
    AND ib_mid_revisit_post_break_minutes < 15
THEN exit at market immediately  (mid-magnet fast — trend failure signal)
```

**Exit priority:**
```
1. T14 mid-magnet fast (if active)
2. T5 VWAP cross
3. T4 partial ladder (default)
```

**Note:** The mid-magnet fast exit is implemented as `exit_mid_magnet_fast` in
`ib_exit_modules.py` but is not separately cataloged in §10.17. It is treated
here as a sub-case of T14 (time-decay) since both are probabilistic exits.

---

## T15 — Session-Boundary Exit (ADR-020)

**Preconditions:** session ∈ {NY AM IB, NY PM IB}.

```
IF  time = 15:50 ET
THEN exit at market
```

---

## bias_formation_firstreach — Formation First-Reach Bias

**Backtest param:** not tested (`bias_source` values: ib_close, fvg, fvg_inversion, confluence)

**Preconditions:** IB window closed; `ib_high` and `ib_low` timestamps known.

```
IF  ib_low timestamp < ib_high timestamp
THEN bias = +1 (bullish)
ELSE IF ib_high timestamp < ib_low timestamp
THEN bias = −1 (bearish)
ELSE  bias = sign(ib_close − ib_open)
```

---

## bias_formation_lasttouch — Formation Last-Touch Bias

**Backtest param:** not tested

**Preconditions:** IB window closed; last-touch timestamps known.

```
IF  last-touch time of ib_low > last-touch time of ib_high
THEN bias = +1 (bullish)
ELSE IF last-touch time of ib_high > last-touch time of ib_low
THEN bias = −1 (bearish)
ELSE  bias = sign(ib_close − ib_open)
```

---

## bias_close_dir — Close Direction Bias  (`bias_source="ib_close"`)

**Backtest param:** `bias_source = "ib_close"` ✅ Tested

**Preconditions:** IB window closed.

```
bias = sign(ib_close − ib_open)
```

---

## bias_fvg — First FVG Bias  (`bias_source="fvg"`)

**Backtest param:** `bias_source = "fvg"` ✅ Tested

**Preconditions:** A 5m FVG formed inside the IB window.

```
IF  bullish FVG formed (bar[2].high < bar[0].low)
THEN bias = +1
ELSE IF bearish FVG formed (bar[2].low > bar[0].high)
THEN bias = −1
ELSE  bias = 0
```

---

## bias_fvg_ifvg — FVG Inversion (IFVG) Bias  (`bias_source="fvg_inversion"`)

**Backtest param:** `bias_source = "fvg_inversion"` ✅ Tested

**Preconditions:** `bias_fvg` produced a bias; outcome window active.

```
Start with bias_fvg.
IF  bullish FVG AND a bar closes below fvg_low (3-bar pattern extreme)
THEN invert bias to −1
ELSE IF bearish FVG AND a bar closes above fvg_high
THEN invert bias to +1
ELSE  keep bias_fvg
# Single inversion only. A wick beyond the pattern extreme is a sweep, NOT an inversion.
```

---

## bias_fvg_rth — FVG 09:30 Bias (NY AM only)

**Backtest param:** not tested

**Preconditions:** Session = NY AM IB.

```
bias = direction of first FVG forming from 09:30 ET
```

---

## bias_fvg_1011 — FVG 10:00 Macro Bias (NY AM only)

**Backtest param:** not tested

**Preconditions:** Session = NY AM IB.

```
bias = direction of first FVG forming in 09:50–11:00 ET (ICT 10:00 macro window)
# Level persists for entries after 11:00; bias fixed at first formation.
# Leakage guard: count only extension hits AFTER the bias is finalized.
```

---

## bias_combined — Combined Bias

**Backtest param:** not tested directly (weights configurable)

**Preconditions:** Multiple bias variants enabled with weights.

```
bias = sign(Σ weight_i × bias_variant_i)
```

---

## confluence — Confluence Bias  (`bias_source="confluence"`)

**Backtest param:** `bias_source = "confluence"` ✅ Tested

**Preconditions:** Validated filter stack from Phase 4c.

```
IF  validated filter stack agrees on direction = +1
THEN bias = +1
ELSE IF validated filter stack agrees on direction = −1
THEN bias = −1
ELSE  bias = 0  (no trade)
```

---

## Regime Router — Day-Type Selector

**Preconditions:** `ib_range_5d_pctile` (trailing 60-day) computed; POC, break speed known.

```
IF  ib_range_5d_pctile < 30%
    AND first_break_minutes ≤ 15
    AND POC near IB extreme
THEN regime = TREND
     suggested_play = Play 1 (breakout, full size)

ELSE IF ib_range_5d_pctile ∈ [30%, 50%]
    AND moderate break speed
    AND POC near ib_mid
THEN regime = NORMAL
     suggested_play = Play 2 (retest, half→full size)

ELSE IF ib_range_5d_pctile > 50%
    AND slow/no break
    AND POC centered
THEN regime = RANGE
     suggested_play = Play 3 (fade)

ELSE IF is_fomc_day
    OR is_nfp_day
    OR is_cpi_day
    OR is_ism_day
    OR mid_lock_frac > 0.85
    OR overnight direction contradicts telegraph
THEN regime = SKIP
     suggested_play = none

ELSE  regime = NORMAL
```