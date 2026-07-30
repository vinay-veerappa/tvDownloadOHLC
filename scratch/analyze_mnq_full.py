#!/usr/bin/env python
import json, datetime
from collections import Counter

d = json.load(open("scratch/mnq_overlay_on_full.json", encoding="utf-8-sig"))
tr = d["trades"]
print("tradeCount", d["tradeCount"], "returned", len(tr))
cutoff = datetime.datetime(2026, 4, 1)
h1 = [t for t in tr if datetime.datetime.fromisoformat(t["entryTime"]) < cutoff]
h2 = [t for t in tr if datetime.datetime.fromisoformat(t["entryTime"]) >= cutoff]
print("H1 n", len(h1), "net", round(sum(t["profitCurrency"] for t in h1), 1))
print("H2 n", len(h2), "net", round(sum(t["profitCurrency"] for t in h2), 1))
print("--- H2 trades (qty, pnl, exit) ---")
for t in sorted(h2, key=lambda x: x["entryTime"]):
    print(f"  {t['entryTime']} {t['marketPosition']:5s} qty={t['quantity']:2d} "
          f"pnl={t['profitCurrency']:+.1f} {t['exitName']}")
print("--- qty dist (all) ---", dict(sorted(Counter(t["quantity"] for t in tr).items())))
# compare to OFF
doff = json.load(open("scratch/mnq_overlay_off_full.json", encoding="utf-8-sig"))
toff = doff["trades"]
print("\n=== H2 ON vs OFF (matched) ===")
on_by = {t["entryTime"]: t for t in tr}
for t in toff:
    if datetime.datetime.fromisoformat(t["entryTime"]) >= cutoff:
        o = on_by.get(t["entryTime"])
        if o:
            same = "SAME" if abs(t["profitCurrency"] - o["profitCurrency"]) < 1 else "DIFF"
            print(f"  {t['entryTime']} OFF q={t['quantity']} pnl={t['profitCurrency']:+.1f} | "
                  f"ON q={o['quantity']} pnl={o['profitCurrency']:+.1f} [{same}]")