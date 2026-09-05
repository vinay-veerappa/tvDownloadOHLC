"""The C# side of the frozen defaults (STRATEGY_WORKFLOW.md section 1.3).

Two jobs:

  1. `TradingDefaults.cs` is GENERATED and must match `trading_defaults.json`.
     A JSON edit that never reached C# is the drift the generator exists to stop,
     and it is invisible on the Python side because every Python test still
     passes.

  2. A bot may not set an execution default silently. Measured 2026-09-05:
     twelve bots, FIVE different flatten times and SIX different daily trade
     caps, every one hand-set, none compared to the Python engine that predicts
     its trades.

     Two of those fields are legitimately per-strategy -- a NY_PM setup must
     enter after 14:30 -- so they are `overridable` in the document and the
     spread is recorded in `known_bot_divergences.py`. ONE field is not:
     ADR-020's 16:00 hard exit. `BBMRReversionBot` flattened at 16:15, which
     was FIXED rather than inventoried. Its 99-trade cap against the Python
     side's 3 remains, and is why that pair is not yet comparable.
"""

import pathlib
import re
import subprocess
import sys

import pytest

from scripts.trading_framework.config.defaults import load_trading_defaults
from scripts.trading_framework.tests.known_bot_divergences import (
    KNOWN_DIVERGENCES, RTH_HARD_EXIT,
)

REPO = pathlib.Path(__file__).resolve().parents[3]
GENERATED = REPO / "scripts" / "ninjatrader" / "shared" / "TradingDefaults.cs"
BOT_ROOT = REPO / "scripts" / "ninjatrader" / "strategies"

_INT_FIELD = "{}\\s*=\\s*(\\d+)"
FIELDS = ("FlattenBy", "MaxTradesPerDay", "LatestEntry")


def _hhmm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 100 + int(m)


def bot_files():
    return sorted(
        [p for p in BOT_ROOT.rglob("*.cs")
         if p.name.endswith("Bot.cs") or p.name.endswith("Base.cs")],
        key=lambda p: p.as_posix())


def declared(path: pathlib.Path):
    """(FlattenBy, MaxTradesPerDay, LatestEntry) as the file declares them."""
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for f in FIELDS:
        m = re.search(_INT_FIELD.format(f), text)
        out.append(int(m.group(1)) if m else None)
    return tuple(out)


# --------------------------------------------------------------------------- #
# 1. The generated file
# --------------------------------------------------------------------------- #

def test_the_generated_cs_matches_the_frozen_json():
    """A JSON edit that never reached C# fails HERE, not in production."""
    p = subprocess.run(
        [sys.executable, "scripts/utils/generate_trading_defaults.py", "--check"],
        cwd=REPO, capture_output=True, text=True)
    assert p.returncode == 0, (p.stdout + p.stderr).strip()


def test_the_generated_cs_carries_the_frozen_risk_numbers():
    """Parse the C# BACK and compare, so the generator cannot lie about itself."""
    risk = load_trading_defaults()["risk"]
    text = GENERATED.read_text(encoding="utf-8")
    for field, want in (("FlattenBy", _hhmm(risk["flattenByEt"])),
                        ("RthHardExit", _hhmm(risk["rthHardExitEt"]))):
        m = re.search(r"const int\s+" + field + r"\s*=\s*(\d+)", text)
        assert m, field
        assert int(m.group(1)) == want, (field, m.group(1), want)


def test_an_analysis_derived_field_is_emitted_as_nolimit_not_zero():
    """A null cap must not become 0.

    0 reads as "no trades allowed" to any caller comparing with >=, and
    int.MaxValue disappears into arithmetic. -1 behind a named constant is the
    only form that cannot be mistaken for a limit.
    """
    risk = load_trading_defaults()["risk"]
    text = GENERATED.read_text(encoding="utf-8")
    assert "public const int    NoLimit = -1;" in text
    for field in ("MaxTradesPerDay", "MaxTradesPerSession", "LastEntry"):
        m = re.search(r"const int\s+" + field + r"\s*=\s*(\S+?);", text)
        assert m, field
        assert m.group(1) == "NoLimit", (field, m.group(1))
    assert risk["maxTradesPerDay"] is None
    assert risk["lastEntryEt"] is None


