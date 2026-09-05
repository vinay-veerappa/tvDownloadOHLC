"""The workflow's verdict must not be able to go green without evidence.

`workflow.py` exists so there is ONE way to run a strategy. Its output is not a
metric, it is a promotion checklist, and the whole value of that checklist rests
on one distinction: a criterion that FAILED and a criterion that was never
MEASURED are different, and neither is a pass.

That distinction is easy to lose by accident. `not self.failed` reads as "nothing
went wrong" and is true of a run that did nothing at all. These tests hold the
line where it is easy to cross.
"""
import pathlib

import pytest

from scripts.trading_framework.workflow import (
    CRITERIA, Checklist, FAIL, NOT_EVALUATED, PASS, _find_alignment,
    _prop_viability, exit_code,
)


def _all(check, status):
    for key, _text in CRITERIA:
        check.set(key, status)


def test_a_fresh_checklist_is_not_validated():
    """The default state must be the safe one: nothing measured, nothing proved."""
    c = Checklist()
    assert not c.validated
    assert len(c.unevaluated) == len(CRITERIA)
    assert not c.failed


def test_all_pass_is_validated():
    c = Checklist()
    _all(c, PASS)
    assert c.validated


def test_a_single_unevaluated_criterion_blocks_validation():
    """The trap: `not failed` would call this validated."""
    c = Checklist()
    _all(c, PASS)
    c.set("trade_set_parity", NOT_EVALUATED, "no NT8 trade set")
    assert not c.failed, "nothing FAILED -- which is exactly why this is the risky case"
    assert not c.validated
    assert [x.key for x in c.unevaluated] == ["trade_set_parity"]


def test_a_single_failure_blocks_validation():
    c = Checklist()
    _all(c, PASS)
    c.set("signal_geometry", FAIL, "527 refused")
    assert not c.validated
    assert [x.key for x in c.failed] == ["signal_geometry"]


def test_the_verdict_line_distinguishes_failed_from_unmeasured():
    """Two very different situations must not print the same sentence."""
    failed = Checklist()
    _all(failed, PASS)
    failed.set("causal", FAIL, "lookahead demonstrated")

    unmeasured = Checklist()
    _all(unmeasured, PASS)
    unmeasured.set("causal", NOT_EVALUATED, "probe was vacuous")

    assert "FAILED" in failed.render()
    assert "never" in unmeasured.render() and "FAILED" not in unmeasured.render()


def test_an_unknown_criterion_is_refused_rather_than_silently_added():
    """A typo'd key must not create a criterion nobody reads."""
    c = Checklist()
    with pytest.raises(KeyError):
        c.set("trade_set_parityy", PASS)


def test_an_unknown_status_is_refused():
    c = Checklist()
    with pytest.raises(ValueError):
        c.set("causal", "probably fine")


def test_serialised_checklist_carries_every_criterion_and_the_verdict():
    c = Checklist()
    _all(c, PASS)
    c.set("nt8_ground_truth", NOT_EVALUATED, "not captured")
    d = c.to_dict()
    assert d["validated"] is False
    assert set(d["criteria"]) == {k for k, _ in CRITERIA}
    assert d["criteria"]["nt8_ground_truth"]["status"] == NOT_EVALUATED
    assert d["criteria"]["nt8_ground_truth"]["detail"] == "not captured"


# --------------------------------------------------------------------------- #
# The alignment reader. This is where the checklist actually got it wrong on its
# first real run: it read one level too high and called a run with 527 impossible
# signals a pass.
# --------------------------------------------------------------------------- #
def test_alignment_is_found_under_the_stage_key_the_recorder_uses():
    doc = {"alignment": {"report": {"signals_kept": 10, "geometry": {"signals_in": 12}}}}
    assert _find_alignment(doc)["signals_kept"] == 10


def test_alignment_is_found_under_any_stage_name():
    doc = {"alignment": {"some_future_stage": {"signals_kept": 3}}}
    assert _find_alignment(doc)["signals_kept"] == 3


def test_no_alignment_returns_none_rather_than_an_empty_dict():
    """None means "not recorded"; {} would be read as "recorded, all zero"."""
    assert _find_alignment({}) is None
    assert _find_alignment({"alignment": {}}) is None


