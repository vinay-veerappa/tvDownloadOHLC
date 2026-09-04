"""Acceptance tests for the run record.

`attributable` is a status boolean, and the standing question for any status
boolean is: what input makes this FALSE? A flag with no reachable false branch
is decoration. So every field in REQUIRED_PATHS has a test below that removes
exactly that field and asserts the flag flips -- and the happy-path test asserts
it is True, so the flag is proven to move in both directions.

The same question is asked of `assert_attributable`: it must raise on a bad
record AND pass a good one, because a gate that always raises is as useless as
one that never does.
"""
import json

import numpy as np
import pandas as pd
import pytest

from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.provenance.run_record import (
    REQUIRED_PATHS,
    UNDECLARED,
    RunRecord,
    assert_attributable,
    fingerprint_frame,
    load_run_record,
    read_ledger,
)


def _frame(periods=500, start="2020-01-01", seed=3):
    idx = pd.date_range(start, periods=periods, freq="1min", tz="US/Eastern")
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.1, periods))
    df = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                       "close": close, "volume": 1000.0}, index=idx)
    df["returns"] = df["close"].pct_change().fillna(0.0)
    return df


def _complete_record(tmp_path, **kw):
    rec = RunRecord.open("RUN_TEST_1", strategy_key="mean_reversion", ticker="NQ1",
                         ledger_path=tmp_path / "ledger.jsonl")
    rec.declare_strategy(name="Mean Reversion", cls_name="MeanReversionStrategy",
                         params={"bb_period": 30, "bb_std": 2.25})
    rec.declare_data(_frame(), ticker="NQ1", loader="test",
                     adjustment=kw.get("adjustment", "unadjusted"))
    rec.declare_engine(VectorizedBacktester())
    with rec.stage("backtest") as st:
        st.detail(note="ok")
    rec.set_metrics({"sharpe_ratio": 1.23, "win_rate_%": 55.0, "num_trades": 40})
    return rec


# --------------------------------------------------------------------------
# The flag moves in BOTH directions
# --------------------------------------------------------------------------
def test_a_complete_record_is_attributable(tmp_path):
    doc = _complete_record(tmp_path).finalize(str(tmp_path))
    assert doc["attributable"] is True, doc["refusals"] + doc["missingRequired"]
    assert doc["missingRequired"] == []
    assert doc["status"] == "complete"


# `runId` cannot be nulled -- the constructor refuses it (test below).
# `stages` cannot be nulled either: `finalize()` rebuilds that key from the
# stage list every time, so writing None into it is not reachable state. Its
# only real empty case is "no stages ran", covered by its own test below. Both
# exclusions are because the field is unreachable BY THIS MECHANISM, not because
# it is unchecked -- REQUIRED_PATHS still contains them and finalize still tests
# them.
_NULLABLE_REQUIRED = [p for p in REQUIRED_PATHS if p not in ("runId", "stages")]


@pytest.mark.parametrize("path", _NULLABLE_REQUIRED)
def test_every_required_field_can_flip_the_flag(tmp_path, path):
    """Remove exactly one load-bearing field; attribution must fail and NAME it."""
    rec = _complete_record(tmp_path)
    parts = path.split(".")
    node = rec._doc
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = None

    doc = rec.finalize(str(tmp_path))
    assert doc["attributable"] is False
    assert path in doc["missingRequired"], (path, doc["missingRequired"])
    assert any(path in r for r in doc["refusals"])


def test_run_id_is_required_at_construction():
    with pytest.raises(ValueError, match="run_id"):
        RunRecord("", strategy_key="k", ticker="NQ1")


def test_empty_metrics_counts_as_missing_not_present(tmp_path):
    """`metrics: {}` is as unattributable as no metrics key at all."""
    rec = _complete_record(tmp_path)
    rec.set_metrics({})
    doc = rec.finalize(str(tmp_path))
    assert doc["attributable"] is False
    assert "metrics" in doc["missingRequired"]


def test_a_run_with_no_stages_is_not_attributable(tmp_path):
    rec = RunRecord.open("RUN_NOSTAGE", strategy_key="k", ticker="NQ1",
                         ledger_path=tmp_path / "l.jsonl")
    rec.declare_data(_frame(), ticker="NQ1", loader="t", adjustment="unadjusted")
    rec.declare_engine(VectorizedBacktester())
    rec.set_metrics({"sharpe_ratio": 9.9})
    doc = rec.finalize(str(tmp_path))
    assert doc["attributable"] is False
    assert "stages" in doc["missingRequired"]


