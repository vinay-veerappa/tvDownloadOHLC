"""ONE document decides the execution policy.

Measured 2026-09-05, a single sanctioned run carried FOUR of them:

  * `config/trading_defaults.json`  -- 1 contract, 1 tick, $0.62, no entry
    cut-off, no daily cap, 15:45 flatten. The one section 1.3 calls canonical.
  * `NT8ParityBacktester.__init__`  -- 2 contracts, 0 ticks, $1.40, 3 trades/day.
  * `run_backtest.py`               -- 09:45-15:30 entries, lunch filtered, 15:55.
  * `NT8ParityEngine`'s signatures  -- the same four literals again, one layer down.

None of the four cited the others, so the canonical one was the only one that
did not decide anything. Two of the disagreements are not cosmetic:
`filter_lunch=True` deletes the NY_LUNCH session that `sessions.reportPerSession`
exists to MEASURE, and a 15:30 cut-off forbids the NY_PM setup BBMRReversionBot
is built around -- the case `lastEntryEt: null` was written for.

This file pins the resolution in both directions. The reds are: a literal
reappearing in the sanctioned path, a policy field drifting from the document,
and a flatten past ADR-020's hard exit. The greens are: a caller who states a
value still gets it, and the engine's own defaults are unreachable from here.
"""
import inspect
import json
import os
import re
import sys

import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.trading_framework.config import defaults as D
from scripts.trading_framework.core.nt8_parity_backtester import NT8ParityBacktester

DOC = os.path.join(PROJECT_ROOT, "scripts", "trading_framework", "config",
                   "trading_defaults.json")

#: ONE pattern, used by the gate AND by its negative control below. Written as a
#: constant because the first version of the control found a hole in the first
#: version of the gate -- an ANNOTATED default (`contracts: int = 2`) did not
#: match, which is exactly the form the second table was written in. Two copies
#: of a regex drift, and the copy that drifts is always the one doing the work.
BANNED_LITERAL = re.compile(
    r"""^\s*(?:'|")?
        # Longest first: `commission` would otherwise consume the head of
        # `commission_per_contract_rt` and then fail on the `_`, so the
        # signature default that actually shipped went unmatched.
        (earliest_entry_hhmm|latest_entry_hhmm|flatten_hhmm|filter_lunch
         |commission_per_contract_rt|commission|contracts|slippage_ticks)
        (?:'|")?
        (?::\s*(?:int|float|bool)\s*)?      # an annotated default is still a default
        \s*[:=]\s*
        (?:945|1530|1555|1545|True|2|0\.0|1\.40|1\.4)\b""",
    re.VERBOSE)


