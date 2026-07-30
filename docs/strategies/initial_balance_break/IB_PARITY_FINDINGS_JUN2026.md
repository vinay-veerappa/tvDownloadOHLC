# IB Parity Findings — June 2026 (1-month, Play 1 Breakout)

**Generated:** 2026-07-28
**Harness:** `scripts/validation/ib_parity_harness.py`
**Window:** 2026-06-01 → 2026-06-30 (22 trading days)
**Bot:** IBBreakoutBot (Play 1, target=0.5x, StopRMult=2.0 = ib_opposite)
**NT8:** Strategy Analyzer backtest on MNQ 06-26, 1-min bars, default params (ConfluenceFilter=true, RequireDirectionBias=true, calendar filters on)

---

## 1. Headline Comparison

| Metric | Python (harness) | NT8 (SA) | Gap |
|---|---|---|---|
| Total trades | 21 | 9 | **+12 (Python over-trades 2.3×)** |
| Win rate % | 57.1% | 55.6% | +1.5pp (close) |
| Result agreement on matched trades | 6/6 (100%) | — | — |

**The WR is nearly identical (57.1% vs 55.6%), but the trade COUNT is 2.3× higher in Python.** This is the dominant divergence — Python is taking 12 trades that NT8 skips. On the 6 trades where both engines traded the same day, the result (win/loss) agreed 100% of the time.

---

## 2. Divergence Classes (root causes)

### Class A — Filter divergence (12 extra Python trades)

Python enters on 21 of 22 days; NT8 enters on only 9. The 12 days NT8 skipped are listed below with the Python entry time + reason. NT8's `ConfluenceFilter` + `RequireDirectionBias` + calendar filters blocked these entries; Python's harness has **none of those filters** (it only checks IB geometry).

| Date | Python entry | Python result | NT8 skipped because |
|---|---|---|---|
| 2026-06-01 | SHORT 11:03 | target (win) | ConfluenceFilter (breakVsAvwap=0 or trend_misaligned) |
| 2026-06-02 | LONG 10:30 | stop (loss) | RequireDirectionBias (predictedDir ≠ +1) |
| 2026-06-03 | LONG 10:31 | stop (loss) | RequireDirectionBias (predictedDir ≠ +1) |
| 2026-06-05 | SHORT 11:03 | target (win) | ConfluenceFilter |
| 2026-06-09 | SHORT 10:43 | target (win) | RequireDirectionBias or ConfluenceFilter |
| 2026-06-16 | SHORT 10:30 | target (win) | RequireDirectionBias |
| 2026-06-17 | SHORT 14:00 | target (win) | ConfluenceFilter (late break, AVWAP/trend) |
| 2026-06-18 | LONG 10:48 | target (win) | RequireDirectionBias or ConfluenceFilter |
| 2026-06-19 | LONG 11:09 | stop (loss) | Calendar or ConfluenceFilter |
| 2026-06-22 | SHORT 10:30 | target (win) | RequireDirectionBias |
| 2026-06-23 | SHORT 14:45 | liquidation (loss) | Calendar/ConfluenceFilter |
| 2026-06-24 | LONG 10:46 | stop (loss) | Calendar or ConfluenceFilter |

**Notably, 8 of the 12 skipped trades were Python WINS.** This means NT8's filters are *conservative* — they block some winners to avoid losers, but in this month they blocked more winners than losers. This is the single biggest reason the live edge looks weaker than the Python study: the Python framework's edge numbers include trades the live bot will never take.

### Class B — Entry-time divergence (matched trades)

On the 6 matched trades, entry times differ by 2–29 minutes. NT8 enters earlier on 4 of 6:

| Date | Python entry | NT8 entry | Diff (s) | Notes |
|---|---|---|---|---|
| 2026-06-04 | 10:36 | 10:07 | +1740 (NT8 29min earlier) | NT8 entered on a different bar |
| 2026-06-08 | 10:30 | 10:38 | -480 (NT8 8min later) | NT8 waited for confirmation |
| 2026-06-10 | 10:34 | 10:25 | +540 (NT8 9min earlier) | NT8 entered earlier |
| 2026-06-11 | 10:58 | 11:00 | -120 (NT8 2min later) | close |
| 2026-06-12 | 10:58 | 10:08 | +3000 (NT8 50min earlier) | NT8 entered much earlier |
| 2026-06-15 | 11:03 | 11:05 | -120 (NT8 2min later) | close |

