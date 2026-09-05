"""The three refusals in `scripts/parity/capture_nt8.py`, and the cap analysis.

None of these touch NinjaTrader. `_check` is a pure function over the bridge
response, which is the whole reason it is a separate function: the failure modes
it guards are exactly the ones that cannot be reproduced on demand against a
live Analyzer.
"""

import json
import pathlib

import numpy as np
import pandas as pd
import pytest

from scripts.parity.capture_nt8 import (
    DEFAULT_MAX_TRADES, Nt8CaptureError, TRADE_FIELDS, _check, _write_csv,
)
from scripts.trading_framework.reporting.trade_ordinal import (
    MIN_SAMPLE_FOR_A_CAP, ordinal_stats, render_trade_ordinal, suggested_cap,
)


def _trade(i=0):
    return {"instrument": "MNQ DEC26", "marketPosition": "Long", "quantity": 1,
            "entryPrice": 20000 + i, "exitPrice": 20010 + i,
            "entryTime": "2026-07-01T10:0{}:00".format(i % 10),
            "exitTime": "2026-07-01T10:1{}:00".format(i % 10),
            "profitCurrency": 20.0, "profitPoints": 10.0,
            "exitName": "Profit target"}


# --------------------------------------------------------------------------- #
# Refusal 1: truncation
# --------------------------------------------------------------------------- #

def test_a_full_trade_list_is_refused_as_possibly_truncated():
    """`len(trades) == maxTrades` cannot be told from a capped list.

    The MCP tool's own default is 50. A 300-trade backtest returns 50 and looks
    complete; parity recall against it is a false red that reads as a strategy
    defect.
    """
    resp = {"trades": [_trade(i) for i in range(50)], "effectiveStrategy": "B"}
    with pytest.raises(Nt8CaptureError) as e:
        _check(resp, "B", 50)
    assert "TRUNCATED" in str(e.value)
    assert "--nt8-max-trades" in str(e.value)


def test_one_below_the_cap_is_accepted():
    resp = {"trades": [_trade(i) for i in range(49)], "effectiveStrategy": "B"}
    assert len(_check(resp, "B", 50)) == 49


def test_the_default_cap_is_far_above_the_mcp_tool_default():
    """50 is the trap; asking for 50 by default would walk straight into it."""
    assert DEFAULT_MAX_TRADES >= 1000


# --------------------------------------------------------------------------- #
# Refusal 2: attribution -- the SA window is REUSED between calls
# --------------------------------------------------------------------------- #

def test_a_run_of_a_different_strategy_is_refused():
    resp = {"trades": [_trade()], "effectiveStrategy": "_McpTestBot"}
    with pytest.raises(Nt8CaptureError) as e:
        _check(resp, "BBMRReversionBot", 5000)
    msg = str(e.value)
    assert "_McpTestBot" in msg and "BBMRReversionBot" in msg
    assert "REUSED" in msg


def test_a_matching_echo_is_accepted():
    resp = {"trades": [_trade()], "effectiveStrategy": "BBMRReversionBot"}
    assert len(_check(resp, "BBMRReversionBot", 5000)) == 1


def test_a_missing_echo_does_not_block():
    """An older bridge may not echo. Absent is not the same as WRONG."""
    resp = {"trades": [_trade()]}
    assert len(_check(resp, "BBMRReversionBot", 5000)) == 1


# --------------------------------------------------------------------------- #
# Refusal 3: the profile / globals
# --------------------------------------------------------------------------- #

def test_a_bridge_error_is_surfaced_with_its_reason():
    resp = {"error": "global mismatch",
            "globalMismatches": ["GlobalMergePolicy is MergeBackAdjusted, "
                                 "profile requires MergeNonBackAdjusted"]}
    with pytest.raises(Nt8CaptureError) as e:
        _check(resp, "B", 5000)
    assert "MergeBackAdjusted" in str(e.value)


