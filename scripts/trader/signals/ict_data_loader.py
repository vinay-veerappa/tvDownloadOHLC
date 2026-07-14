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
#  Phase 2A Loaders (Structure, OB, Liquidity, SMT)
# ═══════════════════════════════════════════════════════════════════════

def load_structure(symbol: str, timeframe: str = "5m", auto_refresh: bool = True,
                    session_date: date | None = None) -> pd.DataFrame:
    """Load swings + structure breaks + CISD from parquet."""
    path = _ICT_DIR / f"{symbol}_structure_{timeframe}.parquet"
    if auto_refresh and _is_stale_intraday(path):
        _trigger_refresh(symbol, "structure")
    try:
        df = pd.read_parquet(path)
        if session_date is not None and not df.empty and "logical_date" in df.columns:
            df = df[df["logical_date"] == session_date]
        return df
    except Exception as e:
        log.warning("[ict_loader] structure load failed: %s", e)
        return pd.DataFrame()


def load_orderblocks(symbol: str, timeframe: str = "5m", auto_refresh: bool = True,
                      session_date: date | None = None) -> pd.DataFrame:
    """Load order blocks from parquet."""
    path = _ICT_DIR / f"{symbol}_ob_{timeframe}.parquet"
    if auto_refresh and _is_stale_intraday(path):
        _trigger_refresh(symbol, "orderblocks")
    try:
        df = pd.read_parquet(path)
        if session_date is not None and not df.empty and "logical_date" in df.columns:
            df = df[df["logical_date"] == session_date]
        return df
    except Exception as e:
        log.warning("[ict_loader] orderblocks load failed: %s", e)
        return pd.DataFrame()


def load_liquidity(symbol: str, timeframe: str = "5m", auto_refresh: bool = True,
                   session_date: date | None = None) -> pd.DataFrame:
    """Load liquidity pools (BSL/SSL/EQH/EQL) from parquet."""
    path = _ICT_DIR / f"{symbol}_liquidity_{timeframe}.parquet"
    if auto_refresh and _is_stale_intraday(path):
        _trigger_refresh(symbol, "liquidity")
    try:
        df = pd.read_parquet(path)
        if session_date is not None and not df.empty and "logical_date" in df.columns:
            df = df[df["logical_date"] == session_date]
        return df
    except Exception as e:
        log.warning("[ict_loader] liquidity load failed: %s", e)
        return pd.DataFrame()


def load_smt(symbol: str = "NQ1", auto_refresh: bool = True,
             session_date: date | None = None) -> pd.DataFrame:
    """Load SMT divergence events (NQ1 vs ES1) from parquet."""
    path = _ICT_DIR / f"{symbol}_smt.parquet"
    if auto_refresh and _is_stale_intraday(path):
        _trigger_refresh(symbol, "smt")
    try:
        df = pd.read_parquet(path)
        if session_date is not None and not df.empty and "logical_date" in df.columns:
            df = df[df["logical_date"] == session_date]
        return df
    except Exception as e:
        log.warning("[ict_loader] smt load failed: %s", e)
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


# ═══════════════════════════════════════════════════════════════════════
#  ICT Daily Bias Model
# ═══════════════════════════════════════════════════════════════════════

