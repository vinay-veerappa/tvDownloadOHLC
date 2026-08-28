"""Expected Volatility [Session] - Pine Script v6 port.

Faithful vectorised replication of "Expected Volatility [Session]"
(https://www.tradingview.com/script/dsXscaGY-Expected-Volatility/) for the
backtesting engine.

On the first bar of the configured session (default 0930-1600 ET) the
indicator computes, from the previous day's close ("settlement") and a
correlated volatility index:

    a = vix / sqrt(252) / 100     (RTH annualisation base)
    b = vix / sqrt(365) / 100     (calendar annualisation base)

and draws a resistance ladder above and a support ladder below the
settlement price at 0.25 / 0.5 / 1.0 / 1.5 standard deviations.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

SQRT252 = math.sqrt(252.0)
SQRT365 = math.sqrt(365.0)

# Box multipliers in the indicator's drawing order (1.0, 1.5, 0.5, 0.25).
# Each box spans [mult*a, mult*b] away from settlement.
BOX_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 0.5, 0.25)

DEFAULT_SESSION = "0930-1600"
DEFAULT_TZ = "America/New_York"


def get_volatility(volatility_index: float) -> tuple[float, float]:
    """Pine ``GetVolatility()``: volatility index value -> (a, b) bases."""
    a = float(volatility_index) / SQRT252 / 100.0
    b = float(volatility_index) / SQRT365 / 100.0
    return a, b


def compute_zone_ladders(settlement: float, vix: float) -> dict:
    """All box band-pairs + midlines for one session, mirroring Pine ``Zones()``.

    Each box has: ``top``/``bottom`` (box edges in Pine's drawing order:
    ``Index_BOX_*TOP`` uses top=+up-mult, bottom=+dn-mult; the support box
    mirrors it below settlement), plus ``mid`` - the dashed midline the script
    draws across each box.
    """
    std1_up = settlement * get_volatility(vix)[0]  # Index * a
    std1_dn = settlement * get_volatility(vix)[1]  # Index * b

    resistance: dict[str, dict[str, float]] = {}
    support: dict[str, dict[str, float]] = {}
    for mult in BOX_MULTIPLIERS:
        label = f"{mult:g}"

        # Resistance box above settlement (Pine: Index_ZONE{m}UP/DN_Res).
        r_top = settlement + std1_up * mult
        r_bot = settlement + std1_dn * mult
        resistance[label] = {
            "top": r_top,
            "bottom": r_bot,
            "mid": (r_top + r_bot) / 2.0,
        }

        # Support box mirrors the resistance box below settlement
        # (Pine: sup_top = Index - (res_bottom - Index),
        #        sup_bottom = Index - (res_top - Index)).
        s_top = settlement - (r_bot - settlement)
        s_bot = settlement - (r_top - settlement)
        support[label] = {
            "top": s_top,
            "bottom": s_bot,
            "mid": (s_top + s_bot) / 2.0,
        }

    return {"resistance": resistance, "support": support}


def compute_zone_dataframe(settlements: pd.Series, vix_values: pd.Series) -> pd.DataFrame:
    """Vectorised ladders for many sessions at once.

    Returns a DataFrame indexed like ``settlements`` with one column per zone
    edge: ``res_{m}_top`` / ``res_{m}_bottom`` / ``res_{m}_mid`` and
    ``sup_{m}_top`` / ``sup_{m}_bottom`` / ``sup_{m}_mid`` for
    m in {0.25, 0.5, 1.0, 1.5}.
    """
    idx = settlements.index
    s = np.asarray(settlements, dtype=float)
    v = np.asarray(vix_values, dtype=float)
    std_up = s * v / SQRT252 / 100.0
    std_dn = s * v / SQRT365 / 100.0

    out: dict[str, np.ndarray] = {}
    for mult in BOX_MULTIPLIERS:
        label = f"{mult:g}"
        r_top = s + std_up * mult
        r_bot = s + std_dn * mult
        out[f"res_{label}_top"] = r_top
        out[f"res_{label}_bottom"] = r_bot
        out[f"res_{label}_mid"] = (r_top + r_bot) / 2.0
        s_top = s - (r_bot - s)
        s_bot = s - (r_top - s)
        out[f"sup_{label}_top"] = s_top
        out[f"sup_{label}_bottom"] = s_bot
        out[f"sup_{label}_mid"] = (s_top + s_bot) / 2.0

    return pd.DataFrame(out, index=idx)


def is_session_start(
    index: pd.DatetimeIndex,
    session: str = DEFAULT_SESSION,
    tz: str = DEFAULT_TZ,
) -> np.ndarray:
    """Pine ``IsSessionStart()``: True on the first bar inside the session.

    ``session`` uses Pine's ``"HHMM-HHMM"`` format, interpreted in ``tz``.
    """
    if index.tz is None:
        localized = index.tz_localize("UTC")
    else:
        localized = index
    et = localized.tz_convert(tz)

    start_str, end_str = session.split("-")
    start_min = int(start_str[:2]) * 60 + int(start_str[2:])
    end_min = int(end_str[:2]) * 60 + int(end_str[2:])

    minutes = (et.hour * 60 + et.minute).to_numpy()
    in_session = mask = (minutes >= start_min) & (minutes < end_min)

    out = in_session & ~np.roll(in_session, 1)
    out[0] = bool(in_session[0])
    return out


def session_start_times(
    index: pd.DatetimeIndex,
    session: str = DEFAULT_SESSION,
    tz: str = DEFAULT_TZ,
) -> pd.DatetimeIndex:
    """Timestamps of the first bar of each session."""
    mask = is_session_start(index, session, tz)
    return index[mask]