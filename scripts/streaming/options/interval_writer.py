"""
interval_writer.py
==================
Writes intraday GEX snapshots directly to Prisma/SQLite from Python.

This replaces the SQLite interval_data table from ezoptionsschwab.py with
Prisma-managed storage queryable from the web dashboard.

During each pipeline cycle (RTH only), call `write_snapshot()` with the
current DealerLevels for each ticker.  The Next.js API route handles the
actual Prisma upsert only as an optional fallback path.
"""
from __future__ import annotations

import json
import logging
import traceback
import math
import asyncio
import os
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any

try:
    from prisma import Prisma
except Exception:
    Prisma = None

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from .gex_calculator import DealerLevels

log = logging.getLogger(__name__)

from .config import SNAPSHOT_ENDPOINT, MACRO_SNAPSHOT_ENDPOINT

# Configure a resilient session with exponential backoff
# Retries: 5, Backoff Factor: 1 (1s, 2s, 4s, 8s, 16s)
# Status codes to retry: 500, 502, 503, 504
_retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["POST"],
    raise_on_status=False
)
_adapter = HTTPAdapter(max_retries=_retry_strategy)
_api_session = requests.Session()
_api_session.mount("http://", _adapter)
_api_session.mount("https://", _adapter)


def _sanitize_payload(data: Any) -> Any:
    """Recursively replace NaN and Inf with None for JSON compatibility."""
    if isinstance(data, dict):
        return {k: _sanitize_payload(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_payload(x) for x in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
    return data


def _ensure_database_url() -> None:
    if os.getenv("DATABASE_URL"):
        return
    # Repo root: scripts/streaming/options -> project root
    project_root = Path(__file__).resolve().parents[3]
    db_file = project_root / "web" / "prisma" / "dev.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"file:{db_file.as_posix()}"


async def _get_prisma() -> Prisma:
    """Return a connected Prisma client bound to the current event loop."""
    if Prisma is None:
        raise RuntimeError("Prisma client is not available")
    _ensure_database_url()
    db = Prisma()
    await db.connect()
    return db


def write_snapshot(levels: DealerLevels, ticker_override: str | None = None) -> bool:
    """
    POST a GexSnapshot record to the Next.js API.

    Parameters
    ----------
    levels          : DealerLevels output from calculate_dealer_levels.
    ticker_override : Use this ticker key instead of levels.ticker (e.g. "NQ" for
                      a futures-translated DealerLevels that still shows QQQ as ticker).

    Returns True on success, False on failure (failures are logged, not raised).
    """
    ticker = ticker_override or levels.ticker
    now_utc = datetime.now(timezone.utc)
    trading_date = _trading_date_str(now_utc)

    payload: dict[str, Any] = {
        "ticker": ticker,
        "timestamp": now_utc.isoformat(),
        "tradingDate": trading_date,
        # Core GEX
        "totalGex": levels.total_gex,
        "totalGexDeltaAdj": levels.total_gex_delta_adj,
        "callGammaTotal": levels.call_gamma_total,
        "putGammaTotal": levels.put_gamma_total,
        "gexRegime": levels.gex_regime,
        "regimeLabel": levels.regime_label,
        # Price context
        "spotPrice": levels.spot,
        "gammaMagnet": levels.gamma_magnet,
        "pinStrike": levels.pin_strike,
        # New analytics
        "callVolumeCentroid": levels.call_volume_centroid,
        "putVolumeCentroid": levels.put_volume_centroid,
        "netSpeedExposure": levels.net_speed_exposure,
        "netVannaExposure": levels.net_vanna_exposure,
        # Institutional skew metrics (were silently dropped — fixed)
        "put25dIv": levels.put_25d_iv,
        "call25dIv": levels.call_25d_iv,
        "volatilitySkewPremium": levels.volatility_skew_premium,
        # Futures translation matrix
        "futuresSymbol": getattr(levels, "futures_symbol", None),
        "futuresTranslationMode": getattr(levels, "translation_mode", None),
        "futuresBasisSpread": getattr(levels, "basis_spread", None),
        "futuresBasisRatio": getattr(levels, "basis_ratio", None),
    }

    payload = _sanitize_payload(payload)

    # Prefer direct Prisma writes so this path has no runtime Node dependency.
    # If direct write fails, fall through to API fallback instead of returning
    # early with False.
    try:
        if asyncio.run(_write_snapshot_direct(payload)):
            return True
    except Exception as e:
        log.warning("Direct DB snapshot path raised for %s: %r", ticker, e)

    # Optional fallback to API route for environments without python prisma.
    try:
        resp = _api_session.post(
            SNAPSHOT_ENDPOINT,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code == 200:
            log.debug("GexSnapshot written via API fallback for %s @ %s", ticker, now_utc.strftime("%H:%M"))
            return True
        log.warning(
            "GexSnapshot API fallback failed for %s: HTTP %d — %s",
            ticker, resp.status_code, resp.text[:200],
        )
        return False
    except Exception as e:
        log.warning("GexSnapshot write error for %s: %s\n%s", ticker, e, traceback.format_exc())
        return False


async def _write_snapshot_direct(payload: dict[str, Any]) -> bool:
    """Write GexSnapshot directly to the database via Prisma."""
    db: Prisma | None = None
    try:
        db = await _get_prisma()
        await db.gexsnapshot.create(data={
            "ticker": payload["ticker"],
            "timestamp": datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00")),
            "tradingDate": datetime.fromisoformat(payload["tradingDate"].replace("Z", "+00:00")),
            "totalGex": payload["totalGex"],
            "totalGexDeltaAdj": payload.get("totalGexDeltaAdj"),
            "callGammaTotal": payload.get("callGammaTotal"),
            "putGammaTotal": payload.get("putGammaTotal"),
            "gexRegime": payload["gexRegime"],
            "regimeLabel": payload.get("regimeLabel"),
            "spotPrice": payload["spotPrice"],
            "gammaMagnet": payload.get("gammaMagnet"),
            "pinStrike": payload.get("pinStrike"),
            "callVolumeCentroid": payload.get("callVolumeCentroid"),
            "putVolumeCentroid": payload.get("putVolumeCentroid"),
            "netSpeedExposure": payload.get("netSpeedExposure"),
            "netVannaExposure": payload.get("netVannaExposure"),
            "put25dIv": payload.get("put25dIv"),
            "call25dIv": payload.get("call25dIv"),
            "volatilitySkewPremium": payload.get("volatilitySkewPremium"),
            "futuresSymbol": payload.get("futuresSymbol"),
            "futuresTranslationMode": payload.get("futuresTranslationMode"),
            "futuresBasisSpread": payload.get("futuresBasisSpread"),
            "futuresBasisRatio": payload.get("futuresBasisRatio"),
        })
        log.info("GexSnapshot written DIRECTLY to DB (Offline Mode) for %s", payload["ticker"])
        return True
    except Exception as e:
        log.warning(
            "Direct DB write failed for %s: %r\n%s",
            payload["ticker"],
            e,
            traceback.format_exc(),
        )
        return False
    finally:
        if db is not None and db.is_connected():
            await db.disconnect()


def write_macro_snapshot(
    ticker: str, 
    spot: float, 
    levels: dict[str, float | None], 
    anomalies: dict[str, list[dict[str, Any]]],
    dominant_nodes: list[dict[str, Any]] = None
) -> bool:
    """
    Pillar 4: POST a macro HTF snapshot to the Next.js API.
    """
    now_utc = datetime.now(timezone.utc)
    trading_date = _trading_date_str(now_utc)
    
    endpoint = MACRO_SNAPSHOT_ENDPOINT

    payload: dict[str, Any] = {
        "ticker": ticker,
        "timestamp": now_utc.isoformat(),
        "tradingDate": trading_date,
        "spotPrice": spot,
        "macroCallWall": levels.get("macro_call_wall"),
        "macroPutWall": levels.get("macro_put_wall"),
        "zeroGamma": levels.get("zero_gamma"),
        "put25dIv": levels.get("put_25d_iv"),
        "call25dIv": levels.get("call_25d_iv"),
        "volatilitySkewPremium": levels.get("volatility_skew_premium"),
        "anomalies": anomalies,
        "dominantNodes": dominant_nodes or [],
    }

    payload = _sanitize_payload(payload)

    # Prefer direct Prisma writes so this path has no runtime Node dependency.
    # If direct write fails, continue to API fallback.
    try:
        if asyncio.run(_write_macro_snapshot_direct(payload)):
            return True
    except Exception as e:
        log.warning("Direct Macro DB path raised for %s: %r", ticker, e)

    # Optional fallback to API route for environments without python prisma.
    try:
        resp = _api_session.post(
            endpoint,
            json=payload,
            timeout=15,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code in (200, 201):
            log.info("Macro HTF snapshot written via API fallback for %s", ticker)
            return True
        log.warning(
            "Macro HTF snapshot API fallback failed for %s: HTTP %d — %s",
            ticker, resp.status_code, resp.text[:200],
        )
        return False
    except Exception as e:
        log.warning("Macro HTF snapshot write error for %s: %s\n%s", ticker, e, traceback.format_exc())
        return False


async def _write_macro_snapshot_direct(payload: dict[str, Any]) -> bool:
    """Write MacroSnapshot directly to the database via Prisma."""
    db: Prisma | None = None
    try:
        db = await _get_prisma()
        
        # We use upsert to match the API behavior (unique on ticker + tradingDate)
        # Note: formatting anomalies/dominantNodes as JSON string for DB
        await db.macrosnapshot.upsert(
            where={
                "ticker_tradingDate": {
                    "ticker": payload["ticker"],
                    "tradingDate": datetime.fromisoformat(payload["tradingDate"].replace("Z", "+00:00")),
                }
            },
            data={
                "create": {
                    "ticker": payload["ticker"],
                    "timestamp": datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00")),
                    "tradingDate": datetime.fromisoformat(payload["tradingDate"].replace("Z", "+00:00")),
                    "spotPrice": payload["spotPrice"],
                    "macroCallWall": payload.get("macroCallWall"),
                    "macroPutWall": payload.get("macroPutWall"),
                    "zeroGamma": payload.get("zeroGamma"),
                    "put25dIv": payload.get("put25dIv"),
                    "call25dIv": payload.get("call25dIv"),
                    "volatilitySkewPremium": payload.get("volatilitySkewPremium"),
                    "anomalies": json.dumps(payload.get("anomalies", [])),
                    "dominantNodes": json.dumps(payload.get("dominantNodes", [])),
                },
                "update": {
                    "timestamp": datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00")),
                    "spotPrice": payload["spotPrice"],
                    "macroCallWall": payload.get("macroCallWall"),
                    "macroPutWall": payload.get("macroPutWall"),
                    "zeroGamma": payload.get("zeroGamma"),
                    "put25dIv": payload.get("put25dIv"),
                    "call25dIv": payload.get("call25dIv"),
                    "volatilitySkewPremium": payload.get("volatilitySkewPremium"),
                    "anomalies": json.dumps(payload.get("anomalies", [])),
                    "dominantNodes": json.dumps(payload.get("dominantNodes", [])),
                }
            }
        )
        log.info("Macro HTF snapshot written DIRECTLY to DB (Offline Mode) for %s", payload["ticker"])
        return True
    except Exception as e:
        log.warning(
            "Direct Macro DB write failed for %s: %r\n%s",
            payload["ticker"],
            e,
            traceback.format_exc(),
        )
        return False
    finally:
        if db is not None and db.is_connected():
            await db.disconnect()


def _trading_date_str(dt: datetime) -> str:
    """Return the trading date as an ISO date string.
    We use the ET date so pre-market runs at 5am ET still map to the correct trading day.
    """
    from zoneinfo import ZoneInfo
    et = dt.astimezone(ZoneInfo("America/New_York"))
    d = et.date()
    return f"{d.isoformat()}T00:00:00.000Z"
