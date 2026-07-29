"""
Debate: remaining IB parity inconsistencies after the AVWAP fix.

Grounded in empirical evidence from the 6-month parity run (Jan-Jun 2026).
Uses the cloud-only agent panel (Maker + 4 Judges + Refiner) to:
1. Rank the remaining inconsistency hypotheses
2. Propose a concrete fix plan
3. Score the fix plan

All models are cloud (:cloud suffix) per user request.
"""
import json
import os
import sys
from pathlib import Path

_root = os.getcwd()
if _root not in sys.path:
    sys.path.insert(0, _root)

from scripts.utils.agentic_panel import run_panel_pipeline

SCRATCH = Path("scratch")

# ─── Empirical evidence (grounded) ──────────────────────────────────────────

EVIDENCE = """
## 6-Month Parity Results (Jan-Jun 2026, NQ1 Play 1 Breakout)

### Headline comparison across AVWAP sources

| AVWAP source | Python trades | Python days | NT8 overlap days | W/L match | Match rate |
|---|---|---|---|---|---|
| none (ablation) | 127 | 127 | 39 | 29/39 | 74.4% |
| parquet (pre-computed) | 60 | 60 | 29 | 22/29 | 75.9% |
| onthefly (feed-consistent) | 60 | 60 | 29 | 22/29 | 75.9% |

### Key observations
1. The `none` ablation (no ConfluenceFilter) matches 39 days (all NT8 trade days),
   with 74.4% W/L agreement. The filter reduces overlap to 29 days but doesn't
   improve the match rate (75.9% vs 74.4% — within noise).
2. `parquet` and `onthefly` produce IDENTICAL trade counts (60) and match rates
   (75.9%). This is because the TrendMisaligned filter (from the parquet) is the
   dominant gate — the AVWAP common gate (break_vs_avwap_0930 != 0) rarely blocks
   since most days have a clear break direction relative to AVWAP.
3. The on-the-fly AVWAP sign DIFFERS from the parquet AVWAP sign on 8/22 June days
   (36% sign flip rate), confirming the feed-dependency. But since TrendMisaligned
   is the dominant filter, the AVWAP sign flip doesn't change which days pass the
   filter.

### Remaining inconsistencies (7 mismatched days out of 29 overlapping)

The 7 mismatches (where Python and NT8 disagree on win/loss) come from:

H1: **Entry-time divergence** — NT8 enters 2-50 minutes earlier than Python on
    some days (e.g. 2026-06-04: NT8 10:07 vs Python 10:36). NT8's bar-close fires
    on the last tick; Python uses the 1-min bar's recorded close. The 50-min gap
    on 2026-06-12 suggests a range-window boundary difference.

H2: **Entry-price divergence** — Even on matched days, entry prices differ by
    $5-$420 due to the different continuous-contract constructions (offset std =
    233pts). This affects whether the stop/target is hit.

H3: **Stop/target fill resolution** — NT8 is tick-level, Python is bar-level
    (high/low). A bar that wicks through both stop and target resolves differently
    (Python: conservative stop-wins tie-break; NT8: first tick encountered).

H4: **AVWAP feed mismatch** — The on-the-fly AVWAP (from live_storage) differs
    from NT8's AVWAP (from ##-## continuous). This flips break_vs_avwap_0930 on
    36% of days, but since TrendMisaligned is the dominant filter, the impact on
    trade selection is minimal.

H5: **TrendMisaligned feed mismatch** — The daily EMA (computed from the fused
    historical+live loader) uses a different continuous series than NT8's ##-##.
    This could cause the EMA20/EMA50 crossover to differ, flipping
    trend_misaligned_with_break.

H6: **Volume profile divergence** — The two feeds have different volume profiles
    (different roll methods aggregate bars differently at contract rolls). This
    affects AVWAP but NOT IB range or break direction.

H7: **Re-entry divergence** — NT8 takes multiple trades per day (re-entry after
    stop/target); Python takes one trade per day. The parity harness matches by
    closest entry time, so NT8's second trade on a day may match Python's single
    trade, causing a result mismatch.

### June 2026 trade-by-trade detail (onthefly mode)
- Python: 8 trades (all SHORT), 75% WR
- NT8: 9 trades (mixed LONG/SHORT), 55.6% WR
- Only 1 day matched (2026-06-04: both SHORT, both loss)
- Python took 7 days NT8 skipped; NT8 took 8 days Python skipped
- Python is all-SHORT because the on-the-fly AVWAP + parquet TrendMisaligned
  combination filters out all LONG signals in June 2026

### The core unresolved question
The `parquet` and `onthefly` modes produce IDENTICAL results (60 trades, 75.9%
match). This means the AVWAP feed fix (onthefly) does NOT improve parity over
the pre-computed parquet. The remaining 24.1% mismatch is NOT from AVWAP — it's
from entry-time/price/fill-resolution differences (H1/H2/H3) and the
TrendMisaligned feed mismatch (H5).
"""

