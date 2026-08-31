"""Per-session PATH extraction — the shared substrate for every study that
needs to know *when* a level was reached, not merely *whether* it was.

`features.build_sessions` collapses each session to its high/low/close. That is
enough to fit a ladder, because a ladder only asks "was this distance reached".
It is not enough for anything a trader actually does:

  * a bracket asks which of two levels was reached FIRST — and the marginal
    touch rates the ladder reports cannot answer that, because both levels are
    frequently touched in the same session;
  * conditioning on time-of-touch asks at what MINUTE a rung was reached, which
    the session aggregate has thrown away.

So this module re-reads the 1-minute bars and, for each session, records the
first-passage time to every distance on a fixed grid, separately up and down.
The running high and running low are monotone by construction, which makes each
first-passage lookup a `searchsorted` rather than a scan.

Two definitions, deliberately matching the Pine indicator so its on-chart table
and these studies are measuring the same object:

    RTH   09:30-15:59 ET, anchored on the 09:30 open
    ON    18:00-09:29 ET, anchored on the 18:00 open, keyed to the RTH day it
          leads into (so a Sunday-evening session is keyed to Monday)

Vol is the prior session's VIX close in both cases — settled at 16:00 ET, so it
is known before either anchor exists. `rth_open` is the anchor the anchor-control
study settled on; see RESEARCH_REPORT §2 for why `prev_close` was rejected.

Ties
----
Within a 1-minute bar the order of two touches is unknowable. `t_up == t_dn` is
reported as a tie and every consumer must decide what to do with it; none of
them may silently drop it, because the tie rate rises with how tight the bracket
is and is therefore worst exactly where it matters most.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.paths
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import (
    DATA, HOLDOUT_START, ODTE_START, TARGET_P, VOL_FOR_TICKER, _read, _to_et,
)

RTH_START_MIN = 9 * 60 + 30
RTH_END_MIN = 16 * 60
ON_START_MIN = 18 * 60
ON_END_MIN = 9 * 60 + 30

# Distance grid in EV units. 0.025 is finer than the tick on any rung we fit
# (the tightest is 0.0766 EV) and 1.5 is past the 5% rung on both sides, so the
# grid brackets every level any consumer will ask about. Anything outside it
# returns +inf rather than being clipped to the edge, which would fabricate a
# touch that never happened.
GRID = np.round(np.arange(0.025, 1.5001, 0.025), 4)

# A half day (13:00 ET close, ~210 bars) IS a session and the fitted ladder
# includes them, so excluding them here would silently measure a different
# object than the one deployed: dropping 48 low-excursion sessions raised every
# RTH quantile by 0.008-0.020 EV, which reads exactly like a calibration error.
# They are kept and flagged instead, so a study whose clock matters can exclude
# them explicitly and say so.
MIN_BARS = {"RTH": 60, "ON": 600}
FULL_BARS = {"RTH": 380, "ON": 900}


@dataclass
class Paths:
    """One row per session; `t_up`/`t_dn` are (n_sessions, len(GRID))."""
    ticker: str
    kind: str
    idx: pd.DatetimeIndex
    S: np.ndarray
    EV: np.ndarray
    ret_n: np.ndarray
    up: np.ndarray
    dn: np.ndarray
    t_up: np.ndarray
    t_dn: np.ndarray
    dow: np.ndarray
    dur: np.ndarray
    nbars: np.ndarray
    half: np.ndarray
    grid: np.ndarray = None

    def __post_init__(self):
        if self.grid is None:
            self.grid = GRID

    def mask(self, train: bool) -> np.ndarray:
        h = pd.Timestamp(HOLDOUT_START)
        return np.asarray(self.idx < h) if train else np.asarray(self.idx >= h)

    def first_at(self, side: str, c: float) -> np.ndarray:
        """First-passage minute to distance `c`, interpolated on the grid.

        Snapping to the nearest grid point would move a level by up to half a
        grid step, which at the 80% rung (0.0766 EV) is a 16% error in the level
        itself. Taking the next grid point OUT instead is conservative: it can
        only ever report a touch later than the truth, never earlier.
        """
        t = self.t_up if side == "up" else self.t_dn
        j = int(np.searchsorted(self.grid, c - 1e-9, side="left"))
        if j >= len(self.grid):
            return np.full(len(self.idx), np.inf)
        return t[:, j]


def _sessions_of(bars: pd.DataFrame, kind: str) -> pd.core.groupby.DataFrameGroupBy:
    idx = bars.index
    mins = idx.hour * 60 + idx.minute
    if kind == "RTH":
        sel = (mins >= RTH_START_MIN) & (mins < RTH_END_MIN)
        sub = bars[sel].copy()
        sub["sess_day"] = sub.index.date
    else:
        sel = (mins >= ON_START_MIN) | (mins < ON_END_MIN)
        sub = bars[sel].copy()
        m = sub.index.hour * 60 + sub.index.minute
        # Evening bars belong to the NEXT calendar day's session; a Friday
        # evening therefore keys to Saturday and is dropped by the RTH join,
        # while a Sunday evening keys to Monday and is kept.
        sub["sess_day"] = np.where(
            m >= ON_START_MIN, (sub.index + pd.Timedelta(days=1)).date, sub.index.date)
    return sub.groupby("sess_day")


def build_paths(ticker: str = "ES1", kind: str = "RTH",
                start: str = ODTE_START) -> Paths:
    vol_name = VOL_FOR_TICKER[ticker]
    bars = _to_et(_read(DATA / f"{ticker}_1m.parquet"))
    vol = _to_et(_read(DATA / f"{vol_name}_1d.parquet"))

    vd = pd.DatetimeIndex(vol.index).date
    vix_prev = pd.Series(vol["close"].to_numpy(), index=vd).shift(1)

    g = _sessions_of(bars, kind)
    keys, S_, EV_, retn_, up_, dn_, tu_, td_, dow_, dur_, nb_ = ([] for _ in range(11))

    for day, grp in g:
        if len(grp) < MIN_BARS[kind]:
            continue
        v = vix_prev.get(day, np.nan)
        if not np.isfinite(v) or v <= 0:
            continue
        S = float(grp["open"].iloc[0])
        EV = S * float(v) / math.sqrt(252) / 100.0
        if EV <= 0:
            continue

        h = grp["high"].to_numpy(dtype=float)
        lo = grp["low"].to_numpy(dtype=float)
        up_run = (np.maximum.accumulate(h) - S) / EV
        dn_run = (S - np.minimum.accumulate(lo)) / EV

        t = grp.index
        mo = ((t - t[0]).total_seconds() / 60.0).to_numpy(dtype=float)
        n = len(mo)

        iu = np.searchsorted(up_run, GRID, side="left")
        idn = np.searchsorted(dn_run, GRID, side="left")
        tu = np.where(iu < n, mo[np.minimum(iu, n - 1)], np.inf)
        td = np.where(idn < n, mo[np.minimum(idn, n - 1)], np.inf)

        keys.append(pd.Timestamp(day))
        S_.append(S); EV_.append(EV)
        retn_.append((float(grp["close"].iloc[-1]) - S) / EV)
        up_.append(float(up_run[-1])); dn_.append(float(dn_run[-1]))
        tu_.append(tu); td_.append(td)
        dow_.append(pd.Timestamp(day).weekday())
        dur_.append(float(mo[-1]))
        nb_.append(n)

    idx = pd.DatetimeIndex(keys)
    keep = idx >= pd.Timestamp(start)
    return Paths(
        ticker=ticker, kind=kind, idx=idx[keep],
        S=np.array(S_)[keep], EV=np.array(EV_)[keep],
        ret_n=np.array(retn_)[keep], up=np.array(up_)[keep], dn=np.array(dn_)[keep],
        t_up=np.array(tu_)[keep], t_dn=np.array(td_)[keep],
        dow=np.array(dow_)[keep], dur=np.array(dur_)[keep],
        nbars=np.array(nb_)[keep],
        half=np.array(nb_)[keep] < FULL_BARS[kind],
    )


def ladder_from(p: Paths, mask: np.ndarray | None = None,
                targets=TARGET_P) -> pd.DataFrame:
    """Same inversion as `features.percentile_ladder`, on path-derived
    excursions. Reproducing the fitted constants is the check that this module's
    session definition agrees with the one the ladder was fitted on."""
    u = p.up if mask is None else p.up[mask]
    d = p.dn if mask is None else p.dn[mask]
    return pd.DataFrame([
        {"target_p": t, "c_up": float(np.quantile(u, 1 - t)),
         "c_dn": float(np.quantile(d, 1 - t))} for t in targets])


def main() -> int:
    print("Path extraction — reproducing the fitted ladder as a self-check.")
    print("Pine constants were fitted on the TRAIN fold, so that is what must "
          "match; the holdout column is the out-of-sample read.\n")
    pine = {
        "RTH": (np.array([0.1239, 0.2215, 0.3397, 0.4974, 0.5982, 0.7456, 0.8569, 1.0267]),
                np.array([0.1029, 0.2108, 0.3267, 0.4787, 0.6258, 0.8245, 1.0191, 1.2564])),
        "ON": (np.array([0.0931, 0.1631, 0.2381, 0.3231, 0.3983, 0.5152, 0.6024, 0.7793]),
               np.array([0.0766, 0.1434, 0.2259, 0.3269, 0.4317, 0.5757, 0.6843, 0.8768])),
    }
    for kind in ("RTH", "ON"):
        p = build_paths(kind=kind)
        tr = p.mask(True)
        lad = ladder_from(p, tr)
        pu, pd_ = pine[kind]
        du = np.abs(lad["c_up"].to_numpy() - pu)
        dd = np.abs(lad["c_dn"].to_numpy() - pd_)
        print(f"{kind}: {len(p.idx)} sessions "
              f"({p.idx.min().date()} -> {p.idx.max().date()}), "
              f"train {tr.sum()} / holdout {(~tr).sum()}")
        print(f"  {'p':>5} {'c_up':>7} {'pine':>7} {'d':>7} | "
              f"{'c_dn':>7} {'pine':>7} {'d':>7}")
        for i, t in enumerate(TARGET_P):
            print(f"  {t:>5.0%} {lad['c_up'][i]:>7.4f} {pu[i]:>7.4f} {du[i]:>7.4f} | "
                  f"{lad['c_dn'][i]:>7.4f} {pd_[i]:>7.4f} {dd[i]:>7.4f}")
        print(f"  max |delta| vs Pine: up {du.max():.4f}  dn {dd.max():.4f}")
        print(f"  median session duration: {np.median(p.dur):.0f} min\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
