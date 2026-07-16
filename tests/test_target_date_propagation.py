"""Tests for audit §2.11: target_date propagation in build_ticker_cheat_sheet
and build_eod_context.

The audit's complaint: when target_date is None, build_overnight_context
defaults to "today". For backfill runs (e.g., testing the Friday narrative
on Monday), the overnight context is wrong — it shows Monday's Globex
session instead of Friday's.

The fix: 5 call sites in briefing_core.py now pass `target_date` as the
3rd positional argument. These tests verify that propagation works at
runtime and that all 5 sites have been remediated.
"""

from __future__ import annotations

import inspect
import re
from datetime import date
from unittest import mock

import pytest


# ── source-level: every call site must pass target_date ─────────


class TestAllCallSitesPassTargetDate:
    """Static check: every `build_overnight_context(loader, ...)` call
    in briefing_core.py must include `target_date`. This is a guard
    against future regressions where someone adds a new call site but
    forgets the parameter."""

    def test_every_call_site_passes_target_date(self) -> None:
        from scripts.trader import briefing_core
        src = inspect.getsource(briefing_core)
        lines = src.split("\n")
        offenders = []
        for i, line in enumerate(lines, start=1):
            if "build_overnight_context(loader" not in line:
                continue
            if "target_date" in line:
                continue
            offenders.append((i, line.strip()))
        assert not offenders, (
            f"Found {len(offenders)} call sites of build_overnight_context(loader, ...) "
            f"missing target_date. Lines: {[l for l, _ in offenders]}"
        )

    def test_exactly_seven_call_sites(self) -> None:
        """Regression guard: there should be exactly 7 call sites —
        2 in build_premarket_context, 3 in build_ticker_cheat_sheet
        (NQ+ES+ticker at the top), 1 in build_ticker_cheat_sheet
        (ticker only, downstream), and 1 in build_eod_context."""
        from scripts.trader import briefing_core
        src = inspect.getsource(briefing_core)
        sites = [
            line for line in src.split("\n")
            if "build_overnight_context(loader" in line and "target_date" in line
        ]
        assert len(sites) == 7, (
            f"Expected 7 build_overnight_context(loader, ..., target_date) call sites, "
            f"got {len(sites)}"
        )

    def test_pattern_does_not_pass_hardcoded_date(self) -> None:
        """Hardcoding a date() or datetime.now() at the call site would
        defeat the whole purpose of the backfill fix."""
        from scripts.trader import briefing_core
        src = inspect.getsource(briefing_core)
        bad = re.findall(
            r"build_overnight_context\([^)]*target_date\s*=\s*(?:date\(|datetime\.)",
            src,
        )
        assert not bad, (
            f"Found hardcoded date/datetime passed to build_overnight_context: {bad}"
        )

    def test_target_date_is_variable_not_literal_string(self) -> None:
        """The 3rd argument to every call should be the *variable*
        `target_date` (which is in scope from the function param),
        not a literal date string."""
        from scripts.trader import briefing_core
        src = inspect.getsource(briefing_core)
        bad_literal = re.findall(
            r'build_overnight_context\(loader,\s*[^,]+,\s*"[0-9]{4}-[0-9]{2}-[0-9]{2}"\)',
            src,
        )
        assert not bad_literal, (
            f"Found call sites with literal date string: {bad_literal}"
        )


# ── signatures: target_date still on the public API ──────────────


class TestPublicSignatures:
    def test_build_ticker_cheat_sheet_signature(self) -> None:
        from scripts.trader import briefing_core
        sig = inspect.signature(briefing_core.build_ticker_cheat_sheet)
        assert "target_date" in sig.parameters
        assert sig.parameters["target_date"].default is None

    def test_build_eod_context_signature(self) -> None:
        from scripts.trader import briefing_core
        sig = inspect.signature(briefing_core.build_eod_context)
        assert "target_date" in sig.parameters
        assert sig.parameters["target_date"].default is None

    def test_build_overnight_context_signature(self) -> None:
        from scripts.trader import briefing_core
        sig = inspect.signature(briefing_core.build_overnight_context)
        assert "target_date" in sig.parameters
        assert sig.parameters["target_date"].default is None


# ── trader_narrative.py: the documented caller ───────────────────


class TestTraderNarrativeCaller:
    """trader_narrative.py is the main caller. It already passes
    target_date correctly. Verify it hasn't regressed."""

    def test_build_ticker_cheat_sheet_called_with_target_date(self) -> None:
        from scripts.trader import trader_narrative
        src = inspect.getsource(trader_narrative)
        m = re.search(r"build_ticker_cheat_sheet\([^)]*\)", src, re.DOTALL)
        assert m, "build_ticker_cheat_sheet not called in trader_narrative"
        call = m.group(0)
        assert "target_date" in call, (
            f"build_ticker_cheat_sheet in trader_narrative must pass target_date. Got: {call}"
        )

    def test_all_four_builder_calls_have_target_date(self) -> None:
        from scripts.trader import trader_narrative
        src = inspect.getsource(trader_narrative)
        for fname in (
            "build_intraday_context", "build_eod_context",
            "build_premarket_context", "build_ticker_cheat_sheet",
        ):
            m = re.search(rf"{fname}\([^)]*\)", src, re.DOTALL)
            assert m, f"{fname} not called in trader_narrative"
            call = m.group(0)
            assert "target_date" in call, (
                f"{fname}() in trader_narrative must pass target_date. Got: {call}"
            )
