"""The Strat shared core must mean the same thing in C# and in Python.

`scripts/ninjatrader/shared/StratCore.cs` opens by declaring itself the C# mirror
of `scripts/libs_py/the_strat/` and says "Rule changes go here AND in Python
together - never in only one side." That is a comment, and a comment cannot fail.
`scripts/parity/strat_core_parity.py` runs 874 cases through both languages; this
is what makes the result binding.

ONE DIVERGENCE WAS KNOWN AND QUARANTINED -- and it CLOSED 2026-09-05, when the
WickType range guard was decided (STRATEGY_WORKFLOW.md section 11 item 2). The
quarantine had been narrow on purpose:

    C#      if (range <= tickSize) return 0;
    Python  if total_range > 1e-8:   ... classify wicks ...

Measured: 24 of 309 wick cases disagreed, every one of them on a bar with range
<= 0.25, and nothing else in the core disagreed at all. It is reachable on real
NQ data, not only on synthetic input -- a one-tick bar that opens and closes at
its high has a lower-wick ratio of 1.0, so Python called it a HAMMER and C# called
it nothing. THE DECISION: adopt the C# rule. A one-tick bar has no wick structure
to read -- the open and close sit on tick boundaries, so the "wick ratio" is a
quantization artifact, always 0 or 1. Python now suppresses sub-tick bars too
(`taxonomy.classify_bar(tick_size=...)`, `classify_bars_df(tick_size=...)`) and
the parity harness passes the tick size to both sides. ALL 874 CASES NOW AGREE.

THE TESTS BELOW DO NOT ASSERT THAT A DIVERGENCE EXISTS, AND NOW NONE DOES. The
scope tests are kept because their value is the failing direction they still
guard: any NEW divergence, in any function, on any input, fails. The positive
tests pin the suppression itself on the Python side, so a revert of
`tick_size` handling goes red here rather than only in the parity run.
"""
import pytest

pytest.importorskip("numpy")

from scripts.parity import strat_core_parity as scp

TICK = 0.25


@pytest.fixture(scope="module")
def divergences():
    """Run the whole differential suite once and hand back the disagreements."""
    import os
    import tempfile

    cases = (scp.classify_cases() + scp.wick_cases() + scp.target_cases()
             + scp.entry_cases() + scp.ftfc_cases())
    tmp = tempfile.mkdtemp(prefix="stratcore_parity_test_")
    cases_csv = os.path.join(tmp, "cases.csv")
    out_csv = os.path.join(tmp, "cs.csv")
    scp.write_cases(cases_csv, cases)
    try:
        scp.run_csharp(cases_csv, out_csv)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        pytest.skip("StratCoreHarness unavailable (needs the dotnet SDK): %s" % exc)

    py = {c["id"]: scp.python_result(c) for c in cases}
    cs = scp.read_results(out_csv)
    rows = scp.compare(cases, py, cs)
    return rows


def test_the_harness_actually_ran_cases(divergences):
    """A suite that silently ran nothing would pass every assertion below."""
    assert len(divergences) > 800, len(divergences)
    fns = {r["fn"] for r in divergences}
    assert fns == {"classify", "wick", "targets", "entry", "ftfc"}, fns


def test_bar_classification_is_identical(divergences):
    bad = [r for r in divergences if r["fn"] == "classify" and not r["agree"]]
    assert not bad, _fmt(bad)


def test_measured_targets_are_identical(divergences):
    """The target/risk engine is the one that decides position sizing, and it is
    the one whose drift would be least visible in a summary metric."""
    bad = [r for r in divergences if r["fn"] == "targets" and not r["agree"]]
    assert not bad, _fmt(bad)


def test_session_gate_is_identical(divergences):
    bad = [r for r in divergences if r["fn"] == "entry" and not r["agree"]]
    assert not bad, _fmt(bad)


def test_ftfc_score_is_identical(divergences):
    bad = [r for r in divergences if r["fn"] == "ftfc" and not r["agree"]]
    assert not bad, _fmt(bad)


def test_the_only_divergence_is_wick_on_sub_tick_bars(divergences):
    """The quarantine. Narrow on purpose.

    Not "wick diverges" -- that would go red when someone FIXES it. This says
    where a divergence is allowed to be, so closing it keeps this green and
    opening a new one anywhere fails.
    """
    bad = [r for r in divergences if not r["agree"]]
    outside = [r for r in bad if r["fn"] != "wick"]
    assert not outside, (
        "a NEW divergence outside the known wick quarantine:\n" + _fmt(outside))

    wide = [r for r in bad if (r["inputs"][2] - r["inputs"][3]) > TICK + 1e-12]
    assert not wide, (
        "a wick divergence on a bar WIDER than one tick, which the known "
        "range-guard difference does not explain:\n" + _fmt(wide))


