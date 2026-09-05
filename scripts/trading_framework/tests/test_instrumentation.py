"""Instrumentation is the DEFAULT, and the exceptions are a shrinking list.

Section 5.5 and 5.7. The rule these enforce: a strategy reports the criteria it
evaluated, on both sides, and anything that does not is a named line in
`uninstrumented.py` rather than a silence.

WHY THE PYTHON CHECK IS BEHAVIOURAL. It calls `hunt()` on synthetic bars and
looks at `last_decisions`. A source scan for `GateRecorder` would pass for a
hunter that imports it and never calls it -- which is the shape that has beaten
source gates in this project repeatedly. It costs a second per strategy.

WHY THE C# CHECK IS A SOURCE SCAN, AND WHY THAT IS SOUND HERE. `GovernedStrategy`
SEALS `CheckForSignal()` and computes the verdict from the declared gates, so
DERIVING from it is the whole condition: a subclass has no path by which it can
act on a criterion the log does not carry. The scan proves the derivation; the
sealing proves the rest. That is different from asserting a call is present,
which a comment or a dead branch would satisfy.
"""

import pathlib
import re

import numpy as np
import pandas as pd
import pytest

from scripts.trading_framework.reporting.decision_log import (
    COLUMNS, contradictions, gate_roster,
)
from scripts.trading_framework.strategies.registry import (
    STRATEGY_FACTORY_REGISTRY, get_strategy,
)
from scripts.trading_framework.tests.uninstrumented import (
    LEGACY_BOT_BASES, UNINSTRUMENTED_BOTS, UNINSTRUMENTED_HUNTERS,
)

REPO = pathlib.Path(__file__).resolve().parents[3]
BOT_ROOT = REPO / "scripts" / "ninjatrader" / "strategies"
SHARED = REPO / "scripts" / "ninjatrader" / "shared"
GOVERNED = SHARED / "GovernedStrategy.cs"


def _bars(n=900, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-02 00:00", periods=n, freq="1min",
                        tz="America/New_York")
    px = 20000 + np.cumsum(rng.normal(0, 3, n))
    return pd.DataFrame({"open": px, "high": px + 3, "low": px - 3, "close": px,
                         "volume": rng.integers(100, 900, n)}, index=idx)


def bot_files():
    return sorted((p for p in BOT_ROOT.rglob("*.cs")
                   if p.name.endswith("Bot.cs") or p.name.endswith("Base.cs")),
                  key=lambda p: p.as_posix())


def base_of(path: pathlib.Path):
    m = re.search(r"class\s+\w+\s*:\s*(\w+)",
                  path.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


# --------------------------------------------------------------------------- #
# The inventories are not vacuous
# --------------------------------------------------------------------------- #

def test_the_registry_and_the_bot_scan_are_not_empty():
    """Negative control. An empty scan makes every assertion below pass."""
    assert len(STRATEGY_FACTORY_REGISTRY) >= 10
    assert len(bot_files()) >= 10


def test_every_inventoried_hunter_is_a_real_registry_key():
    """A typo in the list is an exemption for a strategy that does not exist,
    and it silently un-exempts the one that was meant."""
    unknown = sorted(UNINSTRUMENTED_HUNTERS - set(STRATEGY_FACTORY_REGISTRY))
    assert not unknown, (
        "these keys are on the uninstrumented list but not in the registry: {}. "
        "Either the key was renamed or the strategy is gone -- in both cases the "
        "line is now an exemption for nothing.".format(unknown))


def test_every_inventoried_bot_still_exists():
    gone = sorted(r for r in UNINSTRUMENTED_BOTS if not (REPO / r).exists())
    assert not gone, "remove these lines; the files are gone: {}".format(gone)


# --------------------------------------------------------------------------- #
# Python: the default is instrumented
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "key", sorted(set(STRATEGY_FACTORY_REGISTRY) - UNINSTRUMENTED_HUNTERS))
def test_an_instrumented_hunter_emits_a_usable_decision_log(key):
    """BEHAVIOURAL: run it and look. An import of `GateRecorder` that is never
    called would pass a source scan."""
    s = get_strategy(key, "NQ1")
    s.generate_signals(_bars(), {})
    d = s.last_decisions
    assert d is not None, (
        "{} is not on the uninstrumented list but emitted no decision log. Set "
        "`self.last_decisions` from a GateRecorder (section 5.5), or -- if this "
        "is deliberate and temporary -- add the key to uninstrumented.py WITH a "
        "reason.".format(key))
    assert list(d.columns) == list(COLUMNS), sorted(set(COLUMNS) - set(d.columns))
    assert contradictions(d).empty, (
        "{}'s log contradicts itself: an ENTRY carrying a failed gate, or a "
        "REJECTED carrying none. Such a log looks like evidence and is not."
        .format(key))