def test_geometry_drops_are_read_from_the_nested_report_not_the_outer_one():
    """The measured defect, pinned.

    The outer alignment report's `signals_in` is the count AFTER the geometry
    filter, so it always shows zero drops. Only the nested `geometry` report
    knows how many were refused.
    """
    from scripts.trading_framework.workflow import Checklist, Ctx, _signal_geometry

    doc = {"alignment": {"report": {
        "signals_in": 2661, "signals_kept": 2661,          # post-filter: looks clean
        "geometry": {"signals_in": 3188, "signals_kept": 2661,
                     "dropped_stop_wrong_side": 372,
                     "dropped_stop_sub_tick": 155,
                     "dropped_target_wrong_side": 0,
                     "dropped_non_finite": 0},
    }}}

    class _Args:
        optimize = False
        oos_start = None

    ctx = Ctx(args=_Args(), rec=None, output_dir="", check=Checklist())
    _signal_geometry(ctx, doc)
    item = ctx.check.items["signal_geometry"]
    assert item.status == FAIL
    assert "527" in item.detail and "3188" in item.detail
    assert "stop_wrong_side=372" in item.detail


def test_a_clean_geometry_report_passes():
    """The negative control. Without it the reader above could fire on anything."""
    from scripts.trading_framework.workflow import Checklist, Ctx, _signal_geometry

    doc = {"alignment": {"report": {"geometry": {
        "signals_in": 900, "signals_kept": 900,
        "dropped_stop_wrong_side": 0, "dropped_stop_sub_tick": 0,
        "dropped_target_wrong_side": 0, "dropped_non_finite": 0}}}}

    class _Args:
        optimize = False
        oos_start = None

    ctx = Ctx(args=_Args(), rec=None, output_dir="", check=Checklist())
    _signal_geometry(ctx, doc)
    assert ctx.check.items["signal_geometry"].status == PASS


def test_an_engine_without_a_geometry_report_is_unevaluated_not_passed():
    from scripts.trading_framework.workflow import Checklist, Ctx, _signal_geometry

    doc = {"alignment": {"report": {"signals_in": 10, "signals_kept": 10}}}

    class _Args:
        optimize = False
        oos_start = None

    ctx = Ctx(args=_Args(), rec=None, output_dir="", check=Checklist())
    _signal_geometry(ctx, doc)
    assert ctx.check.items["signal_geometry"].status == NOT_EVALUATED


# --------------------------------------------------------------------------- #
# Causality: a vacuous probe is the one that must not become a green.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("detail,expected", [
    ({"causal": True}, PASS),
    ({"causal": False}, FAIL),
    ({"causal": True, "vacuous": True}, NOT_EVALUATED),   # empty == empty
    ({"vacuous": True, "causal": None}, NOT_EVALUATED),
    ({}, NOT_EVALUATED),
])
def test_causality_verdicts(detail, expected):
    from scripts.trading_framework.workflow import Checklist, Ctx, _causality

    ctx = Ctx(args=None, rec=None, output_dir="", check=Checklist())
    _causality(ctx, {"causality_probe": {"status": "ok", "detail": detail}})
    assert ctx.check.items["causal"].status == expected


def test_a_probe_that_never_ran_is_unevaluated():
    from scripts.trading_framework.workflow import Checklist, Ctx, _causality

    ctx = Ctx(args=None, rec=None, output_dir="", check=Checklist())
    _causality(ctx, {})
    assert ctx.check.items["causal"].status == NOT_EVALUATED


# --------------------------------------------------------------------------- #
# A recorded skip must be a fact, not an omission.
# --------------------------------------------------------------------------- #
def test_a_skipped_stage_is_recorded_with_its_reason():
    from scripts.trading_framework.provenance.run_record import RunRecord

    rec = RunRecord.open(RunRecord.new_run_id("NQ1", "x"), strategy_key="x",
                         ticker="NQ1", ledger_path=None)
    rec.skip_stage("nt8_backtest", "--nt8 not passed")
    st = [s for s in rec.stages if s["name"] == "nt8_backtest"]
    assert len(st) == 1
    assert st[0]["status"] == "skipped"
    assert st[0]["detail"]["reason"] == "--nt8 not passed"


def test_a_skip_without_a_reason_is_refused():
    """An unexplained skip is the omission this method exists to replace."""
    from scripts.trading_framework.provenance.run_record import RunRecord

    rec = RunRecord.open(RunRecord.new_run_id("NQ1", "x"), strategy_key="x",
                         ticker="NQ1", ledger_path=None)
    with pytest.raises(ValueError):
        rec.skip_stage("nt8_backtest", "")


def test_stages_are_visible_before_the_record_is_finalized():
    """`_doc["stages"]` is only filled at finalize; a mid-run reader saw nothing
    and reported a healthy causality probe as "did not run"."""
    from scripts.trading_framework.provenance.run_record import RunRecord

    rec = RunRecord.open(RunRecord.new_run_id("NQ1", "x"), strategy_key="x",
                         ticker="NQ1", ledger_path=None)
    with rec.stage("causality_probe") as st:
        st.detail(causal=True)
    names = [s["name"] for s in rec.doc["stages"]]
    assert "causality_probe" in names