@pytest.fixture(scope="module")
def doc():
    with open(DOC, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# The policy is the document
# --------------------------------------------------------------------------- #
def test_every_execution_field_traces_to_the_frozen_document(doc):
    p = D.execution_policy()
    assert p["contracts"] == doc["execution"]["defaultContracts"]
    assert p["commission"] == doc["execution"]["commissionPerContractRoundTrip"]
    assert p["slippage_ticks"] == doc["execution"]["slippageTicks"]
    assert p["max_trades_per_day"] == doc["risk"]["maxTradesPerDay"]


def test_a_null_entry_cutoff_means_unrestricted_not_missing():
    """`lastEntryEt: null` is a DECISION -- see the risk block's own _doc.

    The engine compares `earliest <= hm <= latest` with integers, so "no
    restriction" has to be spelled as the widest window. Spelling it as a
    missing key would have fallen through to the 09:45-15:30 literal, which is
    how the restriction survived being deleted from the document.
    """
    p = D.execution_policy()
    assert p["earliest_entry_hhmm"] == 0
    assert p["latest_entry_hhmm"] == 2359
    for hm in (30, 945, 1200, 1345, 1559, 2300):
        assert p["earliest_entry_hhmm"] <= hm <= p["latest_entry_hhmm"]


def test_the_lunch_session_is_reported_on_not_filtered_out(doc):
    """Answering "is lunch worth trading?" by refusing to trade it is not an answer."""
    assert D.execution_policy()["filter_lunch"] is False
    assert any(w["name"] == "NY_LUNCH" for w in doc["sessions"]["windows"]), \
        "the session the filter used to delete is not even in the partition"


def test_a_null_cap_is_reported_as_null_and_only_converted_at_the_engine():
    """"capped at 1000000000" and "uncapped" read differently and one is false."""
    p = D.execution_policy()
    assert p["max_trades_per_day"] is None
    assert D.engine_max_trades_per_day(None) == D.UNCAPPED
    assert D.engine_max_trades_per_day(3) == 3


def test_the_flatten_time_cannot_be_after_the_adr020_hard_exit(monkeypatch):
    """ADR-020 has no exemptions, and `rthHardExitEt` is not in `overridable`."""
    real = D.load_trading_defaults()
    bad = json.loads(json.dumps(real))
    bad["risk"]["flattenByEt"] = "16:30"
    monkeypatch.setattr(D, "load_trading_defaults", lambda: bad)
    with pytest.raises(ValueError, match="ADR-020"):
        D.execution_policy()


def test_an_override_of_something_that_is_not_execution_policy_is_refused():
    with pytest.raises(ValueError, match="not part of the execution policy"):
        D.execution_policy({"rthHardExitEt": "17:00"})


def test_an_override_is_applied_and_named_in_the_source():
    p = D.execution_policy({"contracts": 3})
    assert p["contracts"] == 3
    assert "override" in p["_source"] and "contracts" in p["_source"]


# --------------------------------------------------------------------------- #
# The backtester lands on the document, not on its own signature
# --------------------------------------------------------------------------- #
def test_a_backtester_that_was_told_nothing_gets_the_frozen_values():
    b = NT8ParityBacktester()
    p = D.execution_policy()
    assert b.contracts == p["contracts"] == 1
    assert b.commission == p["commission"] == 0.62
    assert b.slippage_ticks == p["slippage_ticks"] == 1.0
    assert b.max_trades_per_day == D.UNCAPPED


def test_a_caller_who_states_a_value_still_gets_it():
    """The negative control. Sourcing from a document must not become ignoring
    the caller -- that would be the same defect pointing the other way."""
    b = NT8ParityBacktester(contracts=4, commission_per_contract_rt=2.05,
                            slippage_ticks=0.0, max_trades_per_day=3)
    assert (b.contracts, b.commission, b.slippage_ticks, b.max_trades_per_day) \
        == (4, 2.05, 0.0, 3)


def test_no_execution_literal_survives_in_the_sanctioned_path():
    """A scan, so a literal cannot creep back in beside the resolved value.

    Matched on the ASSIGNMENT, not on the bare number: `945` appears in prose in
    both files describing the defect, and a scan that could not tell a comment
    from an argument would have to be deleted the first time someone documented
    what they fixed.
    """
    offenders = []
    for rel in ("scripts/trading_framework/run_backtest.py",
                "scripts/trading_framework/core/nt8_parity_backtester.py"):
        path = os.path.join(PROJECT_ROOT, *rel.split("/"))
        with open(path, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                if BANNED_LITERAL.search(line):
                    offenders.append("{}:{}: {}".format(rel, n, line.strip()))
    assert not offenders, "an execution literal is back:\n" + "\n".join(offenders)


def test_that_scan_can_actually_find_one():
    """A gate that cannot go red is not a gate.

    Every probe here is a line that ACTUALLY EXISTED in one of the four tables.
    The second one is why `BANNED_LITERAL` had to learn about annotations: an
    earlier version of this scan reported clean over a file that still declared
    `contracts: int = 2`.
    """
    for probe in ("    'earliest_entry_hhmm': 945,",
                  "        contracts: int = 2,",
                  '    "filter_lunch": True,',
                  "        slippage_ticks: float = 0.0,",
                  "        commission_per_contract_rt: float = 1.40,",
                  "                'flatten_hhmm': 1555,"):
        assert BANNED_LITERAL.search(probe), probe


@pytest.mark.parametrize("probe", [
    "    # `.get(\"earliest_entry_hhmm\", 945)`, `1530`, `1555`, `True` -- a THIRD",
    "    contracts = policy['contracts']",
    "        flatten_hhmm=policy['flatten_hhmm'],",
    "    max_consecutive_losers: int = 2,",
])
def test_the_scan_does_not_fire_on_prose_or_on_the_fix(probe):
    """The other half of a detector: what must it NOT match?

    A scan that fires on the comment describing the defect makes documenting a
    fix impossible, and one that fires on `max_consecutive_losers: int = 2`
    would be flagging a field that is not part of the execution policy at all.
    """
    assert not BANNED_LITERAL.search(probe), probe


def test_the_sanctioned_path_never_reaches_the_engines_own_defaults():
    """`NT8ParityEngine`'s signatures still read 945/1530/1555/True.

    Six of them, and several frozen research runners call it directly, so they
    stay. What must hold is that the SANCTIONED path passes all four every time
    -- otherwise the fix above is one `.get()` away from being undone.
    """
    src = inspect.getsource(NT8ParityBacktester.run)
    assert src.count("**_entry,") == 2, \
        "both engine call sites must forward the resolved entry window"
    assert "risk_params.get(\"earliest_entry_hhmm\"" not in src


def test_the_resolved_window_actually_reaches_the_engine():
    """Not a source scan: call it and read what the engine was handed."""
    seen = {}

    class Spy(NT8ParityBacktester):
        pass

    import scripts.trading_framework.core.nt8_parity_backtester as mod

    class FakeEngine:
        def __init__(self, **kw):
            seen["ctor"] = kw

        def simulate(self, **kw):
            seen["sim"] = kw
            return pd.DataFrame()

    real = mod.NT8ParityEngine
    mod.NT8ParityEngine = FakeEngine
    try:
        idx = pd.date_range("2026-06-01 09:30", periods=8, freq="5min", tz="UTC")
        data = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                             "close": 100.5}, index=idx)
        Spy().run(pd.Series(0, index=idx), data, {"ticker": "NQ1"})
    finally:
        mod.NT8ParityEngine = real

    p = D.execution_policy()
    assert seen["sim"]["earliest_entry_hhmm"] == p["earliest_entry_hhmm"] == 0
    assert seen["sim"]["latest_entry_hhmm"] == p["latest_entry_hhmm"] == 2359
    assert seen["sim"]["flatten_hhmm"] == p["flatten_hhmm"] == 1545
    assert seen["sim"]["filter_lunch"] is False
    assert seen["ctor"]["contracts"] == 1
    assert seen["ctor"]["commission_per_contract_rt"] == 0.62
    assert seen["ctor"]["slippage_ticks"] == 1.0
