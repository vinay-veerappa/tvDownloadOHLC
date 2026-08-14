"""Tests for audit §2.5 (Schwab hub availability) and §2.6
(unified default model) in `scripts/trader/briefing_core.py` and
`scripts/trader/config_loader.py`.

§2.5 covers the Schwab quote failure pollution. The fix:
  - Added `_is_schwab_hub_reachable()` to `briefing_core.py` —
    a 0.25s TCP probe of 127.0.0.1:8080. If the hub is offline,
    the entire Schwab auth + quote path is skipped.
  - Replaced bare `pass` in the inner quote-fetch `except` blocks
    with `log.debug(...)` so failures are visible at DEBUG level
    without polluting INFO-level output.

§2.6 covers the inconsistent default models. The fix:
  - Added a `llm` section to `narrative_stats.yaml` exposing
    `default_model` and `fallback_model`.
  - `config_loader.py` exposes `get_llm_config()` that returns
    this section.
  - Both `daily_narrative.py` and `trader_narrative.py` import
    from there instead of hardcoding.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from unittest import mock

import pytest


# ── §2.5 Schwab hub availability probe ────────────────────────────


class TestSchwabHubReachability:
    """`_is_schwab_hub_reachable()` returns True if something is
    listening on 127.0.0.1:8080, False otherwise."""

    def test_returns_true_when_socket_accepts(self) -> None:
        from scripts.trader.briefing_core import _is_schwab_hub_reachable
        # Spin up a real socket on 8080; the probe should reach it.
        # Use port 0 so the OS picks a free port, then verify the
        # behaviour with port 8080 explicitly.
        # We use a mock instead: replace socket.create_connection
        # to return a context-manager that "succeeds".
        with mock.patch.object(
            socket, "create_connection", return_value=mock.MagicMock()
        ) as cc:
            assert _is_schwab_hub_reachable() is True
            # The probe must have targeted 127.0.0.1:8080 with a
            # short timeout.
            args, kwargs = cc.call_args
            assert args[0] == ("127.0.0.1", 8080)
            assert kwargs["timeout"] <= 1.0

    def test_returns_false_when_oserror_raised(self) -> None:
        from scripts.trader.briefing_core import _is_schwab_hub_reachable
        with mock.patch.object(
            socket, "create_connection", side_effect=OSError("refused")
        ):
            assert _is_schwab_hub_reachable() is False

    def test_returns_false_when_timeout(self) -> None:
        from scripts.trader.briefing_core import _is_schwab_hub_reachable
        with mock.patch.object(
            socket, "create_connection", side_effect=socket.timeout()
        ):
            assert _is_schwab_hub_reachable() is False

    def test_probe_is_fast(self) -> None:
        """The probe must complete in well under a second so it
        doesn't slow down the narrative path when the hub is up."""
        from scripts.trader.briefing_core import _is_schwab_hub_reachable
        import time
        with mock.patch.object(
            socket, "create_connection", return_value=mock.MagicMock()
        ):
            t0 = time.monotonic()
            _is_schwab_hub_reachable()
            elapsed = time.monotonic() - t0
        # The mock returns instantly, so this is just a sanity
        # bound on the call overhead. The real probe uses a 0.25s
        # socket timeout — the mock is well under that.
        assert elapsed < 0.1


