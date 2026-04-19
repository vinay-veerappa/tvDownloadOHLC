# Phase 3 Validation - Label Registry Extraction

**Date:** 2026-04-18
**Scope:** Validate parity after moving label push/merge ownership from indicator-local logic to PineDrawingLib.
**Change set:**
- `refactor(daily-ny-levels): extract label registry push/merge into PineDrawingLib` (`32fcd985`)
- `fix(daily-ny-levels): rename reserved label registry parameter` (`e2a1ee85`)
- `docs(daily-ny-levels): record phase2 label-registry implementation status` (`cab68964`)
- `refactor(daily-ny-levels): add labeled stat-line semantic helper` (`8ba54d52`)

---

## 1. Automated validation (completed)

### 1.1 Compile/diagnostics
- `scripts/indicators/daily-ny-levels/DailyNYLevelsAnalytics.pine`: **no errors**
- `scripts/indicators/daily-ny-levels/lib/PineDrawingLib.pine`: **no errors**

### 1.2 Structural parity checks
- Indicator now uses library registry push API:
  - `PDL.f_label_registry_push(...)` via local helper `f_push_label(...)`.
- Indicator now uses library merge+draw API:
  - `PDL.f_label_registry_draw_merged(...)`.
- Indicator now uses semantic draw helper API:
  - `PDL.f_draw_labeled_stat_line(...)` for repeated "draw stat line + enqueue right-edge label" flow.
- Legacy local label arrays (`lbl_ys`, `lbl_texts`, `lbl_colors`, `lbl_xs`) are removed from active code path.
- Overlap suppression (`f_near_any(...)` against tactical Y levels) remains active for stat-level suppression behavior.

### 1.3 Working tree and baseline
- Repo state at validation start: clean (`main...origin/main`).
- Validation executed on the committed refactor baseline.

---

## 2. Manual chart parity checks (required for full sign-off)

> These checks require TradingView runtime rendering and cannot be fully validated in local static tooling.

### 2.1 Right-edge label parity
- Verify stat labels (Confirm/Target2/Stretch/Avg/Med) appear at same anchor prices as pre-refactor.
- Verify tactical labels (Breakout Activation, Pullback Activation, BO Cashflow/Confirm/Pivot, Max Reversal, Invalidation) align at prior positions.

### 2.2 Merge-on-proximity parity
- With `Label Merge Threshold` unchanged, verify close-proximity labels merge exactly as before.
- Confirm merged text delimiter remains `" | "` and order is stable by insertion order.

### 2.3 Suppression parity
- Verify stat lines near tactical lines remain suppressed where overlap threshold is met.
- Confirm suppression remains label/line behavior consistent with prior logic.

### 2.4 Lifecycle and state
- Verify historical suffix behavior (for retained labels where applicable) remains unchanged.
- Confirm no label drift appears when stepping through live session transitions.

### 2.5 Symbol classes
- Validate at least one representative each:
  - ES/MES
  - NQ/MNQ
  - CL/MCL
  - GC/MGC
- Keep same template settings across checks.

---

## 3. Pass criteria

Phase 3 is considered complete when:
1. All automated checks remain green.
2. Manual parity checklist passes without geometry/content regressions.
3. Any observed drift is either fixed or documented as intentional with rationale.

---

## 4. Notes

- This phase validates behavior parity, not feature expansion.
- Canonical-template enforcement remains soft guidance by design for this stage.

## 5. Follow-on checkpoint (v3 split scaffolding)

A post-validation refactor checkpoint introduced local v3 split-library scaffolds without changing runtime imports:

- Commit: `127fa368`
- Scope: added `PineDrawingCore` + family draft libraries and migration checklists under `scripts/indicators/daily-ny-levels/lib/`
- Runtime impact: none (indicator still imports `vveerappa/PineDrawingLib/4` until split libraries are published)

