#!/usr/bin/env python
"""IB-range ceiling sweep + H2 trade inspection for vol-expansion gate."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "forensic_retest_report.json"), encoding="utf-8"))
tr = d["trades"]
allh1 = [t for t in tr if t["h1"]]
allh2 = [t for t in tr if not t["h1"]]

print("=== IB-range CEILING sweep (skip ib_range > x pts) ===")
for x in [160, 180, 200, 220, 240, 260, 280, 300]:
    kept = [t for t in tr if t["ib_range"] <= x]
    h1 = [t for t in kept if t["h1"]]; h2 = [t for t in kept if not t["h1"]]
    wr1 = sum(t["win"] for t in h1) / len(h1) if h1 else 0
    wr2 = sum(t["win"] for t in h2) / len(h2) if h2 else 0
    net1 = sum(t["pnl"] for t in h1); net2 = sum(t["pnl"] for t in h2)
    pf = "n/a"
    if h1 or h2:
        gw = sum(t["pnl"] for t in kept if t["pnl"] > 0)
        gl = abs(sum(t["pnl"] for t in kept if t["pnl"] < 0))
        pf = round(gw / gl, 3) if gl else float("inf")
    print(f"  ceiling {x}: H1 {len(h1)}/{len(allh1)} WR={wr1:.3f} net={int(net1):+d} | "
          f"H2 {len(h2)}/{len(allh2)} WR={wr2:.3f} net={int(net2):+d} | total net={int(net1+net2):+d} PF={pf}")

print("\n=== H2-LOSS IB ranges (sorted) ===")
h2loss = [t for t in tr if not t["h1"] and t["win"] == 0]
for t in sorted(h2loss, key=lambda x: x["ib_range"]):
    print(f"  {t['date']} {t['side']:5s} ib={t['ib_range']:.0f} depth={t['depth_ratio']:.2f} "
          f"reversal={t['reversal']} pnl={int(t['pnl']):+d}")
print("=== H2-WIN IB ranges (sorted) ===")
for t in sorted([t for t in tr if not t["h1"] and t["win"] == 1], key=lambda x: x["ib_range"]):
    print(f"  {t['date']} {t['side']:5s} ib={t['ib_range']:.0f} depth={t['depth_ratio']:.2f} "
          f"reversal={t['reversal']} pnl={int(t['pnl']):+d}")

# vol-normalized ceiling: ib_range as % of entry price
print("\n=== IB-range % of price CEILING sweep ===")
for x in [0.005, 0.006, 0.007, 0.008, 0.009, 0.010, 0.011]:
    kept = [t for t in tr if t["ib_range"] / t["entry"] <= x]
    h1 = [t for t in kept if t["h1"]]; h2 = [t for t in kept if not t["h1"]]
    wr1 = sum(t["win"] for t in h1) / len(h1) if h1 else 0
    wr2 = sum(t["win"] for t in h2) / len(h2) if h2 else 0
    net1 = sum(t["pnl"] for t in h1); net2 = sum(t["pnl"] for t in h2)
    print(f"  ceiling {x:.3%}: H1 {len(h1)}/{len(allh1)} WR={wr1:.3f} | "
          f"H2 {len(h2)}/{len(allh2)} WR={wr2:.3f} | total net={int(net1+net2):+d}")