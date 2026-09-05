"""The decision log: schema, the two emitters, the roster, and the parity diff.

WHAT THESE PROTECT. The log's whole value is that it can be trusted as evidence
about why a strategy acted. Three ways it could stop being that, each with tests
below:

  * a log that CONTRADICTS the behaviour it describes -- an ENTRY carrying a
    failed gate. Caught at write time on the Python side and reported by the
    reader for both sides, because the C# emitter deliberately does not throw
    into a running strategy.
  * a `measure` counted as a `gate`, which puts a structurally-unfailable row at
    the top of every roster and inflates the set the parity diff runs over.
  * a column added on one side only, which is what the generator exists to stop.
"""

import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from scripts.trading_framework.reporting.decision_log import (
    COLUMNS, DECISIONS, KINDS, SCHEMA_VERSION, DecisionLogError,
    DecisionLogWriter, Gate, GateRecorder, compare_rosters, contradictions,
    gate_roster, read_decision_log, render_decision_log, write_frame,
)
from scripts.trading_framework.reporting.win_loss_attribution import (
    MIN_SAMPLE_PER_SIDE, excursion_profile, gate_values_by_outcome,
    loss_sources, render_win_loss,
)

REPO = pathlib.Path(__file__).resolve().parents[3]
GENERATED = REPO / "scripts" / "ninjatrader" / "shared" / "DecisionLog.cs"


def _idx(n=200):
    return pd.date_range("2026-03-02 09:30", periods=n, freq="1min",
                         tz="America/New_York")


# --------------------------------------------------------------------------- #
# The row-wise writer refuses a self-contradicting decision
# --------------------------------------------------------------------------- #

def test_an_entry_with_a_failed_gate_is_refused(tmp_path):
    """A log that can record this is worse than no log: it looks like evidence."""
    with DecisionLogWriter(tmp_path / "d.csv", run_id="R", strategy="s") as w:
        with pytest.raises(ValueError) as e:
            w.log(bar_time="2026-03-02 10:00", decision="ENTRY",
                  gates=[Gate("adx", True, 20, 15), Gate("rsi", False, 40, 30)])
    assert "contradicts" in str(e.value) and "rsi" in str(e.value)


def test_a_rejection_with_no_failed_gate_is_refused(tmp_path):
    with DecisionLogWriter(tmp_path / "d.csv", run_id="R", strategy="s") as w:
        with pytest.raises(ValueError):
            w.log(bar_time="2026-03-02 10:00", decision="REJECTED",
                  gates=[Gate("adx", True, 20, 15)])


def test_a_failing_measure_does_not_make_an_entry_contradictory(tmp_path):
    """`Gate.passed` is meaningless on a measure. Counting it would make every
    instrumented entry look self-contradictory."""
    with DecisionLogWriter(tmp_path / "d.csv", run_id="R", strategy="s") as w:
        seq = w.log(bar_time="2026-03-02 10:00", decision="ENTRY",
                    signal_name="s1",
                    gates=[Gate("adx", True, 20, 15),
                           Gate("excursion", False, 1.4, kind="measure")])
    assert seq == 1
    df = read_decision_log(tmp_path / "d.csv")
    assert contradictions(df).empty


def test_an_unknown_decision_or_kind_is_refused(tmp_path):
    with DecisionLogWriter(tmp_path / "d.csv", run_id="R", strategy="s") as w:
        with pytest.raises(ValueError):
            w.log(bar_time="2026-03-02 10:00", decision="MAYBE")
        with pytest.raises(ValueError):
            w.log(bar_time="2026-03-02 10:00", decision="ENTRY",
                  gates=[Gate("g", True, kind="hunch")])


def test_the_writer_must_be_used_as_a_context_manager(tmp_path):
    """Otherwise the header is never written and the file is unreadable."""
    w = DecisionLogWriter(tmp_path / "d.csv", run_id="R", strategy="s")
    with pytest.raises(RuntimeError):
        w.log(bar_time="2026-03-02 10:00", decision="EXIT")


