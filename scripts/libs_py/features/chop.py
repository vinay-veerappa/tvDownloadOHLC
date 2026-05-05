"""
Composite chop score combining market internals signals.

Requires upstream columns (from internals.py and vwap.py):
    tick_persistence    (optional — degrades gracefully)
    vold_slope          (optional)
    trin_avg            (optional)
    vwap_cross_count    (optional)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_chop_score(df: pd.DataFrame, config=None) -> pd.DataFrame:
    """
    Compute the composite chop score from 3 internals sub-scores.

    Adds columns:
        chop_tick_score   — int 0-2 (tick persistence sub-score)
        chop_vold_score   — int 0-1 (VOLD slope sub-score)
        chop_trin_score   — int 0-1 (TRIN regime sub-score)
        chop_score        — int 0-4, sum of above
        chop_vwap_flag    — bool, instrument-level chop via VWAP crosses
        chop_regime       — categorical: "trending" | "mixed" | "choppy"

    Config defaults (used when config is None or keys are missing):
        tick_persistence.thresholds = [150, 350]
        vold_slope.threshold        = 0.0
        trin_regime.chop_band       = [0.9, 1.1]
        vwap_cross.max_crosses      = 4
    """
    # ── Config ────────────────────────────────────────────────────────────
    tick_thresholds  = [150, 350]
    vold_threshold   = 0.0
    chop_band        = (0.9, 1.1)
    max_vwap_crosses = 4

    if config is not None:
        try:
            tick_thresholds = list(config.chop.tick_persistence["thresholds"])
        except (AttributeError, KeyError, TypeError):
            pass
        try:
            vold_threshold = float(config.chop.vold_slope["threshold"])
        except (AttributeError, KeyError, TypeError):
            pass
        try:
            chop_band = tuple(config.chop.trin_regime["chop_band"])
        except (AttributeError, KeyError, TypeError):
            pass
        try:
            max_vwap_crosses = int(config.chop.vwap_cross["max_crosses"])
        except (AttributeError, KeyError, TypeError):
            pass

    n = len(df)

    # ── tick score (0-2) ──────────────────────────────────────────────────
    if "tick_persistence" in df.columns:
        tp = df["tick_persistence"].values
        tick_score = np.where(
            tp < tick_thresholds[0], 0,
            np.where(tp <= tick_thresholds[1], 1, 2),
        ).astype(int)
    else:
        tick_score = np.zeros(n, dtype=int)
        logger.debug("tick_persistence absent — chop_tick_score defaulting to 0")

    # ── VOLD slope score (0-1) ────────────────────────────────────────────
    if "vold_slope" in df.columns:
        vs = df["vold_slope"].fillna(0.0).values
        vold_score = (np.abs(vs) > vold_threshold).astype(int)
    else:
        vold_score = np.zeros(n, dtype=int)
        logger.debug("vold_slope absent — chop_vold_score defaulting to 0")

    # ── TRIN score (0-1) outside chop band = trending ─────────────────────
    if "trin_avg" in df.columns:
        ta = df["trin_avg"].fillna(1.0).values
        trin_score = (
            (ta < chop_band[0]) | (ta > chop_band[1])
        ).astype(int)
    else:
        trin_score = np.zeros(n, dtype=int)
        logger.debug("trin_avg absent — chop_trin_score defaulting to 0")

    df["chop_tick_score"] = tick_score
    df["chop_vold_score"] = vold_score
    df["chop_trin_score"] = trin_score
    df["chop_score"]      = tick_score + vold_score + trin_score  # 0-4

    # ── VWAP cross flag (instrument-level chop) ───────────────────────────
    if "vwap_cross_count" in df.columns:
        df["chop_vwap_flag"] = df["vwap_cross_count"] > max_vwap_crosses
    else:
        df["chop_vwap_flag"] = False
        logger.debug("vwap_cross_count absent — chop_vwap_flag defaulting to False")

    # ── Chop regime label ─────────────────────────────────────────────────
    cs = df["chop_score"].values
    regime = np.where(cs >= 3, "trending",
              np.where(cs == 2, "mixed", "choppy"))
    df["chop_regime"] = pd.Categorical(
        regime,
        categories=["choppy", "mixed", "trending"],
        ordered=True,
    )

    return df
