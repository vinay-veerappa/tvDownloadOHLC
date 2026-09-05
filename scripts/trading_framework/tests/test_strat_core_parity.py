"""The Strat shared core must mean the same thing in C# and in Python.

`scripts/ninjatrader/shared/StratCore.cs` opens by declaring itself the C# mirror
of `scripts/libs_py/the_strat/` and says "Rule changes go here AND in Python
together - never in only one side." That is a comment, and a comment cannot fail.
`scripts/parity/strat_core_parity.py` runs 874 cases through both languages; this
is what makes the result binding.

ONE DIVERGENCE IS KNOWN AND QUARANTINED, and the quarantine is deliberately
narrow. `WickType` suppresses hammer/shooter on a bar whose range is at most one
tick:

    C#      if (range <= tickSize) return 0;
    Python  if total_range > 1e-8:   ... classify wicks ...

Measured: 24 of 309 wick cases disagree, every one of them on a bar with range
<= 0.25, and nothing else in the core disagrees at all. It is reachable on real
NQ data, not only on synthetic input -- a one-tick bar that opens and closes at
its high has a lower-wick ratio of 1.0, so Python calls it a HAMMER and C# calls
it nothing.

THE TESTS BELOW DO NOT ASSERT THAT THE DIVERGENCE EXISTS. Asserting a defect is
present is how a wrong test starts enforcing itself: someone fixes the rule, this
goes red, and the fix gets reverted to make it green. They assert its SCOPE
instead --

    * nothing outside `wick` may diverge, at all;
    * a `wick` divergence may only occur on a bar with range <= tick.

so closing the divergence leaves these green, while ANY new divergence, in any
function, on any other input, fails.

WHICH SIDE IS RIGHT IS A DECISION, NOT A BUG FIX, which is why it is not made
here. A one-tick bar has no wick structure to read: on a 0.25-tick instrument the
open and close must both sit on tick boundaries, so the "wick ratio" of such a
bar is a quantization artifact, always 0 or 1. Suppressing it (the C# rule) looks
right, and adopting it would CHANGE existing Python backtest results for the_strat
-- which is exactly the sort of change that should land through a recorded run
rather than quietly.
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

    Every quarantined case must be one where C# returned 0 (suppressed by
    `range <= tickSize`) while Python returned a real classification. A case where
    C# returned a classification and Python returned 0 would be a DIFFERENT
    defect wearing the same shape.
    """
    bad = [r for r in divergences if not r["agree"] and r["fn"] == "wick"]
    for r in bad:
        assert "cs='0'" in r["detail"], (
            "a sub-tick wick divergence where C# did NOT suppress -- this is not "
            "the known range-guard difference:\n" + _fmt([r]))


def _fmt(rows):
    out = []
    for r in rows[:15]:
        out.append("  [{}] {}\n      inputs={} extra={!r}\n      {}".format(
            r["fn"], r["id"], r.get("inputs"), r.get("extra", ""), r["detail"]))
    if len(rows) > 15:
        out.append("  ... {} more".format(len(rows) - 15))
    return "\n".join(out)
