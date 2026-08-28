"""High-level scanner: replicates the indicator's per-bar flow end to end.

The Pine script, on every bar:
  1. detects the session start (0930-1600 ET by default),
  2. on that bar, reads the previous daily close (``close_day``) and the
     correlated volatility index's previous daily close,
  3. computes zone ladders and draws boxes spanning one day forward.

This module reproduces the computation for every session in a history and
exposes the boxes as a DataFrame suitable for the backtesting engine.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .core import compute_zone_dataframe
from .settlements import build_daily_settlements, session_settlements, vol_index_for_ticker

DEFAULT_DATA_DIR = Path("data")


def load_vol_index(ticker: str, data_dir: str | Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """Best-effort load of the local parquet for the paired volatility index.

    Returns an empty frame if no file exists locally.
    """
    vol_symbol = vol_index_for_ticker(ticker).split(":")[-1]  # VIX, VXN, ...
    path = Path(data_dir) / f"{vol_symbol}_1m.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def daily_from_intraday(intraday: pd.DataFrame) -> pd.DataFrame:
    """Resample intraday OHLCV to daily ET bars for settlement reads."""
    et = (intraday.index.tz_convert("America/New_York")
          if intraday.index.tz is not None
          else intraday.index.tz_localize("America/New_York"))
    df = intraday.copy()
    df.index = et
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    daily = df.resample("1D").agg(agg)
    return daily[daily["close"].notna()]


def scan_expected_volatility(
    intraday: pd.DataFrame,
    ticker: str,
    vol_intraday: pd.DataFrame | None = None,
    session: str = "0930-1600",
    tz: str = "America/New_York",
    toggle: bool = False,
) -> pd.DataFrame:
    """Compute one zone-ladder row per session start.

    Parameters
    ----------
    intraday    : underlying OHLCV frame (tz-aware datetime index).
    ticker      : chart symbol the indicator runs on, e.g. ``"ES1!"`` or ``"NQ1!"``.
    vol_intraday: intraday frame of the correlated volatility index. When
                  omitted, auto-loads from ``data/`` via the market pairing
                  table (ES->VIX, NQ->VXN, CL->OVX, RTY->RVX, VIX->VVIX,
                  GC->GVZ, SI->VXSLV, YM->VXD).
    session/tz  : session window + timezone (Pine input mirrors).
    toggle      : mirror of the Pine open/close toggle.

    Returns
    -------
    DataFrame indexed by session-start timestamp with columns:
      ``day``, ``close_day`` (settlement), ``vix`` (vol index value used),
      plus one column per zone edge: ``res_{m}_top``/``_bottom``/``_mid`` and
      ``sup_{m}_top``/``_bottom``/``_mid`` for m in {0.25, 0.5, 1.0, 1.5}.
    """
    if intraday.index.tz is None:
        raise ValueError("intraday frame must have a tz-aware DatetimeIndex")

    daily_chart = daily_from_intraday(intraday)
    if vol_intraday is None:
        vol_intraday = load_vol_index(ticker)

    if vol_intraday is not None and len(vol_intraday):
        vol_daily = daily_from_intraday(vol_intraday)
        vol_settle = build_daily_settlements(vol_intraday, vol_daily, toggle=toggle)
    else:
        vol_settle = pd.Series(dtype=float, name="settlement")

    chart_settle = build_daily_settlements(intraday, daily_chart, toggle=toggle)

    sess = session_settlements(intraday, daily_chart, session, tz, toggle)
    sess["vix"] = vol_settle.reindex(sess["day"]).to_numpy()

    valid = sess["close_day"].notna() & sess["vix"].notna()
    zones = pd.DataFrame(index=sess.index)
    if valid.any():
        zone_df = compute_zone_dataframe(
            sess.loc[valid, "close_day"].astype(float),
            sess.loc[valid, "vix"].astype(float),
        )
        zones.loc[valid, zone_df.columns] = zone_df

    return pd.concat([sess, zones], axis=1)