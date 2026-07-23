"""Test suite for the knowledge_bridge package.

Run with: python -m pytest scripts/knowledge_bridge/test_suite.py -v
Or:      python -m scripts.knowledge_bridge.test_suite
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure project root on sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_detection_catalog():
    """Detection catalog has 34 entries, resolves known and unknown terms."""
    from scripts.knowledge_bridge import (
        DETECTION_CATALOG,
        resolve_detection,
        list_concepts,
        concepts_by_category,
        search_concepts,
    )

    assert len(DETECTION_CATALOG) == 34, f"Expected 34, got {len(DETECTION_CATALOG)}"

    # Known concepts resolve
    assert resolve_detection("FVG") is not None
    assert resolve_detection("Fair Value Gap") is not None
    assert resolve_detection("silver bullet") is not None
    assert resolve_detection("Silver Bullet") is not None
    assert resolve_detection("order block") is not None
    assert resolve_detection("BSL") is not None

    # Unknown returns None
    assert resolve_detection("nonexistent_xyz123") is None

    # Categories
    cats = concepts_by_category()
    assert "price_action" in cats
    assert "structure" in cats
    assert "liquidity" in cats
    assert "sessions" in cats
    assert len(cats) == 11

    # Search
    hits = search_concepts("liquidity")
    assert len(hits) >= 2  # Liquidity Pools + Liquidity Void

    # All entries have valid module + function
    for entry in DETECTION_CATALOG:
        assert entry.module.startswith("scripts.libs_py.ict_engine")
        assert entry.function_name
        assert entry.concept
        assert entry.category

    print("[PASS] test_detection_catalog")


def test_strategy_candidate_generation():
    """Candidate generator maps KB setup prose to detection steps."""
    from scripts.knowledge_bridge import CandidateGenerator, CandidateStatus

    unit = {
        "unit_id": "test_unit_001",
        "summary": "FVG entry after liquidity sweep in NY killzone with Silver Bullet timing",
        "metadata": {
            "domains": ["ict"],
            "concepts_raw": ["FVG", "liquidity sweep", "killzone", "Silver Bullet"],
            "concepts_canonical": ["fvg", "liquidity", "killzone", "silver_bullet"],
            "extraction_confidence": 0.85,
            "epistemic_status": "unvalidated",
        },
        "setup": {
            "name": "NY Silver Bullet + Sweep Reversal",
            "regime_precondition": "Price in discount of dealing range, below equilibrium",
            "bias_source": "HTF draw to PDH, bullish bias",
            "timing_gate": "Silver Bullet window 10:00-11:00 NY",
            "trigger": "Liquidity sweep of Asian session low followed by CISD",
            "entry": "Enter on FVG edge after CISD confirmation",
            "invalidation": "Close above swept liquidity level",
            "target_logic": "1 SD projection from manipulation leg",
            "management": "Partials at 1.5R, move to BE",
        },
    }

    gen = CandidateGenerator()
    cand = gen.generate_from_unit(unit)

    assert cand is not None, "Candidate generation returned None"
    assert cand.candidate_id.startswith("kb_candidate_")
    assert cand.name == "NY Silver Bullet + Sweep Reversal"
    assert cand.source_unit_ids == ["test_unit_001"]
    assert cand.status == CandidateStatus.DRAFT
    assert cand.max_exit_time == "16:00 ET"
    assert len(cand.detection_steps) > 0

    # Check steps have valid function refs
    for step in cand.detection_steps:
        assert step.step_order >= 1
        assert step.concept
        assert step.function_ref.startswith("scripts.libs_py.ict_engine")
        assert step.role in ("regime", "bias", "timing", "trigger", "entry", "invalidation", "target", "management")

    # Strategy key should be inferred from "liquidity sweep"
    assert cand.strategy_key == "ict_liquidity_sweep"

    # Direction should be "long" (from "bullish")
    assert cand.direction == "long"

    print(f"[PASS] test_strategy_candidate_generation ({len(cand.detection_steps)} steps)")


def test_candidate_export_import():
    """JSON export/import round-trip preserves all fields."""
    from scripts.knowledge_bridge import (
        StrategyCandidate,
        CandidateStatus,
        DetectionStep,
        export_candidates_json,
        load_candidates_json,
    )

    cand = StrategyCandidate(
        candidate_id="kb_candidate_test123",
        name="Test Candidate",
        source_unit_ids=["unit_a", "unit_b"],
        direction="short",
        detection_steps=[
            DetectionStep(step_order=1, concept="FVG", function_ref="scripts.libs_py.ict_engine.core.pa.detect_fvg", role="entry"),
        ],
        strategy_key="ict_fvg_rejection",
        max_exit_time="16:00 ET",
        status=CandidateStatus.VALIDATED,
        epistemic_status="validated",
        metadata={"concepts_found": ["FVG"], "concepts_missing": []},
    )

    tmpdir = tempfile.mkdtemp()
    path = export_candidates_json([cand], os.path.join(tmpdir, "candidates.json"))

    loaded = load_candidates_json(path)
    assert len(loaded) == 1
    l = loaded[0]
    assert l.candidate_id == cand.candidate_id
    assert l.name == cand.name
    assert l.source_unit_ids == cand.source_unit_ids
    assert l.direction == cand.direction
    assert l.strategy_key == cand.strategy_key
    assert l.status == CandidateStatus.VALIDATED
    assert len(l.detection_steps) == 1
    assert l.detection_steps[0].concept == "FVG"

    print("[PASS] test_candidate_export_import")


def test_bidirectional_linking():
    """link_candidates_to_units and compute_unit_updates work correctly."""
    from scripts.knowledge_bridge import (
        StrategyCandidate,
        link_candidates_to_units,
        compute_unit_updates,
    )

    c1 = StrategyCandidate(candidate_id="c1", name="A", source_unit_ids=["u1", "u2"])
    c2 = StrategyCandidate(candidate_id="c2", name="B", source_unit_ids=["u2", "u3"])

    links = link_candidates_to_units([c1, c2])
    assert links["u1"] == ["c1"]
    assert links["u2"] == ["c1", "c2"]  # u2 is shared
    assert links["u3"] == ["c2"]

    updates = compute_unit_updates([c1, c2])
    assert "u1" in updates
    assert "u2" in updates
    assert "u3" in updates
    assert "c1" in updates["u1"]["linked_stat_ids"]
    assert "c2" in updates["u2"]["linked_stat_ids"]

    # With existing IDs
    updates2 = compute_unit_updates([c1], existing_linked_stat_ids={"u1": ["old_id"]})
    assert "old_id" in updates2["u1"]["linked_stat_ids"]
    assert "c1" in updates2["u1"]["linked_stat_ids"]

    print("[PASS] test_bidirectional_linking")


def test_backtest_result_round_trip():
    """BacktestResult + ProfileResult JSON export/import round-trip."""
    from scripts.knowledge_bridge import (
        BacktestResult,
        ProfileResult,
        export_backtest_results,
        load_backtest_results,
    )

    pr = ProfileResult(
        profile_name="Apex 50K",
        passed=True,
        blown=False,
        final_equity_delta=3000.0,
        max_drawdown_used=1200.0,
        win_rate=0.55,
        profit_factor=1.8,
        total_trades=50,
        trading_days=10,
        mc_pass_rate_pct=72.0,
        mc_blow_rate_pct=15.0,
        mc_grade="B",
        avg_days_to_pass=8.0,
        p50_final_equity=53000.0,
    )
    br = BacktestResult(
        candidate_id="kb_candidate_test",
        strategy_key="ict_fvg_rejection",
        ticker="NQ1",
        n_signals=10,
        n_trades=8,
        total_return_pct=5.2,
        sharpe_ratio=1.8,
        max_drawdown_pct=12.0,
        win_rate_pct=55.0,
        avg_mae_pct=0.3,
        passed=True,
        grade="B",
        profiles=[pr],
    )

    tmpdir = tempfile.mkdtemp()
    path = export_backtest_results([br], os.path.join(tmpdir, "bt.json"))
    loaded = load_backtest_results(path)

    assert len(loaded) == 1
    l = loaded[0]
    assert l.candidate_id == br.candidate_id
    assert l.strategy_key == br.strategy_key
    assert l.ticker == br.ticker
    assert l.n_signals == br.n_signals
    assert l.passed == br.passed
    assert l.grade == br.grade
    assert len(l.profiles) == 1
    assert l.profiles[0].profile_name == "Apex 50K"
    assert l.profiles[0].mc_grade == "B"
    assert l.profiles[0].mc_pass_rate_pct == 72.0

    print("[PASS] test_backtest_result_round_trip")


def test_apply_backtest_results():
    """apply_backtest_results updates candidate status correctly."""
    from scripts.knowledge_bridge import (
        StrategyCandidate,
        CandidateStatus,
        BacktestResult,
        apply_backtest_results,
    )

    # Candidate with matching ID
    cand_passed = StrategyCandidate(candidate_id="c_pass", name="A", source_unit_ids=["u1"])
    cand_failed = StrategyCandidate(candidate_id="c_fail", name="B", source_unit_ids=["u2"])
    cand_error = StrategyCandidate(candidate_id="c_err", name="C", source_unit_ids=["u3"])

    br_pass = BacktestResult(candidate_id="c_pass", strategy_key="s", ticker="NQ1", passed=True, grade="A")
    br_fail = BacktestResult(candidate_id="c_fail", strategy_key="s", ticker="NQ1", passed=False, grade="F")
    br_err = BacktestResult(candidate_id="c_err", strategy_key="s", ticker="NQ1", error="Something broke")

    updates = apply_backtest_results([cand_passed, cand_failed, cand_error], [br_pass, br_fail, br_err])

    assert updates["c_pass"] == CandidateStatus.VALIDATED
    assert updates["c_fail"] == CandidateStatus.REJECTED
    assert updates["c_err"] == CandidateStatus.REJECTED

    assert cand_passed.epistemic_status == "validated"
    assert cand_failed.epistemic_status == "contradicted"
    assert cand_error.epistemic_status == "contradicted"

    # Unmatched candidate is not in updates
    cand_orphan = StrategyCandidate(candidate_id="orphan", name="O", source_unit_ids=["u9"])
    updates2 = apply_backtest_results([cand_orphan], [br_pass])
    assert "orphan" not in updates2

    print("[PASS] test_apply_backtest_results")


def test_summary_stats():
    """summary_stats and summarize_results produce correct aggregates."""
    from scripts.knowledge_bridge import (
        StrategyCandidate,
        summary_stats,
        BacktestResult,
        summarize_results,
    )

    cands = [
        StrategyCandidate(candidate_id="c1", name="A", source_unit_ids=["u1"], strategy_key="ict_fvg_rejection"),
        StrategyCandidate(candidate_id="c2", name="B", source_unit_ids=["u2"], strategy_key="ict_liquidity_sweep"),
        StrategyCandidate(candidate_id="c3", name="C", source_unit_ids=["u3"], strategy_key="ict_fvg_rejection"),
    ]
    stats = summary_stats(cands)
    assert stats["total"] == 3
    assert stats["by_strategy_key"]["ict_fvg_rejection"] == 2
    assert stats["by_strategy_key"]["ict_liquidity_sweep"] == 1

    results = [
        BacktestResult(candidate_id="c1", strategy_key="s", ticker="NQ1", passed=True, grade="A", n_signals=10, n_trades=5, sharpe_ratio=1.5),
        BacktestResult(candidate_id="c2", strategy_key="s", ticker="NQ1", passed=False, grade="F", n_signals=8, n_trades=3, sharpe_ratio=0.5),
    ]
    rstats = summarize_results(results)
    assert rstats["total"] == 2
    assert rstats["passed"] == 1
    assert rstats["grades"]["A"] == 1
    assert rstats["grades"]["F"] == 1
    assert rstats["avg_signals"] == 9.0

    print("[PASS] test_summary_stats")


def test_kb_api_search():
    """KB API search returns results when API is reachable."""
    from scripts.knowledge_bridge.test_narrative import check_kb_api, fetch_kb_context

    if not check_kb_api():
        print("[SKIP] test_kb_api_search (KB API not running)")
        return

    ctx = fetch_kb_context("FVG entry after liquidity sweep in killzone with Silver Bullet timing")
    assert len(ctx) > 0, "KB context should not be empty for FVG/sweep/SB query"
    assert "KNOWLEDGE BASE CONTEXT" in ctx
    print(f"[PASS] test_kb_api_search ({len(ctx)} chars)")


def run_all():
    """Run all tests."""
    print("=== KNOWLEDGE BRIDGE TEST SUITE ===")
    print()
    tests = [
        test_detection_catalog,
        test_strategy_candidate_generation,
        test_candidate_export_import,
        test_bidirectional_linking,
        test_backtest_result_round_trip,
        test_apply_backtest_results,
        test_summary_stats,
        test_kb_api_search,
    ]
    passed = 0
    failed = 0
    skipped = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {e}")
            failed += 1

    print()
    print(f"=== RESULTS: {passed} passed, {failed} failed, {skipped} skipped ===")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)