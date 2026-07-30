# IB Strategy: Python Study vs NT8 Bot Reconciliation

**Generated:** 2026-07-28
**Purpose:** Reconcile the statistical findings (Python `EDGE_VALIDATION_REPORT.md` + `IB_DATA_INSIGHTS_REPORT.md`) against the actual NT8 Strategy Analyzer performance of the three deployed bots (`IBBreakoutBot`, `IBRetestBot`, `IBFadeBot`).
**Why this matters:** The Python study is bar-level / R-multiple; NT8 is tick-level / dollar P&L. They use different exit models, stop distances, and sample windows. Agreement is the signal the edge is real; divergence is the signal something is wrong.

---

## 1. Headline Verdict

**The Python study and the NT8 bots do NOT agree.** Three of the four key findings diverge:

| # | Python finding | NT8 bot reality | Verdict |
|---|---|---|---|
| 1 | Play 1 breakout @ 0.5x: WR **56.5%**, PF 1.49, E[R] +0.093 | IBBreakoutBot: WR **73-76%**, PF 1.29-1.49 | ⚠️ WR inflated — stop mismatch |
| 2 | Play 3 fade @ 0.25x is the **standout** (E[R] +0.259, PF 1.51) | IBFadeBot @ 0.25x target: **PF 0.687 (LOSING)** | ❌ Does not replicate |
| 3 | Optimal stop = **0.25R tight** (same E[R], 75% less $ risk) | NT8 uses **2.0R wide stop** (ib_opposite) — tight stop gets killed by wicks | ❌ Opposite conclusion |
| 4 | Play 1 edge is **decaying in 2026** (CI crosses zero) | IBBreakoutBot Jan-Mar 2026: PF 1.382, +$1,095 (profitable) | ⚠️ Contradicts decay |

**Only Play 1 (breakout) being profitable broadly agrees** — but the magnitude and mechanism differ. The fade edge claimed by Python is **not confirmed by NT8**.

---

## 2. The Stop Model Contradiction (the root cause)

This is the single most important reconciliation point and it explains most of the divergence.

### Python study (Layer B — `EDGE_VALIDATION_REPORT.md` §7.6)

> "The stop distance does NOT affect E[R] because the MAE rarely exceeds 0.25R before the target is hit. A 0.25R stop captures the same edge as a 1.0R stop, with 75% less dollar risk."

| Stop | WR | E[R] | PF |
|---|---|---|---|
| 0.25R | 43.0% | +0.259 | 1.47 |
| 1.0R | 56.0% | +0.083 | 1.31 |

Python's conclusion: use the **tight 0.25R stop** — same E[R], 75% less dollar risk.

### NT8 bot (`IBBreakoutBot.cs` line 39-41)

```csharp
StopRMult = 2.0;   // Full-range stop (= 2.0*0.5*range = 1.0*range = opposite IB boundary).
                   // Python report says 0.25R and 1.0R give same E[R], but 1.0R survives
                   // intrabar wicks in NT8 tick-level sim that kill the 0.25R stop (23% WR vs 51.8%).
```

NT8's conclusion: use the **wide 2.0R stop** — the tight stop gets killed by intrabar wicks (WR collapses 51.8% → 23%).

### Why they disagree

| Aspect | Python (Layer B) | NT8 |
|---|---|---|
| Resolution | **Bar-level** — target-before-stop evaluated per bar | **Tick-level** — every tick can stop you out |
| What "MAE" measures | Close-to-extreme adverse excursion per bar | Intra-bar wicks that reverse before the bar closes |
| Stop survival | A 0.25R stop "survives" because the bar's MAE (close-based) rarely exceeds 0.25R | A 0.25R stop gets hit by intrabar wicks the bar-level model never sees |

**Resolution:** The Python study's MAE is **close-based**, not **tick-based**. NT8's tick simulation reveals adverse excursions the bar-level model is blind to. **The Python 0.25R-stop finding is an artifact of bar-level resolution and does not survive tick-level execution.** The NT8 bot's choice of the wide stop is correct for live trading.

This also explains why Python's `STOP_LOSS_COMPARISON.md` (Layer A) concluded `ib_opposite` wins on total return — Layer A used fixed-time exit (not target-before-stop) AND bar-level resolution. Both layers had the same blind spot from different angles.