@pytest.mark.parametrize("key", sorted(UNINSTRUMENTED_HUNTERS))
def test_an_uninstrumented_hunter_that_now_reports_loses_its_line(key):
    """The list may only SHRINK. Left alone it becomes a permanent exemption
    that nobody re-reads, which is how an inventory stops meaning anything."""
    try:
        s = get_strategy(key, "NQ1")
        s.generate_signals(_bars(), {})
        emitted = s.last_decisions is not None
    except Exception:
        # A hunter that raises on synthetic bars is a separate defect (section 11
        # item 7 records one). Not this test's business, and failing here would
        # blame the wrong thing.
        pytest.skip("{} raised on synthetic bars".format(key))
    assert not emitted, (
        "{} now emits a decision log -- remove it from UNINSTRUMENTED_HUNTERS in "
        "uninstrumented.py.".format(key))


def test_the_reference_hunter_is_not_on_the_list():
    """`mean_reversion` is the worked example section 5.5 points at. If it ever
    lands on the list, the documentation references a strategy that does not do
    what the documentation says."""
    assert "mean_reversion" not in UNINSTRUMENTED_HUNTERS


def test_at_least_one_hunter_is_instrumented():
    """Otherwise the parametrised test above has an empty argument list and the
    whole file passes while proving nothing."""
    assert set(STRATEGY_FACTORY_REGISTRY) - UNINSTRUMENTED_HUNTERS


# --------------------------------------------------------------------------- #
# C#: the base class is the mechanism
# --------------------------------------------------------------------------- #

def test_the_governed_base_exists_and_is_tracked():
    assert GOVERNED.exists()
    import subprocess
    rel = GOVERNED.relative_to(REPO).as_posix()
    p = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                       cwd=REPO, capture_output=True)
    assert p.returncode == 0, "{} is not tracked".format(rel)


def test_the_governed_base_seals_the_signal_hook():
    """THE LOAD-BEARING ASSERTION. `RiskManagerBase` asks its subclass exactly
    one question -- `CheckForSignal()`. Sealing it is what makes the log
    impossible to diverge from: the verdict is COMPUTED from the declared gates
    rather than supplied alongside them, so a criterion the log does not carry
    cannot influence a trade. Unseal it and the whole design degrades to a
    helper the bot may ignore, which is the pattern B1-B6 proves does not hold.
    """
    text = GOVERNED.read_text(encoding="utf-8")
    assert re.search(r"protected\s+sealed\s+override\s+int\s+CheckForSignal\s*\(",
                     text), "CheckForSignal must be `sealed override`"
    assert re.search(r"protected\s+abstract\s+void\s+OnEvaluate\s*\(\s*SetupEvaluation",
                     text), "the subclass hook must be `OnEvaluate(SetupEvaluation)`"


def test_the_mandated_structure_cannot_place_an_order():
    """`SetupEvaluation` DECLARES. If it could enter, exit or move a stop, a bot
    could act inside it and skip the verdict entirely -- so the absence of those
    verbs is the guarantee, not a style preference."""
    text = GOVERNED.read_text(encoding="utf-8")
    body = text[text.index("public sealed class SetupEvaluation"):]
    body = body[:body.index("public abstract class GovernedStrategy")]
    for verb in ("EnterLong", "EnterShort", "ExitLong", "ExitShort",
                 "SetStopLoss", "SetProfitTarget", "StreamWriter"):
        assert verb not in body, (
            "SetupEvaluation must not be able to {} -- it declares, it does not "
            "act".format(verb))