def test_the_quarantined_divergence_is_the_range_guard_and_nothing_else(divergences):
    """Pins the CAUSE, so a different sub-tick divergence is not absorbed.

    Kept from the quarantined era: if the divergence ever REOPENS, every case
    must still be one where C# suppressed (`range <= tickSize`). A case where
    C# returned a classification and Python returned 0 would be a DIFFERENT
    defect wearing the same shape.
    """
    bad = [r for r in divergences if not r["agree"] and r["fn"] == "wick"]
    for r in bad:
        assert "cs='0'" in r["detail"], (
            "a sub-tick wick divergence where C# did NOT suppress -- this is not "
            "the known range-guard difference:\n" + _fmt([r]))


# --------------------------------------------------------------------------- #
# The CLOSED decision, pinned on the Python side
# --------------------------------------------------------------------------- #

def test_python_suppresses_the_wick_on_a_sub_tick_bar():
    """The decision itself, on the Python side (C# always had it).

    The motivating case: a one-tick bar that opens and closes at its high has
    a lower-wick ratio of 1.0. Without the guard Python called that a HAMMER;
    with it, both sides return NONE. `tick_size=None` deliberately keeps the
    old behavior, so callers who cannot supply a tick size are not silently
    re-decided.
    """
    from scripts.libs_py.the_strat.taxonomy import ActionableWickType, classify_bar

    # The motivating case: a one-tick bar that OPENS AND CLOSES AT ITS HIGH.
    # lower wick = 10.25 - 10.0 = full range, ratio 1.0.
    o, c, h, l = 10.25, 10.25, 10.25, 10.0   # range == exactly one tick
    suppressed = classify_bar(h, l, h, l, open_price=o, close_price=c,
                              wick_threshold=0.65, tick_size=TICK)
    assert suppressed.wick_type == ActionableWickType.NONE

    legacy = classify_bar(h, l, h, l, open_price=o, close_price=c,
                          wick_threshold=0.65, tick_size=None)
    assert legacy.wick_type == ActionableWickType.HAMMER, (
        "tick_size=None must keep the pre-decision behavior; if this fails the "
        "guard has been made unconditional and callers that pass no tick size "
        "silently changed meaning")

    # The failing direction: a bar WIDER than one tick still classifies.
    # classify_bar(high, low, prev_high, prev_low, ...): h=17.0, l=7.0.
    wide = classify_bar(17.0, 7.0, 17.0, 7.0, open_price=16.5, close_price=17.0,
                        wick_threshold=0.65, tick_size=TICK)
    assert wide.wick_type == ActionableWickType.HAMMER


def test_classify_bars_df_suppresses_the_wick_when_given_a_tick_size():
    """The vectorized path carries the same decision, or the hunter and the
    single-bar paths would disagree with each other."""
    import numpy as np
    import pandas as pd

    from scripts.libs_py.the_strat.taxonomy import classify_bars_df

    df = pd.DataFrame({
        "open":   [10.25, 16.5],
        "high":   [10.25, 17.0],   # row 0: one tick wide, o=c=h (ratio 1.0); row 1: wide hammer
        "low":    [10.0, 7.0],
        "close":  [10.25, 17.0],
    })
    out = classify_bars_df(df, wick_threshold=0.65, tick_size=TICK)
    assert int(out["wick_type"].iloc[0]) == 0, (
        "a one-tick bar must carry no wick")
    assert int(out["wick_type"].iloc[1]) == 1, (
        "a wide hammer must still classify -- the guard is not a blanket zero")

    legacy = classify_bars_df(df, wick_threshold=0.65, tick_size=None)
    assert int(legacy["wick_type"].iloc[0]) == 1, (
        "tick_size=None must keep the pre-decision behavior")


def _fmt(rows):
    out = []
    for r in rows[:15]:
        out.append("  [{}] {}\n      inputs={} extra={!r}\n      {}".format(
            r["fn"], r["id"], r.get("inputs"), r.get("extra", ""), r["detail"]))
    if len(rows) > 15:
        out.append("  ... {} more".format(len(rows) - 15))
    return "\n".join(out)
