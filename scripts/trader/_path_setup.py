"""Project-root path setup for `scripts.trader` modules.

Centralises the one-off `sys.path` mutation that every script under
`scripts/trader/` used to inline. The original 10-line block was
duplicated in 7 files and fragile (broke if a file moved or if
`scripts/trader/` was nested differently).

Usage
-----
Replace the duplicated block at the top of each script with:

    from scripts.trader import _path_setup  # noqa: F401

That's it — importing this module is the side effect. The
`scripts.trader` package is importable as long as the repo root is on
`sys.path` (which the scheduler already does in production; the
helper remains a safety net for direct `python -m scripts.trader.x`
or `pytest tests/` invocations).

Why a side-effect import and not a function call?
-------------------------------------------------
Most scripts in `scripts/trader/` used the old block **before** any
project-relative import (e.g. `from scripts.trader.briefing_core
import ...`). Replacing the block with a function call would mean
ordering matters: the call must run before the first import. A
side-effect import is impossible to misorder.

Idempotency
-----------
The helper is safe to call multiple times; we only insert the repo
root if it is not already on `sys.path`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT_MARKER = "scripts"  # walk up until we find a dir named this


def _resolve_repo_root() -> str | None:
    """Walk up from this file until we find the directory that contains
    a `scripts/` child, and return its absolute path as a string. Returns
    None if the layout doesn't match the expected one (e.g. someone
    moved the file outside the repo)."""
    current = Path(__file__).resolve().parent
    while current.name and current.name != _REPO_ROOT_MARKER:
        current = current.parent
    if current.name == _REPO_ROOT_MARKER:
        return str(current.parent)
    return None


def _ensure_repo_root_on_path() -> None:
    """Insert the repo root at the head of `sys.path` if not already
    present. Safe to call more than once."""
    root = _resolve_repo_root()
    if root is None:
        # The structure has changed in a way we don't recognise.
        # Fall back to the previous behaviour: do nothing. Scripts
        # that have a real PYTHONPATH set (e.g. via the scheduler)
        # will still work; only direct invocations that rely on the
        # hack will surface the broken layout as an ImportError,
        # which is the correct signal.
        return
    if root not in sys.path:
        sys.path.insert(0, root)


# Side effect on import — replaces the duplicated 10-line block in
# every consumer.
_ensure_repo_root_on_path()
