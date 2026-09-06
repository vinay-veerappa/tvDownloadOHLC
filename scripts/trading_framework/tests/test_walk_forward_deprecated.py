"""Section 11.1 item 6.1: audit `walk_forward_split`.

The function is DEPRECATED -- an expanding-window split with NO purge and NO
embargo: `train` ends on the bar immediately before `test`, so any
forward-looking label computed at the end of train overlaps the start of
test. The audit found ZERO callers (only the definition and two doc
mentions). This test keeps it that way: a new caller fails loudly here
instead of inheriting the leak silently.

The sanctioned alternatives are `sequential_evaluation_folds` (parameter
sweeps, nothing fitted) and `PurgedKFold` (fitted models).
"""

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
ALLOWED_TO_DEFINE = {"scripts/trading_framework/ml/walk_forward.py"}
ALLOWED_TO_MENTION = {
    "docs/architecture/STRATEGY_WORKFLOW.md",
    "scripts/trading_framework/README.md",
    "scripts/trading_framework/ml/walk_forward.py",
    "scripts/trading_framework/tests/test_walk_forward_deprecated.py",
}


def _iter_python_files():
    for p in REPO.rglob("*.py"):
        s = str(p.relative_to(REPO)).replace("\\", "/")
        if ".venv" in s or "node_modules" in s or s.startswith("web/"):
            continue
        yield p, s


def _parse_or_none(path):
    """utf-8-sig strips a BOM (several files here carry one); a file that
    still cannot be parsed is skipped WITH ITS NAME VISIBLE in the report,
    because a silent skip is the loophole this test must not have."""
    try:
        return ast.parse(path.read_text(encoding="utf-8-sig", errors="ignore"))
    except SyntaxError:
        print("UNPARSEABLE (skipped):", path)
        return None


def test_no_code_calls_the_deprecated_split():
    """AST-count CALLS, not substrings: the module docstring and the
    deprecation message itself both contain the name, and a text scan would
    read them as callers (the exact class of false positive this repo's
    habits section records for `VectorizedBacktester(`)."""
    offenders = []
    for path, rel in _iter_python_files():
        tree = _parse_or_none(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == "walk_forward_split":
                    offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "walk_forward_split is DEPRECATED (no purge, no embargo -- forward "
        "labels at the end of train overlap the start of test). New callers "
        "must use sequential_evaluation_folds (sweeps) or PurgedKFold "
        "(fitted models). Offending call sites: {}".format(offenders))


def test_imports_are_refused_too():
    """`from ... import walk_forward_split` is a caller that has not called
    yet; catching the import catches the intent before the leak is wired."""
    offenders = []
    for path, rel in _iter_python_files():
        if rel in ALLOWED_TO_DEFINE:
            continue
        tree = _parse_or_none(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "walk_forward_split":
                        offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "walk_forward_split imported at {} -- it is deprecated with no purge "
        "and no embargo".format(offenders))


def test_the_deprecated_function_still_refuses_new_friends_by_docstring():
    """If the function is ever undeprecated, this test should be deleted WITH
    it -- the point is not to pin the docstring forever but to pin that the
    ONLY allowed state is deprecated-with-no-callers."""
    import warnings
    src = (REPO / "scripts/trading_framework/ml/walk_forward.py").read_text(
        encoding="utf-8")
    assert "DEPRECATED" in src.split("def walk_forward_split")[1][:400]