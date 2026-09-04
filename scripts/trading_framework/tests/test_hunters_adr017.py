import pandas as pd


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.strategies.failed_auction.core.failed_auction import FailedAuctionStrategy
from scripts.strategies.reversal.core.six_am_reversal import SixAMReversalStrategy
from scripts.strategies.vwap_reclaim.core.vwap_reclaim import VWAPReclaimStrategy


REQUIRED_COLS = ["signal_time", "direction", "entry_price", "stop_price", "target1_price"]


def _build_1m_ohlc(start: str, periods: int = 120, with_volume: bool = True, volume_value: float = 1000.0) -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=periods, freq="min")
    base = pd.Series(range(periods), index=idx, dtype="float64")

    df = pd.DataFrame(
        {
            "open": 100.0 + (base * 0.01),
            "high": 100.2 + (base * 0.01),
            "low": 99.8 + (base * 0.01),
            "close": 100.0 + (base * 0.01),
        },
        index=idx,
    )
    if with_volume:
        df["volume"] = volume_value
    return df


def test_vwap_reclaim_missing_volume_returns_empty_schema():
    df = _build_1m_ohlc("2026-01-15 09:30:00", with_volume=False)

    strategy = VWAPReclaimStrategy(ticker="NQ1")
    out = strategy.hunt(df)

    assert out.empty
    # CONTAINMENT, not equality. This asserted `list(out.columns) ==
    # REQUIRED_COLS` and had been red since two hunters started returning
    # `model_name` and `risk_pts` on the empty path. Exact equality punishes a
    # hunter for adding a useful field, while what actually matters is what the
    # engine consumes: `VectorizedBacktester._standard_signal_columns` selects
    # the canonical five and ignores the rest, so extra columns are harmless and
    # a MISSING canonical column is the real failure.
    assert set(REQUIRED_COLS).issubset(out.columns), (
        "empty schema is missing canonical columns: "
        f"{sorted(set(REQUIRED_COLS) - set(out.columns))}")


def test_every_hunter_agrees_on_the_canonical_empty_schema():
    """The three hunters returned 7, 7 and 5 columns on their empty paths.

    Extra fields are fine; disagreeing about the canonical five would not be, so
    that is what is pinned. Written as one test over all three because a
    per-hunter assertion is what let them drift apart.
    """
    df = _build_1m_ohlc("2026-01-15 09:30:00", with_volume=True)
    for cls in (VWAPReclaimStrategy, FailedAuctionStrategy, SixAMReversalStrategy):
        out = cls(ticker="NQ1").hunt(df)
        assert set(REQUIRED_COLS).issubset(out.columns), cls.__name__


def test_failed_auction_single_day_no_prior_levels_safe_empty():
    df = _build_1m_ohlc("2026-01-15 09:30:00", with_volume=True)

    strategy = FailedAuctionStrategy(ticker="NQ1")
    out = strategy.hunt(df)

    assert out.empty


def test_six_am_reversal_single_day_no_prior_levels_safe_empty():
    df = _build_1m_ohlc("2026-01-15 06:00:00", with_volume=True)

    strategy = SixAMReversalStrategy(ticker="NQ1")
    out = strategy.hunt(df)

    assert out.empty


def test_vwap_reclaim_low_liquidity_filters_signals():
    df = _build_1m_ohlc("2026-01-15 09:30:00", with_volume=True, volume_value=0.0)

    strategy = VWAPReclaimStrategy(ticker="NQ1")
    out = strategy.hunt(df, params={"min_abs_volume": 1.0})

    assert out.empty
