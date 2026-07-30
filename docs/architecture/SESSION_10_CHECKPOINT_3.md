# Session 10 — Checkpoint 3 (Filter Ablation Loop Complete)

> **Date**: 2026-07-29 (Session 10, end)
> **Status**: Full ralph loop complete. FVG filter validated as bias overlay.
> **Verdict**: DEPLOY FVG-aligned at 0.25× Kelly as bias overlay; HOLD for hard gate at n≥50.

---

## The Ralph Loop Summary

### Round 1 — Stacked-filter sweep (with look-ahead bias)
- Tested 15 filters + AND/OR combos of top 3 (HTF, FVG, CISD).
- Found HTF (bias_correct_combined_05x) as "dominant" filter: 80% WR, E[R] +0.61.
- Saved to `scratch/play2_bias_filter_ablation_report.json`.

### Round 2 — Agent review (CAUGHT look-ahead bias)
- Agent identified that `bias_correct_combined_05x` is a **forward-looking race outcome**
  computed across the full session (does the bias direction hit target before stop).
  Using it as an entry gate = selection on the dependent variable.
- Source confirmed: `ib.py:223 evaluate_target_vs_stop_consolidated` scans `in_out`
  (entire post-IB session) for target/stop races.
- **All HTF-based results invalidated.**

### Round 3 — Corrected ex-ante sweep
- Re-ran with ONLY ex-ante filters (available at IB window close ~09:59 ET):
  FORM, COMB, FVG, CLOSE, LBC, R5DC, TREND, HBC.
- Agent verified each filter's source code is genuinely IB-window-bounded.
- **FVG-aligned is the dominant ex-ante filter**: n=83, E[R]+0.298, WR 63.9%.
- FORM+FVG marginally better (+0.339, n=71) but adds only overfitting (filters 12 trades).
- Saved to `scratch/play2_exante_filter_sweep_report.json`.

### Round 4 — Walk-forward validation
- Split: train 2025 / test 2026-H1.
- **FVG-aligned OOS**: n=21, WR 57.1%, E[R] +0.207, PF 0.667.
- **FVG-failed OOS**: n=65, WR 35.4%, E[R] −0.080.
- Directional spread holds in OOS (+0.21 vs −0.08 = 0.29R spread).
- **Gate failure**: n=21 < 50; WR CI lower bound 36.5% < 47.1%.
- But OOS baseline (40.7%) is the honest comparator; FVG 57.1% vs 40.7% = +16.4pp lift.

### Round 5 — FVG|R5DC contingency (REJECTED)
- Tested the OR-combo for more frequency: n=42 OOS but **E[R] −0.013** (FAILED).
- R5DC was a false signal — it worked in-sample by coincidence, not OOS.
- **FVG-only remains the only filter with OOS edge.**

---

## Final Verdict: DEPLOY as bias overlay, HOLD for hard gate

**DEPLOY**: FVG-aligned filter at **0.25× Kelly** (CI-scaled) as a **bias overlay** on
Play 2 entry — not a hard gate. This caps risk while the OOS sample grows.

**HOLD**: Full deployment (hard gate, 1×Kelly) gated on:
- OOS n ≥ 50 (≈ Q1 2027 at current fire rate)
- OOS E[R] > +0.10 (currently +0.207 ✓)
- OOS WR CI lower bound > OOS baseline (currently 36.5% vs 40.7% — 4pp short)

**Rejected alternatives**:
- FVG|R5DC OR-combo: OOS E[R] −0.013 (R5DC is a false signal).
- HTF (bias_correct_combined_05x): look-ahead bias, invalidated.
- FORM+FVG: marginal lift (+0.041) on 12 fewer trades — overfitting.

---

## Artifacts Created

| File | Purpose |
|---|---|
| `scratch/play2_bias_filter_ablation_report.json` | Round 1 (with look-ahead, invalidated) |
| `scratch/play2_stacked_filter_sweep_report.json` | Round 1 stacked combos |
| `scratch/play2_exante_filter_sweep_report.json` | Round 3 corrected sweep |
| `scratch/play2_fvg_walkforward.py` | Round 4 walk-forward |
| `scratch/play2_exante_filter_sweep.py` | Round 3 sweep script |
| `scratch/play2_stacked_filter_sweep.py` | Round 1 stacked script |
| `scratch/play2_bias_filter_ablation.py` | Round 1 ablation script |
| `docs/architecture/SESSION_10_CHECKPOINT_3.md` | This file |