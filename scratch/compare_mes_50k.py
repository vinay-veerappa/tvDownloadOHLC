#!/usr/bin/env python
"""Compare MES $50k overlay ON vs OFF + H1/H2 split + qty distribution."""
import json, datetime
from collections import Counter

OFF = "scratch/mes_50k_off.json"
ON = "scratch/mes_50k_on.json"
cutoff = datetime.datetime(2026, 4, 1)


def load(p):
    d = json.load(open(p, encoding="utf-8-sig"))
    tr = d["trades"]
    for t in tr:
        t["dt"] = datetime.datetime.fromisoformat(t["entryTime"])
    return d, tr


don, ton = load(ON)
doff, toff = load(OFF)


def summ(trs, label):
    h1 = [t for t in trs if t["dt"] < cutoff]
    h2 = [t for t in trs if t["dt"] >= cutoff]
    net = sum(t["profitCurrency"] for t in trs)
    h1n = sum(t["profitCurrency"] for t in h1)
    h2n = sum(t["profitCurrency"] for t in h2)
    h1wr = sum(t["profitCurrency"] > 0 for t in h1) / len(h1) * 100 if h1 else 0
    h2wr = sum(t["profitCurrency"] > 0 for t in h2) / len(h2) * 100 if h2 else 0
    print(f"  {label}: total n={len(trs)} net={net:+.1f}")
    print(f"    H1 n={len(h1)} net={h1n:+.1f} WR={h1wr:.1f}%")
    print(f"    H2 n={len(h2)} net={h2n:+.1f} WR={h2wr:.1f}%")


print("=== MES $50k: overlay ON vs OFF ===")
print(f"ON : PF={don['metrics']['profitFactor']} net={don['metrics']['netProfit']} "
      f"MaxDD={don['metrics']['maxDrawdown']} WR={don['metrics']['tradeWinRatePct']} "
      f"n={don['tradeCount']} returned={len(ton)}")
print(f"OFF: PF={doff['metrics']['profitFactor']} net={doff['metrics']['netProfit']} "
      f"MaxDD={doff['metrics']['maxDrawdown']} WR={doff['metrics']['tradeWinRatePct']} "
      f"n={doff['tradeCount']} returned={len(toff)}")
summ(ton, "ON")
summ(toff, "OFF")

# qty distribution
print("\n=== Qty distribution ===")
print("ON :", dict(sorted(Counter(t["quantity"] for t in ton).items())))
print("OFF:", dict(sorted(Counter(t["quantity"] for t in toff).items())))

# H2 per-trade ON vs OFF
print("\n=== H2 per-trade: ON vs OFF ===")
on_by = {t["entryTime"]: t for t in ton}
for t in sorted(toff, key=lambda x: x["entryTime"]):
    if t["dt"] >= cutoff:
        o = on_by.get(t["entryTime"])
        if o:
            same = "SAME" if abs(t["profitCurrency"] - o["profitCurrency"]) < 1 else "DIFF"
            print(f"  {t['entryTime']} {t['marketPosition']:5s} OFF q={t['quantity']:2d} "
                  f"pnl={t['profitCurrency']:+.1f} | ON q={o['quantity']:2d} "
                  f"pnl={o['profitCurrency']:+.1f} [{same}]")