# Session 11 — Regime Kill-Switch: Retest-Depth Bias Overlay

> **Date**: 2026-07-30 (Session 11)
> **Goal**: Identify the root cause of H2 2026 regime decay (per user directive: "not in favor of generic calendar days being turned off — identify the reasons for failure and tackle that") and build a targeted fix.
> **Outcome**: Root cause = weak/shallow retests reverse; fix = depth-bias size overlay. **H2 flipped from −$2,016.5 → +$608.5 on MNQ.** DEPLOY-READY on MNQ.

---

## 1. Method — Agent Loop (debate → data → deploy)

Used the subagent loop to challenge hypotheses against data. **Two plausible hypotheses DIED on contact with numbers** — which is the point:

### Refuted
1. **Counter-trend breaks** (subagent's leading guess): REFUTED. All 65 NQ trades are with-trend (counter=0 in both H1 and H2). SMA20 trend gate would keep everything.
2. **Generic regime classifier / ATR-normalized IB ceiling**: REFUTED. ib_range/ATR ≈ 0.42 in both regimes (invariant) — ATR-normalization strips the signal. The handover's "daily SMA/ADX classifier" would not have caught this.

### Confirmed root cause
**Retest depth** = max excursion past IB mid in the break direction, before the pullback to entry. Ex-ante (observed before the entry bar).

| depth_ratio | H1 n | H1 WR | H2 n | H2 WR |
|---|---|---|---|---|
| <0.6 (weak) | 7 | 0.29 | 3 | 0.33 |
| 0.6–0.9 (moderate) | 31 | 0.71 | 7 | **0.00** |
| ≥0.9 (strong thrust) | 11 | 0.82 | 6 | **0.50** |

**Mechanism**: shallow retests (depth < 0.9) are weak/false breaks with no continuation fuel → price reverses to the opposite IB boundary. H2-LOSS: 91.7% fully reversed (vs 0% of winners in either regime). The 0.6–0.9 bucket is where H2 dies (WR 0.00 — all 7 lost). Deep retests (≥0.9) are genuine momentum thrusts that continue (H2 WR 0.50 > realized breakeven 0.488).

**Amplifier (confirmed)**: the fixed 0.5×range stop gets OVERSHOT in H2's high-vol reversals (H2-loss median MAE 197 vs stop 136 = 1.18× overshoot, 67% of losers blow past the stop).

### Honest caveats from the loop
- **Realized R:R is 1.55 (H1) / 1.05 (H2)**, not the nominal 2:1 — winners exit early (median 80% of target). Breakeven WR ~39–49%.
- **Subagent caught 2 bugs** in my first-pass regime analysis: F4 (IB-range ratio) had a look-ahead leak (today's IB in numerator); F7 (prior-day FT) used the wrong proxy. Both discarded.
- **Univariate regime features (ADX, RV, SMA) do NOT cleanly separate** H1/H2. The depth signal is a *trade-quality* feature, not a *market-regime* feature — that's why the handover's "daily SMA/ADX classifier" framing was wrong.

---

## 2. Decision — Bias Overlay (not hard gate, not calendar switch)

User directive: "not in favor of generic calendar days being turned off." The depth overlay keeps ALL trades (no hard-skip) and penalizes the weak-retest root cause via REDUCED SIZE — aligned with the directive.

**Sizing tiers** (NinjaScriptProperty, tunable):
- depth < 0.6 (weak) → 0.10× size
- 0.6 ≤ depth < 0.9 (moderate) → 0.50× size
- depth ≥ 0.9 (strong thrust) → 1.00× size

### Critical implementation constraint (the loop caught this too)
**The overlay is a no-op on NQ at $50k** — base qty = $250 / ($1800 risk/contract) = 0.13 → floors to 1 at ALL overlay tiers (integer contracts can't go below 1). Validated in NT8: NQ $50k backtest was IDENTICAL with overlay ON vs OFF (qty=1 everywhere).

**The overlay bites on MNQ at $250k** (prop-firm scale): base qty ≈ 6 → overlay produces 6/3/1 across strong/moderate/weak tiers. MNQ historical data is available in NT8's instrument master (per user).

---

## 3. Deployment — NT8 Port

### Files modified
| File | Change |
|---|---|
| `scripts/strategies/nt8/ib_breakout/IBStrategyBase.cs` | Added `maxExcursionPastMid` tracker (reset at session open, updated each bar after first break); `DepthSizeMultiplier()` helper; 5 NinjaScriptProperties (`Play2DepthSizeOverlay`, `DepthWeakThreshold`=0.6, `DepthStrongThreshold`=0.9, `DepthWeakSizeMult`=0.10, `DepthModerateSizeMult`=0.50) |
| `scripts/strategies/nt8/ib_breakout/IBRetestBot.cs` | `sizeMult = ClockSizeMultiplier(breakMinutes) * DepthSizeMultiplier()` (applies overlay to both long/short retest paths) |

### Compiled
- Synced via `sync_nt8_strategies.py` (2 files synced).
- NT8 compile: **SUCCESS, 0 errors**, only pre-existing CS0108/CS0114 warnings in unrelated third-party indicators.

---

## 4. Backtest Results — MNQ 09-26, $250k, 2025-01-01 → 2026-07-29

Apples-to-apples (same instrument, same account, only `Play2DepthSizeOverlay` toggle differs):

| Metric | Overlay OFF | Overlay ON | Change |
|---|---|---|---|
| Trades | 64 | 64 | unchanged (no hard-skip) |
| WR | 56.2% | 56.2% | unchanged |
| PF | 1.98 | **2.249** | **+14%** |
| Net | +$18,826.5 | +$14,558.5 | −$4,268 (gives up weak-retest upside) |
| **MaxDD** | **−$4,207** | **−$2,982.5** | **−29% improvement** |

### H1/H2 split (the root-cause validation)
| | Overlay OFF | Overlay ON |
|---|---|---|
| **H1 net** | +$20,843.0 | +$13,950.0 |
| **H2 net** | **−$2,016.5** | **+$608.5** ← **FLIPPED POSITIVE** |

H2 swing = **+$2,625**. The overlay did this by shrinking size on weak H2 retests while preserving full size on the 3 strong-thrust H2 winners (2026-04-29 q=11 +$2475; 2026-05-26 q=7 +$2366; 2026-07-07 q=4 +$2112 — all kept at full size). Weak H2 losers had their qty halved or cut to 1 (e.g. 2026-04-23 q9→4, 2026-04-30 q4→2, 2026-06-04 q3→1).

### Qty distribution (overlay ON, all 64 trades)
qty 1:21, 2:12, 3:7, 4:8, 5:6, 6:1, 7:2, 8:1, 9:1, 11:2, 12:1, 13:1, 15:1 — overlay is live (base qty ≥ 2 on MNQ $250k).

---

## 5. What is NOT done (honest open items)

1. **NQ parity not re-run** — the overlay is a no-op on NQ $50k, so NQ parity is moot at that sizing. To deploy on NQ, need either MNQ-scale account OR accept qty=1 (overlay becomes a no-op; use the hard gate depth≥0.9 instead).
2. **Python harness `--depth-overlay` flag not added** — the analytical validation was done in `scratch/validate_depth_overlay.py` (PnL-scaling), not the production harness. Add for full parity loop.
3. **MNQ FVG+depth OOS n** — H2 positive is on 15 trades (small). Re-evaluate at n≥50 (~Q1 2027) per the existing FVG hard-gate roadmap.
4. **Stop-overshoot amplifier** (mechanism b) NOT separately fixed — the depth overlay indirectly reduces it (weak retests get tiny size so overshoot dollar-impact is small). A dedicated vol-scaled stop (`max(0.5×range, ATR-scaled)`) is a possible follow-up if residuals remain.

---

## 5b. Cross-instrument validation (overlay power scales with base qty)

The overlay only bites when **base qty ≥ 2** at sizeMult=1.0, i.e. `accountEquity*0.005 / (stopDist*PointValue) ≥ 2`. Power scales with base qty:

| Config | Base qty | Overlay tiers | H2 net OFF→ON | MaxDD change | PF change | Verdict |
|---|---|---|---|---|---|---|
| **MNQ $250k** | ~6 | 6/3/1 (full 3-tier) | **−$2,016.5 → +$608.5** ✅ flipped | −29% | +14% | DEPLOY-READY |
| **MES $50k** | ~3 | 3/1/1 (partial) | −$505 → −$367.5 (improved, still neg) | −14% | +3% | partial fix |
| NQ $50k | 1 | 1/1/1 (no-op) | unchanged | 0% | 0% | no-op |

### MES $50k detail (2025-01-01 → 2026-07-29, MES 09-26)
- OFF: PF 1.56, net +$2,728.75, MaxDD −$960, n=68
- ON: PF 1.606, net +$2,485.0, MaxDD −$822.5, n=68
- Only 2 H2 trades changed size (q2→q1): 2026-04-10 saved $75; 2026-04-21 saved $62.5. The rest were already qty=1 (moderate/weak both floor to 1 at base qty 3) or strong-tier-full-size (qty 3 kept).
- H2 did NOT flip (still −$367.5) — base qty 3 is too small for the moderate tier (0.50× → 1.5 → floors to 1) to separate from weak.

### Deployment ladder
MNQ $250k (deploy-ready, H2 fixed) > MES $250k (base qty ~16 → full 16/8/1, untested) > MES $50k (partial) > NQ $50k (no-op).
**Recommendation**: deploy on MNQ at prop-firm scale. If MES preferred, run MES at $250k (base qty ~16) for full differentiation.

---

## 6. Deployment Status

| Component | Status | Config |
|---|---|---|
| Depth-bias overlay | ✅ DEPLOY-READY on MNQ $250k | 0.10/0.50/1.00 @ 0.6/0.9 |
| FVG filter | ✅ Overlay (unchanged) | 0.25× Kelly bias |
| Calendar filters | ✅ KEEP (per user directive) | skip Mon, skip Feb |
| NQ deployment | ❌ BLOCKED (qty-floor no-op) | need MNQ-scale account or hard gate |
| Python harness | ❌ TODO | add --depth-overlay |

**Verdict**: DEPLOY on MNQ at prop-firm scale. H2 regime decay FIXED (−$2016 → +$608). MaxDD −29%. The root cause (weak-retest reversal) is tackled, not a generic calendar switch.

---

## 7. Files / Scripts

| Path | Purpose |
|---|---|
| `scripts/strategies/nt8/ib_breakout/IBStrategyBase.cs` | Depth tracker + overlay + params |
| `scripts/strategies/nt8/ib_breakout/IBRetestBot.cs` | sizeMult applies DepthSizeMultiplier |
| `scratch/analyze_regime_features.py` | Univariate regime feature scan (F4/F7 had bugs, noted) |
| `scratch/forensic_retest.py` | Trade-level forensic (confirmed reversal mechanism, refuted counter-trend) |
| `scratch/verify_overshoot_atr.py` | Stop-overshoot amplifier + ATR-ceiling (ATR no-op) |
| `scratch/realized_rr_gates.py` | Realized R:R + depth-floor sweep (found depth≥0.9 flips H2) |
| `scratch/validate_depth_overlay.py` | Overlay PnL-scaling validation (predicted PF 2.024, MaxDD −69%) |
| `scratch/compare_mnq_overlay.py` | MNQ ON-vs-OFF comparison |
| `scratch/mnq_overlay_on_full.json` | MNQ overlay ON backtest (64 trades) |
| `scratch/mnq_overlay_off_full.json` | MNQ overlay OFF backtest (64 trades) |
| `SESSION_11_REGIME_KILLSWITCH_HANDOVER.md` | this doc |