class TestGetIntermarketQuotesHubDown:
    """When the Schwab hub is unreachable, `get_intermarket_quotes()`
    must not raise, must not call schwab.auth, and must still return
    a dict with all 5 quote slots (filled by the yfinance fallback
    or left as {None, None})."""

    def test_hub_down_skips_schwab_auth(self) -> None:
        from scripts.trader import briefing_core
        with mock.patch.object(
            briefing_core, "_is_schwab_hub_reachable", return_value=False
        ):
            with mock.patch(
                "schwab.auth.easy_client", create=True
            ) as easy_client:
                # Stub yfinance so we don't hit the network.
                with mock.patch.dict(sys.modules, {"yfinance": mock.MagicMock()}):
                    quotes = briefing_core.get_intermarket_quotes()
        # schwab.auth.easy_client must NOT have been called.
        assert easy_client.call_count == 0
        # The function must return a dict with all 5 expected keys.
        for key in ("brent", "tnx", "dxy", "vix", "vvix"):
            assert key in quotes
            assert "price" in quotes[key]
            assert "change" in quotes[key]

    def test_hub_down_does_not_log_traceback(self) -> None:
        """The audit's headline issue was a wall of tracebacks in
        the console. The fix downgrades the noise to DEBUG level
        and skips the Schwab path entirely on hub-down — so the
        path must NOT log at WARNING or ERROR level when the hub
        is down (assuming yfinance is also stubbed or fine)."""
        import logging
        from scripts.trader import briefing_core
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        briefing_core.log.addHandler(handler)
        old_level = briefing_core.log.level
        briefing_core.log.setLevel(logging.DEBUG)
        try:
            with mock.patch.object(
                briefing_core, "_is_schwab_hub_reachable", return_value=False
            ):
                with mock.patch.dict(sys.modules, {"yfinance": mock.MagicMock()}):
                    briefing_core.get_intermarket_quotes()
        finally:
            briefing_core.log.removeHandler(handler)
            briefing_core.log.setLevel(old_level)
        # No WARNING or ERROR records on the hub-down path.
        bad = [r for r in records if r.levelno >= logging.WARNING]
        assert not bad, (
            "Hub-down path should not log at WARNING+; "
            f"got: {[r.getMessage() for r in bad]}"
        )


# ── §2.6 Unified default model ───────────────────────────────────


class TestUnifiedDefaultModel:
    """The audit's §2.6 fix: both `daily_narrative.py` and
    `trader_narrative.py` must read their default model from a
    single source of truth, exposed via `config_loader.get_llm_config`.
    """

    def test_config_loader_exposes_llm_config(self) -> None:
        from scripts.trader.config_loader import get_llm_config
        cfg = get_llm_config()
        # Must have at least a default_model key.
        assert "default_model" in cfg
        assert isinstance(cfg["default_model"], str)
        assert cfg["default_model"]  # non-empty

    def test_daily_narrative_default_model_matches_config(self) -> None:
        from scripts.trader import daily_narrative
        from scripts.trader.config_loader import get_llm_config
        # The module-level DEFAULT_MODEL constant must equal the
        # config value, OR be the legacy literal that we are
        # migrating away from. Pin the value once the migration
        # is complete.
        cfg = get_llm_config()
        assert daily_narrative.DEFAULT_MODEL == cfg["default_model"], (
            f"daily_narrative.DEFAULT_MODEL={daily_narrative.DEFAULT_MODEL!r} "
            f"!= config default_model={cfg['default_model']!r}"
        )

    def test_trader_narrative_default_model_matches_config(self) -> None:
        from scripts.trader import trader_narrative
        from scripts.trader.config_loader import get_llm_config
        cfg = get_llm_config()
        expected = cfg.get("default_trader_model") or cfg["default_model"]
        assert trader_narrative.DEFAULT_MODEL == expected, (
            f"trader_narrative.DEFAULT_MODEL={trader_narrative.DEFAULT_MODEL!r} "
            f"!= config expected={expected!r}"
        )

    def test_fallback_model_also_unified(self) -> None:
        from scripts.trader import daily_narrative
        from scripts.trader import trader_narrative
        from scripts.trader.config_loader import get_llm_config
        cfg = get_llm_config()
        # If a fallback_model is exposed in config, both modules
        # must agree on it. trader_narrative has an extra
        # LOCAL_FALLBACK_MODEL (offline-only), which is fine.
        if "fallback_model" in cfg:
            assert daily_narrative.FALLBACK_MODEL == cfg["fallback_model"]
            assert trader_narrative.FALLBACK_MODEL == cfg["fallback_model"]

    def test_config_default_model_is_reasonable(self) -> None:
        """Sanity-check the chosen model: must be a non-empty
        string that doesn't look like a placeholder."""
        from scripts.trader.config_loader import get_llm_config
        cfg = get_llm_config()
        model = cfg["default_model"]
        assert "TODO" not in model.upper()
        assert "FIXME" not in model.upper()
        assert "XXX" not in model.upper()
        assert model != "model-name-here"
