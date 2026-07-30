#!/usr/bin/env python
"""Re-evaluate gates against REALIZED R:R (breakeven WR ~50%), and check
whether the vol ceiling + a retest-quality gate can flip H2 to positive EV."""
import json, os, datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "forensic_retest_report.json"), encoding="utf-8"))
tr = d["trades"]
# realized pts proxy: pnl / NQ point value ($20)
for t in tr:
    t["realized_pts"] = t["pnl"] / 20.0

allh1 = [t for t in tr if t["h1"]]
allh2 = [t for t in tr if not t["h1"]]


def metrics(subset):
    if not subset:
        return None
    n = len(subset)
    wins = [t for t in subset if t["win"]]
    losses = [t for t in subset if not t["win"]]
    wr = len(wins) / n
    avg_win_pts = np.mean([t["realized_pts"] for t in wins]) if wins else 0
    avg_loss_pts = np.mean([abs(t["realized_pts"]) for t in losses]) if losses else 0
    rr = avg_win_pts / avg_loss_pts if avg_loss_pts else float("inf")
    be_wr = 1 / (1 + rr) if rr else 1
    net = sum(t["pnl"] for t in subset)
    # expectancy in R (using avg loss as 1R)
    exp_r = wr * rr - (1 - wr)
    return dict(n=n, wr=wr, rr=rr, be_wr=be_wr, net=int(net), exp_r=exp_r,
                avg_win=int(avg_win_pts), avg_loss=int(avg_loss_pts))


print("=== Baseline (realized R:R) ===")
for lab, sub in [("H1", allh1), ("H2", allh2), ("ALL", tr)]:
    m = metrics(sub)
    print(f"  {lab}: n={m['n']} WR={m['wr']:.3f} R:R={m['rr']:.2f} beWR={m['be_wr']:.3f} "
          f"net={m['net']:+d} E[R]={m['exp_r']:+.3f}")

print("\n=== IB-range ceiling vs REALIZED breakeven ===")
for x in [160, 180, 200, 220, 240, 260, 280]:
    kept = [t for t in tr if t["ib_range"] <= x]
    h1 = [t for t in kept if t["h1"]]; h2 = [t for t in kept if not t["h1"]]
    m1 = metrics(h1); m2 = metrics(h2); ma = metrics(kept)
    print(f"  ceiling {x}: H1 n={m1['n']} WR={m1['wr']:.3f} E[R]={m1['exp_r']:+.2f} net={m1['net']:+d} | "
          f"H2 n={m2['n']} WR={m2['wr']:.3f} E[R]={m2['exp_r']:+.2f} net={m2['net']:+d} | "
          f"ALL E[R]={ma['exp_r']:+.2f} net={ma['net']:+d}")

# The realized R:R is ~1.09 — meaning winners exit EARLY. The target is 2:1 nominal.
# Key question: do H2 winners reach full target? Check H2-win realized pts vs ib_range (target=range).
print("\n=== Do winners reach the 2:1 target? (realized pts vs nominal target = ib_range) ===")
for lab, sub in [("H1-win", [t for t in allh1 if t["win"]]), ("H2-win", [t for t in allh2 if t["win"]])]:
    if not sub:
        continue
    frac = [t["realized_pts"] / t["ib_range"] for t in sub]  # 1.0 = full target reached
    print(f"  {lab}: n={len(sub)} median realized/target={np.median(frac):.2f} mean={np.mean(frac):.2f}")

# Check if a retest-DEPTH gate (the H2 winners had depth>1.0, losers depth<0.85) helps
print("\n=== Retest-depth gate (H2 winners depth>1.0, losers <0.85) — DEPTH FLOOR sweep ===")
for x in [0.7, 0.8, 0.9, 1.0, 1.1]:
    kept = [t for t in tr if t["depth_ratio"] >= x]
    h1 = [t for t in kept if t["h1"]]; h2 = [t for t in kept if not t["h1"]]
    m1 = metrics(h1); m2 = metrics(h2)
    n1 = m1["n"] if m1 else 0; wr1 = m1["wr"] if m1 else 0
    n2 = m2["n"] if m2 else 0; wr2 = m2["wr"] if m2 else 0; net2 = m2["net"] if m2 else 0
    print(f"  depth>={x}: H1 n={n1} WR={wr1:.3f} | H2 n={n2} WR={wr2:.3f} net={net2:+d}")

# COMBO: ib_range ceiling 220 AND depth >= 0.9 (H2 winners all had depth>1.0)
print("\n=== COMBO: ib_range<=220 AND depth>=0.9 ===")
kept = [t for t in tr if t["ib_range"] <= 220 and t["depth_ratio"] >= 0.9]
h1 = [t for t in kept if t["h1"]]; h2 = [t for t in kept if not t["h1"]]
m1 = metrics(h1); m2 = metrics(h2); ma = metrics(kept)
if m1 and m2 and ma:
    print(f"  H1 n={m1['n']} WR={m1['wr']:.3f} E[R]={m1['exp_r']:+.2f} net={m1['net']:+d} | "
          f"H2 n={m2['n']} WR={m2['wr']:.3f} E[R]={m2['exp_r']:+.2f} net={m2['net']:+d} | "
          f"ALL E[R]={ma['exp_r']:+.2f} net={ma['net']:+d}")