# --------------------------------------------------------------------------- #
# The exit code. Added 2026-09-05 after a review found `main` returning
# `1 if check.failed else 0` -- `not failed`, the reading §0.1 disavows.
# --------------------------------------------------------------------------- #

def test_a_checklist_that_measured_nothing_does_not_exit_zero():
    """THE NEGATIVE CONTROL. This is the defect, stated as a test.

    Every criterion NOT EVALUATED: nothing failed, and nothing was proved. Under
    `not failed` this returned 0 and a CI gate would have called it a pass.
    """
    c = Checklist()
    _all(c, NOT_EVALUATED)
    assert not c.failed, "precondition: nothing FAILED"
    assert exit_code(c) == 1


def test_one_unmeasured_criterion_is_enough_to_lose_exit_zero():
    c = Checklist()
    _all(c, PASS)
    c.set(CRITERIA[-1][0], NOT_EVALUATED)
    assert exit_code(c) == 1


def test_all_pass_exits_zero():
    c = Checklist()
    _all(c, PASS)
    assert exit_code(c) == 0


def test_a_failure_exits_one():
    c = Checklist()
    _all(c, PASS)
    c.set(CRITERIA[0][0], FAIL)
    assert exit_code(c) == 1


def test_a_raised_required_stage_outranks_a_green_checklist():
    """2 is "inconclusive", and it must not be maskable by a full green."""
    c = Checklist()
    _all(c, PASS)
    assert exit_code(c, failed_hard="resolve") == 2


def test_exit_zero_agrees_with_validated_for_every_uniform_checklist():
    for status in (PASS, FAIL, NOT_EVALUATED):
        c = Checklist()
        _all(c, status)
        assert (exit_code(c) == 0) is c.validated, status


# --------------------------------------------------------------------------- #
# §9 and CRITERIA have to be the same list. The review found §9 carrying 12
# checkboxes against 10 criteria: two items the document called part of
# "validated" could not block it, because the tool did not know they existed.
# --------------------------------------------------------------------------- #

_DOC = pathlib.Path(__file__).resolve().parents[3] / "docs" / "architecture" / "STRATEGY_WORKFLOW.md"


def _doc_checkboxes():
    text = _DOC.read_text(encoding="utf-8")
    start = text.index('## 9. Definition of "validated"')
    end = text.index("## 10.", start)
    return [ln.strip() for ln in text[start:end].splitlines()
            if ln.strip().startswith("- [ ]")]


def test_the_document_is_present_and_section_9_is_findable():
    """Guards the two tests below against passing vacuously on a renamed heading."""
    assert _DOC.is_file(), _DOC
    assert len(_doc_checkboxes()) > 0


def test_section_9_has_exactly_one_checkbox_per_evaluated_criterion():
    boxes = _doc_checkboxes()
    assert len(boxes) == len(CRITERIA), (
        "section 9 lists {} items, workflow.py evaluates {}. A criterion the "
        "document calls part of 'validated' but CRITERIA omits cannot block "
        "it: {}".format(len(boxes), len(CRITERIA), boxes))


def test_the_two_criteria_the_review_found_missing_are_evaluated():
    keys = {k for k, _ in CRITERIA}
    assert "prop_viability" in keys
    assert "reports_attributed" in keys


# --------------------------------------------------------------------------- #
# prop_viability reads the run record, not a live object.
# --------------------------------------------------------------------------- #

def _stage(**details):
    """Build the stage map the way a REAL run builds it.

    The first version of this helper hand-wrote `{"details": ...}`. The recorder
    serialises `_Stage.details` under the key **"detail"**, so `_prop_viability`
    read `{}` on every real run and reported FAIL "evaluated by 'None'" -- while
    this test passed, because the test restated my assumption instead of asking
    the recorder. Ask the recorder.
    """
    from scripts.trading_framework.provenance.run_record import RunRecord
    rec = RunRecord("RUN_TEST_PROP", strategy_key="t", ticker="NQ1")
    with rec.stage("prop_firm_sim") as st:
        st.detail(**details)
    return {s["name"]: s for s in rec.stages}


def test_the_stage_fixture_uses_the_recorders_own_key():
    """Negative control for the helper above: pin the serialised key name."""
    m = _stage(evaluator="PropFirmSimulator")
    assert "detail" in m["prop_firm_sim"], m["prop_firm_sim"].keys()
    assert m["prop_firm_sim"]["detail"]["evaluator"] == "PropFirmSimulator"


