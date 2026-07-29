"""
Agent loop: fix the AVWAP parity gap between Python (live_storage continuous)
and NT8 (##-## continuous) for the IB parity harness.

ROOT CAUSE (empirically confirmed by scratch/diagnose_avwap_parity.py):
  - The two "continuous" feeds use DIFFERENT roll adjustment methods and volume
    profiles. Offset std = 233.24 pts (not constant), ratio std = 0.0087 (not
    constant). They are fundamentally different constructions.
  - AVWAP is volume-weighted (cumulative TPV / cumulative Vol from 09:30).
    Because the price levels AND volume profiles differ between feeds, the AVWAP
    lands at different relative positions within the IB range, flipping the sign
    of (close > AVWAP) → break_vs_avwap_0930 flips → ConfluenceFilter common
    gate filters different trade days.
  - On 2026-06-04: on-the-fly break_vs_avwap_0930 = +1 (Python feed) but
    pre-computed = -1 (also Python feed, but the confluence parquet was built
    from a DIFFERENT Python loader — the fused historical+live loader, not the
    live_storage-only loader the harness uses). SIGN FLIP CONFIRMED.

SECONDARY BUG:
  - ib_parity_harness.py main() does NOT pass confluence_row to
    simulate_play1_day, so the ConfluenceFilter (break_vs_avwap_0930 common
    gate + TrendMisaligned) is NEVER applied in the parity harness. The harness
    over-trades (Python 60 trades vs NT8 51) because it skips the AVWAP gate.

FIX OPTIONS:
  A. Make the harness compute AVWAP on-the-fly from the SAME bars it uses for
     IB (live_storage continuous), so the AVWAP is consistent with the IB
     boundaries it already uses. This makes Python self-consistent but does NOT
     match NT8 (which uses a different feed). → closes the "self-consistency"
     gap but not the "cross-feed" gap.
  B. Pass the pre-computed confluence_row (from ib_confluence_NQ1.parquet) to
     simulate_play1_day so the harness applies the same filter the production
     Python evaluator does. → matches production Python, not NT8.
  C. Accept that the AVWAP common gate is feed-dependent and remove it from
     the ConfluenceFilter common gate (make it a per-play optional filter
     instead of a common gate), so the parity comparison focuses on the
     feed-invariant IB geometry. → matches the parity doc's conclusion that
     "IB itself is unaffected — roll adjustment is a constant offset" (which
     is TRUE for IB geometry but FALSE for AVWAP).
  D. Load NT8's raw contract bars into Python and compute AVWAP on those, so
     the AVWAP matches NT8 exactly. → most accurate but requires NT8 bar
     export via MCP for every backtest window.

This loop asks the panel to pick the best fix and generate the code.
"""
import json
import os
import sys
from pathlib import Path

# Make repo root importable — resolve from CWD (repo root) with fallback
_root = os.getcwd()
if _root not in sys.path:
    sys.path.insert(0, _root)

from scripts.utils.agentic_panel import run_panel_pipeline

SCRATCH = Path("scratch")

DIAGNOSIS = """
## AVWAP Parity Gap — Empirical Diagnosis

### Confirmed root cause
The Python `live_storage_-NQ.parquet` (continuous) and NT8 `NQ ##-##` (continuous)
feeds are DIFFERENT constructions:
- Price offset std = 233.24 pts (range -643.75 to +438.00) — NOT a constant roll.
- Price ratio std = 0.0087 — NOT a constant multiplicative roll.
- On 2026-06-04: on-the-fly break_vs_avwap_0930 = +1 (Python live_storage) but
  pre-computed confluence parquet = -1 (built from fused historical+live loader).
  SIGN FLIP on the AVWAP common gate.

### Why AVWAP flips but IB doesn't
- IB range = (ib_high - ib_low) is a WITHIN-DAY high/low. A constant or ratio
  roll adjustment shifts both boundaries by the same factor, so the RANGE is
  invariant and the break direction (close > ib_high) is invariant.
- AVWAP = cumulative(TPV) / cumulative(Vol) from 09:30. TPV = (H+L+C)/3 * Vol.
  Different feeds have different absolute prices AND different volume profiles,
  so the volume-weighted average lands at a different relative position. The
  sign of (close > AVWAP) can flip.

### Secondary bug
`ib_parity_harness.py` main() calls `simulate_play1_day(...)` WITHOUT passing
`confluence_row`, so the ConfluenceFilter (break_vs_avwap_0930 common gate +
TrendMisaligned) is NEVER applied. The harness over-trades (Python 60 vs NT8 51).

### Current parity state (Jan-Jun 2026, 6 months)
- NT8: 51 trades (39 days) | Python: 60 trades (60 days)
- Overlapping days: 29 | Win/loss match: 21/29 (72.4%)
- Feb-Mar best: 16/18 (89%) | Jan worst: 1/5 (20%)
- Remaining 8 mismatches are AVWAP-driven (the common gate filters different
  days in the two feeds).

### The fix must
1. Make the parity harness apply the ConfluenceFilter (pass confluence_row).
2. Make the AVWAP computation in the harness consistent with the bars it uses
   (compute on-the-fly from live_storage, not from the pre-computed parquet
   which was built from a different loader).
3. Document that the cross-feed AVWAP gap is a known limitation — the harness
   validates Python self-consistency, not NT8 feed-matching. To match NT8
   exactly, load NT8 raw contract bars (Option D, future work).
4. Re-run the parity check and report the new match rate.
"""

