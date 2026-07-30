# Session Handover — Ralph Loop: All Open Items Resolved

> **Date**: 2026-07-29 (Session 10 ralph loop, end)
> **Status**: ALL 5 open items from Checkpoint 4 + Handover resolved. New critical finding: regime decay.
> **Next session**: Build regime kill-switch for H2-type decay; re-evaluate at OOS n≥50 (~Q1 2027).

---

## 1. Items Resolved

### Item #1 — RiskGatekeeper ATR over-estimate fix ✅ DEPLOY
- **Finding**: The fix was ALREADY in source (`IntradayStrategyBase.GetPotentialLoss()` override routes through `GetEstimatedRiskDistance()`). Memory [85] TODO is DONE.
- **IBRetestBot (Play 2)**: Estimated risk distance = `StopRMult × TargetLvl × rangeRange` = `1.0 × 0.5 × rangeRange` = `0.5 × rangeRange`. Actual stop (mid→opposite boundary) = `0.5 × rangeRange`. **Ratio 1.0 — exact match.** ✅
- **IBBreakoutBot (Play 1, abandoned)**: Under-estimate (ratio <1.0, entry = Close[0] beyond boundary). Acceptable since Play 1 abandoned.
- **Hardening added**: Explicit `GetEstimatedRiskDistance()` override in `IBRetestBot.cs` (pins `0.5 × rangeRange`, protects against future param changes).
- **Docs sync**: `docs/strategies/ninjatrader/risk_manager_suite/RiskManagerBase.cs` updated (was stale — old inline ATR formula).
- **Compiled**: 0 errors, 25 pre-existing warnings (none in Vinay bots).
- **Verdict**: DEPLOY-WITH-CAVEATS (gate now uses true stop distance; live trade count < backtest on losing days due to `!isBacktest` skip; $100/day Apex NOT viable — 1 MNQ avg loss $192 > $100).

### Item #2 — MaxDD investigation ✅ HOLD (regime decay found)
- **MaxDD**: −$23,145 (terminal — peak Mar 31 → trough Jul 29, 17-trade grind).
- **Sizing**: ¼-Kelly ≈ 1 NQ ≈ the backtest itself (46% MaxDD) → Kelly too aggressive. Binding constraint = $2,500 trailing DD → 1 MNQ (0.108× scale). $100/day Apex: NOT viable.
- **CRITICAL FINDING — Regime decay**:
  - H1 (Jan 2025–Mar 2026): 49 trades, WR 67.3%, PF 3.187, net +$46,720
  - H2 (Apr–Jul 2026): 16 trades, WR 25.0%, PF 0.35, net −$21,120
  - Monte-Carlo reshuffle (10k paths): actual MaxDD worse than 98.4% of random (p=0.0159 < 0.05) — **statistically significant temporal clustering**.
- **Verdict**: HOLD — DO NOT DEPLOY. Edge has collapsed in H2. The overall PF 1.475 is entirely carried by H1.

