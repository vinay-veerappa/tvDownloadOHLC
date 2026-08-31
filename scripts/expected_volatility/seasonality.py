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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    ap.add_argument("--kind", default="both", choices=["RTH", "ON", "both"])
    args = ap.parse_args(argv)

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