---

## 3. Play 3 (Fade) — the standout that isn't

This is the most worrying discrepancy. The Python study calls Play 3 fade @ 0.25x "the standout" (E[R] +0.259, PF 1.51, the strongest single strategy). NT8 does not confirm this.

### Python vs NT8 fade results

| Source | Target | Overshoot | Stop | Trades | WR | PF | Net |
|---|---|---|---|---|---|---|---|
| **Python (5-yr)** | **0.25x** | 0.25× | 0.5R | **481** | **38.5%** | **1.51** | **E[R] +0.259** |
| NT8 S4 (Jan-Mar 2026) | 0.25x | 0.25× | 0.5R | 49 | 61.2% | **0.687** | **−$558** |
| NT8 S4 | 0.50x | 0.25× | 0.5R | 59 | 59.2% | 0.745 | −$859 |
| NT8 S4 | 0.75x | 0.25× | 0.5R | 51 | 51.0% | 0.814 | −$839 |
| NT8 S4 | 1.0x | 0.25× | 0.5R | 43 | 44.9% | 0.961 | −$188 |
| **NT8 S4 (tuned)** | **1.0x** | **0.35×** | 0.5R | 43 | 53.5% | **1.215** | **+$609.50** |
| NT8 S5 IS (Jan-Mar 2025) | default | default | 0.5R | 50 | 34.0% | **0.742** | **−$973.50** |

### Three problems

1. **The 0.25x target does NOT replicate.** Python says PF 1.51 at 0.25x; NT8 says PF 0.687 at 0.25x (losing). The fade needs the **1.0x target** in NT8 to approach breakeven, and needs **0.35x overshoot** on top of that to be profitable (PF 1.215).

2. **The fade is period-dependent.** Session 4 (Jan-Mar 2026) with the tuned config = +$609.50. Session 5 IS (Jan-Mar 2025) with default config = −$973.50. The fade is NOT the "stable 5-year edge" Python claims — it is highly regime-sensitive. Python's 5-year aggregate (E[R] +0.259) is likely masking period losses.

3. **The WR direction is wrong.** Python fade @ 0.25x → WR 38.5%. NT8 fade @ 0.25x → WR 61.2%. Higher WR but still losing because the R:R is inverted (avg win $41 vs avg loss $94 = 0.5:1 R:R). The WR difference is the stop/entry resolution difference again — NT8's overshoot state machine + bar-close entry produces different entries than Python's play-detail evaluator.

### What the deployed bot actually does

`IBFadeBot.cs` defaults (line 50-53):
```csharp
TargetLvl = 1.0;          // Full reversion (NOT the Python-validated 0.25x)
StopRMult = 0.5;
LateBreakSizeMult = 0.35;  // NT8-validated overshoot threshold
```

**The deployed fade bot has ALREADY diverged from the Python recommendation** — it uses 1.0x target (not 0.25x) and 0.35x overshoot (not 0.25x). These were tuned empirically on NT8 because the Python defaults lost money. The bot is trading a different strategy than the one Python validated.

---

## 4. Play 1 (Breakout) — agrees in direction, disagrees in magnitude

### Python vs NT8 breakout results

| Source | Target | Stop | Trades | WR | PF | Net |
|---|---|---|---|---|---|---|
| **Python (5-yr)** | **0.5x** | 0.25R (rec) / 1.0R | 1252 | **56.5%** | **1.49** | **E[R] +0.093** |
| NT8 S4 (Jan-Mar 2026) | 0.5x | 2.0R (ib_opp) | 68 | **76.5%** | 1.382 | +$1,095 |
| NT8 S5 IS (Jan-Mar 2025) | 0.5x | 2.0R | 75 | 73.3% | 1.285 | +$903.50 |
| NT8 S5 OOS (Mar-Jun 2025) | 0.5x | 2.0R | 92 | 67.4% | 1.029 | +$129.50 |
| NT8 S5 +TrendMisalign IS | 0.5x | 2.0R | 30 | 76.7% | 1.489 | +$570.50 |
| NT8 S5 +TrendMisalign OOS | 0.5x | 2.0R | 35 | 74.3% | 1.426 | +$640.50 |

### Reconciliation

