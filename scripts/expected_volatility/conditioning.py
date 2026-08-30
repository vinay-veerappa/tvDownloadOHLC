"""Does the VIX ecosystem pack tell you when the ladder is wrong?

This closes DATA_PLAN §2 P2 Q9 and P6 Q20-28, which sat at "built, not
analysed" while the twelve columns were already joined and waiting.

The question, stated so it can be answered
------------------------------------------
The percentile ladder already absorbs a *constant* mis-scaling: it is fit by
inverting the empirical excursion CDF, so if realised runs a steady 0.75x of
VIX-implied, the fit corrects it. What the ladder cannot absorb is
mis-scaling that **varies day to day**. So the question is not "does the pack
predict volatility" — VIX already does that. It is:

    does the pack predict the RESIDUAL, log(realised excursion / EV)?

If it does, the ladder can be widened or narrowed per session and every rung's
stated probability gets more honest. If it does not, the pack is decoration and
the plan should stop carrying 28 questions about it.

Method
------
Target ``log(mx / EV)`` where ``mx = max(up, dn)`` in EV units. Baseline is an
intercept only — that is exactly what the current ladder does. Candidate
features are the pack, all as-of T-1. Coefficients are fit on the train fold and
scored **out of sample** on the chronological holdout, reporting the change in
out-of-sample R-squared. An in-sample R-squared here would be meaningless: with
9 features and ~880 rows something will always fit.

Quintile tables use train-fold breakpoints applied to both folds, so the holdout
column is a genuine forecast and not a re-description.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.conditioning
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.conditioning \\
        --anchor prev_close --vol-input vix_prev_close
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from .features import (
    HOLDOUT_START, OUT_DIR, TARGET_P, VOL_FOR_TICKER,
    build_sessions, folds, frame_for, percentile_ladder,
)

FEATURES = [
    ("term_1d_30d", "VIX1D - VIX (front-loaded event risk)"),
    ("term_9d_30d", "VIX9D - VIX"),
    ("term_30d_90d", "VIX - VIX3M (>0 = inverted, stress)"),
    ("vx_basis", "VX1 - VIX (futures basis)"),
    ("vx_curve", "VX2 - VX1 (curve slope)"),
    ("vvix_ratio", "VVIX / VIX (vol-of-vol, scaled)"),
    ("vrp_20d", "VIX - trailing 20d realised (variance risk premium)"),
    ("vix_pctl_252", "VIX percentile, 252d"),
]


def _ols(x, y):
    a = np.column_stack([np.ones(len(x)), x])
    return np.linalg.lstsq(a, y, rcond=None)[0]


def _pred(beta, x):
    return beta[0] + x @ beta[1:]


def _r2(y, yhat) -> float:
    ss = float(np.sum((y - yhat) ** 2))
    tot = float(np.sum((y - np.mean(y)) ** 2))
    return 1.0 - ss / tot if tot > 0 else float("nan")


def quintile_table(tr: pd.DataFrame, te: pd.DataFrame, col: str, q: int = 5) -> list[dict]:
    """Train-fold breakpoints, applied to both folds."""
    v = tr[col].dropna()
    if len(v) < 100 or v.nunique() < q:
        return []
    edges = np.unique(np.quantile(v, np.linspace(0, 1, q + 1)))
    if len(edges) < 3:
        return []
    edges[0], edges[-1] = -np.inf, np.inf
    rows = []
    for name, f in (("train", tr), ("holdout", te)):
        b = pd.cut(f[col], bins=edges, labels=False, include_lowest=True)
        for k in range(len(edges) - 1):
            sel = f[b == k]
            if len(sel) < 10:
                continue
            rows.append({
                "fold": name, "feature": col, "bucket": k + 1,
                "n": len(sel),
                "lo": None if k == 0 else round(float(edges[k]), 3),
                "hi": None if k == len(edges) - 2 else round(float(edges[k + 1]), 3),
                "mean_mx_over_ev": round(float(sel["mx"].mean()), 4),
                "p_touch_1ev": round(float((sel["mx"] >= 1.0).mean()), 4),
                "median_ret_abs_ev": round(float(sel["ret_n"].abs().median()), 4),
            })
    return rows


def run(ticker: str, anchor: str, vol_input: str) -> dict:
    ses = build_sessions(ticker)
    f = frame_for(ses.df, anchor, vol_input)
    f = f.dropna(subset=["mx"])
    f = f[f["mx"] > 0]
    tr, te = folds(f)
    if len(tr) < 200 or len(te) < 30:
        raise ValueError(f"train {len(tr)} holdout {len(te)}")

    y_tr = np.log(tr["mx"].to_numpy())
    y_te = np.log(te["mx"].to_numpy())

    # Baseline: a constant rescale — precisely what the ladder already applies.
    base = float(np.mean(y_tr))
    base_r2 = _r2(y_te, np.full_like(y_te, base))

    singles = []
    for col, desc in FEATURES:
        m_tr = tr.dropna(subset=[col])
        m_te = te.dropna(subset=[col])
        if len(m_tr) < 200 or len(m_te) < 30:
            singles.append({"feature": col, "desc": desc, "status": "insufficient"})
            continue
        x_tr = m_tr[[col]].to_numpy()
        b = _ols(x_tr, np.log(m_tr["mx"].to_numpy()))
        yy = np.log(m_te["mx"].to_numpy())
        r2 = _r2(yy, _pred(b, m_te[[col]].to_numpy()))
        r2b = _r2(yy, np.full_like(yy, float(np.mean(np.log(m_tr["mx"].to_numpy())))))
        singles.append({
            "feature": col, "desc": desc, "status": "ok", "n_train": len(m_tr),
            "coef": round(float(b[1]), 5),
            "holdout_r2": round(r2, 4),
            "delta_r2": round(r2 - r2b, 4),
        })

    cols = [c for c, _ in FEATURES]
    m_tr = tr.dropna(subset=cols)
    m_te = te.dropna(subset=cols)
    joint = {"status": "insufficient"}
    if len(m_tr) >= 200 and len(m_te) >= 30:
        b = _ols(m_tr[cols].to_numpy(), np.log(m_tr["mx"].to_numpy()))
        yy = np.log(m_te["mx"].to_numpy())
        r2 = _r2(yy, _pred(b, m_te[cols].to_numpy()))
        r2b = _r2(yy, np.full_like(yy, float(np.mean(np.log(m_tr["mx"].to_numpy())))))
        joint = {
            "status": "ok", "n_train": len(m_tr), "n_holdout": len(m_te),
            "holdout_r2": round(r2, 4), "baseline_r2": round(r2b, 4),
            "delta_r2": round(r2 - r2b, 4),
            "coefs": {c: round(float(v), 5) for c, v in zip(cols, b[1:])},
        }

    quints = []
    for col, _ in FEATURES:
        quints += quintile_table(tr, te, col)

    # Does the ladder itself hold inside each regime? Fit once on train, then
    # measure realised touch rates inside each holdout bucket.
    ladder = percentile_ladder(tr)
    ladder_by_regime = []
    key = "term_30d_90d"
    if key in te.columns and te[key].notna().sum() > 50:
        edges = np.unique(np.quantile(tr[key].dropna(), [0, 1 / 3, 2 / 3, 1]))
        edges[0], edges[-1] = -np.inf, np.inf
        b = pd.cut(te[key], bins=edges, labels=False, include_lowest=True)
        for k in range(len(edges) - 1):
            sel = te[b == k]
            if len(sel) < 20:
                continue
            errs = []
            for i, p in enumerate(TARGET_P):
                for side, c in (("up", ladder["c_up"][i]), ("dn", ladder["c_dn"][i])):
                    errs.append(abs(float((sel[side] >= c).mean()) - p))
            ladder_by_regime.append({
                "bucket": k + 1, "n": len(sel),
                "lo": None if k == 0 else round(float(edges[k]), 3),
                "hi": None if k == len(edges) - 2 else round(float(edges[k + 1]), 3),
                "mean_cal_err": round(float(np.mean(errs)), 4),
                "mean_mx_over_ev": round(float(sel["mx"].mean()), 4),
            })

    return {
        "ticker": ticker, "anchor": anchor, "vol_input": vol_input,
        "n_train": len(tr), "n_holdout": len(te),
        "holdout_start": HOLDOUT_START,
        "baseline_holdout_r2": round(base_r2, 4),
        "singles": singles, "joint": joint,
        "quintiles": quints, "ladder_by_term_regime": ladder_by_regime,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1", choices=sorted(VOL_FOR_TICKER))
    ap.add_argument("--anchor", default="rth_open", choices=("prev_close", "rth_open"))
    ap.add_argument("--vol-input", default="vix_prev_close")
    args = ap.parse_args(argv)

    r = run(args.ticker, args.anchor, args.vol_input)
    print(f"\n{r['ticker']} {r['anchor']} / {r['vol_input']} — "
          f"train {r['n_train']} holdout {r['n_holdout']}")
    print("\nTarget: log(max excursion / EV). Baseline = constant rescale "
          "(what the ladder already does).")
    print(f"\n{'feature':<15} {'coef':>10} {'holdout R2':>11} {'vs baseline':>12}")
    for s in r["singles"]:
        if s["status"] != "ok":
            print(f"{s['feature']:<15} {'--':>10} {'insufficient':>11}")
            continue
        print(f"{s['feature']:<15} {s['coef']:>10.5f} {s['holdout_r2']:>11.4f} "
              f"{s['delta_r2']:>+12.4f}")
    j = r["joint"]
    if j["status"] == "ok":
        print(f"\nall 8 jointly: holdout R2 {j['holdout_r2']:+.4f} vs baseline "
              f"{j['baseline_r2']:+.4f}  ->  delta {j['delta_r2']:+.4f}")
    if r["ladder_by_term_regime"]:
        print("\nladder calibration error by VIX-VIX3M tercile (holdout):")
        for b in r["ladder_by_term_regime"]:
            print(f"  bucket {b['bucket']} n={b['n']:<4} "
                  f"cal_err {b['mean_cal_err']:.4f}  mx/EV {b['mean_mx_over_ev']:.4f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"conditioning_{args.ticker}_{args.anchor}.json"
    dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
