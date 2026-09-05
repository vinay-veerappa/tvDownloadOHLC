"""The authoritative gate for this repo. Run it before you push.

WHY THIS EXISTS AND NOT A GITHUB WORKFLOW. A CI run happens AFTER the push: it
notifies, it cannot block. In a repo that pushes straight to `main` with no pull
requests, CI is a mailing list. Two things do real work, in this order:

  1. `.githooks/pre-commit` -- refuses the commit. Fast gates only (~4s).
  2. this file -- the full sweep, run by hand before pushing.

A hosted CI run would add exactly ONE thing neither can: it executes on a FRESH
CLONE, which is the only way to catch a gate whose data is untracked. That is
not hypothetical -- `frozen_runners.txt` was added, silently dropped by a
blanket `*.txt` ignore rule, and was green here while broken on every checkout.
Until CI exists, `test_the_inventory_is_populated_and_tracked_by_git` stands in
for it by asking git directly.

REFUSES TO PASS VACUOUSLY. Every check reports what it inspected, and a check
that inspected nothing is a FAILURE, not a pass. `pytest` exits 0 when it
collects nothing; so does `dotnet test` on the sibling repo's csproj, which is
how that suite read green while running zero tests for an unknown number of
sessions.

    ./.venv/Scripts/python.exe tools/ci_local.py
    ./.venv/Scripts/python.exe tools/ci_local.py --fast
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
MIN_TESTS = 300          # raise this when the suite grows; never lower it silently
DOC = REPO / "docs" / "architecture" / "STRATEGY_WORKFLOW.md"

FAST_GATES = [
    "scripts/trading_framework/tests/test_no_new_runners.py",
    "scripts/trading_framework/tests/test_workflow_checklist.py",
]


class Result:
    def __init__(self, name: str):
        self.name = name
        self.ok = False
        self.detail = ""
        self.inspected = 0


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], cwd=REPO, capture_output=True, text=True)


def check_suite(paths: list[str], label: str, minimum: int) -> Result:
    r = Result(label)
    proc = _run("-m", "pytest", *paths, "-q")
    tail = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) passed", tail)
    r.inspected = int(m.group(1)) if m else 0
    if proc.returncode != 0:
        r.detail = "pytest exit {}".format(proc.returncode)
        for line in tail.splitlines():
            if line.startswith("FAILED") or line.startswith("ERROR"):
                r.detail += "\n      " + line.strip()
        return r
    if r.inspected < minimum:
        # A COLLECTION ERROR CAN EXIT 0. This is the only thing standing between
        # "the suite is green" and "the suite did not run".
        r.detail = ("only {} tests passed, expected at least {} -- a collection "
                    "error exits 0 and reads exactly like a pass"
                    .format(r.inspected, minimum))
        return r
    r.ok = True
    r.detail = "{} tests".format(r.inspected)
    return r


def check_doc_references() -> Result:
    """Every section-N.M citation in the canonical document must resolve."""
    r = Result("doc cross-references")
    if not DOC.is_file():
        r.detail = "{} is missing".format(DOC)
        return r
    text = DOC.read_text(encoding="utf-8")
    heads = set()
    for line in text.splitlines():
        m = re.match(r"^#{2,4}\s+(?:§\s*)?(\d+(?:\.\d+)?)[.\s]", line)
        if m:
            heads.add(m.group(1))
    refs = set(re.findall(r"§\s*(\d+(?:\.\d+)?)", text))
    r.inspected = len(refs)
    if not heads or not refs:
        r.detail = "found {} headings and {} refs -- parser rotted".format(
            len(heads), len(refs))
        return r
    dangling = sorted(refs - heads)
    if dangling:
        r.detail = "dangling: {}".format(", ".join(dangling))
        return r
    r.ok = True
    r.detail = "{} refs over {} headings, zero dangling".format(len(refs), len(heads))
    return r


def check_gate_data_is_tracked() -> Result:
    """A gate whose data git ignores is green here and broken everywhere else."""
    r = Result("gate data tracked by git")
    must_be_tracked = [
        "scripts/trading_framework/tests/frozen_runners.py",
        "docs/architecture/STRATEGY_WORKFLOW.md",
        "AGENTS.md",
        "scripts/parity/fixtures/nt8_trades_BollingerCrossOver_ES_15m_2026-07-01_2026-07-10.csv",
        "scripts/parity/fixtures/nt8_trades_BollingerCrossOver_ES_15m_2026-07-01_2026-07-10.meta.json",
    ]
    r.inspected = len(must_be_tracked)
    missing = []
    for rel in must_be_tracked:
        p = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                           cwd=REPO, capture_output=True)
        if p.returncode != 0:
            missing.append(rel)
    if missing:
        r.detail = "untracked: " + ", ".join(missing)
        return r
    r.ok = True
    r.detail = "{} files, all tracked".format(len(must_be_tracked))
    return r


def check_workflow_help() -> Result:
    """The entry point must at least be importable and able to parse args."""
    r = Result("entry point imports")
    proc = _run("-m", "scripts.trading_framework.workflow", "--help")
    r.inspected = 1
    if proc.returncode != 0:
        r.detail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:]
        r.detail = str(r.detail)
        return r
    if "--price-adjustment" not in proc.stdout:
        r.detail = "--help ran but does not mention --price-adjustment"
        return r
    r.ok = True
    r.detail = "--help ok"
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fast", action="store_true",
                    help="the two gates the pre-commit hook runs, nothing else")
    args = ap.parse_args()

    t0 = time.time()
    checks: list[Result] = []
    if args.fast:
        checks.append(check_suite(FAST_GATES, "fast strategy gates", 40))
    else:
        checks.append(check_suite(["scripts/trading_framework/tests"],
                                  "trading_framework suite", MIN_TESTS))
        checks.append(check_workflow_help())
        checks.append(check_doc_references())
        checks.append(check_gate_data_is_tracked())

    width = max(len(c.name) for c in checks)
    print("=" * (width + 46))
    print("ci_local  ({})".format("fast" if args.fast else "full"))
    print("=" * (width + 46))
    for c in checks:
        print("  [{}] {}  {}".format("PASS" if c.ok else "FAIL",
                                     c.name.ljust(width), c.detail))
    failed = [c for c in checks if not c.ok]
    print("-" * (width + 46))
    print("  {} in {:.1f}s".format(
        "GREEN" if not failed else "RED -- {} check(s) failed".format(len(failed)),
        time.time() - t0))
    print("=" * (width + 46))
    if not failed:
        print("\nSafe to push. A hosted CI run would still add one thing this "
              "cannot:\nit executes on a fresh clone.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