class _Ctx:
    def __init__(self):
        self.check = Checklist()


def _viable(**over):
    """A prop stage that SHOULD pass. Kept in one place so each red below
    differs from it by exactly one field."""
    d = dict(evaluator="PropFirmSimulator", passRatePct=71.0, grade="B",
             primaryProfile="Apex 50k", passThresholdPct=65.0,
             resampling="daily_block", historicalPassed=True,
             historicalBlown=False)
    d.update(over)
    return _stage(**d)


def test_prop_viability_passes_on_a_rate_above_the_threshold():
    ctx = _Ctx()
    _prop_viability(ctx, _viable())
    assert ctx.check.items["prop_viability"].status == PASS


def test_prop_viability_fails_when_the_historical_sequence_blew_the_account():
    """The resampled rate is a statement about orderings that did not happen.

    The deterministic path was computed on every run and read by nothing, so a
    strategy whose ACTUAL trade order blew the account scored PASS on the
    strength of its permutations.
    """
    ctx = _Ctx()
    _prop_viability(ctx, _viable(historicalPassed=False, historicalBlown=True))
    c = ctx.check.items["prop_viability"]
    assert c.status == FAIL
    assert "HISTORICAL" in c.detail and "blew" in c.detail


def test_prop_viability_fails_when_the_historical_sequence_timed_out():
    ctx = _Ctx()
    _prop_viability(ctx, _viable(historicalPassed=False, historicalBlown=False))
    c = ctx.check.items["prop_viability"]
    assert c.status == FAIL
    assert "did not reach the profit target" in c.detail


def test_prop_viability_fails_when_no_deterministic_result_was_recorded():
    """Absent is not "fine". Only resampled orderings would have been judged."""
    ctx = _Ctx()
    _prop_viability(ctx, _viable(historicalPassed=None, historicalBlown=None))
    c = ctx.check.items["prop_viability"]
    assert c.status == FAIL
    assert "no deterministic" in c.detail


def test_prop_viability_fails_when_the_rate_does_not_name_its_resampling():
    """`iid` and `daily_block` disagreed by 22.8 points on the first frame they
    were both run against, so a rate without its scheme is not comparable."""
    ctx = _Ctx()
    _prop_viability(ctx, _viable(resampling=None))
    c = ctx.check.items["prop_viability"]
    assert c.status == FAIL
    assert "resampling scheme" in c.detail


def test_prop_viability_reports_every_failure_not_just_the_first():
    ctx = _Ctx()
    _prop_viability(ctx, _viable(passRatePct=10.0, historicalBlown=True,
                                 resampling=None))
    d = ctx.check.items["prop_viability"].detail
    assert "pass rate" in d and "HISTORICAL" in d and "resampling scheme" in d


def test_prop_viability_fails_on_a_rate_below_the_threshold():
    ctx = _Ctx()
    _prop_viability(ctx, _stage(evaluator="PropFirmSimulator", passRatePct=41.0,
                                grade="D", primaryProfile="Apex 50k",
                                passThresholdPct=65.0))
    assert ctx.check.items["prop_viability"].status == FAIL


def test_prop_viability_refuses_an_evaluator_adr_021_froze():
    ctx = _Ctx()
    _prop_viability(ctx, _stage(evaluator="prop_eval_mc", passRatePct=99.0))
    c = ctx.check.items["prop_viability"]
    assert c.status == FAIL
    assert "ADR-021" in c.detail


def test_prop_viability_is_unevaluated_when_the_stage_was_skipped():
    from scripts.trading_framework.provenance.run_record import RunRecord
    rec = RunRecord("RUN_TEST_PROP", strategy_key="t", ticker="NQ1")
    rec.skip_stage("prop_firm_sim", "no firm profile configured")
    ctx = _Ctx()
    _prop_viability(ctx, {s["name"]: s for s in rec.stages})
    c = ctx.check.items["prop_viability"]
    assert c.status == NOT_EVALUATED
    assert "no firm profile configured" in c.detail


def test_prop_viability_is_unevaluated_when_no_trades_reached_the_simulator():
    ctx = _Ctx()
    _prop_viability(ctx, _stage(evaluator="PropFirmSimulator", passRatePct=None,
                                skippedReason="no trades_detailed"))
    c = ctx.check.items["prop_viability"]
    assert c.status == NOT_EVALUATED
    assert "no trades_detailed" in c.detail


def test_prop_viability_is_unevaluated_when_the_stage_is_absent():
    """An absent stage must not read as "not applicable"."""
    ctx = _Ctx()
    _prop_viability(ctx, {})
    assert ctx.check.items["prop_viability"].status == NOT_EVALUATED
