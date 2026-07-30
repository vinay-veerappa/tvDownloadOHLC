#!/usr/bin/env python
"""Compare MNQ overlay ON vs OFF backtests (H1/H2 + per-trade qty/pnl)."""
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ON = os.path.join(HERE, "mnq_overlay_on.json")
OFF = os.path.join(HERE, "mnq_overlay_off.json")

cutoff = datetime.datetime(2026, 4, 1)


def load(p):
    d = json.load(open(p, encoding="utf-8-sig"))
    trs = d["trades"]
    for t in trs:
        t["dt"] = datetime.datetime.fromisoformat(t["entryTime"])
    return d, trs


don, ton = load(ON)
doff, toff = load(OFF)


def summ(trs, label):
    h1 = [t for t in trs if t["dt"] < cutoff]
    h2 = [t for t in trs if t["dt"] >= cutoff]
    print(f"  {label}: total n={len(trs)} net={sum(t['profitCurrency'] for t in trs):+.1f}")
    print(f"    H1 n={len(h1)} net={sum(t['profitCurrency'] for t in h1):+.1f} "
          f"WR={sum(t['profitCurrency']>0 for t in h1)/len(h1)*100:.1f}%")
    print(f"    H2 n={len(h2)} net={sum(t['profitCurrency'] for t in h2):+.1f} "
          f"WR={sum(t['profitCurrency']>0 for t in h2)/len(h2)*100:.1f}%")


print("=== MNQ $250k: overlay ON vs OFF ===")
print(f"ON : PF={don['metrics']['profitFactor']} net={don['metrics']['netProfit']} "
      f"MaxDD={don['metrics']['maxDrawdown']} WR={don['metrics']['tradeWinRatePct']}")
print(f"OFF: PF={doff['metrics']['profitFactor']} net={doff['metrics']['netProfit']} "
      f"MaxDD={doff['metrics']['maxDrawdown']} WR={doff['metrics']['tradeWinRatePct']}")
summ(ton, "ON")
summ(toff, "OFF")

# qty distribution ON
from collections import Counter
qc = Counter(t["quantity"] for t in ton)
print("\n=== Qty distribution ON ===")
for q in sorted(qc):
    print(f"  qty {q}: {qc[q]} trades")

# H2 per-trade ON vs OFF (matched by entryTime)
print("\n=== H2 per-trade: ON vs OFF ===")
on_by = {t["entryTime"]: t for t in ton}
h2off = [t for t in toff if t["dt"] >= cutoff]
for t in h2off:
    o = on_by.get(t["entryTime"])
    if o:
        same = "SAME" if t["profitCurrency"] == o["profitCurrency"] else "DIFF"
        print(f"  {t['entryTime']} OFF qty={t['quantity']} pnl={t['profitCurrency']:+.1f} | "
              f"ON qty={o['quantity']} pnl={o['profitCurrency']:+.1f} [{same}]")