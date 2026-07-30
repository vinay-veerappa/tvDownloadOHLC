# Session Handover — IB Strategy Profitability & Retest Decision

> **Date**: 2026-07-29 (Session 10, end)
> **Status**: Steps 1-7 COMPLETE. Play 2 selected over Play 1. Decision: Option D.
> **Next session**: Implement the Play 1→Play 2 bias filter; close the Play 2 parity gap (calendar filters).

---

## 1. What Was Accomplished This Session

### Step 1 — Normalized MAE/MFE (ADR-002) ✅
- Regenerated `scratch/ib_parity_sep26_full.csv` (the handover's referenced CSV was missing).
- Analysis script: `scratch/analyze_mae_mfe_normalized.py` → `scratch/mae_mfe_normalized_report.json`.
- **Play 1 winners**: MAE P50=29.5% / P75=54.9% of range (barely retrace before target).
- **Play 1 losers**: MAE P50=108% / P75=115% (blow through IB boundary).
- Stop grid (censoring-aware): 0.60×range breakeven (PF 1.01, E[R] +0.005); current 1.0×range net negative (PF 0.969, E[R] −0.021). Inverted 0.5:1.0 R:R confirmed.

### Step 2 — Play 2 Harness ✅
- Added `simulate_play2_day()` to `scripts/validation/ib_parity_harness.py`.
- Configurable retest entry zone: `--retest-low-pct` / `--retest-high-pct` (defaults 0.40/0.60).
- Mirrors `IBRetestBot.cs`: first-break → retest into zone → next-bar-open entry → IB-relative stop → target = ib_high + target_lvl×range.
- Extended `--play` choices to `[1, 2, 3]`.

### Step 3 — NT8 IBRetestBot Backtest ✅
- Contract: NQ 09-26, full range 2025-01-01 → 2026-07-29.
- **NT8 bridge port: 7890** (NOT 51328 — that port is stale from prior sessions).
- Results: 171 trades, WR 49.1%, PF 1.212, net +$31,190, maxDD −$16,225.
- Saved to `scratch/nt8_ib_retest_nq_sep26_full.json` (BOM stripped).

### Step 4 — Play 2 Python Parity Check ✅
- Python 262 trades vs NT8 171. **Result agreement: 159/168 = 94.6%**.
- Gap (94 Python-only): NT8 calendar filters (skip Mon/Feb for Play 2) + RequireDirectionBias gate not replicated in harness.

### Step 5 — Play 2 MAE/MFE + Entry-Zone Sweep ✅
- Play 2 has **cleaner separation** than Play 1: winner MAE P75=38.2% vs loser P50=66.3% (28-pt gap).
- Zone sweep: **mid_point wins** (E[R] +0.0865, precision filter). 40-60 band captures +16% trades but lower E[R] (dilutive).
- PF < 1 for ALL zones is misleading (1:2 R:R caps PF at ~0.56); trust E[R].

### Step 6 — Stop Geometry Decision ✅ (via agent loop)
- **Option D**: Abandon Play 1 standalone; redirect to Play 2.
- Play 1 best E[R] (+0.005) is 17× worse than Play 2 (+0.087) and statistically zero vs txn costs.
- Option A (raise target to 1.0) is dead — winner MFE P50=48%, so 1.0 target kills 90% of winners.
- Recycle Play 1's 68.6% first-close WR as a directional bias filter for Play 2.
- Fallback if Play 1 mandated: Option C at stop=0.60×range (breakeven).

### Step 7 — Documentation ✅
- Appended §13 to `NT8_PYTHON_PARITY_STANDARD.md` (full normalized results + decision).
- Created `SESSION_10_CHECKPOINT_1.md`, `SESSION_10_CHECKPOINT_2.md`, `SESSION_10_PLAN.md`.
- Updated `/memories/ib_parity_state.md` with Session 10 status.
- Wrote memory.db entry [128] (INSTRUCTION, all findings + decision).

---

## 2. The Strategic Decision (Option D)

**Play 1 (breakout) is not profitable as a standalone strategy.** Its inverted R:R (risk 1.0×range to make 0.5×range) means even at 66% WR it's net negative. The only positive-E[R] stop placements (0.60, 0.75) are loss-trimming artifacts, statistically indistinguishable from zero against transaction costs.

**Play 2 (retest) is the winner.** It has:
- E[R] +0.0865 at mid-point entry (17× Play 1's best)
- Cleaner winner/loser separation (28-pt MAE gap vs Play 1's illusory 16-pt gap)
- NT8 PF 1.212, net +$31,190 over 19 months
- The mid-point entry acts as a precision filter — only high-conviction retests qualify

**Next step**: implement the Play 1→Play 2 bias filter (gate Play 2 entries on Play 1's break quality: break_vs_avwap_0930 aligned, trend NOT misaligned).

---

## 3. Plan for Next Session

### Step 1: Close the Play 2 parity gap (94.6% → 98%+)
- Wire NT8's Play 2 calendar filters (skip Mon, skip Feb) into the harness's `simulate_play2_day`.
- Replicate the `RequireDirectionBias` gate (if enabled in NT8 IBRetestBot).
- Re-run parity — expect ~98%+ matching Play 1's ceiling.

### Step 2: Implement the Play 1→Play 2 bias filter
- Add a `--bias-from-break` flag to the harness that gates Play 2 entries on the Play 1 break quality (break_vs_avwap_0930 alignment + trend NOT misaligned).
- Compare Play 2 E[R] with and without the bias filter — does it lift E[R] above 0.087?
- If yes, implement the same gate in `IBRetestBot.cs` (NT8 side) and verify parity.

### Step 3: Walk-forward validation (Open Item #3)
- Split the 19-month window into in-sample (2025) / out-of-sample (2026).
- Verify Play 2 mid-point E[R] holds out-of-sample.

### Step 4: RiskGatekeeper live verification (Open Item #2)
- The TODO from memory [85]: potentialLoss uses ATR (8× over-estimate) instead of range-based stop distance.
- Override `GetEstimatedRiskDistance()` in `IntradayStrategyBase` to use the actual range-based stop distance.
- Test on a live SIM account before funded deployment.

---

## 4. File Inventory

| Resource | Path | Status |
|---|---|---|
| Parity standard | `docs/architecture/NT8_PYTHON_PARITY_STANDARD.md` | §13 added ✅ |
| Session plan | `docs/architecture/SESSION_10_PLAN.md` | Created ✅ |
| Checkpoint 1 | `docs/architecture/SESSION_10_CHECKPOINT_1.md` | Steps 1-4 ✅ |
| Checkpoint 2 | `docs/architecture/SESSION_10_CHECKPOINT_2.md` | Steps 5-6 ✅ |
| Parity harness | `scripts/validation/ib_parity_harness.py` | Play 2 added ✅ |
| Play 1 parity CSV | `scratch/ib_parity_sep26_full.csv` | Regenerated ✅ |
| Play 1 MAE/MFE report | `scratch/mae_mfe_normalized_report.json` | Created ✅ |
| Play 1 analysis script | `scratch/analyze_mae_mfe_normalized.py` | Created ✅ |
| NT8 retest JSON | `scratch/nt8_ib_retest_nq_sep26_full.json` | Created (BOM stripped) ✅ |
| Play 2 parity CSV | `scratch/ib_parity_retest_sep26.csv` | Created ✅ |
| Play 2 zone sweep report | `scratch/play2_mae_mfe_and_zone_sweep_report.json` | Created ✅ |
| Play 2 analysis script | `scratch/analyze_play2_mae_mfe_and_zone_sweep.py` | Created ✅ |
| Persistent memory | `/memories/ib_parity_state.md` | Session 10 added ✅ |
| Shared memory | `.agent/memory.db` entry [128] | Written ✅ |

---

## 5. Critical Context (do NOT re-derive)

- **Testing contract**: NQ 09-26 (NQ SEP26) — NOT NQ 03-26 or MNQ.
- **NT8 bridge port**: 7890 (NOT 51328 — stale).
- **Parity is COMPLETE**: do NOT re-investigate EMA/AVWAP/TrendMisaligned (§8-§11).
- **Play 1 is net negative** (PF 0.969, E[R] −0.021). Decision: Option D — abandon standalone.
- **Play 2 is the winner** (NT8 PF 1.212, E[R] +0.087 at mid). Adopt mid_point entry.
- **PF < 1 for Play 2 is misleading** (1:2 R:R caps PF); trust E[R].
- **All MAE/MFE in normalized %** (ADR-002): price % and IB range %, NOT absolute points.
- **Stop grid censoring**: loser MAE is censored at the 1.0×range stop; winner MAE is uncensored.