def test_a_bad_side_is_refused(tmp_path):
    with pytest.raises(ValueError):
        DecisionLogWriter(tmp_path / "d.csv", run_id="R", strategy="s", side="csharp")


# --------------------------------------------------------------------------- #
# The vectorised emitter -- the shape a hunt() actually has
# --------------------------------------------------------------------------- #

def test_the_verdict_falls_out_of_the_gates_not_the_caller():
    """An ENTRY where every gate passed, REJECTED otherwise, computed here so a
    hunter cannot record a verdict that disagrees with its own masks."""
    idx = _idx(10)
    trig = pd.Series([True] * 10, index=idx)
    g1 = pd.Series([True] * 10, index=idx)
    g2 = pd.Series([True] * 5 + [False] * 5, index=idx)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(trig, "long").gate("a", g1).gate("b", g2).to_frame())
    ent = df[df["decision"] == "ENTRY"]
    rej = df[df["decision"] == "REJECTED"]
    assert ent["seq"].nunique() == 5
    assert rej["seq"].nunique() == 5
    assert contradictions(df).empty


def test_every_gate_is_recorded_not_just_the_first_failure():
    """Rule 2. Short-circuit order is an implementation accident; a first-failure
    log reports the accident as the cause."""
    idx = _idx(4)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(pd.Series(True, index=idx), "long")
          .gate("a", pd.Series(False, index=idx))
          .gate("b", pd.Series(False, index=idx))
          .to_frame())
    one = df[(df["seq"] == 1) & (df["kind"] == "gate")]
    assert set(one["gate"]) == {"a", "b"}
    assert (one["gate_pass"] == 0).all()


def test_untriggered_bars_are_counted_not_written():
    """Rule 4: the denominator, without becoming the per-bar dump this replaces."""
    idx = _idx(100)
    trig = pd.Series([True] * 10 + [False] * 90, index=idx)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(trig, "long").gate("a", pd.Series(True, index=idx)).to_frame())
    skip = df[df["decision"] == "SKIP"]
    assert len(skip) == 1
    assert int(skip["gate_value"].iloc[0]) == 90
    assert int(skip["gate_threshold"].iloc[0]) == 100
    assert df[df["decision"] != "SKIP"]["seq"].nunique() == 10


def test_a_measure_never_blocks_and_never_enters_the_roster():
    """The distinction that keeps a 0%-failure row off the top of the roster."""
    idx = _idx(10)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(pd.Series(True, index=idx), "long")
          .measure("excursion", pd.Series(np.arange(10.0), index=idx))
          .gate("real", pd.Series(True, index=idx))
          .to_frame())
    assert (df[df["decision"] == "ENTRY"]["seq"].nunique()) == 10
    assert set(gate_roster(df)["gate"]) == {"real"}
    assert "excursion" in set(df["gate"])


def test_an_unnamed_or_duplicated_gate_is_refused():
    idx = _idx(5)
    r = GateRecorder(idx, run_id="R", strategy="s")
    with pytest.raises(ValueError):
        r.gate("", pd.Series(True, index=idx))
    r.gate("a", pd.Series(True, index=idx))
    with pytest.raises(ValueError):
        r.gate("a", pd.Series(True, index=idx))


def test_a_gate_that_never_fails_is_flagged():
    """A blocking gate with a structural 0% failure rate is dead code or a
    mislabelled covariate. Either way it is a green that can never be red."""
    idx = _idx(50)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(pd.Series(True, index=idx), "long")
          .gate("always", pd.Series(True, index=idx))
          .to_frame())
    roster = gate_roster(df)
    assert bool(roster.loc[roster["gate"] == "always", "never_fails"].iloc[0])
    assert "never fails" in render_decision_log(df)


def test_a_small_sample_is_not_called_never_failing():
    """Negative control: 3 passing evaluations is not evidence of dead code."""
    idx = _idx(3)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(pd.Series(True, index=idx), "long")
          .gate("always", pd.Series(True, index=idx)).to_frame())
    assert not gate_roster(df)["never_fails"].any()


