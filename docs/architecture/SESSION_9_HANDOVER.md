# Session Handover — IB Strategy Parity & Profitability

> **Date**: 2026-07-29 (Session 9, end of day)
> **Status**: Parity COMPLETE (100% live, 98.3% full range). Profitability analysis started.
> **Next session**: Re-run MAE/MFE in normalized terms + IBRetestBot parity + profitability optimization

---

## 1. What Was Accomplished This Session

### Parity Verification — COMPLETE
- Compiled latest NT8 code (0 errors, hot-swap OK)
- Verified all 8+ fixes in code AND compiled binary
- Full-range parity (19 months, 2025-01-01 → 2026-07-29): **98.3% (174/177)** result agreement
- July 2026 (live data, no back-adjustment): **100% (12/12)**
- Back-adjustment offset measured from IB boundaries: ~924pts (Jan 2025) unwinding to ~9pts (Jul 2026)
- The 3 disagreements are caused by: (a) entry fill price differences of 4-24pts due to NT8 missing bars in cached data, (b) tick vs 1-min bar resolution at stop/target boundaries
- The 1 remaining disagreement (2026-05-25) is caused by NT8 missing 15 of 30 IB-window bars — data completeness issue, not a code bug

### Stop Fix — Applied & Verified
- **IBBreakoutBot**: stop was entry-relative (`entry - StopRMult*TargetLvl*range`). Changed to IB-relative (`rangeLow` for long, `rangeHigh` for short = opposite IB boundary). The canonical `ib.py` already had this correct.
- **IBRetestBot**: already correct — stop at `rangeLow`/`rangeHigh` (opposite IB boundary) ✓
- **IBFadeBot**: already correct — stop at `rangeHigh + StopRMult*range` (beyond boundary, IB-relative) ✓
- **Parity harness**: Play 1 stop fixed to `ib_low`/`ib_high`. Play 3 (fade) already correct.

### Testing Contract — ESTABLISHED
- **Always use NQ 09-26 (NQ SEP26)** for NT8 backtests — matches `live_storage_-NQ.parquet`
- Previous runs used NQ 03-26 or MNQ → false "Class E" divergence (contract-month mismatch)
- Recorded in memory, docs, and parity standard

### MAE/MFE Analysis — Started (needs re-run in normalized terms)
- 188 trades, 19 months analyzed
- Key finding: losers have very low MFE (median 24pts ≈ 15% of range) — clean separation from winners
- Current geometry (IB-relative stop = 1.0*range, target = 0.5*range) creates inverted R:R (0.5:1.0)
- Tight stop at 0.25*range gives PF 1.27, E[pts]=+6.6 (marginally positive, 54 trades)
- **CORRECTION NEEDED**: MAE/MFE must be in price % and % of IB range, not points (per ADR-002)

---

## 2. Current State of All Files

### Code Fixes (all committed)
| File | Fix | Commit |
|---|---|---|
| `scripts/strategies/nt8/ib_breakout/IBBreakoutBot.cs` | Stop → IB-relative (rangeLow/rangeHigh) | `f3ec4032` + later |
| `scripts/validation/ib_parity_harness.py` | Play 1 stop → ib_low/ib_high | `f3ec4032` + later |
| `scripts/edgeful/ib_avwap_trend.py` | EMA → IB window close (09:59) | `532f813c` |
| `docs/strategies/ninjatrader/risk_manager_suite/RiskManagerBase.cs` | Docs copy synced (FlattenPosition + guard) | `532f813c` |
| `data/derived/ib_avwap_NQ1.parquet` | Regenerated with IB-close EMA | `532f813c` |
| `data/derived/ib_confluence_NQ1.parquet` | Regenerated with IB-close EMA | `532f813c` |
| `docs/architecture/NT8_PYTHON_PARITY_STANDARD.md` | Rewritten — stale content removed | `f3ec4032` + later |