### Item #3 — Python harness `--fvg-filter` ✅ 100% PARITY
- Added `--fvg-filter` CLI flag to `scripts/validation/ib_parity_harness.py`.
- FVG check uses runtime `first_break_dir` (matches NT8's live break detection).
- Hardened: `confluence_row is None` → skip (matches NT8's biasFvg=0→skip).
- **Parity**: 100% result agreement (40/40 matched trades). Python 83 vs NT8 81 (gap = AVWAP feed-dependency, documented).

### Item #4 — Walk-forward at n≥50 ✅ MOOT
- The H1/H2 split IS the OOS/walk-forward result — more honest than a synthetic fold.
- Becomes mandatory post-fix with **regime-conditional design** (train on trend regimes, validate on chop).

### Item #5 — Play 1→Play 2 bias filter ✅ CLOSED
- The FVG-aligned filter IS the bias filter. It supersedes the planned `break_vs_avwap_0930 + trend_aligned` stack:
  - `break_vs_avwap_0930` aligned: lift = 0.0 (already the common gate, zero discrimination)
  - `trend_aligned`: lift +0.0173 (marginal)
  - `bias_fvg` aligned: lift +0.2117 (12× stronger, already deployed as 0.25× Kelly overlay)
- No stacking adds value (FORM+FVG already shown overfit: +0.041 on −12 trades).

---

## 2. The Critical Discovery: Failure Layer Isolation

### 2×2 Ablation Grid (FVG × Calendar)

| Cell | Config | Total n | H1 WR | H1 PF | H2 WR | H2 PF |
|---|---|---|---|---|---|---|
| 1 | Unfiltered + Calendar ON | 171 | 53.1% | 1.482 | 36.6% | 0.795 |
| 2 | FVG + Calendar ON | 65 | 67.3% | 3.187 | 25.0% | 0.35 |
| 3 | Unfiltered + Calendar OFF | 200 | 51.5% | 1.505 | 27.3% | 0.654 |
| 4 | FVG + Calendar OFF | 81 | 60.3% | 2.475 | 27.8% | 0.455 |

### Key findings:
1. **FVG has independent edge** beyond calendar: H1 WR lift +8.8pp (calendar-OFF) vs +14.2pp (calendar-ON). ~5pp is Feb-removal confound; 8.8pp is pure FVG.
2. **H2 decay is structural** across ALL 4 cells (PF 0.35–0.80). The retest premise is regime-bound — NOT filter-fixable.
3. **FVG amplifies H2 decay** (H2 WR 36.6%→25.0% with FVG on). The filter is regime-conditional: sharpens H1, deepens H2.
4. **Calendar filters help** (skip Mon/Feb) — cheap, independent, ex-ante. KEEP.

### Diagnosis:
- **Root cause**: Retest premise is regime-bound (H1 trending works, H2 chop/reversal fails).
- **FVG filter**: Not independently broken — amplifies whatever the premise does.
- **Vol inflation**: H2 avg win/loss ~1.6× larger — explains dollar sizes, NOT WR collapse.
- **Fix**: Regime gate (H1-only time fence) + ex-ante regime classifier. NOT filter tuning.

---

## 3. Final Deployment Status

| Component | Status | Config |
|---|---|---|
| RiskGatekeeper | ✅ DEPLOY | True stop distance (ratio 1.0), `!isBacktest` gate skip |
| FVG filter | ✅ Overlay (0.25× Kelly) | NOT hard gate (OOS n=21 < 50) |
| Calendar filters | ✅ KEEP | Skip Mon, skip Feb |
| H2 time fence | ❌ MANDATORY — NOT YET BUILT | Gate H2 out entirely |
| Regime classifier | ❌ MANDATORY — NOT YET BUILT | Daily SMA/ADX + IB-range-vs-median + prior-day FT |
| Position sizing | 1 MNQ on ≥$1,000/day firm | NOT viable on $100/day Apex |
| Deployment | **HOLD** | Until regime gate built + H2 root-caused |

---

## 4. New Open Items for Next Session

1. **Regime kill-switch** (HIGH): Detect H2-type regime break (PF<1, WR<35%) and flatten/skip. Build ex-ante regime classifier (daily SMA/ADX, IB-range-vs-trailing-median, prior-day follow-through). Train on H1+2023–24, validate OOS on H2.
2. **H1-only time fence** (HIGH): Add a `LatestEntry` fence to restrict Play 2 to H1 regime only. The current `LatestEntry=1430` admits H2 trades that are negative-EV.
3. **Re-evaluate at OOS n≥50** (ONGOING): ~Q1 2027 for hard-gate promotion of FVG filter.
4. **IBBreakoutBot override** (LOW): Add `GetEstimatedRiskDistance()` override if Play 1 ever re-activated (currently under-estimates, ratio <1.0).

---

## 5. Files Modified This Session

| File | Change |
|---|---|
| `scripts/strategies/nt8/ib_breakout/IBRetestBot.cs` | Added explicit `GetEstimatedRiskDistance()` override |
| `docs/strategies/ninjatrader/risk_manager_suite/RiskManagerBase.cs` | Synced CanEnterTrade + GetPotentialLoss (was stale) |
| `scripts/validation/ib_parity_harness.py` | Added `--fvg-filter` flag + FVG gate in `simulate_play2_day` |
| `scratch/analyze_maxdd_sizing.py` | MaxDD + position-sizing analysis script |
| `scratch/analyze_regime_decay.py` | H1/H2 split + Monte-Carlo reshuffle script |
| `scratch/analyze_any_backtest.py` | Generalized backtest analyzer (any JSON path) |
| `scratch/maxdd_sizing_report.json` | MaxDD sizing report |
| `scratch/regime_decay_report.json` | Regime decay report |
| `scratch/nt8_ib_retest_unfiltered_sep26_full.json` | Unfiltered + calendar ON backtest |
| `scratch/nt8_ib_retest_unfiltered_nocal_sep26.json` | Unfiltered + calendar OFF backtest |
| `scratch/nt8_ib_retest_fvg_nocal_sep26.json` | FVG-filtered + calendar OFF backtest |

---

## 6. Critical Context (do NOT re-derive)

- **Testing contract**: NQ 09-26 (NQ SEP26). NT8 bridge port: 7890.
- **Parity is COMPLETE**: do NOT re-investigate EMA/AVWAP/TrendMisaligned (§8-§11).
- **Regime decay is CONFIRMED**: H2 PF 0.35, p=0.016. Not random variance.
- **FVG is regime-conditional**: good in H1, bad in H2. Keep as overlay, gate H2 out.
- **¼-Kelly ≈ 1 NQ ≈ backtest**: Kelly too aggressive (46% MaxDD). Use DD-cap frame (1 MNQ).
- **$100/day Apex**: NOT viable (1 MNQ avg loss $192 > $100 daily limit).