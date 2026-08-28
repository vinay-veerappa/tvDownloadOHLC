"""
Expected Volatility [Session] Engine
====================================
Python port of "Expected Volatility [Session]" (ShadowOfCrimson, MPL 2.0)
https://www.tradingview.com/script/dsXscaGY-Expected-Volatility/

Replicates the session zone ladders (0.25/0.5/1.0/1.5 std-dev resistance +
support around the previous daily close, scaled by a correlated volatility
index) for the backtesting engine.
"""

from .core import (
    BOX_MULTIPLIERS,
    compute_zone_dataframe,
    compute_zone_ladders,
    get_volatility,
    is_session_start,
    session_start_times,
)
from .settlements import (
    MARKET_VOL_PAIRS,
    build_daily_settlements,
    map_ticker_family,
    session_settlements,
    vol_index_for_ticker,
)
from .scanner import daily_from_intraday, load_vol_index, scan_expected_volatility
from .backtest import box_sessions, touch_stats, zone_edges

__all__ = [
    "BOX_MULTIPLIERS",
    "compute_zone_dataframe",
    "compute_zone_ladders",
    "get_volatility",
    "is_session_start",
    "session_start_times",
    "MARKET_VOL_PAIRS",
    "build_daily_settlements",
    "map_ticker_family",
    "session_settlements",
    "vol_index_for_ticker",
    "daily_from_intraday",
    "load_vol_index",
    "scan_expected_volatility",
    "box_sessions",
    "touch_stats",
    "zone_edges",
]