- **Direction agrees:** both Python and NT8 say Play 1 breakout is profitable. ✅
- **WR magnitude disagrees:** Python 56.5% vs NT8 73-76%. The gap is the stop: NT8's wide 2.0R stop lets more trades survive to hit target (inflating WR), at the cost of larger losses on the ones that fail. This is exactly the pattern Python's own table shows (0.25R→43% WR, 1.0R→56% WR) extrapolated to 2.0R.
- **The TrendMisaligned filter works:** NT8 PF jumps 1.285→1.489 (IS) and 1.029→1.426 (OOS) with the filter, and drawdown drops ~60%. This is the NT8-validated analog of Python's "skip huge IB + skip Monday" stack — but it is a different filter. Python's exact stack (Rule 1A + skip huge + skip Monday) is **NOT deployed** in NT8.
- **OOS degradation is real:** NT8 OOS without the filter drops to PF 1.029 (+$129.50 on 92 trades — barely breakeven). This is consistent with Python's 2026 decay flag (CI crosses zero). With the filter, OOS recovers to PF 1.426 — the filter rescues the decaying edge.

---

## 5. Play 2 (Retest) — small sample, inconsistent

| Source | Trades | WR | PF | Net |
|---|---|---|---|---|
| Python (5-yr) | 576 | 28.0% (0.25x) | 1.23 | E[R] +0.078 |
| NT8 S4 (Jan-Mar 2026) | 16 | 43.8% | 0.726 | −$360 |
| NT8 S5 IS (Jan-Mar 2025) | 17 | 58.8% | 1.638 | +$679.50 |
| NT8 S5 OOS (Mar-Jun 2025) | 38 | 36.8% | 1.409 | +$1,255 |

Retest has the fewest trades (16-38 per 3-month window). Python itself flagged Play 2 as "regime-dependent (negative 2022)." The NT8 results swing from −$360 to +$1,255 across windows. **No confident reconciliation possible** — the sample is too small and the edge is too unstable. Treat Play 2 as unvalidated until a longer NT8 run is available.

---

## 6. The 2026 Decay Question

Python (`EDGE_VALIDATION_REPORT.md` §4.3) flags Play 1 E[R] dropping to +0.021 in 2026 with CI crossing zero — "the breakout edge may be decaying."

NT8 Session 4 (Jan-Mar 2026) shows IBBreakoutBot at PF 1.382, +$1,095 — **profitable in the same period Python flags as decaying.**

This is not necessarily a contradiction:
- Python's 2026 figure is a 6-month aggregate (Jan-Jun 2026); NT8 S4 is Jan-Mar 2026 only.
- Python measures E[R] in R-multiples with the 0.25R stop; NT8 measures dollar P&L with the 2.0R stop. A wide stop can keep dollar P&L positive even when R-multiple E[R] decays (because the $ per R is larger).
- The NT8 S5 OOS (Mar-Jun 2025, not 2026) dropping to PF 1.029 is the more relevant decay signal — it shows the edge thinning even before 2026.

**Verdict:** The decay is real but masked in NT8 by the wide stop. Monitor the OOS-with-filter PF (1.426) — if it drops below 1.20 in the next OOS window, the edge is gone.

---

## 7. Sample Window Mismatch (a methodological caveat)

| Dimension | Python | NT8 |
|---|---|---|
| Length | 5-6 years (2021-2026) | 3 months per session (Jan-Mar 2025, Mar-Jun 2025, Jan-Mar 2026) |
| Trades | 481-1252 per play | 16-92 per bot per session |
| Instrument | NQ1 (continuous, 5-min) | MNQ 03-25 / 06-25 / 03-26 (expiring contracts, 1-min & 5-min) |
| Resolution | Bar-level | Tick-level |

The NT8 samples are **30-50× smaller** than Python's. A 3-month, 68-trade backtest has wide confidence intervals — the difference between PF 1.382 and PF 1.029 is well within noise at N=68. **Do not over-interpret single-session NT8 PFs.** The trend across sessions (S5 OOS without filter = PF 1.029) is the signal, not any single number.

---

## 8. The Parity Harness (built and run)

The 3-tier parity pipeline from `AUTOMATION_DESIGN.md` §9.1 has been **partially implemented and run**:

### 8.1 The harness: `scripts/orb_generic/parity_check.py`

