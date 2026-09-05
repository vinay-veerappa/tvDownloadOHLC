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
    for field, want in (
        ("MaxTradesPerDay", risk["maxTradesPerDay"]),
        ("FlattenBy", _hhmm(risk["flattenByEt"])),
        ("LastEntry", _hhmm(risk["lastEntryEt"])),
        ("RthHardExit", _hhmm(risk["rthHardExitEt"])),
    ):
        m = re.search(r"const int\s+" + field + r"\s*=\s*(\d+)", text)
        assert m, field
        assert int(m.group(1)) == want, (field, m.group(1), want)


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


def test_no_new_bot_diverges_from_the_frozen_defaults():
    risk = load_trading_defaults()["risk"]
    frozen = (_hhmm(risk["flattenByEt"]), risk["maxTradesPerDay"],
              _hhmm(risk["lastEntryEt"]))
    new = {}
    for p in bot_files():
        rel = p.relative_to(REPO).as_posix()
        got = declared(p)
        if got == (None, None, None):
            continue                     # declares none of them: inherits
        if rel in KNOWN_DIVERGENCES:
            continue                     # covered by the test below
        if got != frozen:
            new[rel] = got
    assert not new, (
        "these bots set execution defaults the frozen document owns "
        "(want FlattenBy/MaxTradesPerDay/LatestEntry = {}): {}\n\n"
        "Use TradingDefaults.MaxTradesPerDay / .FlattenBy / .LastEntry. Do NOT "
        "add a line to known_bot_divergences.py to silence this."
        .format(frozen, new))


def test_the_overridable_fields_are_declared_as_such():
    """The invariant/overridable split lives in the document, not in this test.

    A correction to my own first version: `lastEntryEt` and `flattenByEt`
    interact with the session a strategy trades, so a global freeze at 14:30
    would forbid a legitimate NY_PM setup. They are overridable. The ADR-020
    hard exit never is.
    """
    risk = load_trading_defaults()["risk"]
    assert set(risk["overridable"]) == {
        "lastEntryEt", "flattenByEt", "maxTradesPerDay"}
    assert "rthHardExitEt" not in risk["overridable"], (
        "the ADR-020 hard exit is a safety limit and must never be overridable")


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
    """A bot that now agrees, or no longer exists, must lose its line."""
    risk = load_trading_defaults()["risk"]
    frozen = (_hhmm(risk["flattenByEt"]), risk["maxTradesPerDay"],
              _hhmm(risk["lastEntryEt"]))
    stale = []
    for rel, expected in KNOWN_DIVERGENCES.items():
        p = REPO / rel
        if not p.exists():
            stale.append("{} (file gone)".format(rel))
        elif tuple(expected) == frozen:
            stale.append("{} (agrees with the frozen defaults)".format(rel))
    assert not stale, "remove these lines from known_bot_divergences.py: {}".format(stale)


def test_the_worst_divergence_is_recorded_with_its_consequence():
    """Pins the specific pair that cannot be compared, so it is not forgotten.

    mean_reversion (Python) flattens 15:45 and caps 3 trades/day.
    BBMRReversionBot (its C# bot) flattens 16:15 and caps 99.
    """
    rel = "scripts/ninjatrader/strategies/bandits_8020/BBMRReversionBot.cs"
    assert rel in KNOWN_DIVERGENCES
    flatten, mx, _latest = KNOWN_DIVERGENCES[rel]
    risk = load_trading_defaults()["risk"]
    assert flatten != _hhmm(risk["flattenByEt"])
    assert mx != risk["maxTradesPerDay"]


@pytest.mark.parametrize("rel", sorted(KNOWN_DIVERGENCES))
def test_every_inventoried_bot_still_exists(rel):
    assert (REPO / rel).exists(), rel
