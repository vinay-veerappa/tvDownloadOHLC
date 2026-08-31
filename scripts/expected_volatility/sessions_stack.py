"""The session stack — does the EV ladder calibrate beyond RTH?

Ad-hoc probes (2026-08-31) found two things the pipeline had not captured:

  * the overnight ladder's §2.3 drift is really an ASIA failure — London
    calibrates about as well as RTH does;
  * ASIA's one-sidedness survives every recency-weighted fit window tried,
    so it ships NOMINAL (distance indicative, probabilities not calibrated)
    with constants from a rolling refit per §7.1.

This module makes those probes a pipeline artifact so the Pine generator and
the report render the same verdicts from the same numbers, and so a §7.1
data refresh re-derives them instead of leaving hand-copied constants.

Windows (ET minutes from midnight), keyed to the RTH day they lead into:

    ASIA    18:00-03:00   evening bars belong to the NEXT day
    LONDON  03:00-09:30   same-day

Vol is the prior session's VIX close in both cases — settled at 16:00 ET,
before either anchor exists (same as-of relationship as `overnight.py`).

Verdicts, predeclared
---------------------
    calibrated  holdout MAE <= 3.1% (≈2x the RTH ladder's 1.45%) AND errors
                not one-sided (<= 12 of 16 positive)
    nominal     one-sided (>= 13 of 16) under every fit window tried — the
                ladder is a distance map, not a probability map, until the
                input regime is understood
Anything else is `refit`. The rule is fixed here so the report cannot pick a
threshold that flatters a session.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.sessions_stack
"""

from __future__ import annotations

import argparse
import json
import math

import numpy as np
import pandas as pd

from .features import (
    DATA, HOLDOUT_START, ODTE_START, OUT_DIR, TARGET_P, VOL_FOR_TICKER,
    _read, _to_et, percentile_ladder,
)

MIN_BARS = 300          # drop holiday stubs and feed gaps
ASIA_ROLLING_FROM = "2024-12-01"  # §7.1-style rolling refit window for Asia
VERDICT_MAE, VERDICT_POS = 0.031, 12


def _frame(bars: pd.DataFrame, vix_prev: pd.Series, kind: str) -> pd.DataFrame:
    idx = bars.index
    mins = idx.hour * 60 + idx.minute
    sel = (mins >= 1080) | (mins < 180) if kind == "ASIA" else (mins >= 180) & (mins < 570)
    sub = bars[sel].copy()
    m = sub.index.hour * 60 + sub.index.minute
    sub["sess"] = (np.where(m >= 1080, (sub.index + pd.Timedelta(days=1)).date,
                            sub.index.date) if kind == "ASIA" else sub.index.date)
    g = sub.groupby("sess")
    s = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                      "low": g["low"].min(), "nb": g["close"].size()})
    s = s[s["nb"] >= MIN_BARS]
    s["vix"] = vix_prev.reindex(s.index)
    s = s.dropna(subset=["vix", "open", "high", "low"])
    s.index = pd.DatetimeIndex(s.index)
    s = s[s.index >= pd.Timestamp(ODTE_START)]
    s["S"] = s["open"]
    s["EV"] = s["S"] * s["vix"] / math.sqrt(252) / 100.0
    s = s[s["EV"] > 0]
    s["up"] = (s["high"] - s["S"]) / s["EV"]
    s["dn"] = (s["S"] - s["low"]) / s["EV"]
    s["mx"] = s[["up", "dn"]].max(axis=1)
    return s


def _evaluate(s: pd.DataFrame, fit_from: str) -> dict:
    tr = s[(s.index >= pd.Timestamp(fit_from)) & (s.index < pd.Timestamp(HOLDOUT_START))]
    te = s[s.index >= pd.Timestamp(HOLDOUT_START)]
    if len(tr) < 100 or len(te) < 30:
        return {"status": "insufficient", "n_train": len(tr), "n_holdout": len(te)}
    lad = percentile_ladder(tr)
    errs, pos = [], 0
    for i, p in enumerate(TARGET_P):
        for side, col in (("up", "c_up"), ("dn", "c_dn")):
            c = float(lad[col][i])
            e = float((te[side] >= c).mean()) - p
            errs.append(abs(e))
            pos += e > 0
    mae = float(np.mean(errs))
    verdict = ("calibrated" if mae <= VERDICT_MAE and pos <= VERDICT_POS
               else "nominal" if pos >= 13 else "refit")
    return {
        "status": "ok", "fit_from": fit_from,
        "n_train": len(tr), "n_holdout": len(te),
        "cal_mae": round(mae, 4), "pos": pos, "n_rungs": len(errs),
        "mx_train": round(float(tr["mx"].mean()), 4),
        "mx_holdout": round(float(te["mx"].mean()), 4),
        "mx_ratio": round(float(te["mx"].mean() / tr["mx"].mean()), 4),
        "verdict": verdict,
        "ladder_up": [round(float(r["c_up"]), 4) for r in lad.to_dict("records")],
        "ladder_dn": [round(float(r["c_dn"]), 4) for r in lad.to_dict("records")],
    }


def run(ticker: str = "ES1") -> dict:
    vol_name = VOL_FOR_TICKER[ticker]
    bars = _to_et(_read(DATA / f"{ticker}_1m.parquet"))
    vol = _to_et(_read(DATA / f"{vol_name}_1d.parquet"))
    vd = pd.DatetimeIndex(vol.index).date
    vix_prev = pd.Series(vol["close"].to_numpy(), index=vd).shift(1)

    out = {"ticker": ticker, "sessions": {}}
    for kind, window in (("LONDON", "03:00-09:30 ET"),
                         ("ASIA", "18:00-03:00 ET, keyed to the next RTH day")):
        s = _frame(bars, vix_prev, kind)
        pooled = _evaluate(s, ODTE_START)
        rec = {"window": window, "n": int(len(s)), "pooled": pooled}
        if kind == "ASIA":
            rec["rolling"] = _evaluate(s, ASIA_ROLLING_FROM)
        out["sessions"][kind] = rec
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    args = ap.parse_args(argv)

    r = run(args.ticker)
    print(f"\n{r['ticker']} SESSION STACK — does the EV ladder calibrate beyond RTH?")
    print(f"  verdicts predeclared: calibrated = MAE <= {VERDICT_MAE:.1%} and "
          f"<= {VERDICT_POS}/16 one-sided; nominal = >= 13/16 one-sided\n")
    for kind, rec in r["sessions"].items():
        print(f"  {kind}  ({rec['window']}, n={rec['n']})")
        for tag in ("pooled", "rolling"):
            if tag not in rec:
                continue
            v = rec[tag]
            if v.get("status") != "ok":
                print(f"    {tag:8s}: insufficient data ({v})")
                continue
            print(f"    {tag:8s}: fit from {v['fit_from']}  tr {v['n_train']}/te {v['n_holdout']}  "
                  f"MAE {v['cal_mae']:.2%}  pos {v['pos']}/{v['n_rungs']}  "
                  f"drift {v['mx_ratio']:.3f}x  -> {v['verdict'].upper()}")
    print("\n  RTH reference: MAE 1.45%, 7/16 positive, drift 0.99x -> CALIBRATED")
    print("  ON reference (§2.3): MAE 3.52%, 16/16 positive, drift 1.06x -> REFIT")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"sessions_stack_{args.ticker}.json"
    dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"\n  wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())