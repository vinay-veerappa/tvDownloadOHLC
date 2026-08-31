"""Study C — WHEN is a rung typically reached? Historical arrival curves.

§2 of RESEARCH_REPORT places each rung at a distance carrying a known P(touch)
by the close. A trader standing at 11:00 with a rung untouched is not asking
that. They are asking two things the marginal touch rate cannot answer:

  * by WHEN in the session is a rung usually reached, among sessions that
    reach it at all;
  * if it is still untouched now, what is the chance it is reached at all
    before the close.

Both are historical distributions over first-passage time, measured on the same
paths substrate as `timing.py` and `bracket.py`. They are NOT forecasts of the
current session and NOT a record of when today's rungs were hit — per-session
hit timestamps are deliberately computed nowhere in this module.

Three pitfalls the obvious version of this study gets wrong
-----------------------------------------------------------
**Half days end at 13:00.** A 13:00 close can only depress late-session
arrival, so half days are excluded from every curve here (they remain in the
fitted ladder, which only asks whether a distance was reached). The exclusion
count is reported, never silent.

**The conditional-remaining denominator collapses.** `P(hit after t | unhit at
t)` conditions on sessions where the rung is untouched at t; late in the day,
on an outer rung, that pool is dominated by sessions that will never hit it.
Every conditional cell with fewer than `MIN_N = 30` unhit sessions behind it
is suppressed rather than published as a small-number probability.

**Rungs are nested** (reaching the 25% rung implies reaching the 35% one), so
no statistic is pooled across rungs — each cell stays one observation per
session, the same discipline `timing.py` documents.

Stability, predeclared
----------------------
Rungs are fit on the TRAIN fold. A milestone cumulative is called stable only
if the holdout value lies within ±`TOL_PP` pp of train at that milestone; the
pass count and the failing cells are reported, because a curve that does not
replicate is not a finding.

The overnight ladder is deliberately NOT run by default: its rungs are known
to be miscalibrated — systematically too narrow, RESEARCH_REPORT §2.3 — and
levels that sit too close are reached too early, so an ON arrival curve
computed on them would carry that width error into its timing. Pass `--kind
ON` explicitly only once that question is settled.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.arrival
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.arrival --kind ON
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from .features import OUT_DIR, TARGET_P
from .paths import (
    ON_END_MIN, ON_START_MIN, RTH_END_MIN, RTH_START_MIN, build_paths,
    ladder_from,
)

MIN_N = 30     # suppress a conditional cell with fewer unhit sessions than this
TOL_PP = 5.0   # predeclared stability tolerance on milestone cumulatives

RTH_LEN = RTH_END_MIN - RTH_START_MIN          # 390
ON_LEN = (24 * 60 - ON_START_MIN) + ON_END_MIN  # 930

# Milestones in elapsed minutes from the session open, labelled in ET.
MILESTONES = {
    "RTH": {"10:00": 30, "11:00": 90, "12:00": 150, "13:30": 240, "15:00": 330},
    "ON": {"20:00": 120, "23:00": 300, "02:00": 480, "05:00": 660, "08:00": 840},
}
# The rungs a trader actually deliberates over. 80/65/50% are near-certainties;
# they are measured and stored, just not printed.
PRIORITY = (0.35, 0.25, 0.15, 0.10, 0.05)


def _clock(kind: str, minutes: float) -> str:
    """Elapsed minutes from the session open -> ET wall clock."""
    start = RTH_START_MIN if kind == "RTH" else ON_START_MIN
    m = int(round(start + minutes)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def _fold_stats(t: np.ndarray, edges: np.ndarray, milestones: dict,
                kind: str) -> dict:
    """Arrival curves for one (rung, side, fold).

    `t` is first-passage minutes, `inf` where the rung was never reached.
    Cumulative cells use every session as denominator; the conditional
    'remaining' series uses only sessions still unhit at the edge and is
    suppressed below `MIN_N`.
    """
    n = len(t)
    hits = np.isfinite(t)
    out: dict = {"n": int(n), "hits": int(hits.sum()),
                 "touch_rate": round(float(hits.mean()), 4) if n else None}
    if hits.any():
        q25, med, q75 = np.quantile(t[hits], (0.25, 0.5, 0.75))
        out.update(hit_q25_min=round(float(q25), 1),
                   hit_med_min=round(float(med), 1),
                   hit_q75_min=round(float(q75), 1))
    else:
        out.update(hit_q25_min=None, hit_med_min=None, hit_q75_min=None)

    cum, rem, nun, mass = [], [], [], []
    for e in edges:
        cum.append(round(float((t <= e).mean()), 4) if n else None)
        k = int((t > e).sum())
        nun.append(k)
        rem.append(round(float((hits & (t > e)).sum() / k), 4)
                   if k >= MIN_N else None)
    out["cum"] = cum
    out["remaining"] = rem
    out["n_unhit"] = nun
    # Per-5-minute-bucket mass among sessions that ever hit: P(first touch
    # lands in (e-5, e]). This is the histogram the trader reads — when is the
    # level USUALLY hit — and `mode` is its peak, which is why the grid is
    # 5 minutes and not quarters or milestones.
    th = t[hits]
    out["mass"] = [round(float(((th > e - 5) & (th <= e)).mean()), 4)
                   if len(th) else None for e in edges]
    if len(th):
        j = int(np.argmax([0 if m is None else m for m in out["mass"]]))
        out["mode_min"] = int(edges[j]) - 5 + 2.5
        out["mode_from"] = _clock(kind, edges[j] - 5)
        out["mode_to"] = _clock(kind, edges[j])
        # The histogram in three numbers, as fractions of session length so
        # the same fields mean the same thing for ON (edges[-1] = 930).
        L = float(edges[-1])
        out["share_first15"] = round(float((th <= 0.15 * L).mean()), 4)
        out["share_mid"] = round(
            float(((th > 0.15 * L) & (th <= 0.85 * L)).mean()), 4)
        out["share_last15"] = round(float((th > 0.85 * L).mean()), 4)
    else:
        out["mode_min"] = None
        out["mode_from"] = None
        out["mode_to"] = None
        out["share_first15"] = None
        out["share_mid"] = None
        out["share_last15"] = None

    out["milestones"] = {}
    for ms, m in milestones.items():
        j = int(np.searchsorted(edges, m))
        out["milestones"][ms] = {"cum": cum[j], "remaining": rem[j],
                                 "n_unhit": nun[j]}
    return out


def run(ticker: str = "ES1", kind: str = "RTH") -> dict:
    p = build_paths(ticker=ticker, kind=kind)
    tr = p.mask(True)
    lad = ladder_from(p, tr)          # TRAIN-fitted rungs, same as Pine
    keep = ~p.half                    # half days end early; see docstring
    edges = np.arange(5, (RTH_LEN if kind == "RTH" else ON_LEN) + 1, 5)
    milestones = MILESTONES[kind]

    rungs = []
    tcache: dict[tuple[int, str], np.ndarray] = {}
    for i, target in enumerate(TARGET_P):
        for side, col in (("up", "c_up"), ("dn", "c_dn")):
            c = float(lad[col][i])
            t_all = p.first_at(side, c)
            tcache[(i, side)] = t_all
            rec = {"target_p": target, "side": side, "c": round(c, 4)}
            for fold, m in (("train", tr & keep), ("holdout", (~tr) & keep)):
                rec[fold] = _fold_stats(t_all[m], edges, milestones, kind)
            rungs.append(rec)

    # Day-of-week: §4.9 found Monday's RTH realises ~17% less on the pooled
    # ladder, so its timing face should differ too. Train fold only — the
    # holdout is ~38 sessions per weekday, too thin for a curve; the counts
    # are stored so the report can say so with numbers.
    DOW = ("Mon", "Tue", "Wed", "Thu", "Fri")
    by_dow = []
    for wd in range(5):
        dm = (p.dow == wd) & keep
        recs = []
        for i, target in enumerate(TARGET_P):
            for side, col in (("up", "c_up"), ("dn", "c_dn")):
                st = _fold_stats(tcache[(i, side)][dm & tr], edges,
                                 milestones, kind)
                recs.append({"target_p": target, "side": side,
                             "c": round(float(lad[col][i]), 4), "train": st})
        by_dow.append({"day": DOW[wd],
                       "n_train": int((dm & tr).sum()),
                       "n_holdout": int((dm & (~tr)).sum()),
                       "rungs": recs})

    cells, worst = [], None
    for r in rungs:
        for ms in milestones:
            a = r["train"]["milestones"][ms]["cum"]
            b = r["holdout"]["milestones"][ms]["cum"]
            if a is None or b is None or r["holdout"]["n"] < MIN_N:
                continue
            d = round(b - a, 4)
            cell = {"rung": r["target_p"], "side": r["side"], "milestone": ms,
                    "train": a, "holdout": b, "delta": d,
                    "pass": bool(abs(d) <= TOL_PP / 100.0)}
            cells.append(cell)
            if worst is None or abs(d) > abs(worst["delta"]):
                worst = cell

    # Does the holdout's modal bucket agree with train's?  A 5-minute bucket
    # is narrow and a 25-70 hit holdout makes the empirical mode jumpy, so
    # exact agreement is strict; +/-1 bucket (the adjacent 10-minute window)
    # is the honest reading, and cells under MIN_N holdout hits are skipped.
    mode_agree = []
    for r in rungs:
        a, b = r["train"]["mode_min"], r["holdout"]["mode_min"]
        if a is None or b is None or r["holdout"]["hits"] < MIN_N:
            continue
        mode_agree.append({"rung": r["target_p"], "side": r["side"],
                           "train_mode": a, "holdout_mode": b,
                           "exact": bool(a == b),
                           "within_10min": bool(abs(a - b) <= 5.0)})

    return {
        "ticker": ticker, "kind": kind, "min_n": MIN_N, "tolerance_pp": TOL_PP,
        "n_sessions": int(len(p.idx)),
        "n_train": int((tr & keep).sum()),
        "n_holdout": int(((~tr) & keep).sum()),
        "n_half_excluded": int(p.half.sum()),
        "edges": [int(e) for e in edges], "milestones": milestones,
        "rungs": rungs, "by_dow": by_dow,
        "stability": {"cells": len(cells), "pass": sum(c["pass"] for c in cells),
                      "worst": worst, "all": cells,
                      "mode_agree": mode_agree,
                      "mode_exact": sum(m["exact"] for m in mode_agree),
                      "mode_within_10min": sum(m["within_10min"] for m in mode_agree),
                      "n_mode_cells": len(mode_agree)},
    }


def _pc(x, w: int = 5) -> str:
    return f"{x:.0%}".rjust(w) if x is not None else "-".rjust(w)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    ap.add_argument("--kind", default="RTH", choices=["RTH", "ON"])
    args = ap.parse_args(argv)

    r = run(args.ticker, args.kind)
    edges = r["edges"]
    # 15-minute display rollup of the 5-minute mass — report convention.
    # mass[j] = P(first touch in (edges[j]-5, edges[j]]); a 15-min window
    # ending at edges[i+2] sums mass[i : i+3].
    nroll = (len(edges) // 3) * 3
    roll_ends = [edges[i + 2] for i in range(0, nroll, 3)]
    print(f"\n{'=' * 78}")
    print(f"{r['ticker']} {r['kind']} — rung ARRIVAL: when is a level typically reached")
    print(f"  full sessions only: train {r['n_train']} / holdout {r['n_holdout']}"
          f" ({r['n_half_excluded']} half-days excluded)")
    print("  rungs TRAIN-fitted, holdout out-of-sample. Historical frequencies —")
    print("  a description of past sessions, not a forecast of today's.\n")

    for fold in ("train", "holdout"):
        print(f"\n  {fold.upper()} — arrival histogram, 15-min buckets "
              f"(share of hit sessions arriving by then)")
        print(f"  {'rung':>4} {'side':>3} {'hits':>5} {'median':>7} "
              f"{'mode':>13} " + " ".join(f"{_clock(args.kind, e):>6}" for e in roll_ends))
        for g in r["rungs"]:
            if g["target_p"] not in PRIORITY:
                continue
            f = g[fold]
            med = (_clock(args.kind, f["hit_med_min"])
                   if f["hit_med_min"] is not None else "-")
            mode = (f"{f['mode_from']}-{f['mode_to']}"
                    if f.get("mode_from") else "-")
            mass = [m for m in f["mass"] if m is not None]
            row = []
            for i in range(0, nroll, 3):
                w = mass[i:i + 3]
                row.append(f"{sum(w):>6.1%}" if w else "     -")
            print(f"  {g['target_p']:>4.0%} {g['side']:>3} {f['hits']:>5} "
                  f"{med:>7} {mode:>13} " + " ".join(row))

    print(f"\n  per-weekday (TRAIN fold) — median arrival and mode, priority rungs")
    print(f"  {'rung':>4} {'side':>3} " + " ".join(f"{d:>18}" for d in
          ("Mon", "Tue", "Wed", "Thu", "Fri")))
    for target in PRIORITY:
        for side in ("up", "dn"):
            cells = []
            for d in r["by_dow"]:
                g = next(x for x in d["rungs"]
                         if x["target_p"] == target and x["side"] == side)
                f = g["train"]
                if f["hits"] >= 30 and f["hit_med_min"] is not None:
                    cells.append(f"{_clock(args.kind, f['hit_med_min'])} "
                                  f"n={f['hits']:<3} "
                                  f"{f['mode_from']}-{f['mode_to']}")
                else:
                    cells.append("-".rjust(18))
            print(f"  {target:>4.0%} {side:>3} " + " ".join(f"{c:>18}" for c in cells))

    st = r["stability"]
    print(f"\n  stability (predeclared +/-{r['tolerance_pp']:.0f} pp on milestone")
    print(f"  cumulatives): {st['pass']}/{st['cells']} cells pass")
    if st.get("mode_agree"):
        print(f"  modal 5-min bucket: {st['mode_exact']}/{st['n_mode_cells']} "
              f"exact train-vs-holdout, "
              f"{st['mode_within_10min']} within one adjacent bucket")
    if st["worst"]:
        w = st["worst"]
        print(f"  worst: {w['rung']:.0%} {w['side']} at {w['milestone']} — "
              f"train {w['train']:.0%} vs holdout {w['holdout']:.0%} "
              f"({w['delta']:+.0%})" + ("" if w["pass"] else "  FAIL"))
    fails = [c for c in st["all"] if not c["pass"]]
    if fails:
        print(f"  failing cells ({len(fails)}):")
        for c in fails[:8]:
            print(f"    {c['rung']:.0%} {c['side']} {c['milestone']}: "
                  f"{c['train']:.0%} -> {c['holdout']:.0%} ({c['delta']:+.0%})")
    else:
        print("  no failing cells")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"arrival_{args.ticker}_{args.kind}.json"
    dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"\n  wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())