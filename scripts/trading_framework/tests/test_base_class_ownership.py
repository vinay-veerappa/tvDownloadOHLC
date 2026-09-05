"""There must be ONE `RiskManagerBase`, and this repo does not own it.

ADR-025, one artifact one owner. `GovernedStrategy` (section 3.4) derives from
`RiskManagerBase`, which nt8-riskguard owns at `strategies/Vinay/`. It reaches NT8
through the bridge's vendored-core sweep, and `sync_nt8_strategies.py` allowlists
the filename as `EXTERNAL_FRAMEWORK_FILES` for exactly that reason.

WHAT HAPPENED, AND WHY THESE TESTS EXIST. A SECOND copy was tracked here at
`docs/strategies/ninjatrader/risk_manager_suite/RiskManagerBase.cs`, and it had
drifted AHEAD of the file that owns the behaviour -- carrying three changes that
had never shipped, while the canonical copy and the DEPLOYED copy were
byte-identical. So the live bots ran the older logic and the fork looked
authoritative.

It was invisible to every check: outside all three directories
`sync_nt8_strategies.py` scans, so `--verify` reported `0 orphan(s)` and never
compared it to anything. Two live documents pointed at it as "the existing base
class to extend", which is how it got there and how it stayed. Deleted 2026-09-05;
its three changes are recorded with a recommendation each in BOT_FIX_BACKLOG.md B9.

THE DEEPER FINDING, which reconciling the fork would not have touched:
`AddSecondaryTimeframe` is a property of the RISK base, ten bots set it, and EIGHT
set it to `false`. A feature most of its users must switch off is in the wrong
layer -- and `GetCurrentATR()` reads that secondary series while ATR drives stop
distance and position size, so a TIMEFRAME choice became load-bearing for a RISK
calculation. Also B9.

These tests hold the line: no copy comes back, and the members `GovernedStrategy`
needs stay available at the accessibility it needs them at.
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
CANON = pathlib.Path.home() / "nt8-riskguard" / "strategies" / "Vinay" / "RiskManagerBase.cs"
GOVERNED = REPO / "scripts" / "ninjatrader" / "shared" / "GovernedStrategy.cs"

#: The members `GovernedStrategy` needs from its base, with the accessibility it
#: needs them at. A private or non-virtual one is a compile error that cannot be
#: seen from this repo -- nothing here compiles NinjaScript.
REQUIRED_BASE_MEMBERS = {
    "FlattenBy": r"public\s+int\s+FlattenBy",
    "LatestEntry": r"LatestEntry\s*\{\s*get;\s*set;",
    "MaxTradesPerDay": r"MaxTradesPerDay\s*\{\s*get;\s*set;",
    "GetSignalName": r"protected\s+virtual\s+string\s+GetSignalName",
    "OnEntryBlocked": r"protected\s+virtual\s+void\s+OnEntryBlocked",
    "SetStrategyDefaults": r"protected\s+abstract\s+void\s+SetStrategyDefaults",
    "InitializeStrategy": r"protected\s+abstract\s+void\s+InitializeStrategy",
    "CheckForSignal": r"protected\s+abstract\s+int\s+CheckForSignal",
}


def test_this_repo_does_not_own_the_base_class():
    """A `.cs` for it under `scripts/ninjatrader/` would make this repo a second
    owner and the sync tool would then deploy it over the vendored copy."""
    owned = [p.as_posix() for p in (REPO / "scripts" / "ninjatrader").rglob("RiskManagerBase.cs")]
    assert not owned, (
        "RiskManagerBase.cs must not live under scripts/ninjatrader/ -- "
        "nt8-riskguard owns it (ADR-025) and sync_nt8_strategies.py allowlists "
        "the filename as external. Found: {}".format(owned))


@pytest.mark.skipif(not CANON.exists(), reason="nt8-riskguard not checked out here")
def test_the_governed_base_only_uses_members_the_canonical_base_offers():
    """THE COMPILE CHECK THIS REPO CANNOT OTHERWISE DO. Nothing here builds
    NinjaScript, so a member that is private, non-virtual or renamed upstream is
    a failure that would first appear as `nt_compile` errors -- and a broken NT8
    Custom assembly is invisible, because NT8 keeps running the last good one.
    """
    canon = CANON.read_text(encoding="utf-8", errors="replace")
    missing = {name: pat for name, pat in REQUIRED_BASE_MEMBERS.items()
               if not re.search(pat, canon)}
    assert not missing, (
        "GovernedStrategy needs these from RiskManagerBase and the canonical "
        "copy does not offer them at that accessibility: {}. Fix it in "
        "nt8-riskguard, not here.".format(sorted(missing)))


def test_the_fork_stays_deleted():
    """It was removed 2026-09-05. A `.cs` reappearing anywhere in this repo is a
    second owner returning, and the last one took three unshipped changes and two
    misleading doc pointers with it."""
    copies = [p.relative_to(REPO).as_posix()
              for p in REPO.rglob("RiskManagerBase.cs")
              if ".git" not in p.parts]
    assert not copies, (
        "RiskManagerBase.cs is back in this repo at {}. nt8-riskguard owns it "
        "(ADR-025). If a change is needed, make it THERE and bump the bridge "
        "pin -- a copy here is invisible to sync_nt8_strategies.py, which "
        "allowlists the filename as external and will report 0 orphans."
        .format(copies))


def test_the_folder_that_held_it_points_somewhere_useful():
    """A deleted file leaves readers who followed a link to it. Two live docs
    named it as the base class to extend, so the folder keeps a pointer rather
    than becoming a 404."""
    readme = (REPO / "docs" / "strategies" / "ninjatrader" / "risk_manager_suite"
              / "README.md")
    assert readme.exists(), "the pointer README must survive the deletion"
    text = readme.read_text(encoding="utf-8")
    assert "nt8-riskguard" in text
    assert "GovernedStrategy" in text, (
        "the pointer must name what to inherit INSTEAD, or a reader arrives and "
        "still does not know what to do")


def test_nothing_live_still_points_at_the_deleted_fork():
    """Dated handover records may keep their references -- they describe what was
    true when written. A CURRENT document telling someone to extend a file that
    no longer exists is a different thing."""
    stale = []
    for md in (REPO / "docs").rglob("*.md"):
        if "HANDOVER" in md.name or "SESSION_" in md.name:
            continue                      # dated records, deliberately intact
        body = md.read_text(encoding="utf-8", errors="replace")
        if "risk_manager_suite/RiskManagerBase.cs" in body:
            stale.append(md.relative_to(REPO).as_posix())
    assert not stale, (
        "these current documents still point at the deleted fork: {}. Point them "
        "at scripts/ninjatrader/shared/GovernedStrategy.cs instead.".format(stale))


def test_the_three_deleted_changes_are_still_recorded():
    """The fork is gone, so this ticket is the ONLY record of what it carried,
    outside git history. Deleting the file without the record would lose a
    breakeven fix that no test covers."""
    backlog = (REPO / "docs" / "architecture" / "BOT_FIX_BACKLOG.md").read_text(
        encoding="utf-8")
    assert "## B9" in backlog
    for change in ("SecondaryTimeframeMinutes", "ConfigureStrategy", "Breakeven"):
        assert change in backlog, (
            "B9 must still name the {!r} change the deleted fork carried, with a "
            "recommendation -- it is the only record left".format(change))
    assert "AddSecondaryTimeframe" in backlog, (
        "B9 must record the LAYERING finding, not just the reconciliation: a "
        "risk-base property that eight of its ten users switch off")


def test_the_governed_base_declares_which_repo_owns_its_parent():
    """A reader who does not know the parent lives elsewhere will edit a local
    copy. That is precisely how the deleted fork came to exist."""
    text = GOVERNED.read_text(encoding="utf-8")
    assert "nt8-riskguard" in text
    assert "ADR-025" in text
