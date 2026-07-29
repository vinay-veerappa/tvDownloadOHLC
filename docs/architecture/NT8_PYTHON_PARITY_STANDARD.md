# NT8 ↔ Python Backtest Parity Standard

> **Status**: MANDATORY — all new strategies MUST comply with this standard before being declared "validated."
>
> **Created**: 2026-07-28 (derived from 6 sessions of IB strategy parity debugging)
>
> **Scope**: Any strategy that exists in both a Python vectorized evaluator and a NinjaTrader 8 (NT8) Strategy Analyzer backtest.

---

## 1. Why This Document Exists

Over 6 sessions of debugging the IB (Initial Balance) strategy family, we discovered that **Python backtests systematically overstate edge** vs NT8 live execution. The gaps fall into 5 classes (A–E), and each has silently inflated or deflated results in ways that took weeks to isolate. This document codifies the lessons so future strategies don't repeat the same mistakes.

### The 5 Divergence Classes (discovered)

| Class | Name | Description | IB Impact |
|---|---|---|---|
| **A** | Filter mismatch | Python has no filters; NT8 has filters that block trades | Trade count: Python 21 vs NT8 9 |
| **B** | Entry-price inflation | Python enters at boundary; NT8 enters at next-bar-open (market order) | E[R] +0.259 → -0.0024 (artifact eliminated) |
| **C** | Stop-geometry mismatch | Python uses one stop formula; NT8 inherits a different one from base class | 8x risk over-estimation |
| **D** | Liquidation fence mismatch | Python liquidates at 15:59; NT8 flattens at 15:50 | 5 extra trades held to close in Python |
| **E** | Session filter mismatch | Python includes Globex; NT8 trades RTH only (or vice versa) | First NT8 trade at 06:34 ET = pre-open |
| **F** | Timestamp convention mismatch | `data_loader.py` preferred numeric `time` column (ET-naive-as-UTC seconds) over `DatetimeIndex`, causing −5 h shift. IB computed on 04:30–05:00 ET (Globex) instead of 09:30–10:00 ET (RTH) | IB range sourced from wrong session; all downstream signals corrupted |

---

## 2. The Parity Checklist (MANDATORY for all new strategies)

Before declaring a strategy "validated" or "deployable," every item on this checklist MUST be verified:

### 2.1 Entry Model Parity

- [ ] **Entry trigger**: Python's signal condition matches NT8's `CheckForEntry()` exactly (close-confirmed, bar-close-only, same threshold).
- [ ] **Entry price**: Python uses the **same fill model** as NT8.
  - NT8 `EnterLong()` / `EnterShort()` = **market order** → fills at the **next bar's open**.
  - NT8 `EnterLong(qty, limitPrice)` = **limit order** → fills at `limitPrice` (if touched).
  - Python must replicate this: `entry_price = df['open'].values[signal_idx + 1]` for market orders, NOT the signal bar's close or the boundary price.
- [ ] **Entry timing**: Python's `entry_idx` is the bar AFTER the signal bar (next-bar execution), matching NT8's OnBarUpdate → order submission → next bar fill.

### 2.2 Stop / Target Geometry Parity

- [ ] **Stop formula**: Python's stop distance formula matches NT8's exactly (same multipliers, same base reference).
- [ ] **Risk metric**: If NT8 uses a range-based stop (`StopRMult * rangeRange`), Python must NOT use ATR (`StopAtrMult * atr`). These differ by 8–16x.
- [ ] **Tie-break**: Both systems use the same same-bar tie-break rule (Python: stop-wins conservative; NT8: `SetProfitTarget` before `SetStopLoss` = target-first). **Document which one is used.**
- [ ] **PotentialLoss gate**: NT8's `RiskGatekeeper.WouldBreachDailyMaxLoss` uses `GetPotentialLoss()` → `GetEstimatedRiskDistance()`. Verify the override chain returns the ACTUAL stop distance, not an ATR over-estimate.

### 2.3 Exit / Liquidation Parity

