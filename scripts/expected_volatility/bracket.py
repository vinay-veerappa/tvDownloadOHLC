"""Study A — bracket expectancy by FIRST PASSAGE.

The ladder reports marginal touch rates: P(this distance is reached at some
point in the session). A trader never faces that question. They face "if I put
a target here and a stop there, which gets hit first" — and the marginal rates
cannot answer it, because on most sessions BOTH are touched. Summing them is
meaningless and the difference is not a probability of anything.

So this measures the race directly, from `paths.first_at`.

Vocabulary is borrowed deliberately from the Magic Hour playbook already in this
repo (`docs/strategies/magic_hour_analysis/master_magic_hour_report.md`) so the
two read the same way — REACH, WIN, MAE, and time-to-target.

Three methodological rules, two of them taken from that report's own warnings:

  * **Win% here is REAL-TIME, not survivorship.** The Magic Hour report's §12
    documents the trap in its own dashboard: a zone win rate of 99.2% is "of the
    trades that PEAKED in this zone, how many won", which is only knowable after
    the fact. Every number below is measured from the session open across ALL
    sessions, conditioning on nothing that is not known at entry.
  * **MAE is walk-away.** Adverse excursion is truncated at the moment the
    target is reached (§ "The Peculiar Truncation"). Measuring heat across the
    whole session credits a trade with damage that happened after you were out.
  * **A tie is a loss.** Within a 1-minute bar the order of two touches is
    unknowable, so `t_target == t_stop` is scored as the stop. The tie rate is
    reported, because it grows as the bracket tightens and is therefore worst
    exactly where the answer matters most.

What this study can and cannot show
-----------------------------------
It cannot manufacture an edge. The anchor-control result (RESEARCH_REPORT §2)
found no directional edge from the session open, so expectancy should land near
zero minus costs at every bracket. That is the null this measures against, and
confirming it is the point: it means the ladder's value is in REFUSING trades
whose arithmetic never worked, not in selecting ones that do.

Usage
-----
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.bracket
    .\\.venv\\Scripts\\python.exe -m scripts.expected_volatility.bracket --kind ON
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from .features import OUT_DIR, TARGET_P
from .paths import build_paths, ladder_from, Paths

# ES round turn: 1 tick of slippage (0.25 pt) + ~$4 commission on a $50/pt
# contract. Expressed per session in EV units, because a fixed point cost is a
# different fraction of the move on a VIX-12 day than a VIX-30 one.
COST_POINTS = 0.25 + 4.0 / 50.0


def evaluate(p: Paths, mask: np.ndarray, c_tgt: float, c_stop: float,
             side: str = "long", cost: bool = True) -> dict:
    """One bracket, measured as a race from the session open."""
    if side == "long":
        t_t, t_s = p.first_at("up", c_tgt), p.first_at("dn", c_stop)
        drift = p.ret_n
        adverse = p.t_dn
    else:
        t_t, t_s = p.first_at("dn", c_tgt), p.first_at("up", c_stop)
        drift = -p.ret_n
        adverse = p.t_up

    t_t, t_s, drift, adverse = t_t[mask], t_s[mask], drift[mask], adverse[mask]
    n = int(mask.sum())

    win = t_t < t_s
    loss = t_s < t_t
    tie = (t_t == t_s) & np.isfinite(t_t)
    neither = ~np.isfinite(t_t) & ~np.isfinite(t_s)

    # Walk-away MAE: how far the trade went against you BEFORE the target was
    # reached. `adverse` is non-decreasing across the grid, so the count of grid
    # distances already breached at t_t is the index of the deepest one.
    k = (adverse < t_t[:, None]).sum(axis=1)
    mae = np.where(k > 0, p.grid[np.clip(k - 1, 0, len(p.grid) - 1)], 0.0)

    pnl = np.where(win, c_tgt, np.where(loss | tie, -c_stop, drift))
    if cost:
        pnl = pnl - COST_POINTS / p.EV[mask]

    # For a driftless random walk run to infinity, P(+a before -b) = b/(a+b)
    # exactly. That is the fair-game benchmark, and it is what `breakeven` is.
    # But a session is FINITE: on a wide bracket most sessions end having
    # touched neither level, and that mass is subtracted from BOTH sides. So
    # `win - breakeven` is not a test of the process — it mostly measures how
    # much probability leaked to "neither", which is why it grows more negative
    # the wider the bracket gets. The horizon-free test conditions on the race
    # having been decided at all.
    be = c_stop / (c_tgt + c_stop)
    wr = float(win.mean())
    resolved = float((win | loss | tie).mean())
    wr_cond = float(win.sum() / max((win | loss | tie).sum(), 1))
    return {
        "side": side, "c_tgt": round(c_tgt, 4), "c_stop": round(c_stop, 4),
        "n": n,
        "reach_tgt": round(float(np.isfinite(t_t).mean()), 4),
        "win": round(wr, 4),
        "loss": round(float(loss.mean()), 4),
        "tie": round(float(tie.mean()), 4),
        "neither": round(float(neither.mean()), 4),
        "breakeven": round(float(be), 4),
        "resolved": round(resolved, 4),
        "win_cond": round(wr_cond, 4),
        "edge_pp": round((wr - be) * 100, 2),
        "edge_cond_pp": round((wr_cond - be) * 100, 2),
        "exp_ev": round(float(pnl.mean()), 4),
        "exp_se": round(float(pnl.std(ddof=1) / np.sqrt(n)), 4),
        "mae_med": round(float(np.median(mae[win])) if win.any() else float("nan"), 4),
        "mae_p80": round(float(np.quantile(mae[win], 0.80)) if win.any() else float("nan"), 4),
        "min_med": round(float(np.median(t_t[win])) if win.any() else float("nan"), 1),
    }


def run(ticker: str = "ES1", kind: str = "RTH") -> dict:
    p = build_paths(ticker=ticker, kind=kind)
    tr, te = p.mask(True), p.mask(False)
    lad = ladder_from(p, tr)
    cu = lad["c_up"].to_numpy()
    cd = lad["c_dn"].to_numpy()

    out = {"ticker": ticker, "kind": kind, "n_train": int(tr.sum()),
           "n_holdout": int(te.sum()),
           "first": str(p.idx.min().date()), "last": str(p.idx.max().date()),
           "cost_points": COST_POINTS, "grids": {}, "runner": []}

    for side in ("long", "short"):
        tgt_c, stop_c = (cu, cd) if side == "long" else (cd, cu)
        rows = []
        for i, pt in enumerate(TARGET_P):
            for j, ps in enumerate(TARGET_P):
                r = evaluate(p, tr, float(tgt_c[i]), float(stop_c[j]), side)
                r["target_rung"], r["stop_rung"] = pt, ps
                r["holdout"] = evaluate(p, te, float(tgt_c[i]), float(stop_c[j]), side)
                rows.append(r)
        out["grids"][side] = rows

    # Runner conversion: given the rung was reached, how often does the NEXT one
    # out follow. Nested rungs make this the ratio of reach rates, which is
    # exactly why it belongs here — it is the number a trader wants ("I am here,
    # does it keep going") and it is NOT the rung's own touch probability.
    for side, c in (("up", cu), ("dn", cd)):
        for i in range(len(TARGET_P) - 1):
            a = np.isfinite(p.first_at(side, float(c[i])))[tr]
            b = np.isfinite(p.first_at(side, float(c[i + 1])))[tr]
            base = int(a.sum())
            out["runner"].append({
                "side": side, "from_rung": TARGET_P[i], "to_rung": TARGET_P[i + 1],
                "n_reached": base,
                "convert": round(float((a & b).sum() / base), 4) if base else None,
            })
    return out


def _fmt_grid(rows: list[dict], key: str, scale: float = 100.0) -> str:
    lines = ["        " + "".join(f"{p:>8.0%}" for p in TARGET_P)]
    for pt in TARGET_P:
        cells = [r for r in rows if r["target_rung"] == pt]
        cells.sort(key=lambda r: -r["stop_rung"])
        lines.append(f"  {pt:>5.0%} " + "".join(
            f"{c[key] * scale:>8.1f}" for c in cells))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", default="ES1")
    ap.add_argument("--kind", default="RTH", choices=["RTH", "ON", "both"])
    args = ap.parse_args(argv)

    kinds = ["RTH", "ON"] if args.kind == "both" else [args.kind]
    for kind in kinds:
        r = run(args.ticker, kind)
        print(f"\n{'=' * 78}\n{r['ticker']} {kind} — bracket first passage")
        print(f"{r['first']} -> {r['last']}, train {r['n_train']} / "
              f"holdout {r['n_holdout']}, cost {r['cost_points']:.2f} pt round turn")

        for side in ("long", "short"):
            rows = r["grids"][side]
            print(f"\n  {side.upper()}: WIN% (target reached before stop), "
                  f"train fold\n  rows = target rung, cols = stop rung")
            print(_fmt_grid(rows, "win"))
            print(f"\n  {side.upper()}: CONDITIONAL EDGE in pp — P(target first | "
                  f"race decided) minus breakeven.\n  Zero is a fair game; this "
                  f"is the number that must be > 0 to trade.")
            print(_fmt_grid(rows, "edge_cond_pp", 1.0))

            best = max(rows, key=lambda x: x["exp_ev"])
            worst = min(rows, key=lambda x: x["exp_ev"])
            allexp = np.array([x["exp_ev"] for x in rows])
            print(f"\n  expectancy across all 64 brackets: mean {allexp.mean():+.4f} EV, "
                  f"range {allexp.min():+.4f} .. {allexp.max():+.4f}")
            print(f"  best  {best['target_rung']:.0%}/{best['stop_rung']:.0%}: "
                  f"win {best['win']:.1%} vs be {best['breakeven']:.1%}, "
                  f"exp {best['exp_ev']:+.4f} +/- {best['exp_se']:.4f} EV "
                  f"(holdout {best['holdout']['exp_ev']:+.4f})")
            print(f"  worst {worst['target_rung']:.0%}/{worst['stop_rung']:.0%}: "
                  f"win {worst['win']:.1%} vs be {worst['breakeven']:.1%}, "
                  f"exp {worst['exp_ev']:+.4f} EV")

        # Long and short expectancies are NOT two independent readings of
        # bracket geometry. ES rose a great deal over 2022-2026, so every long
        # bracket inherits that drift and every short one pays it. Averaging the
        # mirror pair cancels the drift to first order and leaves whatever the
        # geometry is worth; halving the difference recovers the drift. Reading
        # the long column on its own would have called the drift an edge.
        lg = {(x["target_rung"], x["stop_rung"]): x for x in r["grids"]["long"]}
        sh = {(x["target_rung"], x["stop_rung"]): x for x in r["grids"]["short"]}
        geo = np.array([(lg[k]["edge_cond_pp"] + sh[k]["edge_cond_pp"]) / 2 for k in lg])
        dft = np.array([(lg[k]["edge_cond_pp"] - sh[k]["edge_cond_pp"]) / 2 for k in lg])
        leak = np.array([1 - lg[k]["resolved"] for k in lg])
        r["geometry_edge_pp"] = round(float(geo.mean()), 3)
        r["drift_pp"] = round(float(dft.mean()), 3)
        print(f"\n  DRIFT vs GEOMETRY, over all 64 mirrored brackets")
        print(f"    geometry edge (long+short)/2 : {geo.mean():+.2f} pp  "
              f"[{geo.min():+.2f} .. {geo.max():+.2f}]")
        print(f"    drift         (long-short)/2 : {dft.mean():+.2f} pp  "
              f"[{dft.min():+.2f} .. {dft.max():+.2f}]")
        print(f"    unresolved (neither leg hit) : {leak.mean():.1%} of sessions "
              f"[{leak.min():.1%} .. {leak.max():.1%}]")

        print(f"\n  RUNNER CONVERSION — P(next rung out | this rung reached), train")
        print(f"  {'from':>6} {'to':>6} {'up n':>7} {'up':>7} {'dn n':>7} {'dn':>7}")
        for i in range(len(TARGET_P) - 1):
            u = r["runner"][i]
            d = r["runner"][len(TARGET_P) - 1 + i]
            print(f"  {u['from_rung']:>6.0%} {u['to_rung']:>6.0%} "
                  f"{u['n_reached']:>7} {u['convert']:>7.1%} "
                  f"{d['n_reached']:>7} {d['convert']:>7.1%}")

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = OUT_DIR / f"bracket_{args.ticker}_{kind}.json"
        dest.write_text(json.dumps(r, indent=2), encoding="utf-8")
        print(f"\n  wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
