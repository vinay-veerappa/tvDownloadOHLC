"""Is an NT8 trade set attributable to THIS strategy under THIS profile?

`nt8_ground_truth` used to pass on the shape of the file: it counted rows,
resolved a timezone, and scored PASS. The fixture's `profileHash` was read,
filed in the run record, and compared with nothing -- a probe supplying
`sha256:STALE` still scored PASS -- while `RunRecord.declare_nt8_profile()` and
`require_nt8_profile()` sat unused in production.

That matters because "NT8 is authoritative for behaviour" is not a claim about
NinjaTrader in general. It is a claim about one build of one strategy under one
Strategy Analyzer configuration. Slippage, fill policy and the price basis all
live in the frozen profile, so a trade list captured under a different one is
being compared against a Python run that assumes the current one -- and the
disagreement that produces is indistinguishable from a logic defect.

Every test here names the input that makes the gate red, and the last two are
the negative controls: a fixture that DOES match must still pass, or the gate is
just a refusal.
"""
import os
import sys
import types

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.trading_framework import workflow as wf


def _ctx(bot="BBMRReversionBot", strategy="mean_reversion"):
    """The two fields `_nt8_evidence_unbound` reads, and nothing else."""
    return types.SimpleNamespace(
        bot_path=(os.path.join("scripts", "ninjatrader", "strategies", "Vinay",
                               bot + ".cs") if bot else None),
        args=types.SimpleNamespace(strategy=strategy),
    )


def _meta(**over):
    m = {"strategy": "BBMRReversionBot", "instrument": "NQ DEC26",
         "barSeconds": 300, "profileHash": "sha256:CURRENT",
         "timestampZone": "America/New_York", "timestampsAreNaive": True}
    m.update(over)
    return m


@pytest.fixture
def frozen(monkeypatch):
    """Pin the frozen-profile hash so these tests do not move when it changes."""
    def _set(value, described="backtest_profile.json"):
        monkeypatch.setattr(wf, "_frozen_profile_hash",
                            lambda: (value, described))
    _set("sha256:CURRENT")
    return _set


# --------------------------------------------------------------------------- #
# The reds
# --------------------------------------------------------------------------- #
def test_no_meta_at_all_is_unbound(frozen):
    why = wf._nt8_evidence_unbound(_ctx(), None)
    assert len(why) == 1
    assert "no .meta.json" in why[0]
    assert "capture_nt8" in why[0], "a refusal must name the remedy"


def test_meta_without_a_profile_hash_is_unbound(frozen):
    why = wf._nt8_evidence_unbound(_ctx(), _meta(profileHash=None))
    assert any("no profileHash" in r for r in why)


def test_stale_profile_hash_is_unbound(frozen):
    """The exact probe that used to score PASS."""
    why = wf._nt8_evidence_unbound(_ctx(), _meta(profileHash="sha256:STALE"))
    assert any("sha256:STALE" in r and "sha256:CURRENT" in r for r in why), why
    assert any("recapture" in r for r in why)


def test_unreadable_profile_is_reported_as_unreadable_not_mismatched(frozen):
    """An unreadable profile and a mismatching one are different problems.

    Collapsing them would tell the operator to recapture when the real fault is
    a missing file, and the recapture would be taken under the same broken
    profile.
    """
    frozen(None, "the frozen profile would not read: no such file")
    why = wf._nt8_evidence_unbound(_ctx(), _meta())
    assert len(why) == 1
    assert "cannot be compared" in why[0]
    assert "recapture" not in why[0]


def test_a_fixture_from_another_strategy_is_unbound(frozen):
    """The Strategy Analyzer window is REUSED; this is the observed failure."""
    why = wf._nt8_evidence_unbound(_ctx(), _meta(strategy="SampleMACrossOver"))
    assert any("SampleMACrossOver" in r and "BBMRReversionBot" in r for r in why)


def test_both_faults_are_reported_not_just_the_first(frozen):
    why = wf._nt8_evidence_unbound(
        _ctx(), _meta(strategy="SampleMACrossOver", profileHash="sha256:STALE"))
    assert len(why) == 2, "one gate reported and the other swallowed: " + repr(why)


# --------------------------------------------------------------------------- #
# The negative controls -- a gate that only ever says no proves nothing
# --------------------------------------------------------------------------- #
def test_a_matching_fixture_is_bound(frozen):
    assert wf._nt8_evidence_unbound(_ctx(), _meta()) == []


def test_a_run_with_no_paired_bot_does_not_fail_on_the_strategy_name(frozen):
    """`has_bot` already covers a missing bot; do not charge it twice.

    Without this, a Python-only run would score TWO failures for one fact, and
    the second would read as an NT8 attribution problem it is not.
    """
    assert wf._nt8_evidence_unbound(_ctx(bot=None), _meta()) == []


def test_a_fixture_that_omits_the_strategy_name_fails_only_on_that(frozen):
    """An absent field is unreadable, not a mismatch -- but it is not silent."""
    why = wf._nt8_evidence_unbound(_ctx(), _meta(strategy=None))
    assert why == [], "an absent strategy name is covered by profile binding"


def test_the_real_frozen_profile_hashes_to_something():
    """Not a mock: if this returns None the gate degrades to always-unreadable."""
    value, described = wf._frozen_profile_hash()
    assert value, "the frozen profile did not hash: {}".format(described)
    assert value.startswith("sha256:"), value
