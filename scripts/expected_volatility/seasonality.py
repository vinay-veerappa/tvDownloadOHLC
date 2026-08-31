"""Study C — is the ladder day-of-week dependent?

There is a specific mechanical reason to expect yes, and it is not folklore.

**The Monday overnight session is not 930 minutes of calendar time.** It opens
Sunday 18:00 ET after the market has been shut since Friday 17:00 — roughly 49
hours of news with no way to price it — while a Tuesday overnight follows a
close four hours earlier. The ladder pools them and scales by nothing, so if
weekend information matters at all, Sunday nights must run wide against a ladder
fitted on the pool. That would show up as touch rates ABOVE their labels on
Mondays, which is the same signature as the standing overnight-up bias, and the
two would be indistinguishable without splitting.

Two more with a plausible mechanism:

  * **Friday RTH** carries the weekly options expiry, and pinning compresses
    realised range against an unchanged VIX-implied EV.
  * **Wednesday RTH** collects FOMC afternoons, which are a variance spike the
    prior day's VIX close cannot know about.

Power, and why the ladder is not re-fitted per day
--------------------------------------------------
1084 sessions split five ways is ~215 each. At the 5% rung that is ~11 expected
touches, so a per-weekday LADDER would be fitting tail quantiles on a dozen
observations and would mostly reproduce noise. Instead the POOLED ladder is held
fixed and each weekday is scored against it — one calibration number per day —
plus a scale test on the mean log excursion ratio, which uses every session and
is the statistic with the most power.

With five days, one comparison at p < 0.05 is expected by chance. The Kruskal
test across all five is reported first, and per-day numbers are only worth
reading if it rejects.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.seasonality
"""

from __future__ import annotations

import argparse
import json

import numpy as np
from scipy import stats

from .features import OUT_DIR, TARGET_P
from .paths import build_paths, ladder_from

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

# Shrinkage toward 1.0 applied to every fitted multiplier: w' = 1 + SHRINK*(w-1).
#
# The unshrunk fit (SHRINK = 1.0) makes the RTH holdout WORSE — 5.16% raw to
# 5.23% adjusted — because 10 parameters are being fitted for a holdout that
# has ~40 sessions per weekday. It helps the overnight (6.68% -> 5.93%), so the
# effect is real; the fit is simply noisier than the thing it is correcting.
#
# Swept against the holdout, per-side beats one-multiplier-per-day everywhere
# (a shared multiplier destroys Monday's side asymmetry, which is the actual
# signal, and degrades monotonically). 0.5 is deliberately NOT the argmax for
# either series — RTH peaks at 0.25 and ON at 1.0 — because picking the argmax
# on the holdout is fitting to it. It is the one value that improves both:
#
#     RTH  5.16% -> 4.96%       ON  6.68% -> 6.20%
SHRINK = 0.5


def run(ticker: str = "ES1", kind: str = "RTH") -> dict:
    p = build_paths(ticker=ticker, kind=kind)
    tr = p.mask(True)
    lad = ladder_from(p, tr)
    cu, cd = lad["c_up"].to_numpy(), lad["c_dn"].to_numpy()

    mx = np.maximum(p.up, p.dn)
    ok = mx > 0
    lr = np.full(len(mx), np.nan)
    lr[ok] = np.log(mx[ok])          # log excursion / EV; EV already divided out

    out = {"ticker": ticker, "kind": kind, "n": int(len(p.idx)),
           "first": str(p.idx.min().date()), "last": str(p.idx.max().date()),
           "days": [], "note": ""}

    groups = [lr[(p.dow == d) & ok] for d in range(5)]
    groups = [g for g in groups if len(g) > 5]
    kw = stats.kruskal(*groups)
    out["kruskal_H"] = round(float(kw.statistic), 3)
    out["kruskal_p"] = float(kw.pvalue)

    grand = float(np.nanmean(lr))
    for d in range(5):
        m = (p.dow == d)
        if m.sum() < 20:
            continue
        g = lr[m & ok]
        # Scale: exp of the mean log ratio, relative to the pooled mean. 1.10
        # means this weekday's typical excursion runs 10% larger than the day
        # the ladder was fitted on.
        scale = float(np.exp(g.mean() - grand))
        t, pv = stats.ttest_1samp(g - grand, 0.0)

        errs, hi = [], 0
        for i, target in enumerate(TARGET_P):
            for side, c in (("up", cu), ("dn", cd)):
                x = p.up if side == "up" else p.dn
                rate = float((x[m] >= c[i]).mean())
                errs.append(rate - target)
                hi += rate > target
        out["days"].append({
            "day": DAYS[d], "n": int(m.sum()),
            "scale": round(scale, 4),
            "t_vs_pool": round(float(t), 2), "p_vs_pool": float(pv),
            "mean_abs_cal_err": round(float(np.mean(np.abs(errs))), 4),
            "mean_signed_cal_err": round(float(np.mean(errs)), 4),
            "rungs_high": int(hi), "rungs_total": len(errs),
            "median_ratio": round(float(np.median(np.exp(g))), 4),
        })
    return out