def compute_ict_daily_bias(ticker: str, current_price: float) -> dict[str, Any]:
    """Compute a multi-model ICT daily bias.

    Combines 4 bias models from ICT_DAILY_BIAS_MODELS.md:
      A) Premium/Discount — price position in PDH/PDL dealing range
      B) Draw on Liquidity — proximity to BSL (PDH/PWH) vs SSL (PDL/PWL)
      C) IPDA position — multi-day rolling range position
      D) HTF structure — price above/below prior week and prior month levels

    Returns:
        dict with:
            bias: "BULLISH" | "BEARISH" | "NEUTRAL"
            confidence: int (0-100)
            models: list of {model, signal, detail}
            summary: str — one-line human-readable summary
    """
    import numpy as np

    models: list[dict[str, Any]] = []
    bull_score = 0
    bear_score = 0

    ict = load_ict_context(ticker, current_price)

    # ── Model A: Premium/Discount ──
    pd_pct = ict.get("dealing_range_pct")
    if pd_pct is not None and current_price > 0:
        if pd_pct < 40:
            signal = "BULLISH"
            bull_score += 25
            detail = f"Price in deep discount ({pd_pct:.0f}% of PDH-PDL) — longs favored"
        elif pd_pct > 60:
            signal = "BEARISH"
            bear_score += 25
            detail = f"Price in deep premium ({pd_pct:.0f}% of PDH-PDL) — shorts favored"
        else:
            signal = "NEUTRAL"
            detail = f"Price at equilibrium ({pd_pct:.0f}% of PDH-PDL)"
        models.append({"model": "Premium/Discount", "signal": signal, "detail": detail})

    # ── Model B: Draw on Liquidity (proximity to BSL vs SSL) ──
    pdh = ict.get("pdh")
    pdl = ict.get("pdl")
    pwh = ict.get("pwh")
    pwl = ict.get("pwl")
    if pdh and pdl and current_price > 0:
        # Distance to BSL (nearest untaken high) and SSL (nearest untaken low)
        bsl_candidates = [pdh]
        ssl_candidates = [pdl]
        if pwh and pwh > current_price:
            bsl_candidates.append(pwh)
        if pwl and pwl < current_price:
            ssl_candidates.append(pwl)

        nearest_bsl = min(bsl_candidates, key=lambda x: abs(x - current_price))
        nearest_ssl = min(ssl_candidates, key=lambda x: abs(x - current_price))
        dist_to_bsl = abs(nearest_bsl - current_price)
        dist_to_ssl = abs(nearest_ssl - current_price)

        # Closer to SSL = bullish (price will be drawn down to sweep sells first, then rally)
        # Closer to BSL = bearish (price will be drawn up to sweep buys first, then sell off)
        # Actually in ICT: price is DRAWN to the nearest liquidity. If closer to SSL, that's
        # the draw (bearish first). If closer to BSL, that's the draw (bullish first).
        # But the BIAS is the direction AFTER the draw is completed.
        # Simplification: closer to SSL = bearish draw (raid sells first), then reversal up = bullish
        # For daily bias, we look at which side has more untouched liquidity = that's the target
        if dist_to_ssl < dist_to_bsl * 0.7:
            signal = "BEARISH"
            bear_score += 20
            detail = f"SSL ({nearest_ssl:,.2f}) is {dist_to_ssl:,.2f} away — draw on liquidity is downward"
        elif dist_to_bsl < dist_to_ssl * 0.7:
            signal = "BULLISH"
            bull_score += 20
            detail = f"BSL ({nearest_bsl:,.2f}) is {dist_to_bsl:,.2f} away — draw on liquidity is upward"
        else:
            signal = "NEUTRAL"
            detail = f"BSL {dist_to_bsl:,.2f} vs SSL {dist_to_ssl:,.2f} — balanced draw"
        models.append({"model": "Draw on Liquidity", "signal": signal, "detail": detail})

    # ── Model C: IPDA Position ──
    ipda = load_ipda(ticker, auto_refresh=True)
    if not ipda.empty:
        import pytz
        today = _now_et().date()
        ipda["trading_date"] = pd.to_datetime(ipda["trading_date"]).dt.date
        today_row = ipda[ipda["trading_date"] == today]
        if today_row.empty:
            today_row = ipda.tail(1)
        if not today_row.empty:
            row = today_row.iloc[0]
            ipda20_pct = row.get("ipda20_pct")
            ipda60_pct = row.get("ipda60_pct")
            if pd.notna(ipda20_pct) and pd.notna(ipda60_pct):
                # Both in discount = bullish, both in premium = bearish
                if ipda20_pct < 40 and ipda60_pct < 50:
                    signal = "BULLISH"
                    bull_score += 25
                    detail = f"IPDA-20 at {ipda20_pct:.0f}%, IPDA-60 at {ipda60_pct:.0f}% — deep discount across ranges"
                elif ipda20_pct > 60 and ipda60_pct > 60:
                    signal = "BEARISH"
                    bear_score += 25
                    detail = f"IPDA-20 at {ipda20_pct:.0f}%, IPDA-60 at {ipda60_pct:.0f}% — premium across ranges"
                else:
                    signal = "NEUTRAL"
                    detail = f"IPDA-20 at {ipda20_pct:.0f}%, IPDA-60 at {ipda60_pct:.0f}% — mixed signals"
                models.append({"model": "IPDA Position", "signal": signal, "detail": detail})

    # ── Model D: HTF Structure (price vs weekly/monthly levels) ──
    if pwh and pwl and current_price > 0:
        if current_price > pwh:
            signal = "BULLISH"
            bull_score += 20
            detail = f"Price above PWH ({pwh:,.2f}) — bullish HTF structure"
        elif current_price < pwl:
            signal = "BEARISH"
            bear_score += 20
            detail = f"Price below PWL ({pwl:,.2f}) — bearish HTF structure"
        else:
            # Inside weekly range — check position
            weekly_pct = ict.get("weekly_range_pct")
            if weekly_pct is not None:
                if weekly_pct < 30:
                    signal = "BEARISH"
                    bear_score += 10
                    detail = f"Price in lower weekly range ({weekly_pct:.0f}% of PWH-PWL)"
                elif weekly_pct > 70:
                    signal = "BULLISH"
                    bull_score += 10
                    detail = f"Price in upper weekly range ({weekly_pct:.0f}% of PWH-PWL)"
                else:
                    signal = "NEUTRAL"
                    detail = f"Price mid weekly range ({weekly_pct:.0f}% of PWH-PWL)"
            else:
                signal = "NEUTRAL"
                detail = f"Price inside weekly range ({pwl:,.2f}-{pwh:,.2f})"
        models.append({"model": "HTF Structure", "signal": signal, "detail": detail})

    # ── Model E: Previous Day Candle Analysis ──
    pdc = ict.get("pdc")
    if pdh and pdl and pdc and current_price > 0:
        if pdc > pdh:
            signal = "BULLISH"
            bull_score += 20
            detail = f"Prior day closed above PDH ({pdh:,.2f}) — strength signal"
        elif pdc < pdl:
            signal = "BEARISH"
            bear_score += 20
            detail = f"Prior day closed below PDL ({pdl:,.2f}) — weakness signal"
        else:
            # Inside bar — refer to prior direction
            if current_price > pdc:
                signal = "BULLISH"
                bull_score += 5
                detail = f"Prior day inside bar, close above PDC ({pdc:,.2f}) — mild bullish"
            elif current_price < pdc:
                signal = "BEARISH"
                bear_score += 5
                detail = f"Prior day inside bar, close below PDC ({pdc:,.2f}) — mild bearish"
            else:
                signal = "NEUTRAL"
                detail = f"Prior day inside bar, close at PDC ({pdc:,.2f})"
        models.append({"model": "Prior Day Candle", "signal": signal, "detail": detail})

    # ── Model F: Midnight Open Position ──
    midnight_open = ict.get("midnight_open")
    if midnight_open and current_price > 0:
        mid = float(midnight_open)
        if current_price < mid:
            signal = "BULLISH"
            bull_score += 15
            detail = f"Price below midnight open ({mid:,.2f}) — discount of the day, longs favored"
        elif current_price > mid:
            signal = "BEARISH"
            bear_score += 15
            detail = f"Price above midnight open ({mid:,.2f}) — premium of the day, shorts favored"
        else:
            signal = "NEUTRAL"
            detail = f"Price at midnight open ({mid:,.2f}) — equilibrium"
        models.append({"model": "Midnight Open", "signal": signal, "detail": detail})

    # ── Model G: London/Asia Sweep (session confirmation) ──
    kz = load_kz_pivots(ticker, auto_refresh=True)
    if not kz.empty and current_price > 0:
        import pytz
        today = _now_et().date()
        kz["trading_date"] = pd.to_datetime(kz["trading_date"]).dt.date
        today_row = kz[kz["trading_date"] == today]
        if today_row.empty:
            today_row = kz.tail(1)
        if not today_row.empty:
            row = today_row.iloc[0]
            asia_h = row.get("asia_high")
            asia_l = row.get("asia_low")
            london_h = row.get("london_high")
            london_l = row.get("london_low")
            if pd.notna(asia_h) and pd.notna(asia_l) and pd.notna(london_h) and pd.notna(london_l):
                # London swept Asia low → bullish continuation (draws sell stops, then rallies)
                if london_l < asia_l and current_price > london_l:
                    signal = "BULLISH"
                    bull_score += 15
                    detail = f"London swept Asia low ({asia_l:,.2f} → {london_l:,.2f}) then recovered — bullish continuation"
                # London swept Asia high → bearish continuation
                elif london_h > asia_h and current_price < london_h:
                    signal = "BEARISH"
                    bear_score += 15
                    detail = f"London swept Asia high ({asia_h:,.2f} → {london_h:,.2f}) then rejected — bearish continuation"
                else:
                    signal = "NEUTRAL"
                    detail = f"London inside Asia range — no sweep confirmation"
                models.append({"model": "London/Asia Sweep", "signal": signal, "detail": detail})

    # ── Compute final bias ──
    # Max possible score with 7 models: 25+20+25+20+20+15+15 = 140
    max_score = 140
    total = bull_score + bear_score
    if total == 0:
        bias = "NEUTRAL"
        confidence = 0
        summary = "No clear ICT bias — models are balanced."
    elif bull_score > bear_score:
        bias = "BULLISH"
        confidence = int((bull_score / max_score) * 100)
        summary = f"Bullish bias ({confidence}% confidence) — {bull_score} bull vs {bear_score} bear"
    else:
        bias = "BEARISH"
        confidence = int((bear_score / max_score) * 100)
        summary = f"Bearish bias ({confidence}% confidence) — {bear_score} bear vs {bull_score} bull"

    return {
        "bias": bias,
        "confidence": min(confidence, 100),
        "models": models,
        "summary": summary,
    }