def test_the_generated_cs_refuses_an_unknown_instrument():
    """The C# lookup must throw, matching resolve_instrument on the Python side."""
    text = GENERATED.read_text(encoding="utf-8")
    assert "throw new System.ArgumentException" in text
    assert "unknown instrument" in text
    # and it must not carry a default case that RETURNS a number
    assert not re.search(r"default:\s*\n\s*return", text)


def test_the_generated_cs_covers_the_data_tickers_the_workflow_accepts():
    text = GENERATED.read_text(encoding="utf-8")
    for key in ("NQ1", "ES1", "MNQ", "MES", "NQ", "ES"):
        assert '"{}"'.format(key) in text, key


def test_the_generated_cs_sessions_match_the_partition():
    text = GENERATED.read_text(encoding="utf-8")
    for w in load_trading_defaults()["sessions"]["windows"]:
        assert '"{}"'.format(w["name"]) in text, w["name"]


def test_the_generated_file_is_tracked_by_git():
    rel = GENERATED.relative_to(REPO).as_posix()
    p = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                       cwd=REPO, capture_output=True)
    assert p.returncode == 0, "{} is not tracked".format(rel)


# --------------------------------------------------------------------------- #
# 2. The bots
# --------------------------------------------------------------------------- #

def test_the_bot_scan_finds_bots():
    """Negative control: an empty scan makes every assertion below vacuous."""
    files = bot_files()
    assert len(files) >= 10, [p.name for p in files]
    assert any(declared(p) != (None, None, None) for p in files)


def test_no_bot_exits_later_than_the_adr_020_hard_limit():
    """NOT an inventory question. A position open past 16:00 ET is a prop-firm
    liquidation risk, so this fails whether or not the bot is a known divergence.
    """
    late = {}
    for p in bot_files():
        flatten, _mx, latest = declared(p)
        for label, v in (("FlattenBy", flatten), ("LatestEntry", latest)):
            if v is not None and v > RTH_HARD_EXIT:
                late.setdefault(p.relative_to(REPO).as_posix(), []).append(
                    "{}={}".format(label, v))
    assert not late, (
        "ADR-020 caps an intraday exit at {}: {}".format(RTH_HARD_EXIT, late))


def test_no_new_bot_sets_a_flatten_time_outside_the_inventory():
    """ONLY `flattenByEt` is compared.

    `maxTradesPerDay` and `lastEntryEt` are `analysisDerived`: an entry may
    happen at any time, and a cap is an OUTPUT of reporting/trade_ordinal.py.
    Policing them here would have forbidden BBMRReversionBot's deliberate NY_PM
    window, which is a legitimate setup and not a defect.
    """
    frozen_flatten = _hhmm(load_trading_defaults()["risk"]["flattenByEt"])
    new = {}
    for p in bot_files():
        rel = p.relative_to(REPO).as_posix()
        flatten, _mx, _le = declared(p)
        if flatten is None:
            continue                     # inherits
        if rel in KNOWN_DIVERGENCES:
            continue                     # covered by the drift test below
        if flatten != frozen_flatten:
            new[rel] = flatten
    assert not new, (
        "these bots set their own FlattenBy (frozen: {}) without a recorded "
        "reason: {}. Prefer TradingDefaults.FlattenBy. If the strategy genuinely "
        "needs a different one, add it to known_bot_divergences.py AND file it in "
        "docs/architecture/BOT_FIX_BACKLOG.md so it is worked, not just tolerated."
        .format(frozen_flatten, new))