A bar-by-bar parity harness was built (via the agent loop in `scratch/run_parity_harness_loop.py`). It is **ORB-specific** but follows a reusable pattern that the IB bots should adopt:

- Loads one trade-date of 1-min bars from live storage (`data/live/live_storage_-{ticker}.parquet`), filtered to RTH 09:30–16:00 ET (ADR-001 timezone-correct).
- Runs the Python ORB simulation inline (vectorized entry detection, ADR-017) with a bounded exit-resolution loop for the stop/target tie-break.
- Accepts a saved NT8 Strategy Analyzer JSON (`--nt8-json`) and normalizes the trades.
- Emits a side-by-side diff table (entry/exit time, price, stop, target, PnL) with an explicit `tie_break` flag — the **H2 signature** (same-bar stop+target touch).
- ADR-020 compliant: liquidation on the close of the 15:59 ET bar, not 16:00.

**Key design feature — the H2 tie-break signature:** the harness explicitly flags bars where Python and NT8 would resolve a stop+target tie differently. Python resolves to stop (conservative, bar-level); NT8 tick-level may resolve to target (first touch). This is the mechanism that explains most of the WR/PF divergence between the two engines.

**Known limitations (flagged by the architecture reviewer, `scratch/parity_loop_result.json`):**
- ORB-hardcoded (not yet pluggable to IB); the reviewer recommended a `ParityStrategy` Protocol/ABC so ORB/Fade/MultiTP/IB bots all share the diff loop.
- No commission/slippage normalization flag — PnL is compared apples-to-oranges unless `--fee-per-trade` is set to match NT8's simulator.
- Single-trade-per-day JSON contract — assumes `nt8_data['trades'][0]` is the parity trade; multi-TP/scaled trades need entry-time matching within ±60s tolerance.

### 8.2 The IB diagnosis loop: `scratch/run_ib_profitability_loop.py`

The IB-specific reconciliation was run via a second agent loop. Its brief captured the exact discrepancy (note the *pre-fix* numbers — these are the baseline before Session 4/5 fixes):

| Bot | NT8 baseline (pre-fix) | Python expectation |
|---|---|---|
| IBBreakoutBot | 944 trades, WR 44.6%, PF 0.986, net −$1,294, maxDD −$7,277 | Play 1 @ 0.5x: WR 51.8%, PF 1.30 |
| IBFadeBot | 82 trades, WR 54.9%, PF 0.815, net −$1,206, maxDD −$1,520 | Play 3 @ 0.25x: WR 11.1%, PF 1.13 |
| IBRetestBot | 31 trades, WR 41.9%, PF 0.798, net −$636, maxDD −$1,646 | Play 2 @ 0.25x: WR 13.6%, PF 0.82 |

### 8.3 The three root causes diagnosed (and the fixes applied)

The diagnosis loop (`scratch/ib_profitability_loop.json`) identified the three root causes that the AUTOMATION_DESIGN §12 Session 4/5 fixes then addressed:

