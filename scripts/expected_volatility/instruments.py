"""Fit a ladder and a weekday correction PER INSTRUMENT, and emit the Pine table.

The indicator shipped ONE set of constants — fitted on ES — and swapped only the
volatility index per symbol. That assumes the excursion/EV ratio is
instrument-invariant. It nearly is for RTH, which is why the cross-instrument
replication in RESEARCH_REPORT section 2.5 passed; it is not exact, and the
overnight ladder and the weekday multipliers were never checked on anything but
ES at all. Applying an unvalidated constant is not the same as validating it.

So every instrument gets its own numbers here, on the same discipline used
everywhere else in this study:

  * fitted on the TRAIN fold only,
  * weekday multipliers shrunk halfway to 1.0 (`seasonality.SHRINK`),
  * scored on the HOLDOUT against the ES constants the indicator already ships.

**An instrument only gets its own constants if they beat ES out of sample.**
A per-instrument fit has strictly more parameters and will always look better in
sample, so "we fitted it" is not a reason to ship it. Where the fit does not
win, the ES numbers are emitted for that symbol and the fallback is recorded —
an honest tie is worth more than a table row that implies evidence it lacks.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.instruments
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.instruments --pine
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from .features import OUT_DIR, REPO, TARGET_P, VOL_FOR_TICKER
from .paths import build_paths, ladder_from
from .seasonality import SHRINK, DAYS

BASE = "ES1"

# Symbol roots each fitted instrument covers on a TradingView chart. Micros and
# the cash/ETF proxies track the same underlying, so they share its ladder.
ROOTS = {
    "ES1":  ["ES", "MES", "SPX", "SPY"],
    "NQ1":  ["NQ", "MNQ", "NDX", "QQQ"],
    "RTY1": ["RTY", "M2K", "RUT", "IWM"],
    "YM1":  ["YM", "MYM", "DJI", "DIA"],
    "CL1":  ["CL", "MCL", "USO"],
    "GC1":  ["GC", "MGC", "GLD"],
}

MIN_TRAIN = 400
MIN_HOLDOUT = 80


def _cal_err(x: np.ndarray, c: np.ndarray) -> float:
    """Mean |realised touch rate - promised| over the eight rungs."""
    return float(np.mean([abs(float((x >= c[i]).mean()) - t)
                          for i, t in enumerate(TARGET_P)]))


def fit_one(ticker: str, kind: str, base_cu: np.ndarray,
            base_cd: np.ndarray) -> dict:
    p = build_paths(ticker=ticker, kind=kind)
    tr, te = p.mask(True), p.mask(False)
    if tr.sum() < MIN_TRAIN or te.sum() < MIN_HOLDOUT:
        return {"ticker": ticker, "kind": kind, "skip": True,
                "n_train": int(tr.sum()), "n_holdout": int(te.sum())}

    lad = ladder_from(p, tr)
    cu, cd = lad["c_up"].to_numpy(), lad["c_dn"].to_numpy()

    # Weekday multipliers, same estimator and same shrinkage as seasonality.py.
    w = {"up": np.ones(5), "dn": np.ones(5)}
    for side in ("up", "dn"):
        x = p.up if side == "up" else p.dn
        base = np.log(x[tr & (x > 0)]).mean()
        for d in range(5):
            m = tr & (p.dow == d) & (x > 0)
            raw = float(np.exp(np.log(x[m]).mean() - base)) if m.sum() > 20 else 1.0
            w[side][d] = 1.0 + SHRINK * (raw - 1.0)

    # Holdout scoring, three ladders on identical sessions: the ES constants the
    # indicator ships today, this instrument's own fit, and its fit with the
    # weekday correction applied.
    def score(c_up, c_dn, wk=None) -> float:
        errs = []
        for d in range(5):
            m = te & (p.dow == d)
            if m.sum() < 5:
                continue
            fu = wk["up"][d] if wk else 1.0
            fd = wk["dn"][d] if wk else 1.0
            errs.append(_cal_err(p.up[m], c_up * fu))
            errs.append(_cal_err(p.dn[m], c_dn * fd))
        return float(np.mean(errs))

    e_base = score(base_cu, base_cd)
    e_own = score(cu, cd)
    e_own_dow = score(cu, cd, w)
    best = min((e_base, "es"), (e_own, "own"), (e_own_dow, "own+dow"))

    return {
        "ticker": ticker, "kind": kind, "skip": False,
        "vol": VOL_FOR_TICKER[ticker],
        "n_train": int(tr.sum()), "n_holdout": int(te.sum()),
        "first": str(p.idx.min().date()), "last": str(p.idx.max().date()),
        "c_up": [round(float(v), 4) for v in cu],
        "c_dn": [round(float(v), 4) for v in cd],
        "w_up": [round(float(v), 3) for v in w["up"]],
        "w_dn": [round(float(v), 3) for v in w["dn"]],
        "err_es": round(e_base, 4), "err_own": round(e_own, 4),
        "err_own_dow": round(e_own_dow, 4),
        "winner": best[1],
        # Width against ES, for reporting only — never applied as a scalar,
        # because a single multiplier cannot reproduce a re-fitted ladder's
        # shape and the whole point here is to stop hand-scaling.
        "width_vs_es_up": round(float(np.exp(np.mean(np.log(cu / base_cu)))), 3),
        "width_vs_es_dn": round(float(np.exp(np.mean(np.log(cd / base_cd)))), 3),
    }


def run() -> dict:
    out: dict = {"base": BASE, "shrink": SHRINK, "rows": []}
    base = {}
    for kind in ("RTH", "ON"):
        p = build_paths(ticker=BASE, kind=kind)
        lad = ladder_from(p, p.mask(True))
        base[kind] = (lad["c_up"].to_numpy(), lad["c_dn"].to_numpy())
    out["base_ladder"] = {k: {"c_up": [round(float(x), 4) for x in v[0]],
                              "c_dn": [round(float(x), 4) for x in v[1]]}
                          for k, v in base.items()}

    for ticker in VOL_FOR_TICKER:
        for kind in ("RTH", "ON"):
            out["rows"].append(fit_one(ticker, kind, *base[kind]))
    return out


def _arr(vals) -> str:
    return "array.from(" + ", ".join(f"{v:.4f}" for v in vals) + ")"


def _arr3(vals) -> str:
    return "array.from(" + ", ".join(f"{v:.3f}" for v in vals) + ")"


def emit_pine(d: dict) -> str:
    """Pine literals. Rows that lost to ES emit the ES numbers, so the shipped
    table never contains a constant that failed its own holdout test."""
    L = ["// ---- generated by scripts/expected_volatility/instruments.py ----"]
    by = {(r["ticker"], r["kind"]): r for r in d["rows"] if not r.get("skip")}
    for ticker in VOL_FOR_TICKER:
        tag = ticker[:-1]
        for kind, sfx in (("RTH", "R"), ("ON", "N")):
            r = by.get((ticker, kind))
            if r is None:
                continue
            use_own = r["winner"] != "es"
            use_dow = r["winner"] == "own+dow"
            cu = r["c_up"] if use_own else d["base_ladder"][kind]["c_up"]
            cd = r["c_dn"] if use_own else d["base_ladder"][kind]["c_dn"]
            wu = r["w_up"] if use_dow else [1.0] * 5
            wd = r["w_dn"] if use_dow else [1.0] * 5
            note = ("own fit" if use_own else "ES fallback — own fit lost on holdout")
            L.append(f"// {tag} {kind}: {note}; holdout |cal err| "
                     f"ES {r['err_es']:.2%} / own {r['err_own']:.2%} / "
                     f"own+dow {r['err_own_dow']:.2%}  (n={r['n_holdout']})")
            L.append(f"var cUp{sfx}_{tag} = {_arr(cu)}")
            L.append(f"var cDn{sfx}_{tag} = {_arr(cd)}")
            L.append(f"var wUp{sfx}_{tag} = {_arr3(wu)}")
            L.append(f"var wDn{sfx}_{tag} = {_arr3(wd)}")
    return "\n".join(L)


PINE = (REPO / "scripts" / "indicators-pine" / "expected-volatility" /
        "expected_volatility_ladder.pine")
OPEN_TAG = "// <<< EV-LADDER-CONSTANTS >>>"
CLOSE_TAG = "// <<< /EV-LADDER-CONSTANTS >>>"


def write_pine(d: dict) -> int:
    """Replace the sentinel region in the indicator with freshly fitted values.

    Written rather than printed for copy-paste because 48 array literals are 48
    chances to transcribe one wrong, and a single mistyped digit moves a level
    without moving anything that would flag it. The sentinels must both exist and
    be in order — a silent append would leave the OLD constants in force above
    the new ones, and Pine would use whichever it parsed last.
    """
    src = PINE.read_text(encoding="utf-8")
    i, j = src.find(OPEN_TAG), src.find(CLOSE_TAG)
    if i < 0 or j < 0 or j < i:
        raise SystemExit(f"sentinels missing or out of order in {PINE}")
    out = src[:i] + OPEN_TAG + "\n" + emit_pine(d) + "\n" + src[j:]
    PINE.write_text(out, encoding="utf-8")
    n = out.count("array.from(")
    print(f"  wrote {PINE}  ({n} array literals in file)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pine", action="store_true")
    ap.add_argument("--write-pine", action="store_true",
                    help="inject the fitted constants into the .pine directly")
    args = ap.parse_args(argv)

    d = run()
    print(f"\nPer-instrument ladders — fitted on train, scored on holdout "
          f"against the {BASE} constants currently shipped.\n")
    print(f"  {'sym':>5} {'kind':>4} {'vol':>5} {'train':>6} {'hold':>5} | "
          f"{'ES':>7} {'own':>7} {'own+dow':>8} | {'winner':>8} | "
          f"{'w up':>5} {'w dn':>5}")
    for r in d["rows"]:
        if r.get("skip"):
            print(f"  {r['ticker'][:-1]:>5} {r['kind']:>4} "
                  f"{'—':>5} {r['n_train']:>6} {r['n_holdout']:>5} | "
                  f"SKIPPED — under {MIN_TRAIN}/{MIN_HOLDOUT}")
            continue
        print(f"  {r['ticker'][:-1]:>5} {r['kind']:>4} {r['vol']:>5} "
              f"{r['n_train']:>6} {r['n_holdout']:>5} | {r['err_es']:>7.2%} "
              f"{r['err_own']:>7.2%} {r['err_own_dow']:>8.2%} | "
              f"{r['winner']:>8} | {r['width_vs_es_up']:>5.3f} "
              f"{r['width_vs_es_dn']:>5.3f}")

    won = sum(1 for r in d["rows"] if not r.get("skip") and r["winner"] != "es")
    tot = sum(1 for r in d["rows"] if not r.get("skip"))
    print(f"\n  {won} of {tot} instrument-sessions beat the ES constants out of "
          f"sample; the rest fall back to ES.")
    dow = sum(1 for r in d["rows"] if not r.get("skip") and r["winner"] == "own+dow")
    print(f"  {dow} of those also want their own weekday correction.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "instruments.json"
    dest.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print(f"  wrote {dest}")

    if args.pine:
        print("\n" + emit_pine(d))
    if args.write_pine:
        return write_pine(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