- [ ] **Liquidation time**: Python's `out_end` / liquidation fence matches NT8's `FlattenBy` exactly.
  - NT8 IB strategies: `FlattenBy = 1550` (flattens at 15:50 ET).
  - Python: must liquidate at the close of the **15:49 bar** (the bar whose close is at 15:50), NOT 15:59.
- [ ] **Liquidation price**: Both use the close of the liquidation bar (not open, not mid).
- [ ] **No overnight carry**: Both systems close all positions before session end (no Globex carry for RTH strategies).

### 2.4 Session Window Parity

- [ ] **RTH vs Globex**: If the strategy is RTH-only, Python's `in_out` mask must exclude Globex bars (pre-09:30 and post-16:00 ET). NT8 must have `EarliestEntry = 930` and `LatestEntry` set appropriately.
- [ ] **Timezone**: Both systems use ET (America/New_York) for session windows. Python parquet timestamps are UTC ms-epoch → must `tz_convert('America/New_York')` before filtering.
- [ ] **Trading date**: Python's `logical_date` must match NT8's session date (not UTC date). Calendar filters (skip-Mon, skip-Feb) must use ET session date.

### 2.5 Filter Parity

- [ ] **All NT8 filters replicated in Python**: Every filter gate in NT8 (`ConfluenceFilter`, `RequireDirectionBias`, calendar filters, range-size filters) must be ported to the Python evaluator, OR explicitly marked as "NT8-only" with a documented reason.
- [ ] **Filter data availability**: Before porting a filter, verify the Python parquet has the required columns. TPO/VPOC/volume-profile/order-flow columns may NOT exist in OHLCV-only parquet. **Audit columns first, port second.**
- [ ] **Filter ablation**: Run the Python evaluator with and without each filter individually. A filter that kills trade count but doesn't lift WR adds no alpha (the null hypothesis).

### 2.6 Statistical Significance

- [ ] **Sample size**: ≥120 trades per filter configuration across ≥3 regimes before declaring edge.
- [ ] **OOS validation**: Run on a DIFFERENT contract/period than the one used for optimization. IBBreakoutBot IS PF 1.489 → OOS PF 1.426 (edge persisted); IBFadeBot 2-week PF 1.295 → 3-month PF 0.742 (edge was noise).
- [ ] **Bootstrap CI**: For marginal edges (PF 0.8–1.2), compute bootstrap confidence intervals on per-session returns. If CI crosses zero, the edge is not statistically distinguishable from noise.

---

## 3. Known Pitfalls (from IB debugging)

### 3.1 The "0-Trade" Silent Failure Chain

NT8 Strategy Analyzer can produce 0 trades with NO error message. The 4-bug chain that caused this (Session 3):

1. **`BarsRequiredToTrade` set in `OnBarUpdate`**: NT8 throws "cannot be set from this state" on bar 0, silently disabling the strategy. **Fix**: set in `State.Configure`.
2. **`RiskGatekeeper.WouldBreachDailyMaxLoss` blocks backtest**: The AddOn registers the SA "Backtest" account with live risk limits. **Fix**: bypass all gatekeeper gates when `Account.Name` contains "backtest" or "Playback".
3. **`RangeSizeFilter` double-multiply by 100**: `rangePct = (range/prior*100)` compared against `MaxRangePct*100`, so 0.5% range < 10 (MinPct*100) blocked every session. **Fix**: compare `rangePct` directly against `MaxRangePct/MinPct`.
4. **`RequireDirectionBias=true` default**: with `predictedDir=0` (no bias), both long and short breaks blocked. **Fix**: default `false`.

**Lesson**: `Print()` in SA backtest goes to the SA UI window ONLY (invisible). Use `Log(msg, LogLevel.Information)` to write to `Documents/NinjaTrader 8/log/log.YYYYMMDD.00000.txt` — the ONLY way to trace SA backtest execution programmatically.

### 3.2 The PotentialLoss 8x Over-Estimation

`RiskGatekeeper.potentialLoss` used the ATR formula: `StopAtrMult * rangeRange * PointValue * Qty ≈ $143.75` for MNQ. The actual range-based stop distance is `StopRMult * TargetLvl * rangeRange ≈ $18`. This over-estimates by ~8x, blocking entries on funded accounts with tight daily loss limits.