# --------------------------------------------------------------------------
# The gate must refuse AND pass
# --------------------------------------------------------------------------
def test_assert_attributable_passes_a_good_record(tmp_path):
    doc = _complete_record(tmp_path).finalize(str(tmp_path))
    assert_attributable(doc)  # must not raise


def test_assert_attributable_refuses_and_lists_the_reasons(tmp_path):
    rec = _complete_record(tmp_path)
    rec._doc["data"] = None
    doc = rec.finalize(str(tmp_path))
    with pytest.raises(ValueError) as ei:
        assert_attributable(doc)
    msg = str(ei.value)
    assert "NOT attributable" in msg
    assert "data.contentHash" in msg


# --------------------------------------------------------------------------
# Alignment: the field this whole record exists to carry
# --------------------------------------------------------------------------
def test_misaligned_signals_make_the_run_non_attributable(tmp_path):
    """A real mismatched-frame result must not be reportable.

    Built by actually running the engine on mismatched frames rather than by
    hand-writing an alignment dict, so the test breaks if the engine stops
    producing that shape.
    """
    full = _frame(periods=600)
    train, test = full.iloc[:400], full.iloc[400:]
    px = train["close"].to_numpy()
    sig = pd.DataFrame({
        "signal_time": train.index[[0, 50, 100]],
        "direction": "long",
        "entry_price": px[[0, 50, 100]],
        "stop_price": px[[0, 50, 100]] - 5.0,
        "target1_price": px[[0, 50, 100]] + 5.0,
    })
    metrics = VectorizedBacktester().run(sig, test, {"ticker": "NQ1"})

    rec = _complete_record(tmp_path)
    rec.record_alignment("oos", metrics["signal_alignment"])
    doc = rec.finalize(str(tmp_path))

    assert doc["attributable"] is False
    assert any("predate the scored frame" in r for r in doc["refusals"])
    assert doc["alignment"]["oos"]["dropped_before_frame_start"] == 3


def test_clean_alignment_does_not_refuse(tmp_path):
    """Control: the alignment check must not fire on a matched frame."""
    df = _frame(periods=600)
    px = df["close"].to_numpy()
    sig = pd.DataFrame({
        "signal_time": df.index[[10, 100, 200]],
        "direction": "long",
        "entry_price": px[[10, 100, 200]],
        "stop_price": px[[10, 100, 200]] - 5.0,
        "target1_price": px[[10, 100, 200]] + 5.0,
    })
    metrics = VectorizedBacktester().run(sig, df, {"ticker": "NQ1"})

    rec = _complete_record(tmp_path)
    rec.record_alignment("oos", metrics["signal_alignment"])
    doc = rec.finalize(str(tmp_path))
    assert doc["attributable"] is True, doc["refusals"]


def test_absent_alignment_warns_rather_than_refusing(tmp_path):
    """A legacy metrics dict is a gap in knowledge, not proof of a defect."""
    rec = _complete_record(tmp_path)
    rec.record_alignment("oos", None)
    doc = rec.finalize(str(tmp_path))
    assert doc["attributable"] is True
    assert any("no signal_alignment" in w for w in doc["warnings"])


# --------------------------------------------------------------------------
# Declarations that must not acquire a default
# --------------------------------------------------------------------------
def test_undeclared_adjustment_is_recorded_as_undeclared_not_guessed(tmp_path):
    rec = _complete_record(tmp_path, adjustment=UNDECLARED)
    doc = rec.finalize(str(tmp_path))
    assert doc["data"]["adjustment"] == UNDECLARED
    assert any("UNDECLARED" in w for w in doc["warnings"])
    # honest, but still reportable -- a screening run has no NT8 counterpart
    assert doc["attributable"] is True


def test_absent_nt8_profile_is_not_a_refusal_unless_claimed(tmp_path):
    """An inapplicable state is not an unreadable one."""
    doc = _complete_record(tmp_path).finalize(str(tmp_path))
    assert doc["nt8Profile"] is None
    assert doc["attributable"] is True

    rec = _complete_record(tmp_path)
    rec.require_nt8_profile()
    doc2 = rec.finalize(str(tmp_path))
    assert doc2["attributable"] is False
    assert any("no profile hash" in r for r in doc2["refusals"])


