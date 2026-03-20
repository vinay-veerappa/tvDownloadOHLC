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
from datetime import datetime, timezone, date
from typing import Any

import requests

from .gex_calculator import DealerLevels

log = logging.getLogger(__name__)

# The Next.js dev server URL — set NEXT_APP_URL env var to override.
import os
_NEXT_URL = os.environ.get("NEXT_APP_URL", "http://localhost:3000")
_SNAPSHOT_ENDPOINT = f"{_NEXT_URL}/api/options-live/snapshot"


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

    try:
        resp = requests.post(
            _SNAPSHOT_ENDPOINT,
            json=payload,
            timeout=5,
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
        log.debug("Next.js server not reachable — skipping snapshot for %s (not running?)", ticker)
        return False
    except Exception as e:
        log.warning("GexSnapshot write error for %s: %s", ticker, e)
        return False


def _trading_date_str(dt: datetime) -> str:
    """Return the trading date as an ISO date string.
    We use the ET date so pre-market runs at 5am ET still map to the correct trading day.
    """
    from zoneinfo import ZoneInfo
    et = dt.astimezone(ZoneInfo("America/New_York"))
    d = et.date()
    return f"{d.isoformat()}T00:00:00.000Z"
