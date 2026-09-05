"""The workflow's verdict must not be able to go green without evidence.

`workflow.py` exists so there is ONE way to run a strategy. Its output is not a
metric, it is a promotion checklist, and the whole value of that checklist rests
on one distinction: a criterion that FAILED and a criterion that was never
MEASURED are different, and neither is a pass.

That distinction is easy to lose by accident. `not self.failed` reads as "nothing
went wrong" and is true of a run that did nothing at all. These tests hold the
line where it is easy to cross.
"""
import pytest

from scripts.trading_framework.workflow import (
    CRITERIA, Checklist, FAIL, NOT_EVALUATED, PASS, _find_alignment,
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
