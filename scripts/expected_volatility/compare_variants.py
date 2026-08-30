"""Horse race over the two open items you actually cared about: the ANCHOR and
the VOL INPUT.

The Pine indicator fixes both by fiat — the anchor is the prior close before
16:00 ET and the vol input is the prior VIX close. Neither was ever measured
against an alternative. This script measures them, over the canonical frame
from `features.py`.

Anchors (`--anchor`)
--------------------
``prev_close``  the prior settlement, i.e. what the indicator does today.
``rth_open``    today's 09:30 ET opening print.

The prior close is the wrong origin for a day trader and the size of the error
is measurable: the overnight gap already exceeds the 0.25 rung on 49% of days
and the 0.50 rung on 22%. On those days a prior-close ladder has spent its inner
rungs before the trader arrives, and a "touch" of an inner rung is just the
opening print. That is the confound in RESEARCH_REPORT §3.2 — the `rth_open`
anchor is simultaneously the fix and the negative control for it.

Vol inputs (`--vol-input`)
--------------------------
``vix_prev_close``  prior VIX close (today's behaviour).
``vix_open``        today's VIX open. Published in CBOE's global session from
                    03:15 ET, hence known before 09:30 and NOT lookahead for an
                    RTH-forward level. It differs from the prior close by >2% on
                    40% of days and >5% on 12%.
``har_rv``          HAR-RV forecast (Corsi 2009): today's RTH realised variance
                    regressed on its own daily / weekly / monthly lags, all
                    as-of T-1, coefficients fit on the TRAIN fold only.
``blend``           OLS of log realised on log VIX and log HAR, fit on train.

RV is computed from 5-minute sampling of the 1m bars inside RTH — 1m sampling is
contaminated by microstructure noise, and the point of the estimator is to be a
better scale than VIX, not a noisier one.

Scoring
-------
Every variant is fit on the train fold and scored on the chronological holdout.
The headline metric is **ladder calibration error**: place the rungs by
inverting the train excursion CDF at the target probabilities, then measure the
realised touch frequency on the holdout. A rung labelled 50% that is touched 50%
of the time is the entire point of the percentile ladder, so mean |actual -
target| across rungs is what decides the horse race. Dispersion of
excursion/EV and QLIKE on the absolute return are reported alongside.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.compare_variants
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.compare_variants \\
        --ticker NQ1 --json data/expected_volatility/variants_NQ1.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import (
    ANCHORS,
    HOLDOUT_START,
    ODTE_START,
    OUT_DIR,
    TARGET_P,
    VOL_INPUTS,
    VOL_FOR_TICKER,
    percentile_ladder,
)
from .features import build_sessions as _build_sessions
from .features import frame_for as _frame_for



@dataclass
class Variant:
    anchor: str
    vol_input: str
    sessions: pd.DataFrame


def build_variants(ticker: str):
    """Every (anchor, vol input) pairing, from the canonical session frame.

    This function used to rebuild the frame itself — the third independent copy
    of the anchor / vol-read / as-of rules in this package. `features.py` owns
    them now; this is a projection of that one frame onto the 8 combinations.
    """
    ses = _build_sessions(ticker)
    out: dict[tuple[str, str], Variant] = {}
    for anchor in ANCHORS:
        for vi in VOL_INPUTS:
            out[(anchor, vi)] = Variant(anchor, vi, _frame_for(ses.df, anchor, vi))
    return out, ses.har_beta, ses.blend_beta


def score(v: Variant) -> dict:
    tr = v.sessions[v.sessions.index < HOLDOUT_START]
    te = v.sessions[v.sessions.index >= HOLDOUT_START]
    if len(tr) < 100 or len(te) < 30:
        raise ValueError(f"{v.anchor}/{v.vol_input}: train {len(tr)} test {len(te)}")

    ladder = percentile_ladder(tr)
    rungs = []
    err = []
    for i, p in enumerate(TARGET_P):
        for side, col in (("up", "c_up"), ("dn", "c_dn")):
            c = float(ladder[col][i])
            actual = float((te[side] >= c).mean())
            rungs.append(
                {"target_p": p, "side": side, "c": round(c, 4),
                 "holdout_p": round(actual, 4), "err": round(actual - p, 4)}
            )
            err.append(abs(actual - p))

    # QLIKE on the absolute normalised return: proper, scale-free, and it
    # penalises under-forecasting of variance the way a trader experiences it.
    x = te["ret_n"].to_numpy() ** 2
    x = x[np.isfinite(x) & (x > 0)]
    qlike = float(np.mean(x - np.log(x) - 1)) if x.size else float("nan")

    return {
        "anchor": v.anchor,
        "vol_input": v.vol_input,
        "n_train": len(tr),
        "n_holdout": len(te),
        "ladder_cal_err_bps_of_prob": round(float(np.mean(err)) * 10_000, 1),
        "worst_rung_err": round(float(np.max(err)), 4),
        "mean_mx_over_ev_train": round(float(tr["mx"].mean()), 4),
        "sd_mx_over_ev_train": round(float(tr["mx"].std()), 4),
        "cv_mx_over_ev_train": round(float(tr["mx"].std() / tr["mx"].mean()), 4),
        "qlike_holdout": round(qlike, 4),
        "ladder": ladder.to_dict("records"),
        "rungs": rungs,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1", choices=sorted(VOL_FOR_TICKER))
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    variants, har_beta, blend_beta = build_variants(args.ticker)
    results = [score(v) for v in variants.values()]
    results.sort(key=lambda r: r["ladder_cal_err_bps_of_prob"])

    print(f"\n{args.ticker} — anchor x vol-input horse race, 0DTE regime")
    print(f"HAR log-RV coefficients  const {har_beta[0]:+.4f} "
          f"d {har_beta[1]:+.4f} w {har_beta[2]:+.4f} m {har_beta[3]:+.4f}")
    print(f"blend log coefficients   const {blend_beta[0]:+.4f} "
          f"vix {blend_beta[1]:+.4f} har {blend_beta[2]:+.4f}")
    print(f"\n{'anchor':<11} {'vol input':<15} {'cal err':>8} {'worst':>7} "
          f"{'CV':>7} {'QLIKE':>8}  {'mean mx/EV':>10}")
    for r in results:
        print(f"{r['anchor']:<11} {r['vol_input']:<15} "
              f"{r['ladder_cal_err_bps_of_prob']/100:>7.2f}% "
              f"{r['worst_rung_err']*100:>6.2f}% {r['cv_mx_over_ev_train']:>7.3f} "
              f"{r['qlike_holdout']:>8.4f} {r['mean_mx_over_ev_train']:>10.4f}")

    dest = args.json or (OUT_DIR / f"variants_{args.ticker}.json")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ticker": args.ticker,
        "regime_start": ODTE_START,
        "holdout_start": HOLDOUT_START,
        "har_beta": [float(b) for b in har_beta],
        "blend_beta": [float(b) for b in blend_beta],
        "results": results,
    }
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