### NT8 Sync State
- 19 files identical between repo source (`scripts/strategies/nt8/`) and NT8 live folder
- IBBreakoutBot.cs synced with stop fix
- Compile: 0 errors, 25 pre-existing warnings (none in Vinay bots)

### Memory State
- `/memories/ib_parity_state.md` — persistent status snapshot
- `memory.db` entries: parity verification, testing contract, back-adjustment offset, MAE/MFE analysis, stop fix, deja-vu prevention

---

## 3. Plan for Next Session

### Step 1: Re-run MAE/MFE in Normalized Terms (ADR-002 compliance)
- MAE and MFE must be in **price percentage** (MAE/entry_price × 100) AND **IB range percentage** (MAE/ib_range × 100)
- Do NOT use absolute points (not comparable across time/price levels)
- Re-run the analysis on the 188-trade dataset from `scratch/ib_parity_sep26_full.csv`
- The CSV already has `py_mae`, `py_mfe`, `py_ib_range`, `py_entry_price` columns
- Output: winner/loser MAE/MFE percentiles in % terms, stop optimization grid in % terms

### Step 2: IBRetestBot Parity Check
- Run NT8 backtest: `IBRetestBot` on `NQ 09-26`, 2026-03-13 to 2026-07-29 (or full range)
- Run Python parity harness: `--play 2` (or adapt for retest — the harness currently only has Play 1 and Play 3)
- IBRetestBot already has correct IB-relative stops (rangeLow/rangeHigh)
- Check if the parity harness supports Play 2 — if not, add `simulate_play2_day` to the harness
- Compare result agreement — should be similar to Play 1 (98%+)

