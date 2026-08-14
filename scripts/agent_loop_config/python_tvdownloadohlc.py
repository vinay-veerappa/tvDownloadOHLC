"""
python_tvdownloadohlc.py — Python profile for the tvDownloadOHLC repo.

Usage:
    agent-loop --profile python-tvdownloadohlc \
        --profile-module scripts.agent_loop_config.python_tvdownloadohlc \
        --tickets tickets.json --ticket T1
"""
from __future__ import annotations

import sys

from agent_loop.profiles import Profile, register

PYTHON_TVDOWNLOADOHLC = Profile(
    name="python-tvdownloadohlc",
    language="python",
    file_suffixes=(".py",),
    line_comment="#",
    block_comment=(),  # Python has no block comments
    block_kind="indent",
    preprocessor_directives=(),
    # Build and test
    #
    # {files} is substituted with the files the patch actually touched. Naming a
    # fixed file here (it used to compile scripts/shared/data_loader.py) makes
    # the compile gate pass no matter what the patch did -- a gate that cannot
    # fail is worse than no gate.
    # O35: `sys.executable`, not bare `python`. These commands run inside a git
    # worktree, and a bare `python` resolves against PATH -- which on this
    # machine is not necessarily this repo's .venv. The gate would then compile
    # and test under an interpreter with different packages than the one the
    # loop is running in, so a green gate would say nothing about this venv.
    build_cmd=f'"{sys.executable}" -m py_compile {{files}}',
    # scripts/tests/ is a scratch directory, not a suite: 15 of its 47 files
    # fail at import because they read data files at module scope, so pytest
    # reported "15 errors during collection", no baseline could be established,
    # and EVERY ticket on this profile ended in ERROR before reaching a model.
    # These two suites are green (one known failure, frozen as the baseline)
    # and run in ~6s.
    test_cmd=(
        f'"{sys.executable}" -m pytest scripts/libs_py/ict_engine/tests '
        "scripts/trading_framework/tests -q --tb=short -p no:cacheprovider"
    ),
    # No lock primitive in Python
    lock_name="",
    risk_calls=(),
    # File scope (Developer mode)
    file_scope_whitelist=("scripts/",),
    # Protected paths. These are fnmatch patterns against the whole relative
    # path, so a bare directory name matches nothing -- "web/" and "data/" were
    # inert and had to become "web/*" and "data/*".
    protected=(
        "test_*.py",
        "*_test.py",
        "conftest.py",
        "scripts/tests/*",
        "scripts/libs_py/ict_engine/tests/*",
        "scripts/trading_framework/tests/*",
        "scripts/agent_loop/*",
        "scripts/agent_loop_config/*",
        "web/*",
        "data/*",
    ),
    test_sources=(
        "scripts/libs_py/ict_engine/tests/*.py",
        "scripts/trading_framework/tests/*.py",
    ),
    # Context and token budgets
    context_token_budget=3000,
    round_input_token_budget=40000,
    # Graph project
    graph_project="C-Users-vinay-tvDownloadOHLC",
    # Prompts
    implementer_rules="""\
You are a senior Python engineer working on a trading data analysis and
backtesting platform. You make surgical, minimal, provably-correct edits.

HARD CONSTRAINTS:
1. Target Python 3.10+. Use type hints where the codebase already does.
2. The file must compile and all existing tests must pass after your edit.
3. Do not rename existing public members or change method signatures.
4. Preserve the existing 4-space indentation style.
5. Fail closed: if a safety precondition cannot be verified, take the
   conservative action.
6. Do not weaken or delete tests to pass.
7. Follow ADR-017 (zero-loop constraint): use vectorized NumPy/Pandas, no
   for loops in calculation paths.
8. Follow ADR-002: report metrics as price-percentage, not absolute points.""",
    reviewer_priorities="""\
You are an adversarial code reviewer for a trading research platform.
Assume the implementer is confident and wrong.

Check, in priority order:
1. CORRECTNESS: does the fix close the defect in every path?
2. VECTORIZE: any new for-loop in a calculation path (ADR-017 violation)?
3. DATA INTEGRITY: any look-ahead bias, future leakage, or data corruption?
4. TEST ADEQUACY: do the tests cover the defect?
5. COMPILE BREAKS: Python 3.10+ compatibility, missing imports.
6. REGRESSIONS: existing tests that would break.

Be specific. Cite the offending line text.""",
    # What "blocks" means in THIS repo. Without it the arbiter inherits a
    # generic bar; with the NT8 one ("state the sequence of events that loses
    # money") nothing here can ever qualify, so it rejects every finding and
    # recommends SHIP.
    arbiter_rules="""\
You are the arbiter for a patch to a trading research and backtesting platform.
Its output drives strategy decisions, so a wrong number is worse than a crash: a
crash is noticed, a silently wrong backtest is acted on.

An UPHELD finding must name a concrete, reachable failure. Any of these qualify:
  * a wrong result: look-ahead bias, future leakage, off-by-one on a bar index,
    a session boundary or timezone handled inconsistently with ADR-001;
  * silent data corruption, or a metric reported in absolute points where the
    project's standard (ADR-002) is price-percentage;
  * a for-loop in a calculation path (ADR-017) large enough to change runtime
    by an order of magnitude;
  * a crash or an exception on input the function is documented to accept.

These do NOT qualify: style, naming, "could be clearer", missing type hints,
speculative future refactors, or a performance concern with no measured basis.""",
    settled=(),
)

register(PYTHON_TVDOWNLOADOHLC)