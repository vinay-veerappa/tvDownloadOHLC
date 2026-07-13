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