def test_an_empty_trade_list_without_an_error_is_not_refused():
    """Zero trades is a RESULT. Refusing it would hide a real "took no trades"."""
    assert _check({"trades": [], "effectiveStrategy": "B"}, "B", 5000) == []


# --------------------------------------------------------------------------- #
# The written fixture keeps NT8's own field names
# --------------------------------------------------------------------------- #

def test_the_csv_uses_nt8s_own_field_names(tmp_path):
    """normalise_trades must keep being exercised against the real payload."""
    out = tmp_path / "t.csv"
    _write_csv([_trade(), _trade(1)], out)
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header.split(",") == list(TRADE_FIELDS)
    assert "marketPosition" in header and "exitName" in header


def test_an_unexpected_extra_field_does_not_break_the_writer(tmp_path):
    out = tmp_path / "t.csv"
    t = _trade()
    t["somethingNew"] = 1
    _write_csv([t], out)
    assert "somethingNew" not in out.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Where to cap -- the analysis that replaces the frozen cap
# --------------------------------------------------------------------------- #

def _day(pnls, hour=10):
    """One trading day whose Nth trade has P&L pnls[N-1]."""
    times = [pd.Timestamp("2026-07-{:02d} {}:{:02d}".format(d, hour, 5 * i))
             for d in range(1, 21) for i in range(len(pnls))]
    return pd.DataFrame({
        "entry_time": pd.DatetimeIndex(times).tz_localize("America/New_York"),
        "total_pnl_usd": pnls * 20,
    })


def test_the_nth_trade_is_measured_separately_from_the_total():
    df = _day([100.0, 50.0, -200.0])
    s = ordinal_stats(df, scope="day")
    assert list(s["n"]) == [1, 2, 3]
    assert s.loc[s["n"] == 3, "EV_R_at_n"].iloc[0] < 0
    assert s.loc[s["n"] == 1, "EV_R_at_n"].iloc[0] > 0
    # cumulative rows accumulate
    assert s["trades_upto_n"].iloc[-1] == 60


def test_a_losing_third_trade_produces_a_cap_of_two():
    s = ordinal_stats(_day([100.0, 50.0, -200.0]), scope="day")
    cap = suggested_cap(s)
    assert cap["cap"] == 2
    assert cap["trustworthy"] is True


def test_a_cap_from_a_thin_sample_is_flagged_untrustworthy():
    """A cap chosen from a handful of trades is noise wearing a number."""
    df = pd.DataFrame({
        "entry_time": pd.DatetimeIndex(
            [pd.Timestamp("2026-07-01 10:00"), pd.Timestamp("2026-07-01 10:05")]
        ).tz_localize("America/New_York"),
        "total_pnl_usd": [100.0, -50.0],
    })
    cap = suggested_cap(ordinal_stats(df, scope="day"))
    assert cap["trustworthy"] is False
    assert str(MIN_SAMPLE_FOR_A_CAP) in cap["reason"]


def test_a_system_with_no_positive_ordinal_reports_cap_zero():
    cap = suggested_cap(ordinal_stats(_day([-10.0, -20.0]), scope="day"))
    assert cap["cap"] == 0
    assert "no ordinal has positive" in cap["reason"]


def test_the_report_names_both_scopes_and_stays_ascii():
    """cp1252 consoles cannot encode an em-dash or a <= sign."""
    out = render_trade_ordinal(_day([100.0, 50.0, -200.0]))
    assert "per calendar day" in out and "per session" in out
    bad = sorted({c for c in out if ord(c) > 127})
    assert not bad, bad


def test_the_report_states_a_reason_rather_than_rendering_empty():
    assert "Not available" in render_trade_ordinal(pd.DataFrame())


def test_a_frame_without_pnl_is_refused_not_silently_zeroed():
    df = pd.DataFrame({"entry_time": pd.DatetimeIndex(
        [pd.Timestamp("2026-07-01 10:00")]).tz_localize("America/New_York")})
    assert ordinal_stats(df).empty
    assert "Not available" in render_trade_ordinal(df)
