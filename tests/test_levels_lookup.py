# filepath: tests/test_levels_lookup.py
"""Unit tests for the session-aware `build_levels_markdown_table()`.

The function (in `scripts/trader/briefing_core.py`) renders a markdown
table of option levels mapped to futures prices for a single ticker.
It supports three sessions:

  - "open"      → `current/unified_levels_open.txt`  (09:30 RTH open)
  - "eod"/"close" → `current/unified_levels_close.txt` (16:15 RTH close)
  - any other   → `unified_levels.txt` (live mirror, most recent run)

These tests cover:
  - default session is "open" (backward compat)
  - explicit session="open" reads the open file
  - explicit session="eod" reads the close file
  - "intraday" (or any other value) reads the live mirror
  - missing primary file falls back to the live mirror + warning
  - missing all files returns "No data"
  - missing ticker in the source file returns "No data"
  - close file is read for EOD narrative
  - the function actually reads different content for open vs close
  - intraday session reads the live mirror (latest content)

We mock the source file contents by writing fixture TXT files to a
temp dir, then patching `briefing_core.UNIFIED_LEVELS_OPEN_TXT`,
`UNIFIED_LEVELS_CLOSE_TXT`, and `OPTIONS_DATA_DIR` to point at them.
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.trader import briefing_core as bc


# ── Fixtures ────────────────────────────────────────────────────────
SAMPLE_OPEN_TXT = """\
NQ:32131.53:PRIME|1|Expected Move Upper, 29700.0:MAJOR|1|Put Wall, 0:META_FUTURES_BASIS_0.0
ES:7814.94:PRIME|1|Expected Move Upper, 7550.0:MAJOR|1|Put Wall, 0:META_FUTURES_BASIS_0.0
"""

SAMPLE_CLOSE_TXT = """\
NQ:33100.0:PRIME|1|Expected Move Upper, 30500.0:MAJOR|1|Put Wall, 0:META_FUTURES_BASIS_0.0
ES:7900.0:PRIME|1|Expected Move Upper, 7700.0:MAJOR|1|Put Wall, 0:META_FUTURES_BASIS_0.0
"""

SAMPLE_LIVE_TXT = """\
NQ:32500.0:PRIME|1|Live Mid, 30000.0:MAJOR|1|Put Wall, 0:META_FUTURES_BASIS_0.0
ES:7850.0:PRIME|1|Live Mid, 7600.0:MAJOR|1|Put Wall, 0:META_FUTURES_BASIS_0.0
"""


@pytest.fixture
def fake_levels_dir(tmp_path, monkeypatch):
    """Create a temp data dir with the three snapshot files and
    point briefing_core at it.

    Returns the tmp_path so tests can assert on it.
    """
    open_path = tmp_path / "current" / "unified_levels_open.txt"
    close_path = tmp_path / "current" / "unified_levels_close.txt"
    live_path = tmp_path / "unified_levels.txt"

    open_path.parent.mkdir(parents=True, exist_ok=True)
    open_path.write_text(SAMPLE_OPEN_TXT, encoding="utf-8")
    close_path.write_text(SAMPLE_CLOSE_TXT, encoding="utf-8")
    live_path.write_text(SAMPLE_LIVE_TXT, encoding="utf-8")

    monkeypatch.setattr(bc, "UNIFIED_LEVELS_OPEN_TXT", open_path)
    monkeypatch.setattr(bc, "UNIFIED_LEVELS_CLOSE_TXT", close_path)
    monkeypatch.setattr(bc, "OPTIONS_DATA_DIR", tmp_path)

    return tmp_path


# ── Default session is "open" (backward compat) ────────────────────
def test_default_session_is_open(fake_levels_dir) -> None:
    """Calling without `session=` should read the open file."""
    out_open = bc.build_levels_markdown_table("NQ")
    out_eod = bc.build_levels_markdown_table("NQ", session="eod")
    # Different content because different files
    assert out_open != out_eod
    # Open file has 32131.53
    assert "32,131.53" in out_open
    # EOD file has 33100.00
    assert "33,100.00" in out_eod


# ── Explicit session="open" reads the open file ─────────────────────
def test_session_open_reads_open_file(fake_levels_dir) -> None:
    out = bc.build_levels_markdown_table("NQ", session="open")
    assert "32,131.53" in out  # from SAMPLE_OPEN_TXT
    assert "33,100.00" not in out  # close data must NOT leak


# ── Explicit session="eod" reads the close file (THE FIX) ───────────
def test_session_eod_reads_close_file(fake_levels_dir) -> None:
    """This is the core fix for audit issue #1.3: the EOD narrative
    must grade the day against the CLOSE snapshot, not the open one."""
    out = bc.build_levels_markdown_table("NQ", session="eod")
    assert "33,100.00" in out
    assert "32,131.53" not in out  # open data must NOT leak

    out_es = bc.build_levels_markdown_table("ES", session="eod")
    assert "7,900.00" in out_es
    assert "7,814.94" not in out_es


# ── session="close" is an alias for "eod" ──────────────────────────
def test_session_close_alias_for_eod(fake_levels_dir) -> None:
    out_eod = bc.build_levels_markdown_table("NQ", session="eod")
    out_close = bc.build_levels_markdown_table("NQ", session="close")
    assert out_eod == out_close


# ── session="intraday" (or any other value) reads the live mirror ───
def test_intraday_reads_live_mirror(fake_levels_dir) -> None:
    out = bc.build_levels_markdown_table("NQ", session="intraday")
    assert "32,500.00" in out  # from SAMPLE_LIVE_TXT
    # Neither open nor close data should leak
    assert "32,131.53" not in out
    assert "33,100.00" not in out


def test_unknown_session_falls_back_to_live(fake_levels_dir) -> None:
    """Any session value that isn't 'open' or 'eod' should use the
    live mirror. The function comment says this explicitly."""
    out = bc.build_levels_markdown_table("NQ", session="premarket")
    assert "32,500.00" in out  # from live mirror


# ── Missing primary file → fallback to live mirror + warning ───────
def test_missing_open_falls_back_to_live(tmp_path, monkeypatch, caplog) -> None:
    """If the open file is missing, the function should fall back to
    the live mirror and log a warning (not crash)."""
    open_path = tmp_path / "current" / "unified_levels_open.txt"  # NOT created
    close_path = tmp_path / "current" / "unified_levels_close.txt"
    live_path = tmp_path / "unified_levels.txt"

    close_path.parent.mkdir(parents=True, exist_ok=True)
    close_path.write_text(SAMPLE_CLOSE_TXT, encoding="utf-8")
    live_path.write_text(SAMPLE_LIVE_TXT, encoding="utf-8")

    monkeypatch.setattr(bc, "UNIFIED_LEVELS_OPEN_TXT", open_path)
    monkeypatch.setattr(bc, "UNIFIED_LEVELS_CLOSE_TXT", close_path)
    monkeypatch.setattr(bc, "OPTIONS_DATA_DIR", tmp_path)

    with caplog.at_level(logging.WARNING, logger="scripts.trader.briefing_core"):
        out = bc.build_levels_markdown_table("NQ", session="open")
    # Fell back to live mirror
    assert "32,500.00" in out
    # Warning was logged
    assert any("falling back" in r.message for r in caplog.records)


def test_missing_close_falls_back_to_live(tmp_path, monkeypatch, caplog) -> None:
    """Same fallback for the EOD path."""
    open_path = tmp_path / "current" / "unified_levels_open.txt"
    close_path = tmp_path / "current" / "unified_levels_close.txt"  # NOT created
    live_path = tmp_path / "unified_levels.txt"

    open_path.parent.mkdir(parents=True, exist_ok=True)
    open_path.write_text(SAMPLE_OPEN_TXT, encoding="utf-8")
    live_path.write_text(SAMPLE_LIVE_TXT, encoding="utf-8")

    monkeypatch.setattr(bc, "UNIFIED_LEVELS_OPEN_TXT", open_path)
    monkeypatch.setattr(bc, "UNIFIED_LEVELS_CLOSE_TXT", close_path)
    monkeypatch.setattr(bc, "OPTIONS_DATA_DIR", tmp_path)

    with caplog.at_level(logging.WARNING, logger="scripts.trader.briefing_core"):
        out = bc.build_levels_markdown_table("NQ", session="eod")
    assert "32,500.00" in out  # live mirror content
    assert any("falling back" in r.message for r in caplog.records)


# ── Missing all files → "No data" ──────────────────────────────────
def test_all_files_missing_returns_no_data(tmp_path, monkeypatch) -> None:
    open_path = tmp_path / "current" / "unified_levels_open.txt"  # NOT created
    close_path = tmp_path / "current" / "unified_levels_close.txt"  # NOT created
    live_path = tmp_path / "unified_levels.txt"  # NOT created

    monkeypatch.setattr(bc, "UNIFIED_LEVELS_OPEN_TXT", open_path)
    monkeypatch.setattr(bc, "UNIFIED_LEVELS_CLOSE_TXT", close_path)
    monkeypatch.setattr(bc, "OPTIONS_DATA_DIR", tmp_path)

    assert bc.build_levels_markdown_table("NQ", session="open") == "No data"
    assert bc.build_levels_markdown_table("NQ", session="eod") == "No data"
    assert bc.build_levels_markdown_table("NQ", session="intraday") == "No data"


# ── Missing ticker in the source file → "No data" ──────────────────
def test_missing_ticker_returns_no_data(fake_levels_dir) -> None:
    """If the source file has no line for the requested ticker,
    the function should return "No data" (not crash, not return
    another ticker's levels)."""
    assert bc.build_levels_markdown_table("SPX", session="open") == "No data"
    assert bc.build_levels_markdown_table("SPX", session="eod") == "No data"
    assert bc.build_levels_markdown_table("SPX", session="intraday") == "No data"


# ── Open vs EOD content isolation (THE CORE TEST) ─────────────────
def test_open_and_eod_return_different_content(fake_levels_dir) -> None:
    """Sanity: the open and close files have different walls (32131.53
    vs 33100.00). Confirm the function returns the right number for
    each session. This is the regression test for the audit bug."""
    nq_open = bc.build_levels_markdown_table("NQ", session="open")
    nq_eod = bc.build_levels_markdown_table("NQ", session="eod")
    nq_intraday = bc.build_levels_markdown_table("NQ", session="intraday")

    # Each is unique
    assert nq_open != nq_eod
    assert nq_open != nq_intraday
    assert nq_eod != nq_intraday

    # Each contains its own EM value
    assert "32,131.53" in nq_open       # open: 32131.53
    assert "33,100.00" in nq_eod        # close: 33100.00
    assert "32,500.00" in nq_intraday   # live: 32500.00


# ── Both NQ and ES are present in each file ────────────────────────
def test_both_tickers_in_each_file(fake_levels_dir) -> None:
    """Each snapshot file should have both NQ and ES lines."""
    for session in ("open", "eod", "intraday"):
        nq = bc.build_levels_markdown_table("NQ", session=session)
        es = bc.build_levels_markdown_table("ES", session=session)
        assert nq.startswith("**"), f"NQ {session} returned bad output: {nq[:80]}"
        assert es.startswith("**"), f"ES {session} returned bad output: {es[:80]}"
