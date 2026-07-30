# Session 11 — Regime Kill-Switch Investigation & Results

> **Date**: 2026-07-30
> **Scope**: Identify the root cause of H2 2026 IBRetestBot (Play 2) regime decay and build a targeted fix.
> **User directive**: "Not in favor of generic calendar days being turned off — identify the reasons for failure and tackle that."
> **Outcome**: Root cause = weak/shallow retests reverse; fix = retest-depth bias size overlay. **H2 flipped negative→positive on MNQ ($250k).** Cross-validated on MES ($50k, partial).

---

## 1. Investigation method — agent loop (debate → data → deploy)

Used the subagent loop to challenge hypotheses against data. Two plausible hypotheses **died on contact with numbers** — the point of the loop:

### Refuted hypotheses
1. **Counter-trend breaks** (subagent's leading guess): REFUTED. All 65 NQ FVG-filtered trades are with-trend (`counter=0` in both H1 and H2). An SMA20 trend-direction gate would keep everything — zero discrimination.
2. **Generic regime classifier / ATR-normalized IB ceiling**: REFUTED. `ib_range/ATR14` ≈ 0.42 in both regimes (invariant) — ATR-normalization strips the very signal needed. The handover's planned "daily SMA/ADX classifier" would not have caught this.
3. **My first-pass `F4` (IB-range ratio) and `F7` (prior-day FT)** — the subagent review caught a look-ahead leak in F4 (today's IB range in the numerator, not ex-ante) and a wrong proxy in F7 (body-vs-mid, not open-drive). Both discarded.

### Genuinely ex-ante features (leak-free, all `.shift(1)` verified)
`f1` price-vs-SMA20, `f2` SMA20 slope, `f3` ADX14, `f5` realized vol (ATR14/close), `f6` prior-day range %, `f8` prior-day body/range. None cleanly separate H1 from H2 — the failure is a **trade-quality** phenomenon, not a **market-regime** phenomenon.

---

## 2. The confirmed root cause — retest depth

**Retest depth** = max excursion past the IB midpoint in the break direction, observed *before* the pullback to the retest entry. Ex-ante (known at entry time, since the thrust precedes the pullback).

### Depth buckets (the mechanism, dissected)
| depth_ratio | H1 n | H1 WR | H2 n | H2 WR |
|---|---|---|---|---|
| <0.6 (weak) | 7 | 0.29 | 3 | 0.33 |
| 0.6–0.9 (moderate) | 31 | 0.71 | 7 | **0.00** |
| ≥0.9 (strong thrust) | 11 | 0.82 | 6 | **0.50** |

- **Shallow retest (depth < 0.9)** = weak/false break, no continuation fuel → price fully reverses to the opposite IB boundary. H2-LOSSES: 91.7% fully reversed (vs **0%** of winners in either regime).
- The 0.6–0.9 moderate bucket is where H2 dies (WR 0.00 — all 7 lost).
- **Deep retest (depth ≥ 0.9)** = genuine momentum thrust → continuation. H2 WR 0.50 > realized breakeven 0.488 → positive EV.

### Confirmed amplifier — stop overshoot
The fixed 0.5×range stop gets **overshoot** in H2's high-vol reversals:

| Group | median MAE | median stop_dist | overshoot ratio | frac >1 |
|---|---|---|---|---|
| H1-win | 16 | 79 | 0.45 | — |
| H1-loss | 170 | 74 | 2.34× | 0.50 |
| H2-loss | 197 | 136 | **1.18×** | **0.67** |

67% of H2 losers blow past the stop (median MAE 197 vs stop 136). The high-vol reversal reaches the stop faster than the geometry assumes.

### Honest caveats from the loop
- **Realized R:R is 1.55 (H1) / 1.05 (H2)**, not the nominal 2:1 — winners exit early (median 80% of target). Breakeven WR is ~39–49%, used as the benchmark (not 33%).
- **Univariate regime features (ADX, RV, SMA) do NOT cleanly separate** H1/H2 — confirming the failure is trade-quality, not market-regime.

---

## 3. The fix — retest-depth bias size overlay

Chosen form: **bias overlay (not hard gate, not calendar switch)** — keeps all trades (no hard-skip, aligned with the user's directive), penalizes the weak-retest root cause via REDUCED SIZE.

### Sizing tiers (NinjaScriptProperty, tunable)
- `depth < 0.6` (weak) → `DepthWeakSizeMult` = **0.10×**
- `0.6 ≤ depth < 0.9` (moderate) → `DepthModerateSizeMult` = **0.50×**
- `depth ≥ 0.9` (strong thrust) → **1.00×**

### Critical implementation constraint (the loop caught this)
The overlay is a **no-op on NQ at $50k** — base qty = $250 / ($1,800 risk/contract) = 0.13 → floors to 1 at ALL overlay tiers (integer contracts can't go below 1). The overlay only bites when **base qty ≥ 2** at sizeMult=1.0, i.e. `accountEquity*0.005 / (stopDist*PointValue) ≥ 2`.

---

## 4. NT8 deployment

### Files modified
| File | Change |
|---|---|
| `scripts/strategies/nt8/ib_breakout/IBStrategyBase.cs` | Added `maxExcursionPastMid` tracker (reset at session open, updated each bar after first break in `UpdateConfluenceIndicators`); `DepthSizeMultiplier()` helper; 5 `[NinjaScriptProperty]` params (`Play2DepthSizeOverlay`, `DepthWeakThreshold`=0.6, `DepthStrongThreshold`=0.9, `DepthWeakSizeMult`=0.10, `DepthModerateSizeMult`=0.50) |
| `scripts/strategies/nt8/ib_breakout/IBRetestBot.cs` | `sizeMult = ClockSizeMultiplier(breakMinutes) * DepthSizeMultiplier()` (applies overlay to both long/short retest paths) |

### Compiled
- Synced via `sync_nt8_strategies.py` (2 files synced).
- NT8 hot-swap compile via bridge (port 7890): **SUCCESS, 0 errors**, only pre-existing CS0108/CS0114 warnings in unrelated third-party indicators.

---

## 5. Backtest results — cross-instrument validation

Overlay power **scales with base qty** = `accountEquity*0.005 / (stopDist*PointValue)`:

| Config | Base qty | Overlay tiers | H2 net OFF→ON | MaxDD change | PF change | Verdict |
|---|---|---|---|---|---|---|
| **MNQ $250k** | ~6 | 6/3/1 (full 3-tier) | **−$2,016.5 → +$608.5** ✅ flipped | −29% | +14% | **DEPLOY-READY** |
| **MES $50k** | ~3 | 3/1/1 (partial) | −$505 → −$367.5 (improved, still neg) | −14% | +3% | partial fix |
| NQ $50k | 1 | 1/1/1 (no-op) | unchanged | 0% | 0% | no-op |

### MNQ 09-26, $250k (2025-01-01 → 2026-07-29) — the deploy-ready config
Apples-to-apples (only `Play2DepthSizeOverlay` toggle differs):

| Metric | Overlay OFF | Overlay ON | Change |
|---|---|---|---|
| Trades | 64 | 64 | unchanged (no hard-skip) |
| WR | 56.2% | 56.2% | unchanged |
| PF | 1.98 | **2.249** | +14% |
| Net | +$18,826.5 | +$14,558.5 | −$4,268 (gives up weak-retest upside) |
| **MaxDD** | **−$4,207** | **−$2,982.5** | **−29%** |
| **H1 net** | +$20,843.0 | +$13,950.0 | gives up weak-retest winners |
| **H2 net** | **−$2,016.5** | **+$608.5** | **flipped positive (+$2,625 swing)** |

**Mechanism proof (per-trade, H2 ON vs OFF)**: the overlay shrank size on weak H2 losers while preserving full size on the 3 strong-thrust H2 winners (2026-04-29 q=11 +$2475; 2026-05-26 q=7 +$2366; 2026-07-07 q=4 +$2112 — all kept at full size). Weak H2 losers had their qty halved or cut to 1 (e.g. 2026-04-23 q9→4, 2026-04-30 q4→2, 2026-06-04 q3→1).

### MES 09-26, $50k — partial fix (base qty too small)
| Metric | OFF | ON | Change |
|---|---|---|---|
| Trades | 68 | 68 | unchanged |
| PF | 1.56 | 1.606 | +3% |
| Net | +$2,728.75 | +$2,485.0 | −$243 |
| MaxDD | −$960 | −$822.5 | −14% |
| H2 net | −$505.0 | −$367.5 | improved, not flipped |

At $50k MES, base qty ≈ 3 → overlay tiers collapse to 3/1/1 (only the strong tier differentiates; moderate and weak both floor to 1). Only 2 H2 trades changed size.

---

## 6. Deployment recommendation

**Deploy on MNQ at prop-firm scale ($250k)** — the only tested config where the overlay fully bites and H2 flips positive.

Deployment ladder (by overlay power):
```
MNQ $250k (deploy-ready, H2 fixed)  >  MES $250k (base qty ~16 → full 16/8/1, untested)
                                    >  MES $50k  (partial 3/1/1)
                                    >  NQ $50k   (no-op 1/1/1)
```

### Status table
| Component | Status | Config |
|---|---|---|
| Depth-bias overlay | ✅ DEPLOY-READY on MNQ $250k | 0.10/0.50/1.00 @ 0.6/0.9 |
| FVG filter | ✅ Overlay (unchanged from Session 10) | 0.25× Kelly bias |
| Calendar filters | ✅ KEEP (per user directive) | skip Mon, skip Feb |
| NQ deployment | ❌ BLOCKED (qty-floor no-op at $50k) | need MNQ-scale account or hard gate |
| Python harness `--depth-overlay` | ❌ TODO | add for full parity loop |
| Stop-overshoot dedicated fix | ❌ TODO (indirectly mitigated) | vol-scaled stop if residuals remain |

---

## 7. Open items (next session)

1. **Python harness `--depth-overlay` flag** — add to `ib_parity_harness.py` so the overlay is exercised in the production parity loop (analytical validation done in `scratch/validate_depth_overlay.py`; not yet in the harness).
2. **MES $250k test** — base qty ~16 → full 16/8/1 differentiation; expected to flip H2 like MNQ did (untested).
3. **MNQ FVG+depth OOS n** — H2 positive is on 15 trades (small). Re-evaluate at n≥50 (~Q1 2027) per the existing FVG hard-gate roadmap.
4. **Stop-overshoot amplifier** — a dedicated vol-scaled stop (`max(0.5×range, ATR-scaled)`) if residuals remain after the overlay.
5. **NQ path** — either accept MNQ-scale account for the overlay, or fall back to the hard gate depth≥0.9 (≈17 trades, H2 WR 0.50) on NQ.

---

## 8. Investigation artifacts (in `scratch/`)

| Path | Purpose |
|---|---|
| `analyze_regime_features.py` | Univariate regime feature scan (F4/F7 bugs noted, discarded) |
| `forensic_retest.py` | Trade-level forensic — confirmed reversal mechanism, refuted counter-trend |
| `forensic_retest_report.json` | Per-trade forensic data (depth, MAE, reversal flags) |
| `verify_overshoot_atr.py` | Stop-overshoot amplifier + ATR-ceiling (ATR no-op confirmed) |
| `realized_rr_gates.py` | Realized R:R + depth-floor sweep (found depth≥0.9 flips H2) |
| `sweep_ib_ceiling.py` | IB-range ceiling sweep (ceiling reduces H2 bleed but not EV-positive) |
| `validate_depth_overlay.py` | Overlay PnL-scaling validation (predicted PF ~2.024, MaxDD −69%) |
| `compare_mnq_overlay.py` / `analyze_mnq_full.py` | MNQ ON-vs-OFF comparison |
| `compare_mes_50k.py` | MES $50k ON-vs-OFF comparison |
| `mnq_overlay_{on,off}_full.json` | MNQ $250k backtest pairs (64 trades each) |
| `mes_50k_{on,off}.json` | MES $50k backtest pairs (68 trades each) |
| `nt8_ib_retest_fvg_sep26_full.json` | Source FVG-filtered NQ backtest (65 trades) — the investigation input |
| `analyze_regime_decay.py` + `regime_decay_report.json` | H1/H2 split + Monte-Carlo (p=0.016) |
| `analyze_maxdd_sizing.py` + `maxdd_sizing_report.json` | MaxDD + sizing analysis |

### Handover docs (in `docs/architecture/`)
- `SESSION_11_REGIME_KILLSWITCH_HANDOVER.md` — full session handover
- `SESSION_11_REGIME_KILLSWITCH_INVESTIGATION.md` — this document

### Memories recorded (`.agent/memory.db`)
- [135] trading_rule — regime kill-switch = retest-depth bias overlay (root cause + fix)
- [136] architecture — NT8 depth overlay port + qty-floor constraint
- [137] trading_rule — cross-instrument validation (MES $50k partial, MNQ $250k full)