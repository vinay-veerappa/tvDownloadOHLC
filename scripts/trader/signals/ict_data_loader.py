"""ICT Data Loader for the Trader Narrative Engine
===================================================

Thin data-access layer that reads ICT features from the derived parquet
files produced by ``scripts.context.compute_ict_features``.

Design goals
------------
1. **Freshness-aware**: checks if the parquet is stale and triggers an
   incremental refresh via the compute pipeline when needed.
2. **Graceful fallback**: if the parquet is missing or refresh fails,
   falls back to live computation from 1m/1d parquet (the old
   ``compute_ict_from_htf`` behavior).
3. **Single import surface**: narrative code imports from here only —
   no direct parquet reads or ict_engine calls in the narrative modules.

Usage
-----
::

    from scripts.trader.signals.ict_data_loader import (
        load_htf_levels,
        load_ipda,
        load_kz_pivots,
        load_gaps,
        load_imbalances,
        load_active_silver_bullet,
        load_active_macro,
        load_ict_context,  # drop-in replacement for compute_ict_from_htf
    )
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

_REPO = Path(__file__).parent.parent.parent.parent
_ICT_DIR = _REPO / "data" / "derived" / "ICT"

# Freshness thresholds (how stale before we trigger a refresh)
_STALE_DAYS_DAILY = 1      # daily parquets: refresh if >1 day old
_STALE_MINUTES_INTRADAY = 5  # intraday parquets: refresh if >5 min old

# ET timezone
try:
    import pytz
    ET = pytz.timezone("America/New_York")
except ImportError:
    ET = None


# ═══════════════════════════════════════════════════════════════════════
#  Freshness + Refresh
# ═══════════════════════════════════════════════════════════════════════

def _now_et() -> datetime:
    """Current time in ET."""
    if ET:
        return datetime.now(ET)
    return datetime.utcnow()


def _is_stale_daily(path: Path) -> bool:
    """Check if a daily parquet is stale (last row >1 day old)."""
    if not path.exists():
        return True
    try:
        df = pd.read_parquet(path)
        if df.empty:
            return True
        # Check trading_date column
        if "trading_date" in df.columns:
            last_date = pd.to_datetime(df["trading_date"]).max()
            if hasattr(last_date, "date"):
                last_date = last_date.date() if hasattr(last_date, "date") else last_date
            else:
                last_date = pd.to_datetime(last_date).date()
        else:
            last_date = df.index.max()
            if hasattr(last_date, "date"):
                last_date = last_date.date()

        today = _now_et().date()
        return (today - last_date).days > _STALE_DAYS_DAILY
    except Exception:
        return True


def _is_stale_intraday(path: Path) -> bool:
    """Check if an intraday parquet is stale (last bar >5 min old)."""
    if not path.exists():
        return True
    try:
        df = pd.read_parquet(path)
        if df.empty:
            return True
        last_bar = df.index.max()
        if hasattr(last_bar, "to_pydatetime"):
            last_bar = last_bar.to_pydatetime()
        now = _now_et().replace(tzinfo=None)
        age = (now - last_bar).total_seconds() / 60
        return age > _STALE_MINUTES_INTRADAY
    except Exception:
        return True


def _trigger_refresh(symbol: str, feature: str) -> bool:
    """Trigger an incremental refresh of one feature for one symbol.

    Returns True if refresh succeeded (or was not needed), False on failure.
    """
    try:
        import subprocess
        cmd = [
            str(_REPO / ".venv" / "Scripts" / "python.exe"),
            "-m", "scripts.context.compute_ict_features",
            "--symbols", symbol,
            "--features", feature,
            "--incremental",
        ]
        log.info("[ict_loader] Triggering refresh: %s/%s", symbol, feature)
        result = subprocess.run(
            cmd, cwd=str(_REPO), capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            log.warning("[ict_loader] Refresh failed: %s", result.stderr[:200])
            return False
        return True
    except Exception as e:
        log.warning("[ict_loader] Refresh error: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════
#  Parquet Loaders
# ═══════════════════════════════════════════════════════════════════════

def load_htf_levels(symbol: str, auto_refresh: bool = True) -> pd.DataFrame:
    """Load HTF levels (PDH/PDL/PWH/PWL/PMH/PML) from parquet.

    Returns DataFrame with columns:
        trading_date, symbol, pdh, pdl, pdm, pwh, pwl, pwm, pmh, pml, pmm
    Empty DataFrame on failure.
    """
    path = _ICT_DIR / f"{symbol}_htf_levels.parquet"
    if auto_refresh and _is_stale_daily(path):
        _trigger_refresh(symbol, "htf_levels")
    try:
        return pd.read_parquet(path)
    except Exception as e:
        log.warning("[ict_loader] htf_levels load failed: %s", e)
        return pd.DataFrame()


def load_ipda(symbol: str, auto_refresh: bool = True) -> pd.DataFrame:
    """Load IPDA 20/40/60 ranges from parquet.

    Returns DataFrame with columns:
        trading_date, symbol,
        ipda20_high, ipda20_low, ipda20_eq, ipda20_pct,
        ipda40_*, ipda60_*
    Empty DataFrame on failure.
    """
    path = _ICT_DIR / f"{symbol}_ipda.parquet"
    if auto_refresh and _is_stale_daily(path):
        _trigger_refresh(symbol, "ipda")
    try:
        return pd.read_parquet(path)
    except Exception as e:
        log.warning("[ict_loader] ipda load failed: %s", e)
        return pd.DataFrame()


def load_kz_pivots(symbol: str, auto_refresh: bool = True) -> pd.DataFrame:
    """Load killzone pivots from parquet.

    Returns DataFrame with columns:
        trading_date, symbol,
        asia_high, asia_low, asia_mid, asia_range,
        london_high, london_low, london_mid, london_range,
        nyam_high, nyam_low, nyam_mid, nyam_range
    Empty DataFrame on failure.
    """
    path = _ICT_DIR / f"{symbol}_kz_pivots.parquet"
    if auto_refresh and _is_stale_daily(path):
        _trigger_refresh(symbol, "kz_pivots")
    try:
        return pd.read_parquet(path)
    except Exception as e:
        log.warning("[ict_loader] kz_pivots load failed: %s", e)
        return pd.DataFrame()


def load_gaps(symbol: str, auto_refresh: bool = True) -> pd.DataFrame:
    """Load NWOG/NDOG/RTH gaps from parquet.

    Returns DataFrame with columns:
        session_date, symbol, gap_type, open_time, close_time,
        open_price, close_price, gap_high, gap_low, gap_size, gap_ce,
        filled, fill_time, fill_price
    Empty DataFrame on failure.
    """
    path = _ICT_DIR / f"{symbol}_gaps.parquet"
    if auto_refresh and _is_stale_daily(path):
        _trigger_refresh(symbol, "gaps")
    try:
        return pd.read_parquet(path)
    except Exception as e:
        log.warning("[ict_loader] gaps load failed: %s", e)
        return pd.DataFrame()


def load_imbalances(
    symbol: str,
    timeframe: str = "5m",
    auto_refresh: bool = True,
    session_date: date | None = None,
) -> pd.DataFrame:
    """Load FVG + VI imbalances from parquet.

    Parameters
    ----------
    symbol : str
    timeframe : str
        One of "5m", "15m", "1h", "4h".
    auto_refresh : bool
        If True, trigger incremental refresh if stale.
    session_date : date | None
        If provided, filter to only this logical trading date.

    Returns DataFrame with columns:
        bar_time (index), symbol, timeframe, logical_date,
        fvg_type, fvg_top, fvg_bottom, fvg_low, fvg_high, fvg_finalized_time,
        vi_type, vi_top, vi_bottom, vi_finalized_time
    Empty DataFrame on failure.
    """
    path = _ICT_DIR / f"{symbol}_imbalance_{timeframe}.parquet"
    if auto_refresh and _is_stale_intraday(path):
        _trigger_refresh(symbol, "imbalance")
    try:
        df = pd.read_parquet(path)
        if session_date is not None and not df.empty and "logical_date" in df.columns:
            df = df[df["logical_date"] == session_date]
        return df
    except Exception as e:
        log.warning("[ict_loader] imbalance load failed: %s", e)
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════
#  Time-Based Lookups (Silver Bullets + Macros)
# ═══════════════════════════════════════════════════════════════════════

def load_active_silver_bullet(now_et: datetime | None = None) -> dict[str, Any]:
    """Check if current time is inside a Silver Bullet window.

    Returns dict:
        active: bool
        name: str (e.g. "ny_am_sb") or None
        window: str (e.g. "10:00-11:00") or None
        next_window: str (name of next SB) or None
        next_time: str (ETA of next SB) or None
    """
    from scripts.libs_py.ict_engine import SILVER_BULLETS
    from datetime import time as dt_time

    if now_et is None:
        now_et = _now_et()
    t = now_et.time()

    result: dict[str, Any] = {"active": False, "name": None, "window": None,
                               "next_window": None, "next_time": None}

    # Check current
    for name, (start_str, end_str) in SILVER_BULLETS.items():
        start_t = dt_time(*map(int, start_str.split(":")))
        end_t = dt_time(*map(int, end_str.split(":")))
        if start_t <= t <= end_t:
            result["active"] = True
            result["name"] = name
            result["window"] = f"{start_str}-{end_str}"
            break

    # Find next SB if not active
    if not result["active"]:
        upcoming = []
        for name, (start_str, end_str) in SILVER_BULLETS.items():
            start_t = dt_time(*map(int, start_str.split(":")))
            if t < start_t:
                upcoming.append((start_t, name, start_str))
        if upcoming:
            upcoming.sort()
            _, name, start_str = upcoming[0]
            result["next_window"] = name
            result["next_time"] = start_str

    return result


def load_active_macro(now_et: datetime | None = None) -> dict[str, Any]:
    """Check if current time is inside an ICT Macro window.

    Returns dict:
        active: bool
        name: str (e.g. "ny_morning_macro") or None
        window: str (e.g. "09:50-10:10") or None
        next_macro: str or None
        next_time: str or None
    """
    from scripts.libs_py.ict_engine import MACROS
    from datetime import time as dt_time

    if now_et is None:
        now_et = _now_et()
    t = now_et.time()

    result: dict[str, Any] = {"active": False, "name": None, "window": None,
                               "next_macro": None, "next_time": None}

    # Check current
    for name, (start_str, end_str) in MACROS.items():
        start_t = dt_time(*map(int, start_str.split(":")))
        end_t = dt_time(*map(int, end_str.split(":")))
        if start_t <= t <= end_t:
            result["active"] = True
            result["name"] = name
            result["window"] = f"{start_str}-{end_str}"
            break

    # Find next macro if not active
    if not result["active"]:
        upcoming = []
        for name, (start_str, end_str) in MACROS.items():
            start_t = dt_time(*map(int, start_str.split(":")))
            if t < start_t:
                upcoming.append((start_t, name, start_str))
        if upcoming:
            upcoming.sort()
            _, name, start_str = upcoming[0]
            result["next_macro"] = name
            result["next_time"] = start_str

    return result


# ═══════════════════════════════════════════════════════════════════════
#  Drop-in Replacement for compute_ict_from_htf
# ═══════════════════════════════════════════════════════════════════════

def load_ict_context(ticker: str = "NQ1", current_price: float = 0) -> dict:
    """Drop-in replacement for ``compute_ict_from_htf``.

    Reads from derived parquets first, falls back to live computation
    from 1d/1W parquet if parquets are unavailable.

    Returns the same dict schema as ``compute_ict_from_htf``:
        pdh, pdl, pdc, midnight_open, pwh, pwl,
        dealing_range_pct, premium_discount,
        bsl_target, ssl_target, weekly_range_pct
    """
    result: dict[str, Any] = {
        "pdh": None, "pdl": None, "pdc": None, "midnight_open": None,
        "pwh": None, "pwl": None,
        "dealing_range_pct": None, "premium_discount": "unknown",
        "bsl_target": None, "ssl_target": None,
        "weekly_range_pct": None,
    }

    # ── Try parquet first ──
    htf_df = load_htf_levels(ticker, auto_refresh=True)
    today = _now_et().date()

    if not htf_df.empty:
        # Get the most recent row prior to today
        htf_df["trading_date"] = pd.to_datetime(htf_df["trading_date"]).dt.date
        prior_rows = htf_df[htf_df["trading_date"] < today]
        if prior_rows.empty:
            prior_rows = htf_df  # use latest available
        if not prior_rows.empty:
            row = prior_rows.iloc[-1]
            result["pdh"] = round(float(row["pdh"]), 2) if pd.notna(row.get("pdh")) else None
            result["pdl"] = round(float(row["pdl"]), 2) if pd.notna(row.get("pdl")) else None
            result["pwh"] = round(float(row["pwh"]), 2) if pd.notna(row.get("pwh")) else None
            result["pwl"] = round(float(row["pwl"]), 2) if pd.notna(row.get("pwl")) else None

    # ── PDC + Midnight Open still need 1m/1d data (not in HTF parquet) ──
    # Fall back to live computation for these fields
    try:
        df_1d_path = _REPO / "data" / f"{ticker}_1d.parquet"
        if df_1d_path.exists():
            df_1d = pd.read_parquet(df_1d_path)
            if df_1d.index.tz is not None:
                df_1d.index = df_1d.index.tz_convert("US/Eastern")
            else:
                df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

            if len(df_1d) >= 2:
                last_bar_date = df_1d.index[-1].date()
                if last_bar_date == today:
                    prior = df_1d.iloc[-2]
                else:
                    prior = df_1d.iloc[-1]
                result["pdc"] = round(float(prior["close"]), 2)
                # If HTF parquet didn't have PDH/PDL, use daily
                if result["pdh"] is None:
                    result["pdh"] = round(float(prior["high"]), 2)
                if result["pdl"] is None:
                    result["pdl"] = round(float(prior["low"]), 2)
    except Exception as e:
        log.warning("[ict_loader] PDC fallback error: %s", e)

    # Midnight open from 1m parquet
    try:
        from scripts.utils.fused_data_loader import load_fused_data
        df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
        if df_1m is not None and not df_1m.empty:
            if df_1m.index.tz is None:
                df_1m.index = pd.DatetimeIndex(df_1m.index).tz_localize("UTC").tz_convert("US/Eastern")
            else:
                df_1m.index = df_1m.index.tz_convert("US/Eastern")

            now_et = pd.Timestamp.now(tz="US/Eastern")
            midnight = now_et.normalize()
            midnight_bars = df_1m[df_1m.index >= midnight]
            if not midnight_bars.empty:
                result["midnight_open"] = round(float(midnight_bars["open"].iloc[0]), 2)
    except Exception as e:
        log.warning("[ict_loader] Midnight open error: %s", e)

    # ── Weekly: fallback from 1W parquet if HTF didn't have it ──
    if result["pwh"] is None:
        try:
            df_1w = pd.read_parquet(_REPO / "data" / f"{ticker}_1W.parquet")
            if df_1w.index.tz is not None:
                df_1w.index = df_1w.index.tz_convert("US/Eastern")
            else:
                df_1w.index = df_1w.index.tz_localize("UTC").tz_convert("US/Eastern")
            if len(df_1w) >= 2:
                prior_week = df_1w.iloc[-2]
                result["pwh"] = round(float(prior_week["high"]), 2)
                result["pwl"] = round(float(prior_week["low"]), 2)
        except Exception as e:
            log.warning("[ict_loader] Weekly fallback error: %s", e)

    # ── Premium/Discount ──
    if result["pdh"] and result["pdl"] and current_price > 0:
        dealing_range = result["pdh"] - result["pdl"]
        if dealing_range > 0:
            pct = (current_price - result["pdl"]) / dealing_range * 100
            result["dealing_range_pct"] = round(pct, 1)
            result["premium_discount"] = "PREMIUM" if pct > 50 else "DISCOUNT"
            result["bsl_target"] = result["pdh"]
            result["ssl_target"] = result["pdl"]

    # ── Weekly range position ──
    if result["pwh"] and result["pwl"] and current_price > 0:
        weekly_range = result["pwh"] - result["pwl"]
        if weekly_range > 0:
            result["weekly_range_pct"] = round((current_price - result["pwl"]) / weekly_range * 100, 1)

    return result