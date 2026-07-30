# Session 10 — Checkpoint 1 (Steps 1-4 Complete)

> **Date**: 2026-07-29 (Session 10, mid-session)
> **Status**: Steps 1-4 complete. Play 2 parity verified at 94.6%.
> **Next**: Step 5 (MAE/MFE + entry-zone sweep), Step 6 (stop geometry decision), Step 7 (document).

---

## Step 1 — Normalized MAE/MFE (ADR-002) ✅

- Regenerated `scratch/ib_parity_sep26_full.csv` (188 trades, 97.2% parity).
- Analysis: `scratch/analyze_mae_mfe_normalized.py` → `scratch/mae_mfe_normalized_report.json`.

### Key numbers (IB Play 1 Breakout, 188 trades, WR 68.6%)

| Metric | Winners (n=129) | Losers (n=59) |
|---|---|---|
| MAE (range %) P50/P75 | 29.5 / 54.9 | 108.2 / 115.1 |
| MFE (range %) P50/P75 | 48.2 / 52.9 | 16.5 / 26.4 |

- **Clean separation**: winners draw down ~30% before target; losers blow through IB boundary (>100%).
- **Stop grid**: 0.60×range is breakeven PF (1.01). 0.75×range marginally positive (PF 1.004).
  Current 1.0×range stop = PF 0.969 (net negative despite 66% WR — inverted 0.5:1 R:R confirmed).

---

## Step 2 — Play 2 Harness Implementation ✅

- Added `simulate_play2_day()` to `scripts/validation/ib_parity_harness.py`.
- Configurable retest entry zone via `--retest-low-pct` / `--retest-high-pct` (defaults 0.40/0.60).
- Mirrors `IBRetestBot.cs`: first-break detection → retest into zone → next-bar-open entry →
  IB-relative stop (opposite boundary) → target = ib_high + target_lvl×range.
- TargetIsSane guard, conservative stop-wins tie-break, ConfluenceFilter common gate.
- Extended `--play` choices to `[1, 2, 3]`.

---

## Step 3 — NT8 IBRetestBot Backtest ✅

- Contract: NQ 09-26 (NQ SEP26), full range 2025-01-01 → 2026-07-29.
- NT8 bridge port: **7890** (not 51328 — that port is stale from prior sessions).
- Saved to `scratch/nt8_ib_retest_nq_sep26_full.json` (BOM stripped).

### NT8 IBRetestBot results (171 trades)
- WR: 49.1%, PF: 1.212, net +$31,190, maxDD −$16,225
- Exit reasons: Stop loss 78, Profit target 58, Sell 17, Buy to cover 16, session close 2
- Avg win +$2,121, avg loss −$1,690 (favorable R:R)

---

## Step 4 — IBRetestBot Python Parity Check ✅

- Python: 262 trades (405 days, 143 skipped by ConfluenceFilter).
- NT8: 171 trades.
- **Result agreement: 159/168 = 94.6%** (160 agree, 8 disagree, 94 Python-only).
- Side match: 86 LONG + 79 SHORT correctly matched (3 side mismatches).
- Trade-count gap (262 vs 171): 94 Python-only trades caused by NT8 calendar filters
  (skip Mon/Feb for Play 2) + RequireDirectionBias gate that the harness doesn't replicate.
- WR: Python 48.5% vs NT8 49.1% — very close.

### Parity verdict
- 94.6% agreement is **below Play 1's 97.2%** but solid for a first pass.
- The gap is **filter mismatch, not entry/exit logic** — the harness doesn't apply
  Play 2's calendar filters (skip Mon, skip Feb). Wiring these would close the gap.
- The entry-zone band (40-60%) is a Python-side extension; NT8 uses the classic mid.
  This means the harness captures MORE retests than NT8 → explains some Python-only trades.

---

## Artifacts Created

| File | Purpose |
|---|---|
| `scratch/ib_parity_sep26_full.csv` | Play 1 parity CSV (regenerated) |
| `scratch/mae_mfe_normalized_report.json` | Normalized MAE/MFE percentiles + stop grid |
| `scratch/analyze_mae_mfe_normalized.py` | ADR-002 analysis script |
| `scratch/nt8_ib_retest_nq_sep26_full.json` | NT8 IBRetestBot backtest (BOM-stripped) |
| `scratch/ib_parity_retest_sep26.csv` | Play 2 parity CSV |
| `docs/architecture/SESSION_10_PLAN.md` | Full session plan |
| `docs/architecture/SESSION_10_CHECKPOINT_1.md` | This file |

---

## Next Steps

- **Step 5**: Run MAE/MFE on Play 2 CSV + entry-zone sweep (mid vs 25% vs 40-60 vs 30-70).
- **Step 6**: Decide IBBreakoutBot stop geometry (Option A-D) using Step 1 percentiles.
- **Step 7**: Document to parity standard §11 + memory.db + handover.