# ═══════════════════════════════════════════════════════════════════════
#  FTFC (Full Timeframe Continuity) — Multi-TF Bias
# ═══════════════════════════════════════════════════════════════════════

# Timeframes for FTFC computation
FTFC_TIMEFRAMES = {
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
}

# Session-specific model recommendations (from historical validation)
FTFC_SESSION_MODEL = {
    "18:00": None,       # Asia — do not use FTFC
    "02:00": "combined",  # London — combined (candle + MS agree)
    "08:30": "candle",    # Pre-NY — candle FTFC
    "09:30": "candle",    # RTH open — candle FTFC
    "11:00": "combined",  # Lunch — combined FTFC
    "13:30": "ms",        # PM — MS FTFC
}


def compute_ftfc(ticker: str, current_price: float, now_et: datetime | None = None) -> dict[str, Any]:
    """Compute Full Timeframe Continuity bias.

    Three separate views:
      1. Candle FTFC: all timeframes have close > open (green candle)
      2. MS FTFC: all timeframes have HH/HL (market structure bullish)
      3. 200 SMA filter: price above/below 200-day SMA

    Plus a session-adaptive combined bias that picks the best model
    based on the current session time.

    Returns dict with:
        candle_ftfc: dict — per-TF candle directions + alignment
        ms_ftfc: dict — per-TF market structure + alignment
        sma_200: dict — 200 SMA value + direction
        combined: dict — combined FTFC (candle + MS agree)
        session_bias: dict — session-adaptive bias (best model for current time)
        summary: str — one-line human-readable summary
    """
    import numpy as np
    from scripts.edgeful.lib.data_loader import get_loader
    from scripts.libs_py.nqstats.sessions import normalize_to_eastern

    if now_et is None:
        now_et = _now_et()

    result: dict[str, Any] = {
        "candle_ftfc": {},
        "ms_ftfc": {},
        "sma_200": {},
        "combined": {},
        "session_bias": {},
        "summary": "FTFC data unavailable",
    }

    # Load 1m data
    loader = get_loader()
    df_1m = loader.load_1m(ticker)
    if df_1m is None or df_1m.empty:
        return result
    df_et = normalize_to_eastern(df_1m)

    # Compute per-TF candle direction and MS
    tf_candle = {}
    tf_ms = {}
    for tf_label, tf_rule in FTFC_TIMEFRAMES.items():
        df_tf = df_et[["open", "high", "low", "close"]].resample(
            tf_rule, origin="start_day"
        ).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

        if df_tf.empty:
            continue

        # Candle direction (current bar: close vs open)
        last_bar = df_tf.iloc[-1]
        candle_dir = "BULLISH" if last_bar["close"] > last_bar["open"] else (
            "BEARISH" if last_bar["close"] < last_bar["open"] else "NEUTRAL"
        )
        tf_candle[tf_label] = candle_dir

        # Market structure (current bar H/L vs prior bar H/L)
        if len(df_tf) >= 2:
            prior_bar = df_tf.iloc[-2]
            ms_dir = "BULLISH" if (last_bar["high"] > prior_bar["high"] and last_bar["low"] > prior_bar["low"]) else (
                "BEARISH" if (last_bar["high"] < prior_bar["high"] and last_bar["low"] < prior_bar["low"]) else "NEUTRAL"
            )
        else:
            ms_dir = "NEUTRAL"
        tf_ms[tf_label] = ms_dir

    # Daily candle + MS
    daily = df_et[["open", "high", "low", "close"]].resample("D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()
    if not daily.empty:
        last_d = daily.iloc[-1]
        tf_candle["D"] = "BULLISH" if last_d["close"] > last_d["open"] else (
            "BEARISH" if last_d["close"] < last_d["open"] else "NEUTRAL"
        )
        if len(daily) >= 2:
            prior_d = daily.iloc[-2]
            tf_ms["D"] = "BULLISH" if (last_d["high"] > prior_d["high"] and last_d["low"] > prior_d["low"]) else (
                "BEARISH" if (last_d["high"] < prior_d["high"] and last_d["low"] < prior_d["low"]) else "NEUTRAL"
            )
        else:
            tf_ms["D"] = "NEUTRAL"

        # 200 SMA (daily)
        daily["sma_200"] = daily["close"].rolling(200).mean()
        sma_val = daily["sma_200"].iloc[-1] if "sma_200" in daily.columns and not daily["sma_200"].isna().all() else None
    else:
        sma_val = None

    # Compute 200 SMA on intraday timeframes too
    tf_sma = {}
    for tf_label, tf_rule in FTFC_TIMEFRAMES.items():
        df_tf = df_et[["close"]].resample(tf_rule, origin="start_day").agg({"close": "last"}).dropna()
        if len(df_tf) >= 200:
            sma_tf = df_tf["close"].rolling(200).mean().iloc[-1]
            tf_sma[tf_label] = sma_tf

    # Candle FTFC alignment
    all_tfs = list(FTFC_TIMEFRAMES.keys()) + ["D"]
    candle_bull = sum(1 for tf in all_tfs if tf_candle.get(tf) == "BULLISH")
    candle_bear = sum(1 for tf in all_tfs if tf_candle.get(tf) == "BEARISH")
    candle_total = len(all_tfs)
    candle_ftfc_bias = "BULLISH" if candle_bull == candle_total else (
        "BEARISH" if candle_bear == candle_total else (
        "BULLISH" if candle_bull >= 4 else (
        "BEARISH" if candle_bear >= 4 else "NEUTRAL")))

    result["candle_ftfc"] = {
        "per_tf": {tf: tf_candle.get(tf, "N/A") for tf in all_tfs},
        "bull_count": candle_bull,
        "bear_count": candle_bear,
        "total": candle_total,
        "bias": candle_ftfc_bias,
        "alignment": f"{candle_bull}B/{candle_bear}R/{candle_total - candle_bull - candle_bear}N",
    }

    # MS FTFC alignment
    ms_bull = sum(1 for tf in all_tfs if tf_ms.get(tf) == "BULLISH")
    ms_bear = sum(1 for tf in all_tfs if tf_ms.get(tf) == "BEARISH")
    ms_ftfc_bias = "BULLISH" if ms_bull == candle_total else (
        "BEARISH" if ms_bear == candle_total else (
        "BULLISH" if ms_bull >= 4 else (
        "BEARISH" if ms_bear >= 4 else "NEUTRAL")))

    result["ms_ftfc"] = {
        "per_tf": {tf: tf_ms.get(tf, "N/A") for tf in all_tfs},
        "bull_count": ms_bull,
        "bear_count": ms_bear,
        "total": candle_total,
        "bias": ms_ftfc_bias,
        "alignment": f"{ms_bull}B/{ms_bear}R/{candle_total - ms_bull - ms_bear}N",
    }

    # 200 SMA
    sma_dir = None
    if sma_val is not None and current_price > 0:
        sma_dir = "BULLISH" if current_price > sma_val else "BEARISH"

    # Per-TF 200 SMA directions
    tf_sma_dirs = {}
    for tf_label, sma_val_tf in tf_sma.items():
        if sma_val_tf and current_price > 0:
            tf_sma_dirs[tf_label] = "BULLISH" if current_price > sma_val_tf else "BEARISH"

    result["sma_200"] = {
        "daily_value": round(sma_val, 2) if sma_val else None,
        "direction": sma_dir,
        "per_tf_values": {tf: (round(v, 2) if v else None) for tf, v in tf_sma.items()},
        "per_tf_dirs": tf_sma_dirs,
    }

    # Combined FTFC (candle + MS agree)
    combined_bias = "NONE"
    if candle_ftfc_bias == ms_ftfc_bias and candle_ftfc_bias != "NEUTRAL":
        combined_bias = candle_ftfc_bias
    result["combined"] = {
        "bias": combined_bias,
        "candle_agrees": candle_ftfc_bias == ms_ftfc_bias,
    }

    # Session-adaptive bias
    eval_hour = now_et.hour
    eval_minute = now_et.minute
    eval_time_str = f"{eval_hour:02d}:{eval_minute:02d}"

    # Find the best session model
    best_model = None
    for session_time, model_type in FTFC_SESSION_MODEL.items():
        s_h, s_m = int(session_time.split(":")[0]), int(session_time.split(":")[1])
        if eval_hour > s_h or (eval_hour == s_h and eval_minute >= s_m):
            best_model = model_type

    session_bias = "NEUTRAL"
    session_model_name = "none"
    session_confidence = 0
    if best_model == "candle":
        session_bias = candle_ftfc_bias
        session_model_name = "Candle FTFC"
        session_confidence = 92 if sma_dir == session_bias else 75
    elif best_model == "ms":
        session_bias = ms_ftfc_bias
        session_model_name = "MS FTFC"
        session_confidence = 95 if sma_dir == session_bias else 80
    elif best_model == "combined":
        session_bias = combined_bias
        session_model_name = "Combined FTFC"
        session_confidence = 98 if sma_dir == session_bias and combined_bias != "NONE" else 85

    # Apply 200 SMA filter
    if sma_dir and session_bias != "NEUTRAL" and sma_dir != session_bias:
        session_bias = "NEUTRAL (against SMA)"
        session_confidence = 0

    result["session_bias"] = {
        "model": session_model_name,
        "bias": session_bias,
        "confidence": session_confidence,
        "sma_filtered": sma_dir != session_bias if sma_dir else False,
    }

    # Summary
    if session_bias == "NEUTRAL" or "NEUTRAL" in session_bias:
        result["summary"] = f"FTFC: No aligned bias (candle {result['candle_ftfc']['alignment']}, MS {result['ms_ftfc']['alignment']})"
    else:
        result["summary"] = f"FTFC: {session_bias} via {session_model_name} ({session_confidence}% conf, SMA={sma_dir})"

    return result