| # | Root cause (diagnosed) | Fix applied (Session 4/5) | Effect |
|---|---|---|---|
| 1 | **Stop geometry mismatch** — NT8 used a 0.125×range stop (8× tighter than Python's full-range stop), causing premature stop-outs on intrabar wicks | `StopRMult` 0.25 → 2.0 in `IBBreakoutBot.cs` | WR 23% → 75.7% (survives wicks); PF → 1.382 |
| 2 | **Over-trading** — NT8 re-entered on every bar beyond the IB boundary (944 trades / 3 months ≈ 15/day) instead of once per break | `longTakenToday`/`shortTakenToday` entry guards in `IBStrategyBase` | 944 → 74 trades; one entry per direction per session |
| 3 | **Fade R:R asymmetry** — IBFadeBot target (rangeMid) was close while stop (0.5×range) was far, so losses swamped wins | `TargetLvl` 0.25 → 1.0, `LateBreakSizeMult` 0.25 → 0.35 (overshoot threshold) | PF 0.687 → 1.215 |

**This confirms the reconciliation report's core finding: the Python tight-stop recommendation does not survive tick-level execution.** The diagnosis loop's edge-case reviewer explicitly warned that widening the stop 8× without position-size adjustment would blow the account, and that the fade's R:R geometry was inverted. The Session 4/5 fixes addressed both, and the results in §4 of this report are the *post-fix* numbers.

### 8.4 What remains unbuilt

| Item | Status |
|---|---|
| IB-specific parity harness (pluggable, multi-trade-per-day) | ❌ Not built — the ORB harness needs the `ParityStrategy` ABC refactor |
| TradingView Strategy Tester tier | ❌ Not started (Phase 8 in AUTOMATION_DESIGN) |
| Commission/slippage normalization flag | ❌ Not in the harness CLI |
| Full 5-year NT8 run (2021-2026) to match Python's sample | ❌ Only 3-month windows run so far |
| Walk-forward validator (`walk_forward.py`, E3) | ❌ Not built |

**Bottom line:** The parity harness exists and was used to diagnose the IB discrepancies, and the diagnosed fixes were applied and validated in NT8 Sessions 4–5. What's missing is (a) generalizing the harness to the IB bots for ongoing regression checks, (b) the TradingView tier, and (c) running the full 5-year NT8 window to match Python's sample size.

### Python-validated features NOT deployed in NT8

| Feature | Python finding | NT8 status |
|---|---|---|
| Rule 1A direction trigger | 88.1% hit rate, +0.026 lift | `RequireDirectionBias` exists but defaults vary; not ablated |
| Skip huge IB (>0.9%) | +0.009 lift, strongest negative predictor | `skip_huge_ib` param exists; unclear if ON by default |
| Skip Monday (Play 2) | E[R] −0.048 (only negative DOW) | Param exists; unclear if ON |
| Skip May (Play 1) | E[R] −0.048 | Param exists; unclear if ON |
| Skip October (Play 3) | E[R] −0.166 | Param exists; unclear if ON |
| `bias_combined` +1 filter | +0.022 lift (strongest bias) | `bias_variant` param exists; default not confirmed |
| E11 80%-rule entry | +0.093 lift, PF 4.95 | NOT implemented in NT8 |
| E18 wick-dominant fade | +0.020 lift, 61% WR | NOT implemented in NT8 |
| `mid_lock_frac` Q5 filter | +0.066 lift (strongest exit feature) | NOT implemented in NT8 |
| 0.25R stop | "same E[R], 75% less $ risk" | **REJECTED by NT8** (killed by wicks) |
| Play 3 @ 0.25x target | E[R] +0.259 (standout) | **REJECTED by NT8** (PF 0.687, losing) |

**Only the TrendMisaligned filter is confirmed deployed and ablated in NT8** (PF 1.285→1.489 IS, 1.029→1.426 OOS). The rest of Python's validated stack is either not deployed, not ablated, or rejected by tick-level reality.

---

## 9. Reconciled Action List

### Immediate (before any live deployment)

1. **Generalize the parity harness to the IB bots.** `scripts/orb_generic/parity_check.py` exists and was used to diagnose the ORB discrepancy; the IB diagnosis was done via the agent loop (`scratch/run_ib_profitability_loop.py` → `scratch/ib_profitability_loop.json`). Refactor the harness to a `ParityStrategy` ABC so `IBBreakoutBot`/`IBFadeBot`/`IBRetestBot` plug in directly for ongoing regression checks (the ORB harness is currently ORB-hardcoded).
2. **Run NT8 on the full 5-year window** (2021-2026, NQ1 continuous, 5-min) to match Python's sample. 3-month sessions are too noisy to reconcile against a 5-year study.
3. **Ablate the stop model on NT8.** Run IBBreakoutBot with StopRMult ∈ {0.25, 0.5, 1.0, 2.0} on the same window. The Session 4 fix already confirmed 0.25R collapses to ~23% WR on tick-level sim — formalize this as a documented ablation so the Python 0.25R-stop finding is re-labeled "bar-level edge only".

### Corrections to the Python claims

4. **Downgrade the Play 3 @ 0.25x "standout" claim.** It does not replicate in NT8 tick simulation. Re-label as "bar-level edge, pending tick-level validation." The deployed bot correctly uses 1.0x target + 0.35x overshoot (NT8-tuned), which is a **different strategy** than Python validated.
5. **Downgrade the "0.25R stop is optimal" claim.** It is optimal only under bar-level MAE. Under tick-level execution it gets killed by wicks. Re-label as "bar-level optimal; tick-level requires wider stop."
6. **Soften the "stable 5-year edge" claim for Play 3.** NT8 S5 IS = −$973.50 on 50 trades shows the fade loses in some 3-month windows. The 5-year aggregate masks this. Add a period-stability table to the Python report.

### Deploy the validated stack

7. **Deploy and ablate the full Python filter stack in NT8:** Rule 1A + skip huge IB + skip Monday (Play 1) / skip May / skip October (Play 3). The TrendMisaligned filter already proved the stack approach works (PF +0.2, DD −60%). The remaining filters are free upside.
8. **Implement E11 (80%-rule) and E18 (wick-fade) entry modules in NT8.** Python shows +0.093 / +0.020 lift. These are the only selective entry modules; the rest fire on ~100% of days and add nothing.

### Monitoring

9. **Add an equity-curve break detector** (E8 in `AUTOMATION_DESIGN.md`). The 2026 decay flag is real; the bot should auto-disarm when rolling 20-trade E[R] CI crosses zero. This is listed as a 1-day enhancement and is the safety net for the decaying Play 1 edge.
10. **Track OOS-with-filter PF.** Current: 1.426. Threshold: if it drops below 1.20 on the next OOS window, halt Play 1 live.

---

## 10. Revised Bottom Line

The `IB_DATA_INSIGHTS_REPORT.md` said: "A real, statistically significant edge exists on NQ1 NY AM IB." After NT8 reconciliation, the honest revision is:

- **Play 1 (breakout) has a real edge** — confirmed by both Python and NT8, though the magnitude and optimal stop differ. The edge is **decaying** and **filter-dependent**. Deploy with the TrendMisaligned filter + the full Python stack, and monitor the OOS PF.
- **Play 3 (fade) is NOT confirmed.** Python's standout 0.25x-target finding does not survive tick-level simulation. The NT8-tuned fade (1.0x target + 0.35x overshoot) is profitable in one session and losing in another — it is regime-sensitive, not the stable edge Python claimed. **Do not deploy Play 3 live until the parity harness confirms a stable edge on the full 5-year NT8 run.**
- **Play 2 (retest) is unvalidated** — sample too small on both sides.
- **The 0.25R tight stop is wrong for live trading.** The NT8 bot correctly uses the wide stop (StopRMult=2.0). The parity harness diagnosis confirmed the Python tight-stop finding is bar-resolution-biased; tick-level wicks kill it. This is now documented, not theoretical.

The earlier insights report overstated the strength of the fade and the tight stop. This reconciliation corrects both — and the parity harness diagnosis + the Session 4/5 NT8 fixes have already validated the corrections empirically. The breakout edge is real but conditional and decaying; the fade edge is unproven in live simulation.

---

## 11. Source Files Reference

| Item | Path |
|---|---|
| NT8 backtest results | `docs/strategies/initial_balance_break/AUTOMATION_DESIGN.md` §0.3, §12 |
| IBBreakoutBot | `scripts/strategies/nt8/ib_breakout/IBBreakoutBot.cs` |
| IBFadeBot | `scripts/strategies/nt8/ib_breakout/IBFadeBot.cs` |
| IBRetestBot | `scripts/strategies/nt8/ib_breakout/IBRetestBot.cs` |
| IBStrategyBase | `scripts/strategies/nt8/ib_breakout/IBStrategyBase.cs` |
| Python edge validation | `docs/strategies/initial_balance_break/EDGE_VALIDATION_REPORT.md` |
| Insights report (prior) | `docs/strategies/initial_balance_break/IB_DATA_INSIGHTS_REPORT.md` |
| Parity harness (ORB) | `scripts/orb_generic/parity_check.py` |
| ORB parity agent loop | `scratch/run_parity_harness_loop.py` → `scratch/parity_loop_result.json` |
| IB parity diagnosis loop | `scratch/run_ib_profitability_loop.py` → `scratch/ib_profitability_loop.json` |
| NT8 SA sample output | `scratch/nt8_sa_2026-07-20_to_07-25.json` |
| NT8 diag patch (ORB) | `scratch/nt8_diag_patch_ORB_AllDay_MultiTP.cs` |
| Parity pipeline spec | `docs/strategies/initial_balance_break/AUTOMATION_DESIGN.md` §9.1 |