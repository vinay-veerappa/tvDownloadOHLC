"""Study B — does a rung touch mean anything, CONDITIONAL ON WHEN it happened?

RESEARCH_REPORT §2 reports no edge after a rung touch: −0.0016 EV, 49.7% win,
measured from the session open anchor. That test was UNCONDITIONAL, and it has a
specific way of being wrong that a holdout cannot catch.

It averages over time-of-touch. A 25% rung reached at 10:00 leaves six hours of
session; the same rung reached at 15:30 leaves twenty minutes. If early touches
continue and late touches revert, the pooled mean is zero and BOTH effects are
real. "No effect" and "two effects that cancel" produce the same number, and the
unconditional test cannot distinguish them.

So this splits every touch by the fraction of the session elapsed at first
touch, and re-runs the test inside each bucket.

Two measures per bucket, because they answer different questions:

  * **continuation** — the move from the rung to the session close, signed in
    the direction of the excursion. Positive means the move kept going. This is
    what a trader holding through the close earns.
  * **runner conversion** — P(the next rung out is also reached). Positive
    dependence on time-remaining is the mechanism that would produce a
    continuation effect, so if conversion is flat in time, any continuation
    signal is suspect.

Two defects in the obvious version of this test, both found by running it
------------------------------------------------------------------------
**The pooled t-statistic is invalid.** Rungs are NESTED: a session that reaches
the 25% rung has reached the 80%, 65%, 50% and 35% rungs too, so it contributes
up to 8 rows to the same pooled mean. Treating those as independent inflated the
pooled t to 3.93 on a sample of 887 sessions. Only the PER-CELL statistics are
computed on one observation per session; the pooled mean is descriptive and its
t is not reported.

**Continuation-to-close is mechanically positive for late touches.** If a rung
is first reached in the final quarter, there is not enough session left to come
back, so the close is necessarily near or beyond it. `ret_n - c` is therefore
bounded near zero from below by arithmetic, not by market behaviour, and Q4 is
the bucket where the measure is LEAST trustworthy — which is exactly where the
naive read shows its strongest "effect". It is reported with that warning and is
NOT treated as evidence of an edge.

Runner conversion has neither problem: it is a probability, one observation per
session per rung, and its decay with time-remaining is the real result here.

Multiple comparisons
--------------------
8 rungs x 2 sides x 4 buckets is 64 cells. At the 5% level, three will look
significant on noise alone, so the count of strong cells is compared against
that expectation rather than being read as a list of findings.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.timing
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.timing --kind ON
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from .features import OUT_DIR, TARGET_P
from .paths import build_paths, ladder_from, Paths

# Quartiles of session elapsed time. Fractions, not minutes, so the RTH (390m)
# and overnight (930m) sessions are split on the same footing and a half day is
# not miscounted as "all early".
BUCKETS = ((0.00, 0.25, "Q1 first quarter"), (0.25, 0.50, "Q2"),
           (0.50, 0.75, "Q3"), (0.75, 1.01, "Q4 final quarter"))


def _stats(x: np.ndarray) -> dict:
    n = len(x)
    if n < 2:
        return {"n": n, "mean": None, "t": None, "median": None, "pos": None}
    m, sd = float(x.mean()), float(x.std(ddof=1))
    return {"n": n, "mean": round(m, 4),
            "t": round(m / (sd / np.sqrt(n)), 2) if sd > 0 else None,
            "median": round(float(np.median(x)), 4),
            "pos": round(float((x > 0).mean()), 4)}


def run(ticker: str = "ES1", kind: str = "RTH") -> dict:
    p = build_paths(ticker=ticker, kind=kind)
    tr = p.mask(True)
    lad = ladder_from(p, tr)
    cu, cd = lad["c_up"].to_numpy(), lad["c_dn"].to_numpy()

    out = {"ticker": ticker, "kind": kind, "n": int(len(p.idx)),
           "n_train": int(tr.sum()), "cells": [], "pooled": []}

    pooled: dict[str, list[np.ndarray]] = {b[2]: [] for b in BUCKETS}
    conv: dict[str, list[tuple[int, int]]] = {b[2]: [] for b in BUCKETS}

    for i, target in enumerate(TARGET_P):
        for side, c in (("up", cu), ("dn", cd)):
            t = p.first_at(side, float(c[i]))
            hit = np.isfinite(t) & tr
            if hit.sum() < 20:
                continue
            frac = np.where(p.dur > 0, t / np.maximum(p.dur, 1), np.inf)

            # Continuation, signed along the excursion: an up rung continues if
            # the close is ABOVE it; a down rung continues if the close is BELOW.
            cont_all = (p.ret_n - c[i]) if side == "up" else -(p.ret_n + c[i])

            nxt = None
            if i + 1 < len(TARGET_P):
                nxt = np.isfinite(p.first_at(side, float(c[i + 1])))

            for lo, hi, name in BUCKETS:
                m = hit & (frac >= lo) & (frac < hi)
                if m.sum() < 10:
                    continue
                st = _stats(cont_all[m])
                cell = {"rung": target, "side": side, "bucket": name, **st}
                if nxt is not None:
                    cell["convert"] = round(float(nxt[m].mean()), 4)
                    conv[name].append((int((nxt & m).sum()), int(m.sum())))
                out["cells"].append(cell)
                pooled[name].append(cont_all[m])

    for lo, hi, name in BUCKETS:
        if not pooled[name]:
            continue
        x = np.concatenate(pooled[name])
        st = _stats(x)
        cv = conv[name]
        out["pooled"].append({
            "bucket": name, **st,
            "convert": round(sum(a for a, _ in cv) / sum(b for _, b in cv), 4)
            if cv else None,
            "n_rung_cells": len(pooled[name]),
            "cells_positive": sum(1 for a in pooled[name] if a.mean() > 0),
        })
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    ap.add_argument("--kind", default="both", choices=["RTH", "ON", "both"])
    args = ap.parse_args(argv)

    for kind in (["RTH", "ON"] if args.kind == "both" else [args.kind]):
        r = run(args.ticker, kind)
        print(f"\n{'=' * 78}\n{r['ticker']} {kind} — continuation after a rung "
              f"touch, BY TIME OF TOUCH   (train {r['n_train']})")
        print("\n  Continuation = move from the rung to the session close, EV units,")
        print("  signed along the excursion. > 0 means the move kept going.\n")
        print(f"  {'bucket':>18} {'CONVERT':>8} {'touches':>8} {'cont':>8} "
              f"{'median':>8} {'% > 0':>7} {'cells +':>8}")
        for b in r["pooled"]:
            print(f"  {b['bucket']:>18} {b['convert']:>8.1%} {b['n']:>8} "
                  f"{b['mean']:>+8.4f} {b['median']:>+8.4f} {b['pos']:>7.1%} "
                  f"{b['cells_positive']:>3}/{b['n_rung_cells']:<4}")
        print("  no pooled t is shown: rungs are nested, so these rows are not "
              "independent observations")

        cv = [b["convert"] for b in r["pooled"]]
        print(f"\n  HEADLINE — runner conversion decays {cv[0]:.1%} -> {cv[-1]:.1%} "
              f"across the session.")
        print(f"  A rung first reached in the opening quarter goes on to the next "
              f"rung out {cv[0]:.1%}")
        print(f"  of the time; the same rung first reached in the closing quarter, "
              f"{cv[-1]:.1%}. The level")
        print(f"  is identical — what differs is how much session is left to "
              f"travel through it.")

        print(f"\n  Continuation-to-close is tabulated above but is NOT an edge "
              f"estimate. A rung first")
        print(f"  touched late leaves no time to reverse, so `close - rung` is "
              f"bounded near zero from")
        print(f"  below by arithmetic. The measure is weakest exactly where it "
              f"looks strongest.")

        print(f"\n  per-rung detail, cells with |t| >= 2.0:")
        strong = [c for c in r["cells"] if c["t"] is not None and abs(c["t"]) >= 2.0]
        if not strong:
            print("    none — out of "
                  f"{len([c for c in r['cells'] if c['t'] is not None])} cells")
        for c in sorted(strong, key=lambda x: -abs(x["t"])):
            print(f"    {c['rung']:>4.0%} {c['side']:>3} {c['bucket']:<18} "
                  f"n={c['n']:<5} mean {c['mean']:>+7.4f} t={c['t']:>+6.2f}")
        print(f"    (expect ~{0.05 * len([c for c in r['cells'] if c['t'] is not None]):.1f} "
              f"cells at |t|>=2 on noise alone)")

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUT_DIR / f"timing_{args.ticker}_{kind}.json"
        dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
        print(f"\n  wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