def test_declared_nt8_profile_satisfies_the_requirement(tmp_path):
    rec = _complete_record(tmp_path)
    rec.declare_nt8_profile("sha256:abc", "scripts/parity/backtest_profile.json")
    rec.require_nt8_profile()
    doc = rec.finalize(str(tmp_path))
    assert doc["attributable"] is True
    assert doc["nt8Profile"]["hash"] == "sha256:abc"


# --------------------------------------------------------------------------
# Data fingerprint
# --------------------------------------------------------------------------
def test_fingerprint_is_sensitive_to_a_single_changed_bar():
    a = _frame(periods=500)
    b = a.copy()
    b.iloc[250, b.columns.get_loc("high")] += 0.01
    assert fingerprint_frame(a)["contentHash"] != fingerprint_frame(b)["contentHash"]


def test_fingerprint_is_stable_across_identical_frames():
    assert (fingerprint_frame(_frame())["contentHash"]
            == fingerprint_frame(_frame())["contentHash"])


def test_fingerprint_ignores_tz_representation_but_records_it():
    """The same bars carried in UTC and in US/Eastern are the same bars."""
    a = _frame(periods=300)
    b = a.tz_convert("UTC")
    assert fingerprint_frame(a)["contentHash"] == fingerprint_frame(b)["contentHash"]
    assert fingerprint_frame(a)["tz"] != fingerprint_frame(b)["tz"]


def test_fingerprint_ignores_added_derived_columns():
    """A new loader feature must not invalidate every prior run's data identity."""
    a = _frame(periods=300)
    b = a.copy()
    b["some_new_feature"] = 1.0
    assert fingerprint_frame(a)["contentHash"] == fingerprint_frame(b)["contentHash"]
    assert "some_new_feature" in fingerprint_frame(b)["unhashedColumns"]


def test_fingerprint_refuses_an_empty_frame():
    with pytest.raises(ValueError, match="empty frame"):
        fingerprint_frame(pd.DataFrame())


def test_fingerprint_refuses_a_frame_with_no_price_columns():
    df = pd.DataFrame({"foo": [1.0, 2.0, 3.0]},
                      index=pd.date_range("2020-01-01", periods=3, freq="1min"))
    with pytest.raises(ValueError, match="none of the price columns"):
        fingerprint_frame(df)


def test_duplicate_and_non_monotonic_indexes_are_flagged(tmp_path):
    df = _frame(periods=100)
    dup = pd.concat([df, df.iloc[[50]]])
    rec = RunRecord.open("RUN_DUP", strategy_key="k", ticker="NQ1",
                         ledger_path=tmp_path / "l.jsonl")
    rec.declare_data(dup, ticker="NQ1", loader="t", adjustment="unadjusted")
    assert any("DUPLICATE" in w for w in rec.doc["warnings"])
    assert any("NOT monotonically" in w for w in rec.doc["warnings"])


# --------------------------------------------------------------------------
# Engine echo
# --------------------------------------------------------------------------
def test_engine_config_is_read_off_the_instance_not_restated(tmp_path):
    rec = _complete_record(tmp_path)
    rec.declare_engine(VectorizedBacktester(commission=4.5, slippage_pct=0.002))
    doc = rec.finalize(str(tmp_path))
    assert doc["engine"]["commission"] == 4.5
    assert doc["engine"]["slippagePct"] == 0.002


def test_engine_hash_changes_with_cost_assumptions():
    from scripts.trading_framework.provenance.run_record import describe_engine
    a = describe_engine(VectorizedBacktester(slippage_pct=0.0001))
    b = describe_engine(VectorizedBacktester(slippage_pct=0.0002))
    assert a["configHash"] != b["configHash"]


# --------------------------------------------------------------------------
# Code provenance
# --------------------------------------------------------------------------
def test_a_dirty_tree_warns_but_does_not_block(tmp_path):
    """Pre-live this repo is edited continuously; refusing dirty runs would make
    the record unusable. But the commit hash does not identify dirty code, and a
    reader has to be told that."""
    doc = _complete_record(tmp_path).finalize(str(tmp_path))
    if doc["code"]["dirty"]:
        assert any("DIRTY" in w for w in doc["warnings"])
    assert doc["code"]["commit"] is not None


def test_dirty_file_list_is_bounded_but_the_count_is_not(tmp_path):
    doc = _complete_record(tmp_path).finalize(str(tmp_path))
    assert len(doc["code"]["dirtyFiles"]) <= 40
    assert doc["code"]["dirtyFileCount"] >= len(doc["code"]["dirtyFiles"])


