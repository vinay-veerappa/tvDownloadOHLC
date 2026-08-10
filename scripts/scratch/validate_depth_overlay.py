#!/usr/bin/env python
"""Validate the depth-bias-overlay sizing on the 65 FVG-filtered trades.
Overlay: scale position size by retest depth.
  depth < 0.6  -> 0.25x  (weak/false break, minimal size)
  0.6-0.9      -> 0.50x  (moderate retest)
  >= 0.9       -> 1.00x  (genuine momentum thrust, full size)
Recompute net PnL per trade = pnl * size_mult (qty scales linearly with risk).
Compare H1/H2/ALL net, WR-weighted, MaxDD vs baseline 1.0x.
"""
import json, os, datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "forensic_retest_report.json"), encoding="utf-8"))
tr = d["trades"]
allh1 = [t for t in tr if t["h1"]]
allh2 = [t for t in tr if not t["h1"]]


def size_mult(depth, lo=0.6, hi=0.9):
    if depth < lo:
        return 0.25
    if depth < hi:
        return 0.50
    return 1.00


def run(name, fn):
    rows = []
    for t in tr:
        m = fn(t["depth_ratio"])
        rows.append(dict(h1=t["h1"], win=t["win"], pnl=t["pnl"] * m, depth=t["depth_ratio"]))
    h1 = [r for r in rows if r["h1"]]; h2 = [r for r in rows if not r["h1"]]

    def stat(g):
        if not g:
            return None
        pnls = [r["pnl"] for r in g]
        n = len(g); w = sum(r["win"] for r in g)
        net = sum(pnls)
        gw = sum(p for p in pnls if p > 0); gl = abs(sum(p for p in pnls if p < 0))
        pf = gw / gl if gl else float("inf")
        # MaxDD over chronological pnl sequence
        eq = 0.0; peak = 0.0; mdd = 0.0
        for p in pnls:
            eq += p; peak = max(peak, eq); mdd = min(mdd, eq - peak)
        return dict(n=n, wr=w / n, net=int(net), pf=round(pf, 3), mdd=int(mdd))
    s1, s2, sa = stat(h1), stat(h2), stat(rows)
    print(f"=== {name} ===")
    print(f"  H1: n={s1['n']} WR={s1['wr']:.3f} net={s1['net']:+d} PF={s1['pf']} MaxDD={s1['mdd']:+d}")
    print(f"  H2: n={s2['n']} WR={s2['wr']:.3f} net={s2['net']:+d} PF={s2['pf']} MaxDD={s2['mdd']:+d}")
    print(f"  ALL: n={sa['n']} WR={sa['wr']:.3f} net={sa['net']:+d} PF={sa['pf']} MaxDD={sa['mdd']:+d}")
    return s1, s2, sa


# baseline: 1.0x everywhere (matches the backtest)
run("Baseline 1.0x", lambda d: 1.0)
# proposed overlay
run("Depth overlay (0.25/0.50/1.00 @ 0.6/0.9)", lambda d: size_mult(d))
# alternative: continuous linear from 0.25 @ depth 0 to 1.0 @ depth 1.0
run("Depth linear 0.25..1.0", lambda d: 0.25 + 0.75 * min(1.0, max(0.0, d)))
# aggressive: 0.10 below 0.6, 0.5 0.6-0.9, 1.0 above
run("Depth overlay aggressive (0.10/0.50/1.00)", lambda d: 0.10 if d < 0.6 else (0.50 if d < 0.9 else 1.0))

# distribution of depth
print("\n=== Depth distribution ===")
depths = sorted([t["depth_ratio"] for t in tr])
print(f"  min={depths[0]:.2f} p25={np.percentile(depths,25):.2f} "
      f"median={np.median(depths):.2f} p75={np.percentile(depths,75):.2f} max={depths[-1]:.2f}")
buckets = [(0,0.6),(0.6,0.9),(0.9,99)]
for lo,hi in buckets:
    h1=[t for t in allh1 if lo<=t['depth_ratio']<hi]
    h2=[t for t in allh2 if lo<=t['depth_ratio']<hi]
    wr1=sum(t['win'] for t in h1)/len(h1) if h1 else 0
    wr2=sum(t['win'] for t in h2)/len(h2) if h2 else 0
    print(f"  depth[{lo},{hi}): H1 n={len(h1)} WR={wr1:.2f} | H2 n={len(h2)} WR={wr2:.2f}")