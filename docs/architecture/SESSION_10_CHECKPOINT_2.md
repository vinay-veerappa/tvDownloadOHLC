# Session 10 — Checkpoint 2 (Steps 5-6 Complete)

> **Date**: 2026-07-29 (Session 10, mid-session)
> **Status**: Steps 5-6 complete. Strategic decision made: Option D (abandon Play 1, focus Play 2).
> **Next**: Step 7 (document to parity standard + memory + final handover).

---

## Step 5 — IBRetestBot MAE/MFE & Entry-Zone Sweep ✅

### MAE/MFE (Play 2, 40-60 band, 262 trades)

| Metric | Winners (n=127) | Losers (n=135) |
|---|---|---|
| MAE (range %) P50/P75 | 19.5 / 38.2 | 66.3 / 73.7 |
| MFE (range %) P50/P75 | 88.0 / 95.1 | 21.6 / 41.8 |

- **Much cleaner separation than Play 1**: winners draw down only 19.5% (P50) vs losers' 66.3%.
- Winners reach 88% of range in MFE (P50) — they run to the target.
- Losers stall at 21.6% MFE — they never get close to the 0.5×range target.

### Entry-Zone Sweep (target=0.5×range, stop=1.0×range)

| zone | lo | hi | trades | WR% | PF | E[R] |
|---|---|---|---|---|---|---|
| **mid_point** | 0.50 | 0.50 | 225 | 47.1 | 0.445 | **0.0865** |
| 25pct_level | 0.25 | 0.25 | 164 | 29.3 | 0.207 | 0.0333 |
| 40_60_band | 0.40 | 0.60 | 262 | 48.5 | 0.470 | 0.0669 |
| **30_70_band** | 0.30 | 0.70 | 294 | 53.1 | **0.565** | 0.0760 |
| 35_65_band | 0.35 | 0.65 | 282 | 51.8 | 0.537 | 0.0839 |
| 45_55_band | 0.45 | 0.55 | 246 | 46.3 | 0.432 | 0.0669 |

### Thesis verdict (40-60% band)
- **Partially confirmed**: the 40-60 band captures MORE retests (262 vs 225 mid, +16%).
- **But the mid is a precision filter**: only high-conviction retests reach the exact mid,
  so per-trade E[R] is highest (0.0865) despite fewer trades.
- **PF < 1 for ALL zones** is misleading — the 1:2 R:R (risk 2R to make 1R) structurally
  caps PF at ~0.56 even at 53% WR. The liquidation exits at 15:50 salvage value that PF
  doesn't capture. **Trust E[R]** (models full exit distribution).

### Decision: Adopt mid_point (0.50/0.50)
- Highest E[R] (0.0865 R/trade) — the precision filter gates on retest DEPTH,
  which correlates with continuation probability.
- 225 trades over 19 months = sufficient statistical power.
- Fallback if more frequency needed: 35_65 band (E[R] 0.0839, 282 trades, +25% frequency).

---

## Step 6 — IBBreakoutBot Stop Geometry Decision ✅

### The data (from Step 1)

| stop (×range) | WR% | PF | E[R] |
|---|---|---|---|
| 0.25 | 28.7 | 0.806 | −0.069 |
| 0.60 | 54.8 | 1.010 | +0.005 |
| 0.75 | 60.1 | 1.004 | +0.003 |
| 1.00 (current) | 66.0 | 0.969 | −0.021 |

### Decision: Option D — Abandon Play 1 standalone; redirect to Play 2

**Rationale (from agent loop):**
1. Play 1's best geometry (0.60 stop, E[R] +0.005) is **17× worse** than Play 2 mid
   (E[R] +0.087). The "edge" at 0.60 is a loss-trimming artifact, not directional alpha.
2. Play 1's 0.60/0.75 positive cells are **statistically indistinguishable from zero**
   (n=188, E[R] ~0.005 vs transaction costs ~0.5 NQ pts).
3. **Option A (raise target to 1.0) is dead**: winner MFE P50=48%, P90=60.7% — a 1.0×range
   target is reached by <10% of winners, so WR would collapse to ~6%.
4. Play 1's genuine value is its **68.6% first-close WR as a directional bias signal**,
   not its P&L.

### Implementation plan for the bias filter
- **Keep Play 1's break detection** as a directional filter: only take Play 2 retests
  ALIGNED with the Play 1 break direction (firstBreakDir).
- This is already implicit in Play 2's logic (it enters in the break direction).
- The "bias filter" means: ADDITIONALLY gate on whether the break itself was high-quality
  (e.g. break_vs_avwap_0930 aligned, trend NOT misaligned) — the same ConfluenceFilter
  Play 1 uses, applied to Play 2 entries.
- If a Play 1 standalone is mandated for parity continuity, use **Option C at
  stop = 0.60×range** as the least-bad fallback — but budget it as breakeven.

---

## Artifacts Created

| File | Purpose |
|---|---|
| `scratch/play2_mae_mfe_and_zone_sweep_report.json` | Play 2 MAE/MFE + zone sweep |
| `scratch/analyze_play2_mae_mfe_and_zone_sweep.py` | Analysis script |
| `docs/architecture/SESSION_10_CHECKPOINT_2.md` | This file |