**Fix**: Make `GetPotentialLoss()` virtual in `RiskManagerBase`. Override in `IntradayStrategyBase` to use `GetEstimatedRiskDistance() * PointValue * Qty`. Override `GetEstimatedRiskDistance()` in each bot to match the actual stop geometry.

### 3.3 The Entry-Price Inflation Artifact (Class B)

Python evaluators that enter at the signal bar's boundary price (`ib_high`/`ib_low`) create an artificial price advantage. NT8's `EnterLong()` / `EnterShort()` are **market orders** — they fill at the **next bar's open**, which is already inside the IB range for fades.

**Impact**: IBFadeBot E[R] went from +0.259 (boundary entry) to -0.0024 (next-bar-open entry). The entire "strongest single strategy" edge was a Python measurement artifact.

**Rule**: Always model the entry fill as the next bar's open for market-order strategies. Only use the signal-bar price if the NT8 bot uses a limit order at that exact price.

### 3.4 The Filter-Doesn't-Add-Alpha Null Result

When Python WR (57.1%) ≈ NT8 WR (55.6%) on matched trades, but NT8 has fewer trades (9 vs 21), the filters are removing trades **randomly** — not selectively blocking losers. Under a binomial null (p=0.5), observing 8/12 filtered-out trades as wins has p ≈ 0.19 (not significant).

**Rule**: Before loosening a filter, require ≥120 paired filter-on/filter-off trades across ≥3 regimes. Run a McNemar test on matched setup outcomes.

### 3.5 The 1:2 R:R Mathematical Ceiling

IBBreakoutBot: target = 50% of range, stop = 200% of range → 1:2 R:R. At 55.6% WR, PF = 0.556×2 / 0.444×1 = 1.25... wait, that's wrong. PF = (WR × reward) / (LR × risk) = (0.556 × 1) / (0.444 × 2) = 0.626. **A 1:2 R:R requires >66.7% WR to achieve PF > 1.0.** No amount of filter tuning fixes this — it's a geometry constraint.

**Rule**: Before deploying, compute the breakeven WR for the R:R ratio. If the validated WR is below breakeven, change the geometry BEFORE attempting filter optimization.

---

## 4. The Parity Validation Protocol

### Step 1: Audit (before writing any code)
1. List every filter, gate, and condition in the NT8 bot.
2. List every column the filters depend on.
3. Check if those columns exist in the Python parquet. If not, plan backfill or mark as "NT8-only."

### Step 2: Port entry/exit model
1. Match the entry trigger condition (close-confirmed, threshold, direction).
2. Match the entry fill model (market order → next-bar-open; limit order → limit price).
3. Match the stop/target formula exactly (same multipliers, same reference).
4. Match the liquidation fence (same ET time, same price source).

### Step 3: Run the parity harness
Use `scripts/validation/ib_parity_harness.py` as the template. Build a trade-by-trade ledger from both systems and diff them:

```python
# Python side
python -m scripts.validation.ib_parity_harness \
    --ticker NQ1 --play 1 --target 0.5 --stop-mult 2.0 \
    --from 2026-06-01 --to 2026-06-30 \
    --nt8-json scratch/nt8_ib_breakout_jun2026.json \
    --out scratch/ib_parity_breakout_jun2026.csv
```

### Step 4: Classify divergences
For each trade that exists in one system but not the other, classify it:
- **Class A** (filter mismatch): trade blocked by a filter in one system.
- **Class B** (entry-price): trade exists in both but entry prices differ.
- **Class C** (stop geometry): trade exists in both but stop distances differ.
- **Class D** (liquidation): trade liquidated at different times.
- **Class E** (session): trade exists in one system's session but not the other's.