# --------------------------------------------------------------------------
# Stages
# --------------------------------------------------------------------------
def test_a_raising_stage_is_recorded_as_failed_and_re_raises(tmp_path):
    rec = _complete_record(tmp_path)
    with pytest.raises(RuntimeError):
        with rec.stage("optimize"):
            raise RuntimeError("optuna exploded")
    doc = rec.finalize(str(tmp_path), status="failed")
    failed = [s for s in doc["stages"] if s["name"] == "optimize"]
    assert failed and failed[0]["status"] == "failed"
    assert "optuna exploded" in failed[0]["error"]


def test_stage_order_is_preserved(tmp_path):
    rec = _complete_record(tmp_path)
    for name in ("leakage_audit", "optimize", "oos", "prop_firm"):
        with rec.stage(name):
            pass
    doc = rec.finalize(str(tmp_path))
    assert [s["name"] for s in doc["stages"]] == [
        "backtest", "leakage_audit", "optimize", "oos", "prop_firm"]


def test_fail_records_the_exception_and_marks_the_run_failed(tmp_path):
    rec = _complete_record(tmp_path)
    doc = rec.fail(ValueError("data gap"), str(tmp_path))
    assert doc["status"] == "failed"
    assert doc["attributable"] is False
    assert any("ValueError: data gap" in r for r in doc["refusals"])


# --------------------------------------------------------------------------
# Persistence and the ledger
# --------------------------------------------------------------------------
def test_record_is_written_and_reloads_identically(tmp_path):
    doc = _complete_record(tmp_path).finalize(str(tmp_path))
    on_disk = load_run_record(str(tmp_path / "run_record.json"))
    assert on_disk["runId"] == doc["runId"]
    assert on_disk["data"]["contentHash"] == doc["data"]["contentHash"]
    assert on_disk["attributable"] is True


def test_no_temp_file_survives_a_write(tmp_path):
    """The write is atomic via os.replace; a half-written record must never be
    readable by a report."""
    _complete_record(tmp_path).finalize(str(tmp_path))
    assert not list(tmp_path.glob("*.tmp"))


