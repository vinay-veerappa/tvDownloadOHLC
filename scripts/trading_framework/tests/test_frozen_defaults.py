"""The gate that keeps the frozen defaults frozen.

The defect these exist to prevent, measured 2026-09-05: a single `--ticker NQ1`
run valued a point at $20 in the P&L (core/backtest_engine.py's own table) and
at $2 in the prop-firm simulation (config point_value fallback). Three tables,
two answers, 10x apart, and the $20 figure contradicted ADR-009, which had
already decided micros. No test compared them, so all 315 passed either way.
"""

import inspect
import json
import pathlib
import re
import subprocess

import numpy as np
import pandas as pd
import pytest

from scripts.libs_py.data.session_tagger import tag_session_windows
from scripts.trading_framework.config.defaults import (
    SessionWindow, assert_sessions_partition, load_trading_defaults,
    resolve_instrument, session_windows, tradeable_sessions,
)
from scripts.trading_framework.core.backtest_engine import VectorizedBacktester
from scripts.trading_framework.core.nt8_parity_backtester import NT8ParityBacktester
from scripts.trading_framework.reporting.session_breakdown import (
    label_trades_by_session, render_session_breakdown, session_stats,
)

REPO = pathlib.Path(__file__).resolve().parents[3]

# Matches a literal NQ multiplier declaration, e.g. `"NQ1": 20.0` or `'MNQ': 2.0`.
NQ_TABLE = re.compile(r"""["']M?NQ1?["']\s*:\s*(?:20|2)\.0""")


def test_the_document_loads_and_validates():
    d = load_trading_defaults()
    assert d["schemaVersion"] == 1
    assert d["instruments"]["default"] == "MNQ"


@pytest.mark.parametrize("ticker,symbol,pv", [
    ("NQ1", "MNQ", 2.0), ("nq1", "MNQ", 2.0), ("NQ1!", "MNQ", 2.0),
    ("MNQ", "MNQ", 2.0), ("ES1", "MES", 5.0), ("MES", "MES", 5.0),
    ("NQ", "NQ", 20.0), ("ES", "ES", 50.0),
])
def test_a_data_ticker_resolves_to_the_contract_actually_traded(ticker, symbol, pv):
    """NQ1 names a PRICE SERIES; MNQ names the CONTRACT. Conflating them is the bug."""
    inst = resolve_instrument(ticker)
    assert (inst.symbol, inst.point_value) == (symbol, pv)


def test_an_unknown_instrument_raises_rather_than_defaulting():
    """`point_value.get(ticker, 2.0)` is what made two answers possible."""
    with pytest.raises(KeyError) as e:
        resolve_instrument("CL1")
    assert "unknown instrument" in str(e.value)


def test_an_empty_ticker_raises():
    for bad in ("", None, "   "):
        with pytest.raises(ValueError):
            resolve_instrument(bad)


def test_tick_value_is_consistent_with_tick_size_times_point_value():
    for sym, spec in load_trading_defaults()["instruments"]["table"].items():
        assert spec["tickValue"] == pytest.approx(
            spec["tickSize"] * spec["pointValue"]), sym


def test_the_default_instrument_is_a_micro():
    assert resolve_instrument(
        load_trading_defaults()["instruments"]["default"]).is_micro


# --------------------------------------------------------------------------- #
# THE REGRESSION TEST FOR THE 10x DEFECT
# --------------------------------------------------------------------------- #

def test_neither_engine_carries_its_own_multiplier_table():
    """The test whose absence let a 10x disagreement live inside one run."""
    for eng in (VectorizedBacktester, NT8ParityBacktester):
        e = eng()
        assert not hasattr(e, "tick_multipliers"), eng.__name__
        assert not hasattr(e, "multipliers"), eng.__name__


def test_no_module_carries_a_second_point_value_table():
    hits = []
    for f in (REPO / "scripts" / "trading_framework").rglob("*.py"):
        if "tests" in f.parts or "__pycache__" in f.parts:
            continue
        if NQ_TABLE.search(f.read_text(encoding="utf-8", errors="replace")):
            hits.append(f.relative_to(REPO).as_posix())
    assert not hits, (
        "these declare their own NQ multiplier; the only table is "
        "config/trading_defaults.json: {}".format(hits))


def test_the_scan_above_can_actually_find_a_table():
    """Negative control: otherwise the scan passes on a rotted regex."""
    assert NQ_TABLE.search('self.m = {"NQ1": 20.0, "MNQ": 2.0}')
    assert not NQ_TABLE.search("pv = resolve_instrument(ticker).point_value")


def test_both_engines_refuse_a_run_that_did_not_declare_its_ticker():
    """Section 2.7 marks this ENFORCED. It was a defaulting .get() in both."""
    for mod in (VectorizedBacktester, NT8ParityBacktester):
        src = inspect.getsource(mod)
        assert "must carry" in src, mod.__name__
        assert "risk_params.get('ticker', 'NQ1')" not in src, mod.__name__
        assert 'risk_params.get("ticker", "NQ1")' not in src, mod.__name__