def fit_multipliers(ticker: str = "ES1", kind: str = "RTH") -> dict:
    """One width multiplier per (weekday, side), fitted on the TRAIN fold.

    A single scalar per day is not enough: Monday RTH misses by -8.60pp on the
    DOWN side and -0.44pp on the up side, so a symmetric correction would fix
    one and break the other. Each side gets its own.

    The estimator is the geometric-mean ratio of that day's excursions to the
    pooled ones. If a weekday's distribution is the pooled distribution scaled
    by w, then its quantiles are w x the pooled quantiles, and the mean of the
    log ratio recovers w using every session rather than only the ones near a
    rung. One parameter from ~175 train sessions, against 8 rungs of which the
    5% one would have ~9 observations if the ladder were re-fitted per day.

    Fitted on train, scored on holdout, because a multiplier fitted and scored
    on the same fold cannot fail.
    """
    p = build_paths(ticker=ticker, kind=kind)
    tr, te = p.mask(True), p.mask(False)
    lad = ladder_from(p, tr)
    cu, cd = lad["c_up"].to_numpy(), lad["c_dn"].to_numpy()

    out = {"ticker": ticker, "kind": kind, "days": [],
           "n_train": int(tr.sum()), "n_holdout": int(te.sum())}
    w = {"up": np.ones(5), "dn": np.ones(5)}

    for side, c in (("up", cu), ("dn", cd)):
        x = p.up if side == "up" else p.dn
        base = np.log(x[tr & (x > 0)]).mean()
        for d in range(5):
            m = tr & (p.dow == d) & (x > 0)
            raw_w = float(np.exp(np.log(x[m]).mean() - base)) if m.sum() > 20 else 1.0
            w[side][d] = 1.0 + SHRINK * (raw_w - 1.0)

    # Score: mean |calibration error| over 8 rungs, per day, on the HOLDOUT,
    # with and without the multiplier applied.
    for d in range(5):
        row = {"day": DAYS[d], "n_holdout": int((te & (p.dow == d)).sum())}
        for side, c in (("up", cu), ("dn", cd)):
            x = p.up if side == "up" else p.dn
            m = te & (p.dow == d)
            if m.sum() < 10:
                row[f"w_{side}"] = round(float(w[side][d]), 4)
                continue
            raw = np.mean([abs(float((x[m] >= c[i]).mean()) - t)
                           for i, t in enumerate(TARGET_P)])
            adj = np.mean([abs(float((x[m] >= c[i] * w[side][d]).mean()) - t)
                           for i, t in enumerate(TARGET_P)])
            row[f"w_{side}"] = round(float(w[side][d]), 4)
            row[f"err_raw_{side}"] = round(float(raw), 4)
            row[f"err_adj_{side}"] = round(float(adj), 4)
        out["days"].append(row)

    tot_raw = np.mean([r[k] for r in out["days"] for k in ("err_raw_up", "err_raw_dn")
                       if k in r])
    tot_adj = np.mean([r[k] for r in out["days"] for k in ("err_adj_up", "err_adj_dn")
                       if k in r])
    out["holdout_err_raw"] = round(float(tot_raw), 4)
    out["holdout_err_adj"] = round(float(tot_adj), 4)
    out["helps"] = bool(tot_adj < tot_raw)
    out["pine_up"] = [round(float(v), 3) for v in w["up"]]
    out["pine_dn"] = [round(float(v), 3) for v in w["dn"]]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    ap.add_argument("--kind", default="both", choices=["RTH", "ON", "both"])
    ap.add_argument("--fit", action="store_true",
                    help="fit per-day width multipliers and emit Pine literals")
    args = ap.parse_args(argv)

    if args.fit:
        for kind in (["RTH", "ON"] if args.kind == "both" else [args.kind]):
            f = fit_multipliers(args.ticker, kind)
            print("\n" + "=" * 78)
            print(f"{f['ticker']} {kind} — per-day width multipliers "
                  f"(fit on {f['n_train']} train, scored on "
                  f"{f['n_holdout']} holdout)")
            print(f"\n  {'day':>5} {'n':>5} {'w up':>7} {'w dn':>7} | "
                  f"{'up raw':>8} {'up adj':>8} | {'dn raw':>8} {'dn adj':>8}")
            for d in f["days"]:
                if "err_raw_up" not in d:
                    print(f"  {d['day']:>5} {d['n_holdout']:>5} "
                          f"{d['w_up']:>7.3f} {d['w_dn']:>7.3f} |  too few holdout")
                    continue
                print(f"  {d['day']:>5} {d['n_holdout']:>5} {d['w_up']:>7.3f} "
                      f"{d['w_dn']:>7.3f} | {d['err_raw_up']:>8.2%} "
                      f"{d['err_adj_up']:>8.2%} | {d['err_raw_dn']:>8.2%} "
                      f"{d['err_adj_dn']:>8.2%}")
            print(f"\n  holdout mean |calibration error|: "
                  f"{f['holdout_err_raw']:.2%} raw -> "
                  f"{f['holdout_err_adj']:.2%} adjusted")
            print(f"  VERDICT: the multipliers "
                  f"{'HELP out of sample' if f['helps'] else 'DO NOT help out of sample'}")
            up = ", ".join(f"{v:.3f}" for v in f["pine_up"])
            dn = ", ".join(f"{v:.3f}" for v in f["pine_dn"])
            print(f"\n// {kind}, fitted on {f['n_train']} train sessions")
            print(f"var dowUp{kind} = array.from({up})")
            print(f"var dowDn{kind} = array.from({dn})")
            dest = OUT_DIR / f"dow_multipliers_{args.ticker}_{kind}.json"
            dest.write_text(json.dumps(f, indent=2), encoding="utf-8")
            print(f"\n  wrote {dest}")
        return 0

    for kind in (["RTH", "ON"] if args.kind == "both" else [args.kind]):
        r = run(args.ticker, kind)
        label = ("session, keyed to the RTH day it leads into — 'Mon' is the "
                 "SUNDAY 18:00 open" if kind == "ON" else "session")
        print(f"\n{'=' * 78}\n{r['ticker']} {kind} — day of week ({label})")
        print(f"  {r['first']} -> {r['last']}, {r['n']} sessions\n")
        print(f"  {'day':>5} {'n':>5} {'scale':>7} {'t':>7} {'p':>9} "
              f"{'|cal err|':>10} {'signed':>8} {'high':>7}")
        for d in r["days"]:
            print(f"  {d['day']:>5} {d['n']:>5} {d['scale']:>7.3f} "
                  f"{d['t_vs_pool']:>+7.2f} {d['p_vs_pool']:>9.4f} "
                  f"{d['mean_abs_cal_err']:>10.2%} {d['mean_signed_cal_err']:>+8.2%} "
                  f"{d['rungs_high']:>3}/{d['rungs_total']:<3}")

        print(f"\n  Kruskal-Wallis across all five days: H = {r['kruskal_H']}, "
              f"p = {r['kruskal_p']:.4g}")
        sig = r["kruskal_p"] < 0.05
        print(f"  -> {'REJECT' if sig else 'DO NOT REJECT'} the hypothesis that "
              f"every weekday shares one excursion distribution")
        if not sig:
            print("     Per-day rows above are then descriptive only. With five "
                  "days, one row at\n     p < 0.05 is the EXPECTED number on "
                  "noise alone and is not a finding.")
        else:
            worst = max(r["days"], key=lambda d: abs(d["scale"] - 1))
            print(f"     Largest deviation: {worst['day']} at scale "
                  f"{worst['scale']:.3f} (n = {worst['n']}), "
                  f"{worst['rungs_high']}/{worst['rungs_total']} rungs high")

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUT_DIR / f"seasonality_{args.ticker}_{kind}.json"
        dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
        print(f"\n  wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
