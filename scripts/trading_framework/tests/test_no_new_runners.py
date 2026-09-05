"""The gate that stops a 33rd bespoke backtest runner.

WHY THIS IS NOT A FILENAME CHECK. The obvious gate freezes `run_*.py`. Measured
on this repo that is 51 files, of which only **6** actually drive a backtest
engine -- and 26 modules that DO drive one are not called `run_*` at all
(`scripts/analysis/bb_grid_optim.py`, `scripts/research/verify_mtf_framework.py`,
...). A filename gate would have frozen the 6, declared victory, and let the
other 26 keep breeding under any name.

So the test is behavioural: a module is a runner if it NAMES a backtest engine
or the research pipeline AND is executable. The inventory of the 32 that already
existed is frozen in `frozen_runners.txt`.

WHAT MAKES THIS GATE NON-VACUOUS. An absence gate passes silently when the code
it inspects moves -- this repo has had four of those. Three negative controls
below make the failure directions symmetric:

  * a synthetic module matching the pattern MUST be detected
  * a module that imports an engine but is not executable MUST NOT be
  * the sanctioned pair MUST be detected, so a broken pattern cannot read clean

Run standalone:  python scripts/trading_framework/tests/test_no_new_runners.py
"""

import pathlib
import re

import pytest

# The two modules that are ALLOWED to drive an engine. Everything else that does
# is either frozen legacy or a new defect.
SANCTIONED = {
    "scripts/trading_framework/workflow.py",
    "scripts/trading_framework/run_backtest.py",
}

_ENGINE = re.compile(r"VectorizedBacktester|NT8ParityBacktester|BacktestEngine"
                     r"|run_research_pipeline")
_EXECUTABLE = re.compile(r"^if __name__\s*==|ArgumentParser\(", re.M)
_SKIP_PARTS = {"tests", "__pycache__", "_archive_predecessor", ".venv"}

_REPO = pathlib.Path(__file__).resolve().parents[3]
from scripts.trading_framework.tests.frozen_runners import FROZEN


def find_runners(root: pathlib.Path, relative_to: pathlib.Path = None):
    """Every executable module under `root` that drives a backtest engine."""
    base = relative_to or root
    found = set()
    for f in root.rglob("*.py"):
        if _SKIP_PARTS & set(f.parts):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if _ENGINE.search(text) and _EXECUTABLE.search(text):
            found.add(f.relative_to(base).as_posix())
    return found


def frozen():
    return set(FROZEN)


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #

def test_no_new_bespoke_runner_appeared():
    found = find_runners(_REPO / "scripts", relative_to=_REPO) - SANCTIONED
    new = sorted(found - frozen())
    assert not new, (
        "{} module(s) drive a backtest engine and are not in the frozen "
        "inventory:\n  {}\n\n"
        "Do NOT add them to frozen_runners.txt to make this pass. Use the one "
        "entry point:\n"
        "  python -m scripts.trading_framework.workflow --strategy <key> "
        "--ticker <T> --price-adjustment <basis>\n"
        "See docs/architecture/STRATEGY_WORKFLOW.md section 4.1.".format(
            len(new), "\n  ".join(new)))


def test_the_inventory_has_no_stale_entries():
    """A deleted runner must lose its line, or the count stops meaning anything."""
    found = find_runners(_REPO / "scripts", relative_to=_REPO) - SANCTIONED
    gone = sorted(frozen() - found)
    assert not gone, (
        "frozen_runners.txt lists {} module(s) that no longer drive an engine "
        "(deleted, or refactored onto the entry point -- either is good news). "
        "Remove these lines:\n  {}".format(len(gone), "\n  ".join(gone)))


# --------------------------------------------------------------------------- #
# Negative controls. Without these the gate can pass by finding nothing.
# --------------------------------------------------------------------------- #

def test_the_sanctioned_pair_is_detected():
    """If the pattern stops matching, THIS fails first and loudly."""
    found = find_runners(_REPO / "scripts", relative_to=_REPO)
    for path in SANCTIONED:
        assert path in found, (
            "the detector no longer recognises {} -- the pattern has rotted or "
            "the file moved, and every assertion above would now pass "
            "vacuously".format(path))


def test_the_detector_finds_a_synthetic_runner(tmp_path):
    (tmp_path / "sneaky_analysis.py").write_text(
        "from scripts.trading_framework.core.backtest_engine import "
        "VectorizedBacktester\n"
        "def go():\n    return VectorizedBacktester()\n"
        "if __name__ == '__main__':\n    go()\n", encoding="utf-8")
    assert find_runners(tmp_path) == {"sneaky_analysis.py"}


def test_the_detector_finds_one_that_uses_argparse_without_main(tmp_path):
    (tmp_path / "cli_ish.py").write_text(
        "import argparse\n"
        "from scripts.trading_framework.run_backtest import run_research_pipeline\n"
        "p = argparse.ArgumentParser()\n", encoding="utf-8")
    assert find_runners(tmp_path) == {"cli_ish.py"}


def test_a_library_that_merely_names_an_engine_is_not_a_runner(tmp_path):
    """The other failure direction: a filter that matches too much."""
    (tmp_path / "helpers.py").write_text(
        "from scripts.trading_framework.core.backtest_engine import "
        "VectorizedBacktester\n"
        "def build():\n    return VectorizedBacktester()\n", encoding="utf-8")
    assert find_runners(tmp_path) == set()


def test_an_executable_that_touches_no_engine_is_not_a_runner(tmp_path):
    (tmp_path / "plot_something.py").write_text(
        "import matplotlib\n"
        "if __name__ == '__main__':\n    print('hi')\n", encoding="utf-8")
    assert find_runners(tmp_path) == set()


def test_the_scan_finds_a_non_trivial_number_of_files(tmp_path):
    """Guards the scan root: an empty or wrong root makes every gate above green."""
    n = len(list((_REPO / "scripts").rglob("*.py")))
    assert n > 500, "only {} python files under scripts/ -- wrong root?".format(n)


def test_the_inventory_is_populated_and_tracked_by_git():
    """A gate whose data is gitignored is not a gate.

    This inventory was first written as `frozen_runners.txt`; `.gitignore` line
    69 is a blanket `*.txt`, so `git add` dropped it without failing and the
    gate would have errored on any fresh clone. Assert both facts.
    """
    import subprocess
    assert len(frozen()) >= 30, len(frozen())
    mod = pathlib.Path(__file__).with_name("frozen_runners.py")
    out = subprocess.run(["git", "check-ignore", "-q", str(mod)],
                         cwd=_REPO, capture_output=True)
    assert out.returncode != 0, "{} is gitignored".format(mod)
    out = subprocess.run(["git", "ls-files", "--error-unmatch", str(mod)],
                         cwd=_REPO, capture_output=True)
    assert out.returncode == 0, "{} is not tracked by git".format(mod)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