def test_the_governed_base_applies_the_hard_exit_after_the_bot_speaks():
    """Order matters. The bot's own defaults run in the middle; ADR-020's clamp
    must come AFTER, or a bot that sets a later flatten time is trusted."""
    text = GOVERNED.read_text(encoding="utf-8")
    i_bot = text.index("OnStrategyDefaults();")
    i_clamp = text.index("TradingDefaults.RthHardExit")
    assert i_clamp > i_bot, (
        "the ADR-020 clamp must be applied after OnStrategyDefaults(), otherwise "
        "a bot can widen it afterwards")


def test_the_governed_base_treats_a_null_cap_as_nolimit():
    """0 reads as "no trades allowed" to RiskManagerBase's `>=` comparison, and
    int.MaxValue vanishes into arithmetic."""
    text = GOVERNED.read_text(encoding="utf-8")
    assert "TradingDefaults.NoLimit" in text
    assert re.search(r"MaxTradesPerDay\s*!=\s*TradingDefaults\.NoLimit", text), (
        "a null cap must not be assigned at all, rather than assigned as 0")


def test_the_governed_base_names_entries_uniquely():
    """`RiskManagerBase.GetSignalName` returns `<Strategy>_Long` for every long
    entry ever taken; that string is the fill's only join key back to the
    decision that produced it (was ticket B7)."""
    text = GOVERNED.read_text(encoding="utf-8")
    assert re.search(r"protected\s+override\s+string\s+GetSignalName", text)
    assert "entrySeq++" in text


def test_the_governed_base_records_the_frameworks_own_refusals():
    """A bot stopped by a framework rule must appear in the roster rather than
    vanish -- the C# half of the funnel gap section 11 item 13 records."""
    text = GOVERNED.read_text(encoding="utf-8")
    assert re.search(r"protected\s+override\s+void\s+OnEntryBlocked", text), (
        "CanEnterTrade's nine refusals reach the log only through this override")
    for gate in ("GateLastEntry", "GateHardExit"):
        assert "TradingDefaults.{}".format(gate) in text, gate


def test_the_governance_gate_names_come_from_the_frozen_document():
    """A literal here and a literal in Python would split one gate into two rows
    that never compare, and nothing would fail."""
    from scripts.trading_framework.config.defaults import load_trading_defaults
    gates = load_trading_defaults()["governance"]["gates"]
    cs = (SHARED / "TradingDefaults.cs").read_text(encoding="utf-8")
    for key, name in gates.items():
        const = "Gate{}".format(key[0].upper() + key[1:])
        assert 'public const string {} = "{}";'.format(const, name) in cs, (
            "{} = {!r} is in trading_defaults.json but not generated into "
            "TradingDefaults.cs".format(const, name))
    assert "GovernanceGates" in cs
    gov = GOVERNED.read_text(encoding="utf-8")
    assert 'Gate("' not in gov.replace('Gate("' + "name", ""), (
        "GovernedStrategy must reference TradingDefaults.Gate* rather than "
        "writing a governance gate name as a literal")


@pytest.mark.parametrize("rel", sorted(UNINSTRUMENTED_BOTS))
def test_an_uninstrumented_bot_that_migrated_loses_its_line(rel):
    """Shrink-only, same as the hunter list."""
    base = base_of(REPO / rel)
    assert base != "GovernedStrategy", (
        "{} now derives from GovernedStrategy -- remove it from "
        "UNINSTRUMENTED_BOTS in uninstrumented.py and close its BOT_FIX_BACKLOG "
        "ticket.".format(rel))
    assert base in LEGACY_BOT_BASES, (
        "{} derives from {!r}, which is neither GovernedStrategy nor a known "
        "legacy base. A base nobody has heard of is a different problem from "
        "'not yet migrated' and needs a different answer.".format(rel, base))


def test_a_new_bot_must_derive_from_the_governed_base():
    """The rule that makes instrumentation the DEFAULT: there is nowhere to add
    a new bot to the exemption list without saying so in the same commit."""
    new = {}
    for p in bot_files():
        rel = p.relative_to(REPO).as_posix()
        if rel in UNINSTRUMENTED_BOTS:
            continue
        base = base_of(p)
        if base != "GovernedStrategy":
            new[rel] = base
    assert not new, (
        "these bots derive from something other than GovernedStrategy and are "
        "not on the recorded exception list: {}. A new bot inherits "
        "GovernedStrategy (section 5.7); it gets the decision log, the frozen "
        "defaults and unique entry names without writing any of it."
        .format(new))
