"""Fit and validate a percentile ladder for the OVERNIGHT session.

The study so far is RTH-only (09:30-16:00 ET). The overnight session — 18:00 ET
to 09:30 ET, 930 minutes — is a different animal and must not borrow the RTH
constants:

  * it is 2.4x longer in clock time but carries far less variance per minute
    (Asia runs ~0.47x the average minute, London ~0.76x, against NY_AM's 2.41x
    — see RESEARCH_REPORT §4.6), so a naive `sqrt(minutes)` rescale of the RTH
    ladder would be wrong in both directions at once;
  * it spans the Asia and London handover, which is two regimes, not one;
  * its anchor is the 18:00 open, and the gap into 18:00 is much smaller than
    the gap into 09:30 because the Globex reopen is nearly continuous with the
    16:00 close.

So the ladder is refit from scratch on overnight excursions, on the same
chronological train/holdout split, and validated the same way. If it does not
calibrate out of sample it does not ship.

Anchor and leakage
------------------
Anchor is the first print at or after 18:00 ET on day T-1. Vol is the VIX close
of T-1, published at 16:00 ET — two hours BEFORE the anchor exists, so this is
the cleanest as-of relationship anywhere in the study.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.overnight
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.overnight --pine
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

ON_START_MIN = 18 * 60   # 18:00 ET
ON_END_MIN = 9 * 60 + 30  # 09:30 ET next day
ON_MINUTES = 930


def build_overnight(ticker: str = "ES1", start: str = ODTE_START) -> pd.DataFrame:
    """One row per overnight session, keyed by the RTH day it leads into."""
    vol_name = VOL_FOR_TICKER[ticker]
    bars = _to_et(_read(DATA / f"{ticker}_1m.parquet"))
    vol = _to_et(_read(DATA / f"{vol_name}_1d.parquet"))

    idx = bars.index
    mins = idx.hour * 60 + idx.minute
    in_on = (mins >= ON_START_MIN) | (mins < ON_END_MIN)
    on = bars[in_on].copy()

    # Key each bar to the RTH day it leads into: bars from 18:00 onward belong
    # to the NEXT calendar day's session, bars before 09:30 to their own.
    on_mins = on.index.hour * 60 + on.index.minute
    on["sess_day"] = np.where(
        on_mins >= ON_START_MIN,
        (on.index + pd.Timedelta(days=1)).date,
        on.index.date,
    )

    g = on.groupby("sess_day")
    s = pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(),
        "low": g["low"].min(), "close": g["close"].last(),
        "bars": g["close"].size(),
    })
    # A full overnight is 930 minutes; allow for holidays and feed gaps but drop
    # the stubs, which would otherwise report tiny excursions as real ones.
    s = s[s["bars"] >= 600]

    vd = pd.DatetimeIndex(vol.index).date
    # VIX close of T-1 — settled at 16:00 ET, two hours before the 18:00 anchor.
    s["vix"] = pd.Series(vol["close"].to_numpy(), index=vd).shift(1).reindex(s.index)

    # The prior RTH close, for the gap-into-18:00 comparison.
    pre16 = bars.between_time("00:00", "15:59")
    settle = pre16.groupby(pre16.index.date)["close"].last()
    s["prev_close"] = settle.shift(1).reindex(s.index)

    s = s.dropna(subset=["vix", "open", "high", "low"])
    s.index = pd.DatetimeIndex(s.index)
    s = s[s.index >= pd.Timestamp(start)]

    s["S"] = s["open"]
    s["EV"] = s["S"] * s["vix"] / math.sqrt(252) / 100.0
    s = s[s["EV"] > 0]
    s["up"] = (s["high"] - s["S"]) / s["EV"]
    s["dn"] = (s["S"] - s["low"]) / s["EV"]
    s["mx"] = s[["up", "dn"]].max(axis=1)
    s["ret_n"] = (s["close"] - s["S"]) / s["EV"]
    s["gap_ev"] = (s["open"] - s["prev_close"]) / s["EV"]
    return s


def run(ticker: str = "ES1") -> dict:
    s = build_overnight(ticker)
    tr = s[s.index < HOLDOUT_START]
    te = s[s.index >= HOLDOUT_START]
    if len(tr) < 200 or len(te) < 30:
        raise ValueError(f"train {len(tr)} holdout {len(te)}")

    lad = percentile_ladder(tr)
    rungs, errs = [], []
    for i, p in enumerate(TARGET_P):
        for side, col in (("up", "c_up"), ("dn", "c_dn")):
            c = float(lad[col][i])
            a = float((te[side] >= c).mean())
            rungs.append({"target_p": p, "side": side, "c": round(c, 4),
                          "holdout_p": round(a, 4), "err": round(a - p, 4),
                          "n_hits": int((te[side] >= c).sum())})
            errs.append(abs(a - p))

    gap = s["gap_ev"].dropna()
    return {
        "ticker": ticker, "session": "overnight 18:00-09:30 ET",
        "minutes": ON_MINUTES,
        "n_train": len(tr), "n_holdout": len(te),
        "first": str(s.index.min().date()), "last": str(s.index.max().date()),
        "mean_mx": round(float(tr["mx"].mean()), 4),
        "cal_err": round(float(np.mean(errs)), 4),
        "worst_err": round(float(np.max(errs)), 4),
        "gap_into_1800_mean_abs": round(float(gap.abs().mean()), 4),
        "gap_exceeds_0p25": round(float((gap.abs() > 0.25).mean()), 4),
        "ladder": lad.to_dict("records"), "rungs": rungs,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    ap.add_argument("--pine", action="store_true", help="print Pine array literals")
    args = ap.parse_args(argv)

    r = run(args.ticker)
    print(f"\n{r['ticker']} OVERNIGHT ({r['session']}, {r['minutes']} min)")
    print(f"  {r['first']} -> {r['last']}, train {r['n_train']} / holdout {r['n_holdout']}")
    print(f"  mean max excursion / EV (train) : {r['mean_mx']:.4f}")
    print(f"  gap into 18:00, mean |EV|       : {r['gap_into_1800_mean_abs']:.4f} "
          f"(vs 0.334 into 09:30)")
    print(f"  gap exceeds 0.25 EV on          : {r['gap_exceeds_0p25']:.1%} of sessions "
          f"(vs 49.1% into 09:30)")
    print(f"\n  {'rung':>5} {'c_up':>7} {'c_dn':>7} | {'up hit':>7} {'dn hit':>7} "
          f"| {'err up':>7} {'err dn':>7}")
    for i, p in enumerate(TARGET_P):
        u = next(x for x in r["rungs"] if x["target_p"] == p and x["side"] == "up")
        d = next(x for x in r["rungs"] if x["target_p"] == p and x["side"] == "dn")
        print(f"  {p:>5.0%} {u['c']:>7.4f} {d['c']:>7.4f} | {u['holdout_p']:>7.1%} "
              f"{d['holdout_p']:>7.1%} | {u['err']:>+7.1%} {d['err']:>+7.1%}")
    print(f"\n  mean |error| across 16 rungs : {r['cal_err']:.2%}   "
          f"worst rung {r['worst_err']:.2%}")
    se50 = math.sqrt(0.25 / r["n_holdout"])
    print(f"  1 SE at a 50% rung on {r['n_holdout']} holdout sessions = {se50:.2%}")
    # Magnitude alone is not the test. 16 independent errors should scatter
    # around zero; if they all share a sign the ladder is biased, however small
    # each one is. A mean |error| at the noise floor with 16/16 the same sign is
    # a systematically mis-scaled ladder, not a calibrated one.
    npos = sum(1 for x in r["rungs"] if x["err"] > 0)
    k = max(npos, 16 - npos)
    p_sign = 2 * sum(math.comb(16, j) for j in range(k, 17)) / 2 ** 16
    print(f"  sign test: {npos}/16 rungs err > 0, two-sided p = {p_sign:.2g}")
    biased = p_sign < 0.01
    print("  VERDICT:", "BIASED — all rungs miss the same way; magnitude is at the "
          "noise floor but the direction is not"
          if biased else ("calibrated within sampling noise"
                          if r["cal_err"] <= se50 else "outside noise"))
    if biased:
        mean_err = sum(x["err"] for x in r["rungs"]) / 16
        print(f"  mean SIGNED error {mean_err:+.2%} -> the ladder is too "
              f"{'NARROW' if mean_err > 0 else 'WIDE'} out of sample")

    if args.pine:
        up = ", ".join(f"{x['c_up']:.4f}" for x in r["ladder"])
        dn = ", ".join(f"{x['c_dn']:.4f}" for x in r["ladder"])
        print(f"\n// overnight 18:00-09:30 ET, {r['n_train']} train sessions")
        print(f"var cUpN = array.from({up})")
        print(f"var cDnN = array.from({dn})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"overnight_{args.ticker}.json"
    dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
