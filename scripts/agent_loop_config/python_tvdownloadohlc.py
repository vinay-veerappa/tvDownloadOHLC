"""
python_tvdownloadohlc.py — Python profile for the tvDownloadOHLC repo.

Usage:
    agent-loop --profile python-tvdownloadohlc \
        --profile-module scripts.agent_loop_config.python_tvdownloadohlc \
        --tickets tickets.json --ticket T1
"""
from __future__ import annotations

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
    build_cmd="python -m py_compile scripts/shared/data_loader.py",
    test_cmd="python -m pytest scripts/tests/ -v --tb=short 2>&1",
    # No lock primitive in Python
    lock_name="",
    risk_calls=(),
    # File scope (Developer mode)
    file_scope_whitelist=("scripts/",),
    # Protected paths
    protected=(
        "test_*.py",
        "*_test.py",
        "scripts/tests/*",
        "scripts/agent_loop/*",
        "scripts/agent_loop_config/*",
        "web/",
        "data/",
    ),
    test_sources=("scripts/tests/*.py",),
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
    settled=(),
)

register(PYTHON_TVDOWNLOADOHLC)