# --------------------------------------------------------------------------- #
# Sessions -- the partition property is what makes the breakdown sum
# --------------------------------------------------------------------------- #

def test_the_session_windows_tile_the_day_exactly_once():
    assert_sessions_partition(session_windows())


def test_the_window_spans_sum_to_a_full_day():
    total = 0
    for w in session_windows():
        span = (w.end_min - w.start_min) % (24 * 60)
        total += span or 24 * 60
    assert total == 24 * 60, total


def test_an_overlapping_partition_is_refused():
    """Negative control. nqstats' own set overlaps: RTH, IB and NY_AM at 09:30."""
    with pytest.raises(ValueError, match="is in both"):
        assert_sessions_partition([SessionWindow("A", 0, 700),
                                   SessionWindow("B", 600, 1440)])


def test_a_gapped_partition_is_refused():
    """The worse failure: trades vanish and the total still looks right."""
    with pytest.raises(ValueError, match="belong to no session"):
        assert_sessions_partition([SessionWindow("A", 0, 600),
                                   SessionWindow("B", 700, 1440)])


def test_the_six_sessions_the_bot_trades_are_all_present():
    names = {w.name for w in session_windows()}
    for s in ("GLOBEX", "ASIA", "LONDON", "NY_AM", "NY_LUNCH", "NY_PM"):
        assert s in names, s
    assert "CLOSED" not in tradeable_sessions()


def test_the_wrapping_session_actually_wraps():
    asia = next(w for w in session_windows() if w.name == "ASIA")
    assert asia.wraps
    assert asia.contains_minute(23 * 60)
    assert asia.contains_minute(60)
    assert not asia.contains_minute(3 * 60)


def test_every_minute_of_a_real_day_gets_exactly_one_label():
    idx = pd.date_range("2026-07-01 00:00", periods=24 * 60, freq="1min",
                        tz="America/New_York")
    df = tag_session_windows(
        pd.DataFrame({"c": np.arange(len(idx))}, index=idx), session_windows())
    assert df["session_name"].value_counts().sum() == 24 * 60
    assert df["session_name"].isna().sum() == 0


# --------------------------------------------------------------------------- #
# The per-session report
# --------------------------------------------------------------------------- #

def _trades():
    return pd.DataFrame({
        "entry_time": pd.to_datetime([
            "2026-07-01 21:00", "2026-07-01 03:00", "2026-07-01 10:00",
            "2026-07-01 12:00", "2026-07-01 14:00", "2026-07-01 14:30",
        ]).tz_localize("America/New_York"),
        "total_pnl_usd": [100.0, -50.0, 200.0, -25.0, 75.0, -100.0],
        "total_points": [50.0, -25.0, 100.0, -12.5, 37.5, -50.0],
    })


def test_trades_are_labelled_by_the_session_they_entered_in():
    assert list(label_trades_by_session(_trades())) == [
        "ASIA", "LONDON", "NY_AM", "NY_LUNCH", "NY_PM", "NY_PM"]


def test_the_session_rows_sum_to_the_total():
    s = session_stats(_trades())
    per = s[s["session"] != "ALL"]
    total = s[s["session"] == "ALL"].iloc[0]
    assert per["trades"].sum() == total["trades"]
    assert per["pnl_$"].sum() == pytest.approx(total["pnl_$"])


def test_the_report_states_a_reason_rather_than_rendering_empty():
    assert "Not available" in render_session_breakdown(pd.DataFrame())


def test_sessions_with_no_trades_are_named_as_zero_not_omitted_silently():
    out = render_session_breakdown(_trades())
    assert "No trades in" in out and "GLOBEX" in out


# --------------------------------------------------------------------------- #
# Cross-consumer consistency
# --------------------------------------------------------------------------- #

def test_the_nt8_block_agrees_with_the_frozen_sa_profile():
    """One value in two files that disagree is the drift this removes."""
    prof = json.loads((REPO / "scripts" / "parity" / "backtest_profile.json")
                      .read_text(encoding="utf-8"))
    nt8 = load_trading_defaults()["nt8"]
    assert prof["requireGlobals"]["GlobalMergePolicy"] == nt8["globalMergePolicy"]
    assert (prof["requireGlobals"]["IsTickReplayEnabled"] == "True") is \
        nt8["isTickReplayEnabled"]
    t = prof["strategyTemplate"]
    assert t["OrderFillResolution"] == nt8["orderFillResolution"]
    assert t["IncludeCommission"] is nt8["includeCommission"]
    assert t["Calculate"] == nt8["calculate"]
    assert t["ExitOnSessionCloseSeconds"] == nt8["exitOnSessionCloseSeconds"]


def test_the_defaults_document_is_tracked_by_git():
    rel = "scripts/trading_framework/config/trading_defaults.json"
    p = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                       cwd=REPO, capture_output=True)
    assert p.returncode == 0, "{} is not tracked".format(rel)