PROMPT = f"""
You are a panel of expert quantitative trading engineers debating the remaining
IB strategy parity inconsistencies between Python and NT8.

{EVIDENCE}

## Task
1. RANK the 7 hypotheses (H1-H7) by their expected contribution to the remaining
   24.1% win/loss mismatch. Use evidence from the data above.
2. Identify the DOMINANT root cause (the one that accounts for the most mismatches).
3. Propose a concrete fix plan (ordered P0/P1/P2) with specific code changes.
4. For each fix, estimate the expected match-rate improvement and the implementation
   effort (S/M/L).

## Constraints
- All fixes must be to `scripts/validation/ib_parity_harness.py` only (the parity
  harness). Do NOT propose changes to the production evaluator (`ib.py`) or the
  confluence pipeline (`ib_avwap_trend.py`).
- Fixes must comply with ADR-001 (ET timezone), ADR-017 (vectorization), and
  ADR-020 (RTH liquidation at 15:50).
- The harness validates Python self-consistency, NOT NT8 feed-matching. Fixes
  that require loading NT8 raw contract bars are P2 (future work).
- Be concrete: specify the function, the change, and the expected impact.

## Output format
Return a JSON object with:
{{
  "ranking": [{{"hypothesis": "H1", "rank": 1, "contribution_pct": 30, "rationale": "..."}}],
  "dominant_root_cause": "H...",
  "fix_plan": [
    {{"priority": "P0", "fix": "...", "file": "...", "function": "...",
      "change": "...", "expected_improvement_pct": 5, "effort": "S"}}
  ],
  "expected_final_match_rate": 85.0,
  "confidence": "high|medium|low",
  "residual_gap_explanation": "..."
}}
"""

if __name__ == "__main__":
    # Use the agentic panel for the debate (cloud models only)
    # We use the panel as a debate engine: Maker drafts the ranking+fix plan,
    # Judges evaluate correctness/trading-rules/adversarial/style.
    result = run_panel_pipeline(
        task_prompt=PROMPT,
        max_retries=3,
        threshold=7.0,
    )

    print("\n" + "=" * 78)
    print("DEBATE RESULT — Remaining IB Parity Inconsistencies")
    print("=" * 78)
    print(f"Approved: {result.approved}")
    print(f"Final score: {result.weighted_score}")
    print(f"Cycles: {result.attempts}")

    # Save the final output
    out_path = SCRATCH / "avwap_debate_result.json"
    debate_output = {
        "approved": result.approved,
        "weighted_score": result.weighted_score,
        "attempts": result.attempts,
        "merged_feedback": result.merged_feedback,
        "final_code": result.final_code,
        "verdicts": [
            {"judge": v.judge, "model": v.model, "score": v.score,
             "approved": v.approved, "feedback": v.feedback}
            for v in result.verdicts
        ] if result.verdicts else [],
    }
    out_path.write_text(json.dumps(debate_output, indent=2), encoding="utf-8")
    print(f"Saved to: {out_path}")

    # Also save the raw code/output
    code_path = SCRATCH / "avwap_debate_output.txt"
    code_path.write_text(result.final_code or "", encoding="utf-8")
    print(f"Raw output saved to: {code_path}")