### Step 5: Fix and re-run
Fix one class at a time, re-run the harness, and verify the divergence count drops. Do NOT fix multiple classes simultaneously (you won't know which fix worked).

---

## 5. LLM Debate Grounding Rules

From the IB profitability debate sessions (V1 failed, V2 succeeded):

1. **Always pass the diagnosis into the debate prompt.** V1 only substituted `%(role)s` and never passed the Maker's diagnosis to judges → judges got empty templates and said "cannot determine without diagnostic data."
2. **Always ground in actual current code state.** V1 diagnosed stale code (0.125×range stop) but the actual code already had `StopRMult=2.0`. Read the actual `.cs` files before diagnosing.
3. **Always run an empirical tracer BEFORE trusting an LLM debate.** The V1 debate moderated H2 (stop/target fill resolution) as dominant root cause. An empirical tracer disproved this: NT8's first trade was at 06:34 ET = pre-open Globex → H3 (RTH session filter) was the actual dominant cause.
4. **Judges should RANK all hypotheses**, not pick one. Ranking avoids premature convergence on a plausible-but-wrong answer.

---

## 6. NT8 Debugging Cheatsheet

| Symptom | First Check | Second Check | Third Check |
|---|---|---|---|
| 0 trades in SA | `BarsRequiredToTrade` in `OnBarUpdate` (move to `Configure`) | `RiskGatekeeper` blocking SA account (bypass for "backtest") | `RequireDirectionBias` default true (set false) |
| Over-trading (14 trades/day) | `PotentialLoss` 8x over-estimate (override `GetEstimatedRiskDistance`) | `RangeSizeFilter` double-multiply by 100 | `MaxTradesPerDay` not set |
| PF drops 3-month vs 2-week | 2-week result was favorable noise (run OOS) | Filter over-restriction (run ablation) | Entry-price inflation (check fill model) |
| Can't see Print() output | `Print()` goes to SA UI window only | Use `Log(msg, LogLevel.Information)` → `Documents/NinjaTrader 8/log/log.YYYYMMDD.00000.txt` | Check NT8 log file, not Output tab |
| MCP bridge goes down | Repeated hot-swap compiles crash SA AppDomain | Restart NT8 to reset SA window | Retry backtest after restart |

---

## 7. File References

| File | Role |
|---|---|
| `scripts/libs_py/nqstats/ib.py` | Canonical Python IB evaluator (`evaluate_all_plays_consolidated`) |
| `scripts/validation/ib_parity_harness.py` | Trade-by-trade parity validation harness |
| `scripts/strategies/nt8/base/IntradayStrategyBase.cs` | NT8 base class (entry/exit, `EnterWithRangeStop`) |
| `scripts/strategies/nt8/base/RiskManagerBase.cs` | NT8 risk gates (`CanEnterTrade`, `FlattenBy`, `RiskGatekeeper`) |
| `scripts/strategies/nt8/ib_breakout/IBStrategyBase.cs` | IB base (filters, defaults, `FlattenBy=1550`) |
| `scripts/strategies/nt8/ib_breakout/IBFadeBot.cs` | Play 3 fade bot (overshoot → close-back-inside) |
| `scripts/strategies/nt8/ib_breakout/IBBreakoutBot.cs` | Play 1 breakout bot |
| `scripts/utils/sync_nt8_strategies.py` | Single sync mechanism to NT8 live folder |
| `scripts/edgeful/ib_avwap_trend.py` | Confluence pipeline (AVWAP + EMA trend, daily-close EMA) |
| `scripts/edgeful/ib_master_confluence.py` | Master confluence parquet builder |
| `docs/architecture/STRATEGY_DESIGN_STANDARD.md` | SDS hunter/vectorization standard (Layer 4-5) |

---

## 8. Parity Validation Results (2026-07-29)

### Fixes Applied (Steps 1–5 + EMA + IB Duration)

| Fix | Class | File | Impact |
|---|---|---|---|
| Entry-price (next-bar-open) | B | `ib.py`, `ib_parity_harness.py` | E[R] +0.259 → -0.0024 (Play 3 artifact eliminated) |
| Liquidation fence 15:50 | D | `ib.py`, `ib_parity_harness.py` | 16 trades eliminated (9-min gap closed) |
| ConfluenceFilter port | A | `ib.py` | 4975→1249 trades, E[R] +17% |
| Play 2 entry parity | B | `ib.py` | WR 42%→14.3% (mid-price artifact removed) |
| Geometry decision | — | none (confirmed) | Keep 1:2 R:R — PF 1.415 with filter |
| IB duration 30-min | — | `ib.py` SESSION_CONFIGS_V5 | ib_end 10:30→10:00 (matches NT8 RangeDurationMin=30) |
| EMA on daily closes | A | `ib_avwap_trend.py` | Overlap 7→29 days (4x), match 72.4% |

### 6-Month Day-by-Day Win/Loss Parity (Jan–Jun 2026)

| Metric | Value |
|---|---|
| NT8 trades | 51 (39 trade days) |
| Python trades | 60 (60 trade days) |
| Overlapping days | 29 |
| Win/loss match | **21/29 (72.4%)** |
| Both WIN | 14 |
| Both LOSS | 7 |
| Mismatch | 8 |

### By Period

| Period | Match | Notes |
|---|---|---|
| Feb–Mar 2026 | **16/18 (89%)** | Best alignment — code parity confirmed |
| Jan 2026 | 1/5 (20%) | AVWAP anchor offset from roll gap affects `break_vs_avwap_0930` |
| May–Jun 2026 | 4/6 (67%) | Moderate data gap |

### Note on Continuous vs Raw Contract (empirically verified 2026-07-29)

**CORRECTION**: The initial assumption that "a futures roll adjustment is a
constant price offset" is **WRONG**. Empirical testing
(`scratch/diagnose_avwap_parity.py`) across 51 NT8 trades (Jan-Jun 2026) showed:

- Price offset (NT8 - Python): mean=55.75, **std=233.24**, range -643.75 to +438.00
- Price ratio (NT8/Python): mean=1.0025, **std=0.0087**, range 0.979 to 1.017
- **Neither constant nor multiplicative** — the two "continuous" feeds use
  fundamentally different roll adjustment methods and volume profiles.

**What IS feed-invariant** (unaffected by the roll construction):
- IB range (high - low is the same within a day)
- Break direction (close > ib_high is the same in both series)
- Win/loss outcome (stop/target distances are the same)

**What is NOT feed-invariant** (affected by the roll construction):
- **AVWAP** (`break_vs_avwap_0930`): cumulative TPV/Vol from 09:30. Different
  feeds have different absolute prices AND volume profiles, so the AVWAP lands
  at different relative positions. The sign of (close > AVWAP) **flips** on
  ~36% of days (8/22 June days). This is the `break_vs_avwap_0930` common gate.
- **TrendMisaligned** (`trend_misaligned_with_break`): daily EMA20/EMA50. The
  EMA is computed on daily closes from the fused historical+live loader, which
  uses a different continuous construction than NT8's ##-## feed. The EMA
  crossover can differ, flipping the trend filter.

### AVWAP Feed Fix (2026-07-29 Session 7)

Added `--avwap-source {parquet,onthefly,none}` CLI flag to `ib_parity_harness.py`:

| Source | Description | Trade count (6mo) | W/L match | Use case |
|---|---|---|---|---|
| `none` | Disable ConfluenceFilter entirely | 127 | 29/39 (74.4%) | Ablation baseline |
| `parquet` | Pre-computed ib_confluence (fused loader) | 60 | 22/29 (75.9%) | Production pipeline parity |
| `onthefly` | Compute AVWAP from harness's own bars | 60 | 22/29 (75.9%) | Python self-consistency |

**Key finding**: `parquet` and `onthefly` produce IDENTICAL trade counts and
match rates. The TrendMisaligned filter (from the parquet) is the dominant gate;
the AVWAP common gate (break_vs_avwap_0930 != 0) rarely blocks since most days
have a clear break direction. The AVWAP sign flip on 36% of days does NOT change
which days pass the filter. The remaining 24.1% mismatch is from entry-time,
entry-price, and fill-resolution differences, NOT from AVWAP.

The secondary bug (harness `main()` not passing `confluence_row` to
`simulate_play1_day`) was also fixed — the harness now applies the
ConfluenceFilter, reducing over-trading from 127 to 60 trades.

---

## 10. Session 8 — Data Integrity & Timestamp Fix (2026-07-30)

### Root Cause: Class F — Timestamp Convention Mismatch

The dominant root cause of residual parity divergence was a **timestamp
convention bug** in `scripts/edgeful/lib/data_loader.py`. The loader fused
historical (`NQ1_1m.parquet`) and live (`live_storage_-NQ.parquet`) parquet
stores but had two compounding defects:

1. **NQ1_1m.parquet 2025+ corruption**: The historical file contained stale
   NT8 import data (not back-adjusted) from 2025-01-01 onward, and its `time`
   column had mixed units (ms vs sec vs corrupted values) introduced during a
   live merge.
2. **Loader preference bug**: `_read_and_normalize()` preferred the numeric
   `time` column over the `DatetimeIndex`. For historical data, the `time`
   column stores ET-naive-as-UTC unix seconds. When interpreted as UTC and
   converted to ET, this shifts all bars **−5 h** (EST) / **−4 h** (EDT),
   moving the 09:30 RTH open to 04:30/05:00 Globex.

### Fixes Applied

| Fix | File | Impact |
|---|---|---|
| Replace 2025+ data with live_storage back-adjusted | `scripts/data_processing/merge/fix_nq1_live_merge.py` (new) | NQ1_1m.parquet 2025+ now matches NT8 back-adjusted feed |
| Normalize mixed time units (ms/sec/corrupted) | `scripts/data_processing/merge/fix_nq1_time_column_v2.py` (new) | `time` column all unix seconds, consistent |
| Prefer DatetimeIndex over `time` column | `scripts/edgeful/lib/data_loader.py` | Eliminates −5 h shift; IB correctly at 09:30–10:00 ET |
| FVG fallback resample include open/close | `scripts/edgeful/ib_pipeline.py` | Fixes KeyError in FVG fallback path |
| Timezone handling in diff_ledgers | `scripts/validation/ib_parity_harness.py` | Correct ET conversion for trade time comparison |

### Regenerated Derived Tables

All downstream parquet tables rebuilt with the corrected loader:

| Table | Rows | Notes |
|---|---|---|
| `data/derived/ib_facts_NQ1.parquet` | 41,422 | IB ranges now ~197 pts for 2026 (was ~5 pts when shifted to Globex) |
| `data/derived/ib_avwap_NQ1.parquet` | 41,422 | AVWAP anchored to correct 09:30 ET session |
| `data/derived/ib_confluence_NQ1.parquet` | 41,422 × 352 | Full confluence matrix regenerated |

### Final Parity Result (Jan–Jun 2026, NQ JUN26 back-adjusted)

| Metric | Python | NT8 |
|---|---|---|
| Trades | 56 | 71 |
| Win rate | 64.3% | 63.4% |
| **Result agreement** | **93.6% (44/47 overlapping trades)** | |

**Key insight**: The contract price offset between NT8 NQ JUN26 and the Python
continuous feed is **irrelevant** to parity because the IB strategy is
relative (break = close > ib_high; both series shift by the same offset).

### Checklist Addition (Class F)

Before running any IB-family backtest, verify:
- [ ] `data_loader._read_and_normalize()` prefers `DatetimeIndex` over numeric `time` column
- [ ] `NQ1_1m.parquet` `time` column units are consistent (all unix seconds)
- [ ] IB range for a known date is sourced from 09:30–10:00 ET (not 04:30–05:00)

---

## 11. Revision History

| Date | Session | Change |
|---|---|---|
| 2026-07-28 | Session 6 | Initial document created from 6 sessions of IB parity debugging |
| 2026-07-29 | Session 6 | Added §8: parity validation results, EMA fix, IB duration fix, continuous vs raw contract note |
| 2026-07-29 | Session 7 | Corrected "constant offset" claim (empirically disproven: std=233pts). Added AVWAP feed fix (--avwap-source flag), secondary bug fix (confluence_row not wired in main()). |
| 2026-07-30 | Session 8 | Added Class F (timestamp convention mismatch), §10: data integrity & timestamp fix, 93.6% parity result. Fixed data_loader.py, ib_pipeline.py, ib_parity_harness.py. Regenerated derived tables. |