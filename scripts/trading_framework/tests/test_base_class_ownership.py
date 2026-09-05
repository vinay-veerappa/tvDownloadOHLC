"""There must be ONE `RiskManagerBase`, and this repo does not own it.

ADR-025, one artifact one owner. `GovernedStrategy` (section 5.7) derives from
`RiskManagerBase`, which nt8-riskguard owns at `strategies/Vinay/`. It reaches
NT8 through the bridge's vendored-core sweep, and `sync_nt8_strategies.py`
allowlists the filename as `EXTERNAL_FRAMEWORK_FILES` for exactly that reason.

WHAT THESE TESTS EXIST TO CATCH, found 2026-09-05. A SECOND copy of
`RiskManagerBase.cs` is tracked in this repo at
`docs/strategies/ninjatrader/risk_manager_suite/`, and it is **33 diff-lines
AHEAD of the canonical one**:

  * a configurable `SecondaryTimeframeMinutes` (default 15) replacing a
    hardcoded `AddDataSeries(Minute, 5)`
  * `ConfigureStrategy()` called BEFORE `AddDataSeries` rather than after, which
    is what lets a subclass influence which series gets added
  * a breakeven trigger that also fires on the bar's high/low, and checks
    whether the queen leg actually filled

The canonical copy and the DEPLOYED copy are byte-identical, so the live bots run
the older logic and these three improvements have never shipped. They are real
work, they are not mine to land -- each changes live bot behaviour -- and the
question of whose version wins is the user's.

WHY THIS IS WORSE THAN A PLAIN DUPLICATE. The fork is invisible to every existing
check: it sits outside all three directories `sync_nt8_strategies.py` scans, so
`--verify` reports `0 orphan(s)` and never compares it to anything. It is also
the copy a reader working in THIS repo will open, so it is a lower-profile second
source of truth -- the same shape as an "appendix" that contradicts the canonical
document.

These tests do not delete it and do not reconcile it. They make it LOUD, and they
fail if it drifts further.
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
FORK = REPO / "docs" / "strategies" / "ninjatrader" / "risk_manager_suite" / "RiskManagerBase.cs"
CANON = pathlib.Path.home() / "nt8-riskguard" / "strategies" / "Vinay" / "RiskManagerBase.cs"
GOVERNED = REPO / "scripts" / "ninjatrader" / "shared" / "GovernedStrategy.cs"

#: FORK-ONLY lines: content present in the fork and absent from canonical.
#: Measured 2026-09-05 on LF-normalised text.
#:
#: DELIBERATELY NOT THE TOTAL DIFF. That was the first metric and it was wrong:
#: it counted canonical-only lines too, so it ROSE from 33 to 75 the moment a
#: legitimate upstream edit landed. A debt number that grows when you fix the
#: right file trains you to ignore it.
#:
#: Composition of the 24, stated because the number alone is misleading:
#:   * 14 are genuine unlanded work -- the configurable `SecondaryTimeframeMinutes`,
#:     the `ConfigureStrategy()` reordering, and the breakeven improvement
#:   * 10 are the fork being STALE against the hooks added upstream 2026-09-05
#:     (nine `return false;` now routed through `Blocked`, and `GetSignalName`
#:     still private there)
#:
#: Shrink-only either way: landing the fork's changes upstream reduces it, and so
#: does refreshing the fork from canonical.
KNOWN_FORK_ONLY_LINES = 24

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


def _lf(p: pathlib.Path) -> list:
    return p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split("\n")


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


@pytest.mark.skipif(not CANON.exists(), reason="nt8-riskguard not checked out here")
def test_the_docs_fork_has_not_drifted_further():
    """Shrink-only. The fork is real unlanded work, so this does not demand it be
    deleted -- it demands that nobody adds to it, because every line added is a
    line that will have to be reconciled by someone who does not remember why.
    """
    if not FORK.exists():
        return                      # reconciled: nothing left to guard
    import difflib
    diff = list(difflib.unified_diff(_lf(CANON), _lf(FORK), lineterm="", n=0))
    # Only FORK-ONLY lines. Counting canonical-only lines as well made the number
    # rise when the correct file was edited -- see the constant's comment.
    fork_only = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
    assert len(fork_only) <= KNOWN_FORK_ONLY_LINES, (
        "the docs fork of RiskManagerBase.cs now carries {} lines that canonical "
        "does not (recorded: {}). Someone edited the FORK instead of the file "
        "that owns the behaviour. Land it in nt8-riskguard and shrink this "
        "number; see BOT_FIX_BACKLOG.md B9.\nNew fork-only content:\n{}".format(
            len(fork_only), KNOWN_FORK_ONLY_LINES,
            "\n".join("  " + l[1:].strip() for l in fork_only[:12])))


@pytest.mark.skipif(not CANON.exists(), reason="nt8-riskguard not checked out here")
def test_the_fork_is_recorded_as_a_ticket_not_just_tolerated():
    """An inventory with no ticket behind it is a permanent exemption. This is
    how B1-B6 avoided becoming one."""
    if not FORK.exists():
        return
    backlog = (REPO / "docs" / "architecture" / "BOT_FIX_BACKLOG.md").read_text(
        encoding="utf-8")
    assert "RiskManagerBase" in backlog, (
        "the forked base class must have a ticket in BOT_FIX_BACKLOG.md naming "
        "the three unlanded changes, or nothing will ever reconcile it")


def test_the_governed_base_declares_which_repo_owns_its_parent():
    """A reader who does not know the parent lives elsewhere will edit the fork.
    That is precisely how the fork got 33 lines ahead."""
    text = GOVERNED.read_text(encoding="utf-8")
    assert "nt8-riskguard" in text
    assert "ADR-025" in text