def test_the_invariant_overridable_and_derived_split_lives_in_the_document():
    """Two corrections to my own first version, both pinned here.

    1. `lastEntryEt` was frozen at 14:30, which would forbid a deliberate NY_PM
       setup. An entry may happen at ANY time; reporting is per session and the
       decision of when a bot should run comes FROM those results.
    2. `maxTradesPerDay` was frozen at 3 with no recorded basis. A cap is an
       OUTPUT of the trade-ordinal analysis.

    The ADR-020 hard exit is neither overridable nor derived, ever.
    """
    risk = load_trading_defaults()["risk"]
    assert set(risk["overridable"]) == {"flattenByEt"}
    assert set(risk["analysisDerived"]) == {
        "maxTradesPerDay", "maxTradesPerSession", "lastEntryEt"}
    assert "rthHardExitEt" not in risk["overridable"], (
        "the ADR-020 hard exit is a safety limit and must never be overridable")
    assert "rthHardExitEt" not in risk["analysisDerived"]
    assert risk["rthHardExitEt"] == "16:00"


def test_a_known_divergence_has_not_moved_further_away():
    """A recorded value may only change by becoming the frozen one."""
    drifted = {}
    for rel, expected in KNOWN_DIVERGENCES.items():
        p = REPO / rel
        if not p.exists():
            continue                     # covered by the staleness test
        got = declared(p)
        if got != tuple(expected):
            drifted[rel] = {"recorded": tuple(expected), "now": got}
    assert not drifted, (
        "a known divergence changed. If it moved TOWARD the frozen defaults, "
        "remove its line; otherwise it drifted further: {}".format(drifted))


def test_the_inventory_has_no_stale_entries():
    """A bot that now agrees on the compared field, or is gone, loses its line.

    This is how EMAPullbackBot left the list: it differed only in LatestEntry,
    which stopped being a frozen field. An inventory that keeps entries after
    they stop being true stops meaning anything.
    """
    frozen_flatten = _hhmm(load_trading_defaults()["risk"]["flattenByEt"])
    stale = []
    for rel, expected in KNOWN_DIVERGENCES.items():
        p = REPO / rel
        if not p.exists():
            stale.append("{} (file gone)".format(rel))
        elif expected[0] == frozen_flatten:
            stale.append("{} (FlattenBy now matches the frozen {})"
                         .format(rel, frozen_flatten))
    assert not stale, (
        "remove these lines from known_bot_divergences.py, and close the "
        "matching ticket in docs/architecture/BOT_FIX_BACKLOG.md: {}".format(stale))


def test_the_pair_that_motivated_the_backlog_is_now_comparable():
    """Pins the specific pair B1 was filed over, in its CLOSED state.

    B1's original premise (bot 99 vs engine 3) stopped being true on
    2026-09-05: the engine became uncapped (maxTradesPerDay null) and the bot
    stopped declaring a cap (BOT_FIX_BACKLOG.md B1), so the pair is comparable
    at the trade-set layer again. This asserts BOTH halves of that, so neither
    can silently regress: a re-declared bot cap, or an engine cap, re-opens B1.
    """
    rel = "scripts/ninjatrader/strategies/bandits_8020/BBMRReversionBot.cs"
    assert rel in KNOWN_DIVERGENCES
    _flatten, mx, _latest = KNOWN_DIVERGENCES[rel]
    risk = load_trading_defaults()["risk"]
    assert mx is None, (
        "BBMRReversionBot declares a trade cap again -- re-open BOT_FIX_BACKLOG "
        "B1 or update this pin with the evidence that justifies it")
    assert risk["maxTradesPerDay"] is None
    text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
    assert not re.search(r"MaxTradesPerDay\s*=", text), (
        "the bot declares MaxTradesPerDay; the B1 pin says it must not")


@pytest.mark.parametrize("rel", sorted(KNOWN_DIVERGENCES))
def test_every_inventoried_bot_still_exists(rel):
    assert (REPO / rel).exists(), rel
