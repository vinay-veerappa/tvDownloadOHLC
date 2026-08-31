"""Study D — where does a move DIE? Extension zones, reversal, terminal cluster.

`arrival.py` (§5.4) answers WHEN a rung is typically first reached. A trader
looking at a touched level asks three further questions, all about the move's
END:

  * how far past the level does the excursion typically EXTEND — the zone
    ladder behind a touched rung, banded TYPICAL / DEEP / STRETCHED / RISK;
  * where does a move DIE — sessions that touched this rung but never the
    next one out, i.e. the rung the excursion terminated in;
  * does the move come back to the anchor, and how long the round trip took.

All three are historical distributions over the same 1-minute paths, computed
per rung-side on train and holdout folds separately, rungs train-fitted, full
sessions only (half-days excluded and counted — a 13:00 close truncates the
reversion clock).

Honesty rules this module enforces on itself
--------------------------------------------
**Zones are percentiles of the excursion, not of a trade.** Extension
percentiles are taken among sessions that TOUCHED the rung, so a zone boundary
means "among historical touches, the move ran this far past the level p50 of
the time" — never a claim about a live position.

**Back-to-anchor is context, not an edge.** §3.1 measured that fading the
touch loses at every rung; the reversion rate here describes where moves
end, and the report renders it as such.

**The reversion clock starts AT THE TOUCH.** Minutes are measured from the
first touch, not from the open — so the stat answers "how long did the round
trip historically take" without any live touch-tracking. Rungs are nested;
nothing is pooled across them.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.reversal
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from .features import (
    DATA, TARGET_P, build_sessions, frame_for, folds, percentile_ladder,
)
from .paths import _read, _to_et

PRIORITY = (0.35, 0.25, 0.15, 0.10, 0.05)
HALF_BARS = 380  # a full RTH is 390 minutes; half-days close at 13:00
BIN = 0.05       # terminal-cluster bin width, in EV


def _cells(frame, paths, lad, tag, min_bars=380):
    cells = []
    for i, p in enumerate(TARGET_P):
        if p not in PRIORITY:
            continue
        for side, col in (("up", "c_up"), ("dn", "c_dn")):
            c = float(lad[col][i])
            c2 = float(lad[col][i + 1]) if i + 1 < len(TARGET_P) else None
            hits = die = back = 0
            ext, mins = [], []
            for ts, row in frame.iterrows():
                pp = paths.get(ts.date())
                if pp is None or row["EV"] <= 0 or pp[2] < HALF_BARS:
                    continue
                hi, lo = pp[0], pp[1]
                S, EV = float(row["S"]), float(row["EV"])
                lvl = S + EV * c if side == "up" else S - EV * c
                arr = hi if side == "up" else lo
                hit_now = (arr >= lvl) if side == "up" else (arr <= lvl)
                touched = np.flatnonzero(hit_now)
                if touched.size == 0:
                    continue
                hits += 1
                exc = float(row["up"] if side == "up" else row["dn"])
                ext.append(exc - c)
                if c2 is not None:
                    lvl2 = S + EV * c2 if side == "up" else S - EV * c2
                    hit_next = (arr >= lvl2) if side == "up" else (arr <= lvl2)
                    if not hit_next.any():
                        die += 1
                j = int(touched[0])
                rest = lo[j:] if side == "up" else hi[j:]
                b2 = np.flatnonzero((rest <= S) if side == "up" else (rest >= S))
                if b2.size > 0:
                    back += 1
                    mins.append(int(b2[0]))
            q = (lambda a, k: round(float(np.percentile(a, k)), 4)) if ext else \
                (lambda a, k: None)
            cells.append({
                "rung": p, "side": side, "c": round(c, 4), "fold": tag,
                "n_hits": hits,
                "ext_p50": q(ext, 50), "ext_p75": q(ext, 75), "ext_p90": q(ext, 90),
                "die_pct": round(die / hits, 4) if hits else None,
                "back_pct": round(back / hits, 4) if hits else None,
                "back_med_min": int(np.median(mins)) if mins else None,
                "back_p75_min": int(np.percentile(mins, 75)) if mins else None,
            })
    return cells


def _terminal(frame, paths):
    mx, n = [], 0
    for ts, row in frame.iterrows():
        pp = paths.get(ts.date())
        if pp is None:
            continue
        n += 1
        mx.append(float(max(row["up"], row["dn"])))
    if not mx:
        return None
    h, edges = np.histogram(mx, bins=np.arange(0.0, 1.55, BIN))
    j = int(np.argmax(h))
    return {"lo": round(float(edges[j]), 4), "hi": round(float(edges[j + 1]), 4),
            "n": int(h[j]), "n_sessions": n}


def run(ticker: str = "ES1") -> dict:
    ses = build_sessions(ticker)
    f = frame_for(ses.df, "rth_open", "vix_prev_close")
    tr, te = folds(f)
    lad = percentile_ladder(tr)

    bars = _to_et(_read(DATA / f"{ticker}_1m.parquet")).between_time("09:30", "15:59")
    paths = {d: (b["high"].to_numpy(float), b["low"].to_numpy(float), int(len(b)))
             for d, b in bars.groupby(bars.index.date)}

    n_half = int(sum(1 for ts, _ in f.iterrows()
                     if paths.get(ts.date()) and paths[ts.date()][2] < HALF_BARS))
    return {
        "ticker": ticker, "kind": "RTH", "n_sessions": int(len(f)),
        "n_half_excluded": n_half,
        "cells": _cells(tr, paths, lad, "train") + _cells(te, paths, lad, "holdout"),
        "terminal": {"train": _terminal(tr, paths), "holdout": _terminal(te, paths)},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    args = ap.parse_args(argv)

    r = run(args.ticker)
    print(f"\n{r['ticker']} RTH — where a move dies: zones, reversal, terminal cluster")
    print(f"  full sessions only ({r['n_half_excluded']} half-days excluded). "
          "Historical frequencies, not forecasts.\n")
    print(f"  {'rung':>5} {'side':>3} | {'hits':>5} {'p50':>6} {'p75':>6} {'p90':>6} "
          f"| {'die@':>5} {'back@':>6} {'med':>5} {'p75':>5}")
    for fold in ("train", "holdout"):
        print(f"\n  {fold.upper()}")
        for c in r["cells"]:
            if c["fold"] != fold or c["n_hits"] < 30:
                continue
            if c["ext_p50"] is None or c["die_pct"] is None:
                # all-None stats (e.g. median undefined when every touch
                # reverted instantly) — print what exists, skip formatting
                print(f"  {c['rung']:>5.0%} {c['side']:>3} | {c['n_hits']:>5}  (stats undefined)")
                continue
            print(f"  {c['rung']:>5.0%} {c['side']:>3} | {c['n_hits']:>5} "
                  f"{c['ext_p50']:>6.3f} {c['ext_p75']:>6.3f} {c['ext_p90']:>6.3f} "
                  f"| {c['die_pct']:>5.0%} {c['back_pct']:>6.0%} "
                  f"{c['back_med_min'] if c['back_med_min'] is not None else -1:>4}m "
                  f"{c['back_p75_min'] if c['back_p75_min'] is not None else -1:>4}m")
    for fold in ("train", "holdout"):
        t = r["terminal"][fold]
        if t:
            print(f"\n  modal terminal excursion ({fold}): "
                  f"{t['lo']:.2f}-{t['hi']:.2f} EV  ({t['n']} of {t['n_sessions']} sessions)")

    from .features import OUT_DIR
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"reversal_{args.ticker}_RTH.json"
    dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"\n  wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())