PROMPT = f"""
You are fixing an AVWAP parity gap in the IB strategy parity harness.

{DIAGNOSIS}

## Task
Generate a Python code change to `scripts/validation/ib_parity_harness.py` that:

1. **Loads the confluence parquet** (`data/derived/ib_confluence_{{ticker}}.parquet`)
   filtered to the session slot, and passes `confluence_row` to
   `simulate_play1_day` and `simulate_play3_day` for every trading day. This
   applies the ConfluenceFilter (break_vs_avwap_0930 common gate +
   TrendMisaligned) so the harness stops over-trading.

2. **Adds an on-the-fly AVWAP computation** as a fallback/override: a new helper
   `compute_break_vs_avwap_0930(bars_day, ib_end_idx)` that computes the
   09:30-anchored AVWAP from the SAME `bars_day` DataFrame the harness uses
   (live_storage continuous), and returns the break_vs_avwap_0930 sign (+1/-1/0)
   at the first break bar. This makes the AVWAP consistent with the IB
   boundaries (both from the same feed). When `--avwap-source onthefly` is
   passed, use this; when `--avwap-source parquet` (default), use the pre-computed
   confluence parquet value; when `--avwap-source none`, skip the AVWAP gate
   entirely (ablation).

3. **Adds a `--avwap-source` CLI flag** with choices `parquet` (default),
   `onthefly`, `none`.

4. **Keeps ADR-017 (vectorization)**: the on-the-fly AVWAP must use vectorized
   pandas/numpy ops (cumsum), not a Python for-loop over bars.

5. **Does NOT change the production evaluator** (`scripts/libs_py/nqstats/ib.py`)
   or the confluence pipeline (`ib_avwap_trend.py`). Only the parity harness
   changes.

6. **Adds a clear docstring** explaining the feed-dependency limitation:
   the harness validates Python self-consistency (onthefly) or production-pipeline
   parity (parquet), NOT NT8 feed-matching. NT8 feed-matching requires loading
   NT8 raw contract bars (future work).

## Constraints
- Only edit `scripts/validation/ib_parity_harness.py`.
- Do NOT touch any other file.
- Keep the existing CLI flags working.
- Vectorized AVWAP (cumsum), no for-loops over bars.
- Preserve the existing `simulate_play1_day` / `simulate_play3_day` signatures
  (confluence_row is already an optional param — just wire it up in main()).

## Output
Return the COMPLETE updated `scripts/validation/ib_parity_harness.py` file.
"""

if __name__ == "__main__":
    result = run_panel_pipeline(
        task_prompt=PROMPT,
        max_retries=3,
        threshold=7.0,
    )
    print("\n=== AGENT LOOP RESULT ===")
    print(f"Approved: {result.approved}")
    print(f"Final score: {result.weighted_score}")
    print(f"Cycles: {result.attempts}")
    if result.final_code:
        print(f"Code length: {len(result.final_code)} chars")
    # Save the final code
    out_path = SCRATCH / "avwap_fix_harness_final.py"
    out_path.write_text(result.final_code or "", encoding="utf-8")
    print(f"Final code saved to: {out_path}")
    # Save the report
    report_path = SCRATCH / "avwap_fix_report.json"
    report = {
        "approved": result.approved,
        "weighted_score": result.weighted_score,
        "attempts": result.attempts,
        "merged_feedback": result.merged_feedback,
        "verdicts": [
            {"judge": v.judge, "model": v.model, "score": v.score,
             "approved": v.approved, "feedback": v.feedback}
            for v in result.verdicts
        ] if result.verdicts else [],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report saved to: {report_path}")