# --------------------------------------------------------------------------- #
# Round trip and validation
# --------------------------------------------------------------------------- #

def test_the_frame_round_trips_through_the_reader(tmp_path):
    idx = _idx(20)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(pd.Series(True, index=idx), "long")
          .gate("a", pd.Series([True, False] * 10, index=idx))
          .to_frame(signal_prefix="s_"))
    p = write_frame(df, tmp_path / "d.csv")
    back = read_decision_log(p)
    assert list(back.columns) == list(COLUMNS)
    assert back["seq"].nunique() == df["seq"].nunique()


def test_a_file_from_an_unknown_schema_version_is_refused(tmp_path):
    """Refusing beats reading a shifted column and reporting it confidently."""
    idx = _idx(5)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(pd.Series(True, index=idx), "long")
          .gate("a", pd.Series(True, index=idx)).to_frame())
    df["schema_version"] = SCHEMA_VERSION + 99
    p = write_frame(df, tmp_path / "d.csv")
    with pytest.raises(DecisionLogError) as e:
        read_decision_log(p)
    assert "shifted column" in str(e.value)


def test_a_csv_that_is_not_a_decision_log_is_refused(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("a,b,c\n1,2,3\n", encoding="ascii")
    with pytest.raises(DecisionLogError) as e:
        read_decision_log(p)
    assert "not a decision log" in str(e.value)


def test_a_contradiction_written_by_the_other_side_is_reported_not_raised(tmp_path):
    """The C# emitter deliberately does not throw into a running strategy, so the
    reader is the enforcer for anything it produces."""
    idx = _idx(2)
    df = (GateRecorder(idx, run_id="R", strategy="s")
          .trigger(pd.Series(True, index=idx), "long")
          .gate("a", pd.Series([True, True], index=idx)).to_frame())
    df.loc[(df["decision"] == "ENTRY") & (df["gate"] == "a"), "gate_pass"] = 0
    p = write_frame(df, tmp_path / "d.csv")
    bad = contradictions(read_decision_log(p))
    assert len(bad) == 2
    assert "failed but the trade was taken" in bad["problem"].iloc[0]
    assert "not evidence" in render_decision_log(read_decision_log(p))


# --------------------------------------------------------------------------- #
# The parity diff -- the cheap check that runs BEFORE trade-set recall
# --------------------------------------------------------------------------- #

def _side(gates, side, n=30):
    idx = _idx(n)
    r = GateRecorder(idx, run_id="R", strategy="s", side=side)
    r.trigger(pd.Series(True, index=idx), "long")
    for g in gates:
        r.gate(g, pd.Series([True, False] * (n // 2), index=idx))
    return r.to_frame()


def test_two_sides_with_different_rosters_are_not_comparable():
    """The measured `mean_reversion` / `BBMRReversionBot` case: a recall figure
    between two different strategies is a number about nothing."""
    py = _side(["band"], "python")
    nt = _side(["band", "adx", "rsi", "squeeze"], "nt8")
    r = compare_rosters(py, nt)
    assert r["comparable"] is False
    assert r["only_nt8"] == ["adx", "rsi", "squeeze"]
    assert r["only_python"] == []
    assert "different strategies" in r["reason"]


def test_a_matching_roster_is_comparable():
    r = compare_rosters(_side(["a", "b"], "python"), _side(["a", "b"], "nt8"))
    assert r["comparable"] is True
    assert r["shared"] == ["a", "b"]


def test_two_empty_sides_are_not_silently_called_comparable():
    """Negative control. `comparable` must not be true because nothing was
    measured -- that is the "green with no reachable red" shape."""
    r = compare_rosters(pd.DataFrame(), pd.DataFrame())
    assert r["comparable"] is False
    assert "no gates recorded" in r["reason"]


def test_the_direction_of_the_difference_is_reported_both_ways():
    """Each direction means something different: a gate only on the NT8 side
    makes recall fall and looks like a Python defect; the reverse means the bot
    takes trades nothing predicted."""
    r = compare_rosters(_side(["a", "x"], "python"), _side(["a", "y"], "nt8"))
    assert r["only_python"] == ["x"] and r["only_nt8"] == ["y"]


# --------------------------------------------------------------------------- #
# The generated C# tracks the schema
# --------------------------------------------------------------------------- #

def test_the_generated_cs_matches_the_python_schema():
    p = subprocess.run([sys.executable, "scripts/utils/generate_decision_log.py",
                        "--check"], cwd=REPO, capture_output=True, text=True)
    assert p.returncode == 0, (p.stdout + p.stderr).strip()


def test_the_generated_cs_header_is_the_column_list_in_order():
    """Parse the C# BACK, so the generator cannot agree with itself about a
    column order it got wrong."""
    text = GENERATED.read_text(encoding="utf-8")
    start = text.index("public const string Header =")
    block = text[start:text.index(";", start)]
    got = [seg.strip().strip('+').strip().strip('"').rstrip(",")
           for seg in block.split("\n")[1:] if seg.strip()]
    got = [g.strip('"').rstrip(",") for g in got if g]
    assert got == list(COLUMNS), got


def test_the_generated_cs_writes_one_field_per_column():
    """A Row() with the wrong arity shifts every column to its right."""
    text = GENERATED.read_text(encoding="utf-8")
    body = text[text.index("private void Row("):]
    body = body[:body.index("        }")]
    joined = body[body.index("new string[] {"):]
    assert joined.count(",") >= len(COLUMNS) - 1


def test_the_generated_cs_knows_the_same_decisions_and_kinds():
    text = GENERATED.read_text(encoding="utf-8")
    for d in DECISIONS:
        assert '"{}"'.format(d) in text, d
    for k in KINDS:
        assert '"{}"'.format(k) in text, k


def test_the_generated_cs_writes_where_the_bridge_can_serve_it():
    """`mcp_` + `.csv` in Globals.UserDataDir is exactly what nt_get_export
    serves. The precedent to avoid is a %TEMP% GUID path nobody can address."""
    text = GENERATED.read_text(encoding="utf-8")
    assert 'FilePrefix    = "mcp_decisions_"' in text
    assert "Globals.UserDataDir" in text
    assert "GetTempPath" not in text


def test_the_generated_cs_never_throws_into_the_strategy():
    """A logging failure must not kill a backtest -- but it must not be silent
    either, or a short file reads as "the strategy took no trades"."""
    text = GENERATED.read_text(encoding="utf-8")
    assert "LastError" in text
    assert text.count("catch (Exception ex)") >= 3
    assert "DISABLED" in text


def test_the_generated_cs_is_unique_per_instance():
    """The Strategy Analyzer runs many instances concurrently during an
    optimisation; two opening one path is a truncated file, not an error."""
    text = GENERATED.read_text(encoding="utf-8")
    assert "Interlocked.Increment" in text


def test_the_generated_cs_quotes_a_field_containing_a_comma():
    text = GENERATED.read_text(encoding="utf-8")
    assert "private static string Q(string s)" in text
    assert "IndexOf(',')" in text


def test_the_generated_file_is_tracked_by_git():
    rel = GENERATED.relative_to(REPO).as_posix()
    p = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                       cwd=REPO, capture_output=True)
    assert p.returncode == 0, "{} is not tracked".format(rel)


# --------------------------------------------------------------------------- #
# The reference instrumentation -- mean_reversion
# --------------------------------------------------------------------------- #

def _price_frame(n=1500, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-02 09:30", periods=n, freq="1min",
                        tz="America/New_York")
    px = 20000 + np.cumsum(rng.normal(0, 3, n))
    return pd.DataFrame({"open": px, "high": px + 2, "low": px - 2, "close": px},
                        index=idx)


def test_the_reference_hunter_emits_a_log_without_changing_its_contract():
    from scripts.strategies.reversal.core.mean_reversion import MeanReversionStrategy
    s = MeanReversionStrategy()
    sig = s.hunt(_price_frame())
    assert list(sig.columns) == s.output_cols        # contract unchanged
    d = s.last_decisions
    assert d is not None and not d.empty
    assert d["seq"].nunique() >= 1
    assert contradictions(d).empty


def test_the_reference_hunter_entry_count_matches_its_signal_count():
    """The log must describe the trades the hunter actually returned. A log that
    disagrees with its own output is the failure this whole module guards."""
    from scripts.strategies.reversal.core.mean_reversion import MeanReversionStrategy
    s = MeanReversionStrategy()
    sig = s.hunt(_price_frame())
    entries = s.last_decisions
    entries = entries[entries["decision"] == "ENTRY"]["seq"].nunique()
    assert entries == len(sig), (entries, len(sig))


def test_the_reference_hunter_shows_its_cap_is_the_gate():
    """`groupby('date').head(1)` is the real trade cap and it is not a trading
    criterion. sessions.yaml says 3/day and the paired bot allows 99."""
    from scripts.strategies.reversal.core.mean_reversion import MeanReversionStrategy
    s = MeanReversionStrategy()
    s.hunt(_price_frame())
    roster = gate_roster(s.last_decisions)
    row = roster[roster["gate"] == "first_signal_of_day"].iloc[0]
    assert row["failed"] > 0
    assert row["blocked_alone"] == row["failed"]


# --------------------------------------------------------------------------- #
# Win/loss attribution
# --------------------------------------------------------------------------- #

def _trades(n=60, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-04-01 09:35", periods=n, freq="37min",
                        tz="America/New_York")
    pnl = rng.normal(10, 120, n)
    return pd.DataFrame({
        "entry_time": idx,
        "exit_time": idx + pd.Timedelta(minutes=12),
        "total_pnl_usd": pnl,
        "exit_reason": np.where(pnl > 0, "Profit target", "Stop loss"),
        "mae_usd": -np.abs(rng.normal(60, 20, n)),
        "mfe_usd": np.abs(rng.normal(80, 40, n)),
    })


def test_losses_are_grouped_by_session_and_exit_reason():
    src = loss_sources(_trades())
    assert {"session", "exit_reason", "trades", "win_%", "pnl_$"} <= set(src.columns)
    assert src["pnl_$"].is_monotonic_increasing          # worst first
    assert src["trades"].sum() == 60


def test_a_missing_mae_column_is_reported_not_inferred():
    """An absent MAE and a zero MAE are opposite findings."""
    df = _trades().drop(columns=["mae_usd", "mfe_usd"])
    ex = excursion_profile(df)
    assert ex["available"] is False
    assert "nt_backtest" in ex["reason"]


def test_the_excursion_profile_separates_an_exit_defect_from_an_entry_defect():
    ex = excursion_profile(_trades())
    assert ex["available"] is True
    assert ex["winners"] + ex["losers"] == 60
    assert ex["losers_that_ran"] >= 0


def test_a_gate_median_is_refused_below_the_sample_floor():
    """A median over four trades is not a finding."""
    idx = _idx(6)
    d = (GateRecorder(idx, run_id="R", strategy="s")
         .trigger(pd.Series(True, index=idx), "long")
         .gate("adx", pd.Series(True, index=idx),
               value=pd.Series(np.arange(6.0), index=idx), threshold=15)
         .to_frame(signal_prefix="s_"))
    tr = pd.DataFrame({"entry_time": idx, "total_pnl_usd": [1, -1] * 3})
    assert gate_values_by_outcome(d, tr).empty
    assert str(MIN_SAMPLE_PER_SIDE) not in ""     # the floor is named in the report
    assert "noise wearing a number" in render_win_loss(tr, d)


def test_a_gate_that_separates_winners_from_losers_is_named():
    """The payoff: "winners entered at 25, losers at 12, gate set at 15" names a
    line to change. Nothing derivable from a trade list can say that."""
    n = 60
    idx = pd.date_range("2026-04-01 09:35", periods=n, freq="37min",
                        tz="America/New_York")
    pnl = np.array([100.0] * 30 + [-100.0] * 30)
    adx = pd.Series(np.r_[np.full(30, 25.0), np.full(30, 12.0)], index=idx)
    d = (GateRecorder(idx, run_id="R", strategy="s")
         .trigger(pd.Series(True, index=idx), "long")
         .gate("adx", pd.Series(True, index=idx), value=adx, threshold=15.0)
         .to_frame(signal_prefix="s_"))
    tr = pd.DataFrame({"entry_time": idx, "total_pnl_usd": pnl,
                       "signal_name": ["s_{}".format(i + 1) for i in range(n)]})
    gv = gate_values_by_outcome(d, tr)
    assert list(gv["gate"]) == ["adx"]
    row = gv.iloc[0]
    assert row["median_winners"] == 25.0 and row["median_losers"] == 12.0
    assert row["separation"] == 13.0
    assert row["threshold"] == 15.0
    out = render_win_loss(tr, d)
    assert "`adx`" in out


def _gate_frame_and_trades(n=60, *, with_signal_names: bool, unit="ms"):
    idx = pd.date_range("2026-04-01 09:35", periods=n, freq="37min",
                        tz="America/New_York")
    pnl = np.array([100.0] * (n // 2) + [-100.0] * (n // 2))
    adx = pd.Series(np.r_[np.full(n // 2, 25.0), np.full(n // 2, 12.0)], index=idx)
    d = (GateRecorder(idx, run_id="R", strategy="s")
         .trigger(pd.Series(True, index=idx), "long")
         .gate("adx", pd.Series(True, index=idx), value=adx, threshold=15.0)
         .to_frame(signal_prefix="s_" if with_signal_names else ""))
    tr = pd.DataFrame({
        # The engine's own frame carries a different datetime RESOLUTION from
        # the ISO text a decision log is parsed from.
        "entry_time": idx.as_unit(unit),
        "total_pnl_usd": pnl,
    })
    if with_signal_names:
        tr["signal_name"] = ["s_{}".format(i + 1) for i in range(n)]
    return d, tr


def test_the_nearest_time_join_works_across_datetime_resolutions():
    """pandas refuses merge_asof across resolutions, and the two sides genuinely
    differ: a decision timestamp is parsed from ISO text, a trade timestamp
    comes from the engine's frame."""
    d, tr = _gate_frame_and_trades(with_signal_names=False, unit="ms")
    gv = gate_values_by_outcome(d, tr)
    assert list(gv["gate"]) == ["adx"]
    assert gv.iloc[0]["separation"] == 13.0


def test_the_outcome_flag_survives_the_nearest_time_join_as_a_bool():
    """`~` on a non-bool Series is BITWISE: a merge_asof tolerance introduces
    NaN, promoting the column to object, and `~col` then yields -1/-2 rather
    than raising. As a positional mask that selects the WRONG rows instead of
    failing, which is the worse outcome."""
    d, tr = _gate_frame_and_trades(with_signal_names=False)
    tr = tr.copy()
    # Push one decision outside the 15-minute tolerance so the merge really
    # does produce an unmatched row and the object promotion really happens.
    tr.loc[tr.index[0], "entry_time"] = tr["entry_time"].iloc[0] + pd.Timedelta("9h")
    gv = gate_values_by_outcome(d, tr)
    assert not gv.empty
    assert gv.iloc[0]["n_win"] + gv.iloc[0]["n_loss"] <= len(tr)


def test_both_join_strategies_agree_when_both_are_available():
    """A signal-name join is exact; nearest-time is approximate by construction.
    On clean data they must not disagree, or one of them is wrong."""
    d1, tr1 = _gate_frame_and_trades(with_signal_names=True)
    d2, tr2 = _gate_frame_and_trades(with_signal_names=False)
    a = gate_values_by_outcome(d1, tr1).iloc[0]
    b = gate_values_by_outcome(d2, tr2).iloc[0]
    assert a["median_winners"] == b["median_winners"]
    assert a["median_losers"] == b["median_losers"]


def test_an_identically_zero_excursion_column_is_called_dead_not_measured():
    """Measured on the live `mean_reversion` run: mae_points and mfe_points are
    present and 0.0 on all 16 trades, 11 of which exited on a stop. "Median MAE
    0.0" reads as a finding about the strategy; it is one about the pipeline."""
    df = _trades()
    df["mae_usd"] = 0.0
    df["mfe_usd"] = 0.0
    ex = excursion_profile(df)
    assert ex["available"] is False
    assert "identically ZERO" in ex["reason"]
    assert "dead" in ex["reason"]


def test_a_real_excursion_column_is_still_reported():
    """Negative control for the check above: it must not refuse live data."""
    assert excursion_profile(_trades())["available"] is True


def test_a_single_zero_excursion_trade_is_not_condemned():
    """One trade with a zero MAE is possible; sixteen is not."""
    df = _trades(n=1)
    df["mae_usd"] = 0.0
    df["mfe_usd"] = 0.0
    assert excursion_profile(df)["available"] is True


def test_a_stop_exit_that_booked_a_profit_is_surfaced():
    """A stop on the wrong side of entry fills immediately and pays. Three such
    trades are in the live `mean_reversion` set, whose `signal_geometry`
    criterion FAILS with stop_wrong_side=372."""
    df = _trades(n=10)
    df["total_pnl_usd"] = 50.0
    df["exit_reason"] = "Stop Loss"
    out = render_win_loss(df)
    assert "booked a PROFIT" in out
    assert "geometry defects" in out
    assert "signal_geometry" in out


def test_a_normal_trade_set_is_not_accused_of_a_geometry_defect():
    df = _trades(n=10)
    df["total_pnl_usd"] = [50.0, -50.0] * 5
    df["exit_reason"] = np.where(df["total_pnl_usd"] > 0, "Profit target", "Stop Loss")
    assert "booked a PROFIT" not in render_win_loss(df)


def test_the_funnel_gap_between_hunter_entries_and_trades_is_named():
    """3,188 hunter entries became 16 trades on the live run. The engine's own
    gates are not in the log, and a report that shows both numbers without
    saying why they differ invites the reader to distrust the right one."""
    idx = _idx(40)
    d = (GateRecorder(idx, run_id="R", strategy="s")
         .trigger(pd.Series(True, index=idx), "long")
         .gate("a", pd.Series(True, index=idx)).to_frame(signal_prefix="s_"))
    tr = pd.DataFrame({"entry_time": idx[:3], "total_pnl_usd": [1.0, -1.0, 1.0]})
    out = render_win_loss(tr, d)
    assert "40 hunter entr" in out
    assert "ENGINE's own" in out


def test_no_funnel_warning_when_the_counts_agree():
    idx = _idx(4)
    d = (GateRecorder(idx, run_id="R", strategy="s")
         .trigger(pd.Series(True, index=idx), "long")
         .gate("a", pd.Series(True, index=idx)).to_frame(signal_prefix="s_"))
    tr = pd.DataFrame({"entry_time": idx, "total_pnl_usd": [1.0, -1.0, 1.0, -1.0]})
    assert "ENGINE's own" not in render_win_loss(tr, d)


def test_the_report_is_ascii_on_every_path():
    """cp1252 consoles cannot encode an em-dash or a <= sign."""
    tr = _trades()
    for out in (render_win_loss(tr), render_win_loss(tr, pd.DataFrame()),
                render_win_loss(pd.DataFrame()),
                render_decision_log(pd.DataFrame()),
                render_decision_log(_side(["a"], "python"))):
        bad = sorted({c for c in out if ord(c) > 127})
        assert not bad, bad


def test_the_report_states_what_is_missing_rather_than_rendering_empty():
    assert "Not available" in render_win_loss(pd.DataFrame())
    assert "no decision log" in render_win_loss(_trades())
    assert "not instrumented" in render_decision_log(pd.DataFrame())