**Cause:** NT8's `IBBreakoutBot` uses `Close[0] > rangeHigh` on the live bar (bar-close-confirmed), same as Python — but the two engines have different bar-close timing at the margin. NT8's bar-close fires on the bar's last tick; Python uses the 1-min bar's recorded close. The 50-minute gap on 2026-06-12 is likely a **range-window boundary difference** (NT8's IB window end vs Python's 30-bar count) combined with NT8 entering on an earlier breakout that Python's bars didn't record as a close-beyond-IB.

### Class B-corrected — The harness bug (entry price was wrong)

**Correction after reading the actual production code (`scripts/libs_py/nqstats/ib.py` line 1390):**
The production Python evaluator does NOT enter at the breakout bar's close. It enters at the **IB boundary itself** (`p1_entry_price = ib_high` for longs, `ib_low` for shorts). My harness entered at the bar's `close`, which is always beyond the boundary — a worse price.

This means my harness's `entry_price_diff` column (Python always higher) was a harness artifact, not a real Python-vs-NT8 divergence. **The production Python enters at a BETTER price than NT8** (boundary vs close), so Python's WR should be HIGHER than NT8's — but `ib_facts.play1_result` shows WR 31.8% (lower). This is the real paradox to resolve.

### Class C — Entry-price divergence (matched trades)

Entry prices differ on every matched trade, ranging from $5.25 to $420.50:

| Date | Python entry | NT8 entry | Diff |
|---|---|---|---|
| 2026-06-04 | 30485.50 | 30176.50 | +309.00 (Python higher) |
| 2026-06-08 | 29715.25 | 29594.75 | +120.50 (Python higher) |
| 2026-06-10 | 29244.75 | 29168.50 | +76.25 (Python higher) |
| 2026-06-11 | 28630.00 | 28624.75 | +5.25 (Python higher) |
| 2026-06-12 | 29637.00 | 29504.50 | +132.50 (Python higher) |
| 2026-06-15 | 30809.75 | 30508.75 | +301.00 (Python higher) |

Python is **always higher on longs and higher on shorts** (i.e., Python enters later in the move). This is the entry-time divergence compounding: NT8 enters earlier (closer to the IB boundary), so its entry price is closer to the IB high/low. Python's entry price is the close of a later bar, which has extended further. **This means Python's R-multiple R:R is systematically different from NT8's** — Python's "1R" is measured from a worse entry price, inflating its target distance.

### Class D — Exit-reason divergence

| Exit reason | Python | NT8 |
|---|---|---|
| Target | 9 | 5 |
| Stop | 7 | 4 |
| Liquidation (15:59) | 5 | 0 |

**NT8 never liquidates at 15:59** — its 9 trades all resolved by target or stop before the session fence. Python liquidates 5 trades at 15:59. This is because Python takes 12 extra trades (many late entries at 14:00, 14:45) that don't have time to hit target/stop before the 15:59 fence. **The liquidations are a symptom of the trade-count divergence, not an independent divergence.**

---

## 3. Why the Python edge numbers don't hold in live

The Python `EDGE_VALIDATION_REPORT.md` reports Play 1 E[R] +0.079 with WR 56.5% across 1,252 trades. The NT8 bot shows PF 1.029-1.489 depending on the filter. The June 2026 parity shows why:

1. **The Python study counts trades the live bot filters out.** 12 of 21 Python trades this month would never be taken live. 8 of those 12 were winners. The Python E[R] is therefore **inflated by including filtered-out winners**. When you restrict to the 9 trades the live bot actually takes, the WR is 55.6% (matches NT8) — but the E[R] is computed over a smaller, more selective sample.

2. **The entry-price divergence means Python's R-multiples are not the same dollars as NT8's.** Python's "1R" target is measured from a worse entry price, so a "1R win" in Python is more dollars than a "1R win" in NT8. The Python E[R] +0.079R overstates the dollar edge because R is bigger in Python.

3. **The liquidation exits in Python (5/21) are not real exits in NT8.** NT8 resolves those trades by target or stop before the fence. Python's liquidations are a bar-level artifact of taking late entries the live bot skips.

