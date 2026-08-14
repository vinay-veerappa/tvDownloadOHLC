#!/usr/bin/env python
"""Generalized regime-decay + MaxDD analysis for any NT8 SA trade JSON.

Usage: python scratch/analyze_any_backtest.py <path-to-json> [label]
"""
import json, os, sys, datetime, random
from collections import Counter

def load(path):
    with open(path, encoding="utf-8-sig") as f:
        d = json.load(f)
    ts = d.get("trades", [])
    pnls = [float(t.get("profitCurrency", 0)) for t in ts]
    dates = []
    for t in ts:
        et = t.get("entryTime", t.get("entryDate", ""))
        try:
            dates.append(datetime.datetime.fromisoformat(et).date())
        except Exception:
            dates.append(None)
    return d, pnls, dates

def stats(pnls):
    n = len(pnls)
    if n == 0:
        return {"n": 0}
    w = sum(1 for p in pnls if p > 0)
    gross_w = sum(p for p in pnls if p > 0)
    gross_l = abs(sum(p for p in pnls if p < 0))
    pf = gross_w / gross_l if gross_l else float("inf")
    avg_w = gross_w / w if w else 0
    avg_l = gross_l / (n - w) if (n - w) else 0
    return {"n": n, "wins": w, "WR": round(w / n * 100, 1), "net": round(sum(pnls), 0),
            "PF": round(pf, 3), "avg_win": round(avg_w, 0), "avg_loss": round(avg_l, 0)}

def drawdown(pnls):
    eq = 0.0; peak = 0.0; mdd = 0.0
    for p in pnls:
        eq += p; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    return mdd

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "scratch/nt8_ib_retest_fvg_sep26_full.json"
    label = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(path)
    d, pnls, dates = load(path)
    n = len(pnls)

    h1 = [p for p, dt in zip(pnls, dates) if dt and (dt.year == 2025 or (dt.year == 2026 and dt.month <= 3))]
    h2 = [p for p, dt in zip(pnls, dates) if dt and dt.year == 2026 and dt.month >= 4]

    actual_mdd = drawdown(pnls)
    rng = random.Random(42)
    perm_dds = sorted([drawdown(list(shuffled := list(pnls)) or (rng.shuffle(shuffled), shuffled)[1])
                       for _ in range(10000)])
    p95 = perm_dds[int(0.95 * 10000)]
    p_value = sum(1 for dd in perm_dds if dd <= actual_mdd) / 10000

    print(f"=== {label} ===")
    print(f"Total: {stats(pnls)}")
    print(f"MaxDD: {actual_mdd:.0f}  (reshuffle p95={p95:.0f}, p-value={p_value:.4f})")
    print(f"H1 (Jan25-Mar26): {stats(h1)}")
    print(f"H2 (Apr-Jul 26):  {stats(h2)}")
    decay = "YES" if (len(h2) > 5 and stats(h2).get("PF", 0) < 1.1) else "NO"
    sig = "significant" if p_value < 0.05 else "within variance"
    print(f"Regime decay: {decay} (H2 PF {stats(h2).get('PF','?')}, clustering {sig})")

if __name__ == "__main__":
    main()