"""Arrival + extension-zone statistics for the London and Asia sessions.

Identical method to `arrival.py` / `reversal.py` (RTH), applied to the two
other validated session windows so the Pine session stack can render timing
and extension zones for every session, not only RTH:

  * arrival — first-passage minutes to each rung, median among hits, and
    cumulative P(first touch by t) at 5 milestones, per rung-side, TRAIN fold;
  * reversal — how far past a touched rung the excursion ran (ext p50/p75/p90),
    die-in-zone (touched this rung, never the next out), and back-to-anchor
    with its median time, per rung-side, TRAIN fold, n>=30.

Session windows and day-keying are the ones `sessions_stack.py` settled:

    LONDON  03:00-09:30 ET  (390 min)  bars keyed to their own day
    ASIA    18:00-03:00 ET  (540 min)  evening bars keyed to the NEXT day

Milestones are session-specific elapsed minutes:

    LONDON  04:00 / 05:30 / 07:00 / 08:30 / 09:30
    ASIA    20:00 / 22:00 / 00:00 / 02:00 / 03:00

Rungs are train-fitted from the same session frame (`percentile_ladder`), so
these arrival/zone constants index the ladders the indicator already draws.
London inherits its session verdict from sessions_stack; Asia's numbers are
NOMINAL by the same verdict and read as indicative.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.session_timing
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from .features import (
    DATA, HOLDOUT_START, TARGET_P, VOL_FOR_TICKER, _read, _to_et,
    percentile_ladder,
)

MILES = {
    "LONDON": (60, 150, 240, 330, 390),   # 04:00 05:30 07:00 08:30 09:30
    "ASIA": (120, 240, 360, 480, 540),    # 20:00 22:00 00:00 02:00 03:00
}
PRIORITY = (0.35, 0.25, 0.15, 0.10)  # reversal rows; 5% has no next rung


def _sess_bars_keys(bars, kind):
    """Session-window slice + per-session key (same as sessions_stack)."""
    idx = bars.index
    mins = idx.hour * 60 + idx.minute
    if kind == "ASIA":
        sel = (mins >= 1080) | (mins < 180)
        sub = bars[sel]
        m = sub.index.hour * 60 + sub.index.minute
        key = np.where(m >= 1080, (sub.index + pd.Timedelta(days=1)).date,
                       sub.index.date)
    else:
        sel = (mins >= 180) & (mins < 570)
        sub = bars[sel]
        key = sub.index.date
    return sub, key


def run(ticker: str = "ES1") -> dict:
    from .sessions_stack import _frame

    vol_name = VOL_FOR_TICKER[ticker]
    bars = _to_et(_read(DATA / f"{ticker}_1m.parquet"))
    vol = _to_et(_read(DATA / f"{vol_name}_1d.parquet"))
    vd = pd.DatetimeIndex(vol.index).date
    vix_prev = pd.Series(vol["close"].to_numpy(), index=vd).shift(1)

    out = {"ticker": ticker, "sessions": {}}
    for kind in ("LONDON", "ASIA"):
        s = _frame(bars, vix_prev, kind)
        tr = s[s.index < HOLDOUT_START]
        lad = percentile_ladder(tr)

        sub, key = _sess_bars_keys(bars, kind)
        sub = sub.copy()
        sub["sess"] = key
        paths = {}
        for day, b in sub.groupby("sess"):
            t = b.index
            paths[day] = (b["high"].to_numpy(float), b["low"].to_numpy(float),
                          ((t - t[0]).total_seconds() / 60.0).to_numpy(float))

        out["sessions"][kind] = {"arrival": _arrival(tr, paths, lad, kind),
                                 "reversal": _reversal(tr, paths, lad)}
    return out


def _arrival(tr, paths, lad, kind) -> list:
    ms = MILES[kind]
    rows = []
    for i, p in enumerate(TARGET_P):
        for side, col in (("up", "c_up"), ("dn", "c_dn")):
            c = float(lad[col][i])
            tmins = []
            for ts, row in tr.iterrows():
                pp = paths.get(ts.date())
                if pp is None or row["EV"] <= 0:
                    continue
                hi, lo, tm = pp
                S, EV = float(row["S"]), float(row["EV"])
                run = ((np.maximum.accumulate(hi) - S) / EV if side == "up"
                       else (S - np.minimum.accumulate(lo)) / EV)
                hit = np.flatnonzero(run >= c)
                if hit.size:
                    tmins.append(float(tm[int(hit[0])]))
            n = len(tr)
            med = float(np.median(tmins)) if tmins else -1.0
            # cum over ALL train sessions: P(first touch by m) = hits/n
            cum = [round(int(sum(1 for t in tmins if t <= m)) / n, 4)
                   if n else 0.0 for m in ms]
            rows.append({"p": p, "side": side, "c": round(c, 4),
                         "hits": len(tmins),
                         "med": int(round(med)) if med >= 0 else -1,
                         "cum": cum})
    return rows


def _reversal(tr, paths, lad) -> list:
    cells = []
    for i, p in enumerate(TARGET_P):
        if p not in PRIORITY:
            continue
        for side, col in (("up", "c_up"), ("dn", "c_dn")):
            c = float(lad[col][i])
            c2 = float(lad[col][i + 1]) if i + 1 < len(TARGET_P) else None
            hits = die = back = 0
            ext, mins = [], []
            for ts, row in tr.iterrows():
                pp = paths.get(ts.date())
                if pp is None or row["EV"] <= 0:
                    continue
                hi, lo, tm = pp
                S, EV = float(row["S"]), float(row["EV"])
                lvl = S + EV * c if side == "up" else S - EV * c
                arr = hi if side == "up" else lo
                hit = np.flatnonzero(arr >= lvl if side == "up" else arr <= lvl)
                if hit.size == 0:
                    continue
                hits += 1
                exc = float(row["up"] if side == "up" else row["dn"])
                ext.append(exc - c)
                if c2 is not None:
                    lvl2 = S + EV * c2 if side == "up" else S - EV * c2
                    hit2 = np.flatnonzero(arr >= lvl2 if side == "up"
                                          else arr <= lvl2)
                    if hit2.size == 0:
                        die += 1
                j = int(hit[0])
                rest = lo[j:] if side == "up" else hi[j:]
                b2 = np.flatnonzero(rest <= S if side == "up" else rest >= S)
                if b2.size:
                    back += 1
                    mins.append(float(tm[j + int(b2[0])] - tm[j]))
            q = (lambda k: round(float(np.percentile(ext, k)), 4)) if ext else \
                (lambda k: None)
            cells.append({"rung": p, "side": side, "c": round(c, 4),
                          "n_hits": hits,
                          "ext_p50": q(50), "ext_p75": q(75), "ext_p90": q(90),
                          "die_pct": round(die / hits, 4) if hits else None,
                          "back_pct": round(back / hits, 4) if hits else None,
                          "back_med_min": int(round(np.median(mins)))
                          if mins else None})
    return cells


def _sess_bars_keys(bars, kind):
    idx = bars.index
    mins = idx.hour * 60 + idx.minute
    if kind == "ASIA":
        sel = (mins >= 1080) | (mins < 180)
        sub = bars[sel]
        m = sub.index.hour * 60 + sub.index.minute
        key = np.where(m >= 1080, (sub.index + pd.Timedelta(days=1)).date,
                       sub.index.date)
    else:
        sel = (mins >= 180) & (mins < 570)
        sub = bars[sel]
        key = sub.index.date
    return sub, key


# _frame is imported here to avoid a cycle at module import time
def _frame(bars, vix_prev, kind):
    from .sessions_stack import _frame as _sf
    return _sf(bars, vix_prev, kind)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    args = ap.parse_args(argv)

    r = run(args.ticker)
    print(f"\n{r['ticker']} — per-session arrival + reversal (train fold)\n")
    from .features import OUT_DIR
    import math
    for kind, rec in r["sessions"].items():
        print(f"  {kind}")
        print(f"    {'rung':>5} {'side':>3} {'hits':>5} {'med':>6} "
              + " ".join(f"{f'by {m}':>7}" for m in _ms_clock(kind)))
        for row in rec["arrival"]:
            if row["med"] < 0:
                continue
            print(f"    {row['p']:>5.0%} {row['side']:>3} {row['hits']:>5} "
                  f"{_clock(kind, row['med']):>6} "
                  + " ".join(f"{c*100:>6.1f}" for c in row["cum"]))
        print()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"session_timing_{args.ticker}.json"
    dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"  wrote {dest}")
    return 0


def _clock(kind, m):
    start = 180 if kind == "LONDON" else 1080
    mm = int(round(start + float(m))) % (24 * 60)
    return f"{mm // 60:02d}:{mm % 60:02d}"


def _ms_clock(kind):
    return [_clock(kind, m) for m in MILES[kind]]


if __name__ == "__main__":
    raise SystemExit(main())