# Session 10 Plan — IB Profitability, Normalized MAE/MFE & Retest Entry Zone

> **Date**: 2026-07-29 (Session 10, start)
> **Predecessor**: `SESSION_9_HANDOVER.md` — parity COMPLETE (100% live, 98.3% full range)
> **Focus**: Profitability analysis + IBRetestBot parity + entry-zone optimization

---

## 0. Trading Thesis — Why the 40-60% Zone (Not the Mid)

The IB retest entry (Play 2) is conventionally taught as "enter at the IB mid"
(`rangeMid = (ib_high + ib_low) / 2`). But the **mid is a single point** — price
rarely tags it precisely on a retest, and forcing a mid entry means either:

1. **Missing the retest** when price reverses at the 40% or 60% retracement
   (a "shallow" retest that never reaches mid), or
2. **Entering too early** on a deep retest that blows through mid toward the
   opposite boundary (turning a retest into a breakout-failure).

The IB retest is really a **return-to-mean** trade. The mean of the IB is the
mid, but the **practical retest zone** is the 40-60% band (in IB-range terms,
that's `ib_low + 0.40*range` → `ib_low + 0.60*range`). This band:

- Captures shallow retests (40%) that reverse before reaching mid.
- Captures deep retests (60%) that overshoot mid slightly.
- Is **6× wider** than a single mid point → more trades, less slippage sensitivity.
- Keeps R:R favorable: entry at 40% → stop at opposite boundary = 0.60*range risk,
  target = `ib_high + 0.5*range` → reward = 1.1*range → R:R ≈ 1.83:1. Entry at
  60% → risk 0.40*range, reward 0.90*range → R:R ≈ 2.25:1. Both beat the mid's
  flat 2.0:1 on average because the band skews toward better entries.

**The question for data**: Does price retest to the **mid**, the **25% level**
(`ib_low + 0.25*range` = shallow), or does the **40-60% band** cover the bulk of
reversals? We need the MAE/MFE of the retest pullback (how deep does the retest
go before reversing) to choose the entry trigger zone. This is exactly what
Step 5 measures.

---

## 1. Pre-flight Finding — Missing Parity CSVs

The handover references `scratch/ib_parity_sep26_full.csv` and
`scratch/ib_parity_sep26_fixed.csv`, but these **do not exist** on disk.
Only the NT8 backtest JSONs exist (`scratch/nt8_ib_breakout_nq_sep26_full.json`,
132KB; `..._fixed.json`, 32KB). Step 1 must regenerate the CSV by running the
parity harness before any normalized analysis is possible.

---

## 2. The Plan

### Step 1 — Re-run MAE/MFE in Normalized % Terms (ADR-002)

**Goal**: Replace the absolute-points MAE/MFE from Session 9 with ADR-002-compliant
normalized metrics.

**Why**: Absolute points are not comparable across time/price levels (NQ ranged
~17,900 in Jan 2025 to ~30,400 in Jul 2026). ADR-002 mandates **price %** and
**IB range %**.

**Method**:
1. Regenerate the parity CSV by running the harness on the full-range NT8 JSON:
   ```bash
   python -m scripts.validation.ib_parity_harness --ticker NQ1 --play 1 \
     --target 0.5 --stop-mult 2.0 --from 2025-01-01 --to 2026-07-29 \
     --avwap-source parquet \
     --nt8-json scratch/nt8_ib_breakout_nq_sep26_full.json \
     --out scratch/ib_parity_sep26_full.csv
   ```
2. The harness already emits `mae`, `mfe`, `ib_range`, `entry_price` per trade.
3. Write a small analysis script (`scratch/analyze_mae_mfe_normalized.py`) that:
   - Loads the CSV.
   - Adds `mae_price_pct = mae / entry_price * 100`.
   - Adds `mfe_price_pct = mfe / entry_price * 100`.
   - Adds `mae_range_pct = mae / ib_range * 100`.
   - Adds `mfe_range_pct = mfe / ib_range * 100`.
   - Splits winners (result=+1) vs losers (result=-1).
   - Reports percentiles (P10, P25, P50, P75, P90, P95) for each metric.
   - Outputs a stop-optimization grid: for stop ∈ {0.25, 0.40, 0.50, 0.60, 0.75, 1.0}×range,
     compute WR, PF, E[R], trade count (how many losers have MAE > stop, how
     many winners have MFE > target at 0.5×range).
4. The key output: **P50/P75 winner MFE in range %** tells us the realistic
   target ceiling; **P50/P75 loser MAE in range %** tells us where stops belong.

**Deliverable**: `scratch/mae_mfe_normalized_report.json` + console summary table.

---

### Step 2 — Add Play 2 to the Parity Harness (40-60% Entry Zone)

**Goal**: Extend `ib_parity_harness.py` to support `--play 2` (IBRetestBot)
with a **configurable retest entry zone**, NOT a fixed mid.

**Why**: The current harness only supports Play 1 (breakout) and Play 3 (fade).
IBRetestBot parity (Step 4) requires Play 2. Per the thesis in §0, the entry
should be a **band** (default 40-60% of IB range from the broken boundary), with
the data telling us whether mid, 25%, or 40-60% is the empirical retest depth.

**Design** (mirrors `IBRetestBot.cs` + `simulate_play3_day`):
- New `simulate_play2_day(day_bars, ib_high, ib_low, ib_range, target_lvl,
  stop_mult, retest_low_pct, retest_high_pct)`:
  - **Signal**: after the IB forms (09:30-10:00 ET), price breaks one boundary
    (close beyond `ib_high` for long, `ib_low` for short), then **retests** back
    INTO the IB toward the opposite side.
  - **Entry zone**: the retest is "complete" when price touches the entry band.
    For a long (broke `ib_high`): entry band = `ib_low + retest_low_pct*range`
    → `ib_low + retest_high_pct*range`. Default `retest_low_pct=0.40`,
    `retest_high_pct=0.60`. The mid is `retest_low_pct=0.50, retest_high_pct=0.50`.
  - **Entry price**: next-bar-open after the retest band is touched (market order,
    parity with NT8).
  - **Stop**: opposite IB boundary (`ib_low` for long, `ib_high` for short) —
    IB-relative, already correct in `IBRetestBot.cs`.
  - **Target**: `ib_high + target_lvl * range` (long) / `ib_low - target_lvl*range`
    (short) — symmetric to the break direction.
  - **Tie-break**: conservative (stop-wins), matching Play 1/3.
  - **TargetIsSane**: reject if target ≤ entry (long) or target ≥ entry (short).
- Add CLI flags: `--retest-low-pct` (default 0.40), `--retest-high-pct` (default 0.60).
- Extend `--play` choices to `[1, 2, 3]`.
- The entry-zone band lets us **sweep** in Step 5: run the harness with
  `--retest-low-pct 0.25 --retest-high-pct 0.25` (25% level), `0.50/0.50` (mid),
  `0.40/0.60` (band), `0.30/0.70` (wide band) and compare trade counts + PF.

**Deliverable**: harness supports `--play 2` with configurable retest zone.

---

### Step 3 — Run IBRetestBot NT8 Backtest (NQ 09-26)

**Goal**: Get the ground-truth NT8 trade ledger for IBRetestBot to compare against.

**Contract**: NQ 09-26 (NQ SEP26) — NOT 03-26 or MNQ.

**Method**:
1. Verify `IBRetestBot.cs` is compiled (sync + `/api/compile`).
2. POST `/api/backtest`:
   ```json
   {"strategy":"IBRetestBot","symbol":"NQ 09-26",
    "from":"2025-01-01","to":"2026-07-29",
    "period":"Minute","periodValue":1,"maxTrades":5000,"timeoutSec":420}
   ```
3. Save JSON to `scratch/nt8_ib_retest_nq_sep26_full.json` (strip BOM if needed).

**Deliverable**: NT8 retest trade JSON on disk.

---

### Step 4 — Run IBRetestBot Python Parity Check

**Goal**: Verify Play 2 parity matches Play 1's ceiling (~98%+).

**Method**:
```bash
python -m scripts.validation.ib_parity_harness --ticker NQ1 --play 2 \
  --target 0.5 --retest-low-pct 0.40 --retest-high-pct 0.60 \
  --from 2025-01-01 --to 2026-07-29 --avwap-source parquet \
  --nt8-json scratch/nt8_ib_retest_nq_sep26_full.json \
  --out scratch/ib_parity_retest_sep26.csv
```
- Compare result agreement, trade counts, entry-time diffs.
- If parity < 90%, diagnose using the parity standard checklist (§2). Likely
  candidates: retest-trigger definition mismatch, or entry-zone band vs NT8's
  fixed mid.

**Deliverable**: parity CSV + agreement report.

---

### Step 5 — IBRetestBot MAE/MFE & Entry-Zone Sweep (the data question)

**Goal**: Answer the thesis question — does price retest to **mid**, **25%**, or
does the **40-60% band** capture more reversals?

**Method**:
1. Run the normalized MAE/MFE analysis (same script as Step 1) on the Play 2 CSV.
2. **Retest-depth analysis**: for each retest day, measure how far price pulled
   back into the IB before reversing (the "retest depth" in range %). This is the
   MAE of the pre-entry pullback, measured from the broken boundary. Distribution
   tells us where entries actually happen.
3. **Entry-zone sweep**: run the harness with these configurations and tabulate
   trade count, WR, PF, E[R]:
   | Config | retest_low_pct | retest_high_pct | Meaning |
   |---|---|---|---|
   | Mid point | 0.50 | 0.50 | Classic retest (single price) |
   | 25% level | 0.25 | 0.25 | Shallow retest |
   | 40-60 band | 0.40 | 0.60 | Thesis default |
   | 30-70 band | 0.30 | 0.70 | Wide band |
   | 35-65 band | 0.35 | 0.65 | Moderate band |
4. The config with the best PF × trade-count (enough trades to be statistically
   meaningful, ideally ≥30) wins. If the 40-60 band captures, say, 2× the trades
   of the mid with comparable WR, that confirms the thesis.

**Deliverable**: `scratch/retest_zone_sweep_report.json` + recommendation.

---

### Step 6 — IBBreakoutBot Stop Geometry Decision

**Goal**: Resolve the inverted R:R (0.5:1.0) problem for Play 1.

**Method**: Use the normalized MAE/MFE percentiles from Step 1 to pick among:
- **Option A**: Keep IB-relative stop (1.0×range), raise target to 1.0×range
  (R:R 1:1). Check if WR at 1.0×range target ≥ 50% (breakeven).
- **Option B**: Tight entry-relative stop at 0.25×range (PF 1.27 from Session 9).
  Accept parity < 100% (stop is entry-relative, not IB-relative).
- **Option C**: Fractional IB-relative stop — `ib_low + 0.25×range` (long).
  Both IB-relative AND tighter. Parity preserved if NT8 uses the same formula.
- **Option D**: Abandon Play 1, focus on Play 2 (favorable 2:1 R:R).

**Decision rule**: the P75 loser MAE in range % is the natural stop placement
(captures 75% of losers before they reverse). If P75 MAE ≈ 0.25×range, Option
B/C; if P75 MAE ≈ 1.0×range, the IB stop is correctly placed and only Option A
(raising target) fixes R:R.

**Deliverable**: documented decision with percentile evidence.

---

### Step 7 — Document & Remember

- Append **§11 "Session 10 — Normalized MAE/MFE + Retest Zone"** to
  `NT8_PYTHON_PARITY_STANDARD.md` with all numbers.
- Update `AUTOMATION_DESIGN.md` if stop geometry or retest zone changes.
- Write findings to `memory.db` via `remember.py`:
  - `--category INSTRUCTION --content "..." --tags "session10,mae_mfe,retest,zone,..."`
- Update `/memories/ib_parity_state.md` if profitability conclusions shift.

---

## 3. File Inventory

| Resource | Path | Status |
|---|---|---|
| Session 9 handover | `docs/architecture/SESSION_9_HANDOVER.md` | Read ✓ |
| Parity standard | `docs/architecture/NT8_PYTHON_PARITY_STANDARD.md` | Read ✓ |
| Parity harness | `scripts/validation/ib_parity_harness.py` | Needs Play 2 |
| IBBreakoutBot | `scripts/strategies/nt8/ib_breakout/IBBreakoutBot.cs` | Stop fixed ✓ |
| IBRetestBot | `scripts/strategies/nt8/ib_breakout/IBRetestBot.cs` | Ready |
| IBFadeBot | `scripts/strategies/nt8/ib_breakout/IBFadeBot.cs` | Ready (deprioritized) |
| NT8 breakout JSON (full) | `scratch/nt8_ib_breakout_nq_sep26_full.json` (132KB) | Exists ✓ |
| NT8 breakout JSON (fixed) | `scratch/nt8_ib_breakout_nq_sep26_fixed.json` (32KB) | Exists ✓ |
| Parity CSV (full) | `scratch/ib_parity_sep26_full.csv` | **MISSING — regenerate** |
| NT8 retest JSON | `scratch/nt8_ib_retest_nq_sep26_full.json` | **To create (Step 3)** |

---

## 4. Guardrails (from memory, do NOT re-derive)

- **Testing contract**: NQ 09-26 (NQ SEP26) — NOT NQ 03-26 or MNQ.
- **Parity is COMPLETE**: do NOT re-investigate EMA/AVWAP/TrendMisaligned (§8-§11).
- **The 3 disagreements**: NT8 missing bars + fill-price differences, NOT code bugs.
- **Stop fix**: IBBreakoutBot stop = IB-relative opposite boundary (already applied).
- **ADR-002**: all MAE/MFE in price % and IB range %, NOT absolute points.
- **ADR-017**: vectorized NumPy/Pandas, no for-loops in calc paths.
- **RiskGatekeeper live TODO**: potentialLoss uses ATR (8x over-estimate) — not
  this session's scope, but flag before any live deployment.