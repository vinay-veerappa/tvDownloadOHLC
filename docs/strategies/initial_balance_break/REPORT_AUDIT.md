# STRATEGY_STATISTICS.md Report Audit (2026-07-25)

## Current State
- File: `docs/strategies/initial_balance_break/STRATEGY_STATISTICS.md`
- Size: 1,342 lines, 12 sections
- Generated: 2026-07-25 (before BL-2, BL-5, BL-6, BL-7 fixes)
- Covers: NQ1, ES1, YM1, RTY1, CL1, GC1

## Issues Found

### CRITICAL: Report is stale — does not reflect BL-2/BL-5/BL-6/BL-7 fixes

The report was generated before the following fixes were applied:

1. **BL-2 (MAE stop R:R bug)** — §5 MAE-Calibrated Stops shows **old buggy values**:
   - `Stop (R)` column has values like 4.9644, 2.8949, 39.2054, 5.1571
   - These are `p95 / median_mae` (WRONG) — should be `p95 / target_lvl`
   - Fixed values would be: 0.25R target → 1.24R stop (not 4.96R)
   - CL1 Play 2 shows Stop=39.21R — nonsensical

2. **BL-7 (regime look-ahead bias)** — §3 Regime-Adjusted Statistics shows **old regime distribution**:
   - NQ1: trend 86,316 (52%), range 8,224 (5%) — look-ahead biased
   - New distribution: trend 19,632 (47%), range 6,251 (15%)
   - All regime WR/expectancy values are unreliable — they use the biased classifier

3. **BL-5/BL-6 (commission + ADR-020)** — not reflected in report at all
   - All expectancy values are pre-commission (inflated)
   - No mention of 16:00 forced exit impact

### MISSING: Backtest results section
- No §13 for PropFirmSimulator results (dollar P&L, MC pass rates, grades)
- NQ1 moderate grid results exist in `results/ib_backtest/ib_backtest_NQ1.json` but not in report
- No cross-reference between strategy stats and prop-firm viability

### MISSING: Empirical targets section
- `ib_empirical_targets.parquet` exists but not in report
- No §5.5 for Gunship-style percentile targets (FR-10/BL-3)
- Key finding (all NQ1 expectancies negative) not documented

### STRUCTURAL: Encoding issues
- Report has UTF-8 characters showing as mojibake (â instead of —, etc.)
- The `ib_strategy_report.py` generator needs `encoding='utf-8'` on output

### STRUCTURAL: No "Generated with fixes" header
- Report should note which fixes are applied
- Report should include generation timestamp with fix versions

## Recommended Changes

### 1. Regenerate the report (immediate)
Run the full pipeline with all fixes:
```powershell
.\.venv\Scripts\python.exe -m scripts.edgeful.ib_mae_stops --instruments NQ1,ES1,YM1,RTY1,CL1,GC1
.\.venv\Scripts\python.exe -m scripts.edgeful.ib_regime_classifier --instruments NQ1,ES1,YM1,RTY1,CL1,GC1
.\.venv\Scripts\python.exe -m scripts.edgeful.ib_strategy_report --instruments NQ1,ES1,YM1,RTY1,CL1,GC1
```

### 2. Add backtest results section (§13)
Add a new section to `ib_strategy_report.py` that reads `results/ib_backtest/ib_backtest_*.json` and produces:
- Top 10 candidates by return per instrument
- MC pass rate distribution (grade A/B/C/D/F counts)
- Det PASS count per prop firm profile
- Best config per instrument

### 3. Add empirical targets section (§5.5)
Add a section that reads `ib_empirical_targets_best.parquet` and shows:
- Best target/stop per session per play
- R:R ratio, WR, expectancy for each selection mode
- Key finding: all NQ1 expectancies negative

### 4. Fix encoding
Add `encoding='utf-8'` to the file write in `ib_strategy_report.py`

### 5. Add fix version header
Add to the report header:
```
**Fixes applied:** BL-2 (MAE R:R), BL-3 (empirical targets), BL-5 (commission), BL-6 (ADR-020 exit), BL-7 (regime look-ahead)
**Backtest fixes:** commission model, 16:00 ET forced exit, trailing regime classifier
```

### 6. Add commission-adjusted expectancy column
Add a column to all stats tables showing expectancy after $2.05/round-turn commission:
`exp_r_net = exp_r - commission_pct_r`

### 7. Add "Caveats" section
Document remaining limitations:
- All stats still in-sample (no walk-forward)
- Commission is approximate (% of notional, not fixed $)
- ADR-020 16:00 exit is in backtester but not in stats tables (stats use MAX_SEARCH=1440)
- Regime classifier uses trailing 5d percentile (no look-ahead) but stats may still reference old regime labels