def test_ledger_records_the_run_at_open_so_a_crash_leaves_a_trace(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    RunRecord.open("RUN_CRASHED", strategy_key="k", ticker="NQ1", ledger_path=ledger)
    # process "dies" here -- finalize never called
    rows = read_ledger(str(ledger))
    assert len(rows) == 1
    assert rows[0]["runId"] == "RUN_CRASHED"
    assert rows[0]["status"] == "running"


def test_ledger_is_append_only_and_reader_takes_the_last_state(tmp_path):
    # A ledger of its own: `_complete_record` writes to tmp_path/ledger.jsonl,
    # and counting raw lines only means anything on a ledger with one run in it.
    ledger = tmp_path / "isolated_ledger.jsonl"
    rec = RunRecord.open("RUN_X", strategy_key="k", ticker="NQ1", ledger_path=ledger)
    rec.declare_data(_frame(), ticker="NQ1", loader="t", adjustment="unadjusted")
    rec.declare_engine(VectorizedBacktester())
    with rec.stage("s"):
        pass
    rec.set_metrics({"sharpe_ratio": 0.5})
    rec.finalize(str(tmp_path))

    raw = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(raw) == 2, "both the open and the close line must remain on disk"
    assert [r["status"] for r in raw] == ["running", "complete"]

    rows = read_ledger(str(ledger))
    assert len(rows) == 1 and rows[0]["status"] == "complete"


def test_ledger_carries_the_fields_a_search_must_be_corrected_by(tmp_path):
    """An arm ledger that cannot name the data, the code and the parameters it
    used cannot support a multiple-testing correction."""
    ledger = tmp_path / "ledger.jsonl"
    rec = RunRecord.open("RUN_L", strategy_key="mean_reversion", ticker="NQ1",
                         ledger_path=ledger)
    rec.declare_strategy(params={"bb_period": 30})
    rec.declare_data(_frame(), ticker="NQ1", loader="t", adjustment="unadjusted")
    rec.declare_engine(VectorizedBacktester())
    with rec.stage("s"):
        pass
    rec.set_metrics({"sharpe_ratio": 1.5, "win_rate_%": 60.0, "num_trades": 30})
    rec.finalize(str(tmp_path))

    row = read_ledger(str(ledger))[-1]
    for k in ("runId", "strategyKey", "paramsHash", "commit", "dataHash",
              "adjustment", "engineHash", "sharpe", "winRate", "trades",
              "attributable", "nRefusals"):
        assert k in row and row[k] is not None, k


def test_ledger_failure_warns_rather_than_killing_the_run(tmp_path):
    """Bookkeeping must not take down a research run -- nor fail silently."""
    bad = tmp_path / "not_a_dir"
    bad.write_text("i am a file", encoding="utf-8")
    rec = RunRecord("RUN_BAD_LEDGER", strategy_key="k", ticker="NQ1",
                    ledger_path=bad / "ledger.jsonl")
    rec._append_ledger()
    assert any("could not append to run ledger" in w for w in rec.doc["warnings"])


def test_read_ledger_on_a_missing_file_is_empty_not_an_error(tmp_path):
    assert read_ledger(str(tmp_path / "nope.jsonl")) == []


def test_read_ledger_skips_a_corrupt_line(tmp_path):
    ledger = tmp_path / "l.jsonl"
    ledger.write_text('{"runId":"A","status":"complete"}\nnot json\n'
                      '{"runId":"B","status":"failed"}\n', encoding="utf-8")
    rows = read_ledger(str(ledger))
    assert [r["runId"] for r in rows] == ["A", "B"]


# --------------------------------------------------------------------------
# Corrections found by reading a real record rather than the code
# --------------------------------------------------------------------------
def test_stage_duration_measures_the_stage_not_the_run(tmp_path):
    """Regression: durations were computed at SERIALIZATION time.

    Every stage is serialized together at finalize, so each reported "my start
    until the end of the whole run". Measured on a real run: load_data 181s,
    split 175s, optimize 174s -- on a run whose split was instantaneous. A
    duration that measures the wrong interval is worse than none, because it is
    the number someone optimises against.
    """
    import time as _time

    rec = _complete_record(tmp_path)
    with rec.stage("quick"):
        pass
    with rec.stage("slow"):
        _time.sleep(0.25)
    _time.sleep(0.3)  # time between the last stage and finalize
    doc = rec.finalize(str(tmp_path))

    by_name = {s["name"]: s for s in doc["stages"]}
    assert by_name["quick"]["durationSec"] < 0.1
    assert 0.2 <= by_name["slow"]["durationSec"] < 0.29, by_name["slow"]
    # and the gap before finalize must not have been attributed to either
    assert by_name["quick"]["durationSec"] < by_name["slow"]["durationSec"]


def test_a_failed_stage_still_records_its_own_duration(tmp_path):
    rec = _complete_record(tmp_path)
    with pytest.raises(RuntimeError):
        with rec.stage("boom"):
            raise RuntimeError("x")
    doc = rec.finalize(str(tmp_path), status="failed")
    boom = [s for s in doc["stages"] if s["name"] == "boom"][0]
    assert boom["durationSec"] is not None


def test_zero_signals_is_distinguishable_from_a_legacy_engine(tmp_path):
    """Both used to arrive as an absent `signal_alignment` key."""
    df = _frame(periods=300)
    empty = pd.DataFrame(columns=["signal_time", "direction", "entry_price",
                                  "stop_price", "target1_price"])
    metrics = VectorizedBacktester().run(empty, df, {"ticker": "NQ1"})
    align = metrics["signal_alignment"]
    assert align["signals_in"] == 0
    assert "no signals reached the engine" in align["note"]

    rec = _complete_record(tmp_path)
    rec.record_alignment("oos", align)
    doc = rec.finalize(str(tmp_path))
    # a real, readable "zero signals" report -- not a warning about the engine
    assert not any("no signal_alignment" in w for w in doc["warnings"])
    assert doc["alignment"]["oos"]["signals_in"] == 0


def test_metrics_preserve_integer_types(tmp_path):
    """A trade COUNT rendered as 0.0 invites a reader to treat it as a rate."""
    rec = _complete_record(tmp_path)
    rec.set_metrics({"num_trades": 40, "sharpe_ratio": 1.5, "grade": "A",
                     "flagged": True, "nothing": None})
    doc = rec.finalize(str(tmp_path))
    assert isinstance(doc["metrics"]["num_trades"], int)
    assert isinstance(doc["metrics"]["sharpe_ratio"], float)
    assert doc["metrics"]["grade"] == "A"
    assert doc["metrics"]["flagged"] is True
    assert doc["metrics"]["nothing"] is None


def test_metrics_drop_curves_and_frames(tmp_path):
    rec = _complete_record(tmp_path)
    rec.set_metrics({"sharpe_ratio": 1.0,
                     "equity_curve": pd.Series([1.0, 1.1]),
                     "trades_detailed": pd.DataFrame({"a": [1]}),
                     "rolling_performance": {"30d": {}}})
    doc = rec.finalize(str(tmp_path))
    assert set(doc["metrics"]) == {"sharpe_ratio"}


# --------------------------------------------------------------------------
# attribution() must agree with finalize()
# --------------------------------------------------------------------------
def test_attribution_preview_agrees_with_finalize_when_good(tmp_path):
    rec = _complete_record(tmp_path)
    assert rec.attribution()["attributable"] is True
    assert rec.finalize(str(tmp_path))["attributable"] is True


def test_attribution_preview_agrees_with_finalize_when_bad(tmp_path):
    rec = _complete_record(tmp_path)
    rec.refuse("something is wrong")
    pre = rec.attribution()
    assert pre["attributable"] is False
    assert rec.finalize(str(tmp_path))["attributable"] is False


def test_attribution_preview_does_not_mutate_the_record(tmp_path):
    """It is called before reporting; if it added refusals, calling it would
    change the verdict it reports."""
    rec = _complete_record(tmp_path)
    rec._doc["data"] = None
    before = len(rec.doc["refusals"])
    for _ in range(3):
        assert rec.attribution()["attributable"] is False
    assert len(rec.doc["refusals"]) == before


def test_attribution_sees_stages_before_finalize_rebuilds_them(tmp_path):
    """`stages` is only populated at finalize, so a naive preview would report
    every run as missing stages."""
    rec = RunRecord.open("RUN_PRE", strategy_key="k", ticker="NQ1",
                         ledger_path=tmp_path / "l.jsonl")
    rec.declare_data(_frame(), ticker="NQ1", loader="t", adjustment="unadjusted")
    rec.declare_engine(VectorizedBacktester())
    rec.set_metrics({"sharpe_ratio": 1.0})
    assert "stages" in rec.attribution()["missingRequired"]
    with rec.stage("s"):
        pass
    assert "stages" not in rec.attribution()["missingRequired"]


def test_run_ids_are_unique_within_the_same_second():
    """Regression: `new_run_id` used second resolution only.

    Two runs started inside the same second received the SAME id, wrote to the
    same directory and overwrote each other's record -- the exact failure the
    run-id'd output path exists to prevent, one granularity down. A tight loop
    is the realistic case (a sweep issuing runs back to back), so 200 ids in
    immediate succession must all differ.
    """
    ids = [RunRecord.new_run_id("NQ1", "mean_reversion") for _ in range(200)]
    assert len(set(ids)) == 200, "collision among {} ids".format(len(ids))


def test_run_id_stays_sortable_and_readable():
    """The random suffix must not cost lexicographic ordering by time."""
    import time as _time

    a = RunRecord.new_run_id("NQ1", "s")
    _time.sleep(0.01)
    b = RunRecord.new_run_id("NQ1", "s")
    assert a < b
    assert a.startswith("RUN_") and "NQ1" in a and "S" in a


# --------------------------------------------------------------------------
# trade_count -- the alias problem that made a gate fire on the wrong runs
# --------------------------------------------------------------------------
def test_trade_count_reads_either_engines_key():
    """VectorizedBacktester says `num_trades`; NT8ParityBacktester says
    `total_trades`. A caller must not have to know which engine ran."""
    from scripts.trading_framework.provenance.run_record import trade_count

    assert trade_count({"num_trades": 12}) == 12
    assert trade_count({"total_trades": 38}) == 38
    assert trade_count({"trades": 5}) == 5


def test_trade_count_raises_rather_than_returning_zero():
    """Regression, and the whole point of the helper.

    A zero-trade gate written as `metrics.get('num_trades', 0)` read 0 from an
    NT8ParityBacktester result and refused a run that had actually taken 38
    trades at a 71% win rate. Absent and zero are different facts.
    """
    from scripts.trading_framework.provenance.run_record import trade_count

    with pytest.raises(KeyError, match="no trade-count key"):
        trade_count({"sharpe_ratio": 8.8, "profit_factor": 21.9})
    with pytest.raises(KeyError):
        trade_count({})


def test_trade_count_still_reports_a_genuine_zero():
    """Control: the fix must not make a real zero unreachable."""
    from scripts.trading_framework.provenance.run_record import trade_count

    assert trade_count({"num_trades": 0}) == 0
    assert trade_count({"total_trades": 0}) == 0
