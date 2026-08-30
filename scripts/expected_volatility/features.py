"""Canonical session frame for the Expected Volatility study — one definition,
used by every downstream script.

This module exists because the earlier scripts each rebuilt the session frame
themselves. Three copies of "what is the anchor, what is the vol read, when is
it known" is how a corrected definition reaches one consumer and not the others.
`build_sessions()` is now the only place any of it is decided.

Everything here is **as-of T-1 or earlier**, with two deliberate exceptions that
are known before the RTH session opens and are therefore legitimate inputs to an
RTH-forward level:

  * ``rth_open``  — today's 09:30 ET opening print
  * ``vix_open``  — today's VIX daily open, published in CBOE's global session
                    from 03:15 ET

Nothing else in the frame may be read from day T. The VIX ecosystem pack is
shifted one session before it is joined.

Definitions
-----------
anchor        ``prev_close`` = last print strictly before 16:00 ET on the prior
              session (the Pine convention); ``rth_open`` = today's 09:30 print.
vol input     an annualised percentage, so that ``a = v / sqrt(252) / 100`` and
              ``EV = S * a`` are one line of code for every source.
excursion     ``up = (high - S) / EV``, ``dn = (S - low) / EV`` over 09:30-15:59.

`har_rv` and `blend` are fit on the TRAIN fold only and applied to both folds;
`HOLDOUT_START` is the single place that boundary is defined.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT_DIR = DATA / "expected_volatility"
FIG_DIR = REPO / "docs" / "indicators" / "ExpectedVolatility" / "figures"

# The 0DTE break: also the VIX1D inception and the five-way vol-source common
# window. The regime we can measure and the regime we trade coincide.
ODTE_START = "2022-05-13"
HOLDOUT_START = "2025-10-21"  # last ~20% of the common window, chronological

VOL_FOR_TICKER = {
    "ES1": "VIX", "NQ1": "VXN", "RTY1": "RVX",
    "YM1": "VXD", "CL1": "OVX", "GC1": "GVZ",
}

ANCHORS = ("prev_close", "rth_open")
VOL_INPUTS = ("vix_prev_close", "vix_open", "har_rv", "blend")

# Target touch probabilities. The ladder inverts the empirical excursion CDF at
# these, so each rung carries a known P(touch) by construction.
TARGET_P = (0.80, 0.65, 0.50, 0.35, 0.25, 0.15, 0.10, 0.05)

RV_SAMPLE_MIN = 5  # 1m sampling is microstructure noise; 5m is the usual choice

# Session windows in ET minutes-from-midnight. These tile the CME trading day
# 18:00 -> 17:00 exactly: 540 + 390 + 150 + 240 + 60 = 1380.
SESSIONS: dict[str, tuple[int, int]] = {
    "Asia (18:00-03:00)": (1080, 180),
    "London (03:00-09:30)": (180, 570),
    "NY_AM (09:30-12:00)": (570, 720),
    "NY_PM (12:00-16:00)": (720, 960),
    "Settlement (16:00-17:00)": (960, 1020),
}
SESSION_MINUTES = {
    "Asia (18:00-03:00)": 540, "London (03:00-09:30)": 390,
    "NY_AM (09:30-12:00)": 150, "NY_PM (12:00-16:00)": 240,
    "Settlement (16:00-17:00)": 60,
}
TRADING_DAY_MINUTES = 1380

# VIX ecosystem pack. Every one is joined shifted by one session.
PACK = {
    "vix1d": "VIX1D_1d", "vix9d": "VIX9D_1d", "vix3m": "VIX3M_1d",
    "vvix": "VVIX_1d", "vx1": "VX1_1d", "vx2": "VX2_1d",
}


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def _to_et(df: pd.DataFrame) -> pd.DataFrame:
    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    out = df.copy()
    out.index = idx.tz_convert("America/New_York")
    return out.sort_index()


def _daily(name: str, col: str = "close") -> pd.Series:
    """A daily series keyed by ET date. Not yet shifted — callers shift."""
    d = _to_et(_read(DATA / f"{name}.parquet"))
    return pd.Series(d[col].to_numpy(), index=pd.DatetimeIndex(d.index).date)


def rth_realised_vol(bars: pd.DataFrame) -> pd.Series:
    """Daily RTH realised vol as a DAILY sigma, on the same footing as
    ``VIX/sqrt(252)/100`` so that ``EV = S * sigma`` holds for every input."""
    rth = bars.between_time("09:30", "15:59")
    px = rth["close"].resample(f"{RV_SAMPLE_MIN}min").last().dropna()
    r2 = np.log(px).diff() ** 2
    # Drop each day's first sample: it spans the overnight gap and would put
    # close-to-open variance into an intraday estimator.
    day = pd.Series(px.index.date, index=px.index)
    r2 = r2[day.values == day.shift(1).values]
    var = r2.groupby(r2.index.date).sum()
    n = r2.groupby(r2.index.date).size()
    return np.sqrt(var[n >= 50])  # drop half days


def _ols(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(np.column_stack([np.ones(len(x)), x]), y, rcond=None)[0]


def _apply(beta: np.ndarray, x: np.ndarray) -> np.ndarray:
    return beta[0] + x @ beta[1:]


@dataclass
class Sessions:
    df: pd.DataFrame
    bars: pd.DataFrame
    ticker: str
    vol_name: str
    har_beta: np.ndarray
    blend_beta: np.ndarray


def build_sessions(ticker: str = "ES1", start: str = ODTE_START) -> Sessions:
    vol_name = VOL_FOR_TICKER[ticker]
    bars = _to_et(_read(DATA / f"{ticker}_1m.parquet"))
    vol = _to_et(_read(DATA / f"{vol_name}_1d.parquet"))

    pre16 = bars.between_time("00:00", "15:59")
    settle = pre16.groupby(pre16.index.date)["close"].last()

    rth = bars.between_time("09:30", "15:59")
    g = rth.groupby(rth.index.date)
    s = pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(),
        "low": g["low"].min(), "close": g["close"].last(),
        "bars": g["close"].size(),
    })
    s = s[s["bars"] >= 200]

    vd = pd.DatetimeIndex(vol.index).date
    s["vix_prev_close"] = pd.Series(vol["close"].to_numpy(), index=vd).shift(1).reindex(s.index)
    s["vix_open"] = pd.Series(vol["open"].to_numpy(), index=vd).reindex(s.index)
    s["prev_close"] = settle.shift(1).reindex(s.index)
    s["rth_open"] = s["open"]

    rv = rth_realised_vol(bars)
    s["rv_realised_ann"] = rv.reindex(s.index) * 100 * math.sqrt(252)

    # Close-to-close 20d realised, as-of T-1. A DIFFERENT estimator from
    # rv_realised_ann above (which is intraday RTH): this one spans the
    # overnight gap. The vol-input horse race in measure_baselines section G
    # is defined on this one, so the two are kept separate rather than merged.
    anchor_px = pd.Series(settle.to_numpy(), index=pd.DatetimeIndex(settle.index))
    lr = np.log(anchor_px).diff()
    rv20 = (lr.rolling(20).std() * math.sqrt(252) * 100).shift(1)
    s["rv20_cc"] = pd.Series(rv20.to_numpy(), index=rv20.index.date).reindex(s.index)

    # --- HAR-RV (Corsi 2009), log target, coefficients from the train fold only
    lv = np.log(rv.replace(0.0, np.nan)).dropna()
    des = pd.DataFrame({
        "rv_d": lv.shift(1),
        "rv_w": lv.shift(1).rolling(5).mean(),
        "rv_m": lv.shift(1).rolling(22).mean(),
        "y": lv,
    }).dropna()
    des = des[des.index >= pd.Timestamp(ODTE_START).date()]
    tr = des[des.index < pd.Timestamp(HOLDOUT_START).date()]
    if len(tr) < 100:
        raise ValueError(f"{ticker}: only {len(tr)} HAR train rows")
    cols = ["rv_d", "rv_w", "rv_m"]
    har_beta = _ols(tr[cols].to_numpy(), tr["y"].to_numpy())
    s["har_rv"] = pd.Series(
        np.exp(_apply(har_beta, des[cols].to_numpy())) * 100 * math.sqrt(252),
        index=des.index,
    ).reindex(s.index)

    # --- blend: log realised on log VIX and log HAR, again train-only
    bi = s[["vix_prev_close", "har_rv", "rv_realised_ann"]].dropna()
    bi = bi[bi.index >= pd.Timestamp(ODTE_START).date()]
    btr = bi[bi.index < pd.Timestamp(HOLDOUT_START).date()]
    blend_beta = _ols(
        np.log(btr[["vix_prev_close", "har_rv"]].to_numpy()),
        np.log(btr["rv_realised_ann"].to_numpy()),
    )
    s["blend"] = pd.Series(
        np.exp(_apply(blend_beta, np.log(bi[["vix_prev_close", "har_rv"]].to_numpy()))),
        index=bi.index,
    ).reindex(s.index)

    # --- VIX ecosystem pack, every column shifted one session before joining
    for key, fn in PACK.items():
        try:
            s[key] = _daily(fn).shift(1).reindex(s.index)
        except FileNotFoundError:
            s[key] = np.nan

    v = s["vix_prev_close"]
    s["term_1d_30d"] = s["vix1d"] - v        # >0 = front-loaded / event risk
    s["term_9d_30d"] = s["vix9d"] - v
    s["term_30d_90d"] = v - s["vix3m"]       # >0 = inverted (stress)
    s["vx_basis"] = s["vx1"] - v             # futures over spot = contango
    s["vx_curve"] = s["vx2"] - s["vx1"]
    s["vrp_20d"] = v - s["rv_realised_ann"].shift(1).rolling(20).mean()
    s["vvix_ratio"] = s["vvix"] / v
    s["vix_pctl_252"] = v.rolling(252, min_periods=63).rank(pct=True) * 100

    s.index = pd.DatetimeIndex(s.index)
    s = s[s.index >= pd.Timestamp(start)]
    return Sessions(s, bars, ticker, vol_name, har_beta, blend_beta)


def frame_for(df: pd.DataFrame, anchor: str, vol_input: str) -> pd.DataFrame:
    """Attach S / EV / normalised excursions for one (anchor, vol) choice."""
    f = df.dropna(subset=[anchor, vol_input, "high", "low"]).copy()
    f["S"] = f[anchor]
    f["a"] = f[vol_input] / math.sqrt(252) / 100.0
    f["EV"] = f["S"] * f["a"]
    f = f[f["EV"] > 0]
    f["up"] = (f["high"] - f["S"]) / f["EV"]
    f["dn"] = (f["S"] - f["low"]) / f["EV"]
    f["mx"] = f[["up", "dn"]].max(axis=1)
    f["ret_n"] = (f["close"] - f["S"]) / f["EV"]
    f["gap_ev"] = (f["open"] - f["prev_close"]) / f["EV"]
    f["abs_pct"] = (f["close"] - f["S"]).abs() / f["S"] * 100.0
    return f


def percentile_ladder(f: pd.DataFrame, targets=TARGET_P) -> pd.DataFrame:
    """Invert the empirical excursion CDF: the rung for target p is the
    (1-p) quantile of the excursion, taken separately for each side."""
    return pd.DataFrame([
        {"target_p": p,
         "c_up": float(np.quantile(f["up"], 1 - p)),
         "c_dn": float(np.quantile(f["dn"], 1 - p))}
        for p in targets
    ])


def folds(f: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return f[f.index < HOLDOUT_START], f[f.index >= HOLDOUT_START]