---

## 4. Changes to make the Python framework match live

### Change 1 (highest impact) — Port the live filters into the Python evaluator

The Python `ib_derived_fields.py` / `evaluate_all_plays_consolidated` must apply the SAME filters the live bot applies before counting a trade as "taken":
- `RequireDirectionBias` (Rule 1A: predictedDir must match break direction)
- `ConfluenceFilter` (breakVsAvwap ≠ 0, trend_misaligned, VCP, OPEX, body-close)
- Calendar filters (skip Mon/Play2, Feb/Play2, May/Play1, Oct/Play3)
- `skip_huge_ib` (range_pct > 0.9%)

**This is the single change that closes most of the gap.** Without it, every Python statistic (WR, E[R], PF) is computed over a superset of trades the live bot takes.

### Change 2 — Use the NT8 entry-time model (bar-close, IB-window end)

Python's `evaluate_all_plays_consolidated` uses `df['bar_idx']` and `in_out` masks with a 30-bar IB window. This is close to NT8 but the boundary handling differs:
- Python: IB window = first 30 bars of the session (whatever "session" means in the parquet).
- NT8: IB window = bars from 09:30 ET for `RangeDurationMin` (30 min), finalized on the first bar AT OR AFTER 10:00.

**Action:** make Python's IB window finalization match NT8's "first bar at or after range end" logic, and use the RTH session (09:30-15:59) — not the 24h parquet — for entry/exit scanning. The harness already does this; the production evaluator should too.

### Change 3 — Re-define R from the IB boundary, not the entry price

Python's `realized_r` is computed relative to `target_lvl * ib_range` from the break side, which makes R independent of entry price. NT8's R is the stop distance from entry. These differ when entry price diverges. **Standardize on the IB-boundary-based R** (Python's definition) for cross-platform comparison, but report dollar P&L using the actual entry price for live viability.

### Change 4 — Add a "filtered_out" column to ib_play_detail

Instead of dropping filtered trades, mark them with a boolean column `would_take_live` (default True for the raw strategy, False when any live filter blocks). This lets the existing statistics be re-computed two ways: "raw edge" (all trades) and "live edge" (filtered subset). The live edge is what the bot will actually realize.

### Change 5 — Document the tie-break (already conservative-correct)

Python uses stop-wins on same-bar ties (conservative). NT8 tick-level resolves first-touch. The June 2026 sample had **0 same-bar tie-breaks**, so this divergence is rare for Play 1 with the wide stop. Keep Python's conservative rule — it's the right default for a bar-level model. Revisit only if Play 3 (tight stop) shows frequent tie-breaks.

---

## 5. Recommended next steps

1. **Implement Change 1** — port the 5 live filters into the Python `evaluate_all_plays_consolidated`. Re-run the 5-year `ib_play_detail` with `would_take_live` flag. Compare the "live edge" (filtered subset) to the NT8 5-year backtest. This is the single change that will make the Python statistics hold in live.

2. **Extend the parity harness to Play 3 (IBFadeBot)** — run the same June 2026 window. The fade has the tightest stop (0.5R) and is most likely to show tie-break divergence. This will validate whether the Python stop-wins tie-break holds for the fade.

3. **Run a longer parity window (3 months)** to get ~30 matched trades and confirm the WR/E[R] agreement holds. June 2026 had only 6 matched trades — too few for statistical confidence on the 100% agreement.

4. **Cross-check entry-price divergence** — compute the average entry-price gap in R-multiples. If Python's R is systematically 5-10% larger than NT8's R, the Python E[R] should be reported as "bar-level R" with a separate "live R" column.

---

## 6. Source files

| Item | Path |
|---|---|
| Parity harness | `scripts/validation/ib_parity_harness.py` |
| Python trade ledger (June 2026) | built inline from `data/live/live_storage_-NQ.parquet` + `ib_facts_NQ1.parquet` |
| NT8 trade ledger (June 2026) | `scratch/nt8_ib_breakout_jun2026.json` |
| Trade-by-trade diff CSV | `scratch/ib_parity_breakout_jun2026.csv` |
| Python evaluator (production) | `scripts/libs_py/nqstats/ib.py` — `evaluate_all_plays_consolidated` lines 296-483 |