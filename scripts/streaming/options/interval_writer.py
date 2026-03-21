"""
interval_writer.py
==================
Writes intraday GEX snapshots to the Prisma/SQLite database via the Next.js
internal API route (POST /api/options-live/snapshot).

This replaces the SQLite interval_data table from ezoptionsschwab.py with
Prisma-managed storage queryable from the web dashboard.

During each pipeline cycle (RTH only), call `write_snapshot()` with the
current DealerLevels for each ticker.  The Next.js API route handles the
actual Prisma upsert so we don't need Python Prisma client installed in
the pipeline environment.
"""
from __future__ import annotations

import json
import logging
import traceback
import math
from datetime import datetime, timezone, date
from typing import Any

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
    }

    payload = _sanitize_payload(payload)

    try:
        resp = _api_session.post(
            SNAPSHOT_ENDPOINT,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code == 200:
            log.debug("GexSnapshot written for %s @ %s", ticker, now_utc.strftime("%H:%M"))
            return True
        else:
            log.warning(
                "GexSnapshot write failed for %s: HTTP %d — %s",
                ticker, resp.status_code, resp.text[:200],
            )
            return False
    except requests.exceptions.ConnectionError:
        log.warning("GexSnapshot write failed for %s: Connection Refused (Is the Next.js server running at %s?)", ticker, SNAPSHOT_ENDPOINT)
        return False
    except Exception as e:
        log.warning("GexSnapshot write error for %s: %s\n%s", ticker, e, traceback.format_exc())
        return False


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
        "anomalies": anomalies,
        "dominantNodes": dominant_nodes or [],
    }

    payload = _sanitize_payload(payload)

    try:
        resp = _api_session.post(
            endpoint,
            json=payload,
            timeout=15,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code in (200, 201):
            log.info("Macro HTF snapshot written for %s", ticker)
            return True
        else:
            log.warning(
                "Macro HTF snapshot write failed for %s: HTTP %d — %s",
                ticker, resp.status_code, resp.text[:200],
            )
            return False
    except requests.exceptions.ConnectionError:
        log.warning("Macro HTF snapshot write failed for %s: Connection Refused (Is the Next.js server running at %s?)", ticker, endpoint)
        return False
    except Exception as e:
        log.warning("Macro HTF snapshot write error for %s: %s\n%s", ticker, e, traceback.format_exc())
        return False


def _trading_date_str(dt: datetime) -> str:
    """Return the trading date as an ISO date string.
    We use the ET date so pre-market runs at 5am ET still map to the correct trading day.
    """
    from zoneinfo import ZoneInfo
    et = dt.astimezone(ZoneInfo("America/New_York"))
    d = et.date()
    return f"{d.isoformat()}T00:00:00.000Z"
