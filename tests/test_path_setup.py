"""Tests for scripts/trader/_path_setup.py (audit §2.8).

Covers:
  - Repo root is resolved correctly.
  - The side-effect import is idempotent (safe to call more than once).
  - A second import of the module does not duplicate sys.path entries.
  - The hack works in all 7 consumer files (smoke import).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from scripts.trader import _path_setup


class TestResolveRepoRoot:
    def test_resolves_repo_root_for_scripts_trader(self) -> None:
        """The module is at `scripts/trader/_path_setup.py`, so the
        repo root is the parent of `scripts/`."""
        root = _path_setup._resolve_repo_root()
        assert root is not None
        root_path = Path(root)
        # The resolved root must contain a `scripts/` directory.
        assert (root_path / "scripts").is_dir()
        # And it must contain a `tests/` directory (sanity check that
        # we did not accidentally resolve to some other repo).
        assert (root_path / "tests").is_dir()

    def test_resolved_root_is_absolute(self) -> None:
        root = _path_setup._resolve_repo_root()
        assert root is not None
        assert Path(root).is_absolute()


class TestEnsureRepoRootOnPath:
    def test_adds_repo_root_when_missing(self) -> None:
        """If the repo root is not on sys.path, calling the helper
        inserts it at the head. We mutate sys.path in place (rather
        than reassigning the attribute) so other modules that hold
        a reference to the list see the change too. We strip ALL
        occurrences of the root before running, since conftests in
        this repo each `sys.path.insert` the root multiple times."""
        root = _path_setup._resolve_repo_root()
        assert root is not None
        original = list(sys.path)
        try:
            # Pre-condition: not present (strip every occurrence).
            sys.path[:] = [p for p in sys.path if p != root]
            assert root not in sys.path
            # Act
            _path_setup._ensure_repo_root_on_path()
            # Post-condition: present at the head, exactly once.
            assert sys.path[0] == root
            assert sys.path.count(root) == 1
        finally:
            sys.path[:] = original

    def test_idempotent_when_already_on_path(self) -> None:
        """If the repo root is already on sys.path (possibly multiple
        times — conftests in this repo each `sys.path.insert` the
        repo root, so the count can be > 1 in the full suite),
        calling the helper must not add a new occurrence."""
        root = _path_setup._resolve_repo_root()
        assert root is not None
        original = list(sys.path)
        try:
            if root not in sys.path:
                sys.path.insert(0, root)
            count_before = sys.path.count(root)
            _path_setup._ensure_repo_root_on_path()
            count_after = sys.path.count(root)
            # The count must not have grown (idempotency).
            assert count_after == count_before
        finally:
            sys.path[:] = original


class TestSideEffectImport:
    def test_module_has_expected_exports(self) -> None:
        """The module must expose the public API we use elsewhere."""
        assert hasattr(_path_setup, "_ensure_repo_root_on_path")
        assert hasattr(_path_setup, "_resolve_repo_root")
        assert callable(_path_setup._ensure_repo_root_on_path)
        assert callable(_path_setup._resolve_repo_root)

    def test_repo_root_is_on_path_after_import(self) -> None:
        """The whole point of the side-effect import is that, after
        `from scripts.trader import _path_setup`, the repo root is
        present in sys.path."""
        root = _path_setup._resolve_repo_root()
        assert root is not None
        assert root in sys.path

    def test_no_duplicate_entries_on_reimport(self) -> None:
        """Re-importing the module must not duplicate the repo root."""
        root = _path_setup._resolve_repo_root()
        assert root is not None
        before = sys.path.count(root)
        importlib.reload(_path_setup)
        after = sys.path.count(root)
        assert before == after


class TestConsumerFilesSmokeImport:
    """Verify the 7 files that used to inline the hack can now be
    imported cleanly with the side-effect import. We import by file
    path so we exercise the import-time path setup, not the package
    import path."""

    CONSUMERS = [
        "scripts/trader/briefing_core.py",
        "scripts/trader/daily_eod_update.py",
        "scripts/trader/daily_narrative.py",
        "scripts/trader/seed_vol_history.py",
        "scripts/trader/trader_narrative.py",
        "scripts/trader/weekly_briefing.py",
        "scripts/trader/weekly_narrative.py",
    ]

    @pytest.mark.parametrize("rel_path", CONSUMERS)
    def test_consumer_file_does_not_inline_hack(self, rel_path: str) -> None:
        """The 10-line sys.path hack must not appear in any consumer
        file anymore. We grep for the unique substring that only
        appears in the old block."""
        repo_root = _path_setup._resolve_repo_root()
        assert repo_root is not None
        full = Path(repo_root) / rel_path
        text = full.read_text(encoding="utf-8")
        # The unique marker for the old hack: the while-loop.
        assert "while _current_dir.name and _current_dir.name" not in text, (
            f"{rel_path} still contains the old sys.path hack"
        )
        # And the side-effect import must be present.
        assert "from scripts.trader import _path_setup" in text, (
            f"{rel_path} does not import the new _path_setup module"
        )