### Step 3: IBRetestBot MAE/MFE & Profitability
- Run the same MAE/MFE analysis on IBRetestBot trades
- IBRetestBot entry = rangeMid (IB mid), stop = opposite boundary, target = ib_high + TargetLvl*range
- Risk = rangeMid - rangeLow = 0.5*range (for long), reward = ib_high + 0.5*range - rangeMid = 1.0*range
- R:R = 1.0:0.5 = 2:1 (FAVORABLE — opposite of Play 1's problem!)
- Prior backtest: PF 1.638 (Session 5, MNQ 03-25, Jan-Mar 2025) — need to verify on NQ 09-26

### Step 4: Stop Geometry Decision for IBBreakoutBot
The IB-relative stop (opposite boundary = 1.0*range) creates inverted R:R. Options:
- **Option A**: Keep IB-relative stop (correct for parity) but change TargetLvl to 1.0*range (R:R = 1:1). Need to check if WR at 1.0*range target is high enough.
- **Option B**: Use a tight entry-relative stop at 0.25*range (PF 1.27, E[pts]=+6.6) but accept that parity won't be 100% (stop is entry-relative). The target stays IB-relative.
- **Option C**: Use IB-relative stop but at a FRACTION of the opposite boundary — e.g. stop = ib_low + 0.25*range (long) = 75% of the way to the opposite boundary. This is both IB-relative AND tighter.
- **Option D**: Abandon Play 1 breakout, focus on Play 2 (retest) which has favorable R:R (2:1) and prior PF 1.638.

### Step 5: Document Everything
- Update `NT8_PYTHON_PARITY_STANDARD.md` with normalized MAE/MFE results
- Update `AUTOMATION_DESIGN.md` with stop geometry decision
- Record all findings to `memory.db`

---

## 4. Key Commands for Next Session

```bash
# Sync startup
sync  (runs the full startup sequence)

# NT8 backtest (ALWAYS use NQ 09-26)
# POST /api/backtest {strategy:'IBRetestBot', symbol:'NQ 09-26', from:'2026-03-13', to:'2026-07-29', period:'Minute', periodValue:1, maxTrades:5000, timeoutSec:420}

# Python parity harness (Play 1)
python -m scripts.validation.ib_parity_harness --ticker NQ1 --play 1 --target 0.5 --stop-mult 2.0 --from 2025-01-01 --to 2026-07-29 --avwap-source parquet --nt8-json scratch/nt8_ib_breakout_nq_sep26_full.json --out scratch/ib_parity_sep26_full.csv

# Sync NT8 strategies
python scripts/utils/sync_nt8_strategies.py --verify

# Compile NT8
# POST /api/compile then GET /api/compile/result

# Save NT8 backtest JSON (strip BOM)
$content = Get-Content "scratch/file.json" -Raw
[System.IO.File]::WriteAllText("path", $content, (New-Object System.Text.UTF8Encoding $false))
```

---

## 5. Open Items (from earlier audit)

| # | Item | Status | Priority |
|---|---|---|---|
| 1 | EMA residual (8 Python-only trades) | Known — EMA close convention | Low |
| 2 | RiskGatekeeper live-account verification | NOT TESTED on live SIM | High (pre-deployment) |
| 3 | Walk-forward validation | NOT DONE | Medium |
| 4 | IBBreakoutBot stop geometry | IB-relative stop creates inverted R:R — need decision | High |
| 5 | IBRetestBot parity check | NOT DONE | High |
| 6 | MAE/MFE in normalized terms | Started but used points, needs re-run in % | High |
| 7 | IBFadeBot profitability | PF 0.742-0.802, negative — deprioritized | Low |

---

## 6. Critical Context (do NOT re-derive)

- **Testing contract**: NQ 09-26 (NQ SEP26) — NOT NQ 03-26 or MNQ
- **Parity is COMPLETE**: 100% on live July data, 98.3% full range. Do NOT re-investigate parity.
- **The 3 disagreements**: caused by NT8 missing bars in cached data + entry fill differences. NOT code bugs.
- **Back-adjustment offset**: ~924pts (Jan 2025) → ~9pts (Jul 2026). Constant within a day. NOT the cause of disagreements (user corrected this).
- **Stop fix**: IBBreakoutBot stop changed from entry-relative to IB-relative (opposite boundary). IBRetestBot and IBFadeBot were already correct.
- **Geometry problem**: IB-relative stop (1.0*range) + 0.5*range target = inverted R:R (0.5:1.0). This is the core profitability issue.
- **MAE/MFE must be in % terms** (ADR-002): price % and IB range %, NOT absolute points.
- **All parity docs**: `docs/architecture/NT8_PYTHON_PARITY_STANDARD.md` — read §8-§11 before any parity work.
- **Memory**: `/memories/ib_parity_state.md` — persistent status snapshot. `memory.db` has all session findings.

---

## 7. File Locations

| Resource | Path |
|---|---|
| Parity standard doc | `docs/architecture/NT8_PYTHON_PARITY_STANDARD.md` |
| Parity harness | `scripts/validation/ib_parity_harness.py` |
| Canonical Python evaluator | `scripts/libs_py/nqstats/ib.py` |
| NT8 IBBreakoutBot | `scripts/strategies/nt8/ib_breakout/IBBreakoutBot.cs` |
| NT8 IBRetestBot | `scripts/strategies/nt8/ib_breakout/IBRetestBot.cs` |
| NT8 IBFadeBot | `scripts/strategies/nt8/ib_breakout/IBFadeBot.cs` |
| NT8 IBStrategyBase | `scripts/strategies/nt8/ib_breakout/IBStrategyBase.cs` |
| Confluence pipeline | `scripts/edgeful/ib_avwap_trend.py` |
| Sync script | `scripts/utils/sync_nt8_strategies.py` |
| Persistent memory | `/memories/ib_parity_state.md` |
| Shared memory | `.agent/memory.db` (use `remember.py` / `recall.py`) |
| NT8 backtest JSON (full range) | `scratch/nt8_ib_breakout_nq_sep26_full.json` |
| NT8 backtest JSON (fixed stop) | `scratch/nt8_ib_breakout_nq_sep26_fixed.json` |
| Parity CSV (full range) | `scratch/ib_parity_sep26_full.csv` |
| Parity CSV (fixed stop) | `scratch/ib_parity_sep26_fixed.csv` |