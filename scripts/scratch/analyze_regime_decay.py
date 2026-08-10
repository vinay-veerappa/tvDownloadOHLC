#!/usr/bin/env python
"""Regime-decay check: half-split + Monte-Carlo reshuffle for terminal-DD significance."""
import json, os, datetime, random
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_IN = os.path.join(HERE, "nt8_ib_retest_fvg_sep26_full.json")
REPORT_OUT = os.path.join(HERE, "regime_decay_report.json")

def load():
    with open(JSON_IN, encoding="utf-8-sig") as f:
        d = json.load(f)
    ts = d["trades"]
    pnls = [float(t["profitCurrency"]) for t in ts]
    dates = [datetime.datetime.fromisoformat(t["entryTime"]).date() for t in ts]
    return pnls, dates

def stats(pnls):
    n = len(pnls)
    w = sum(1 for p in pnls if p > 0)
    gross_w = sum(p for p in pnls if p > 0)
    gross_l = abs(sum(p for p in pnls if p < 0))
    pf = gross_w / gross_l if gross_l else float("inf")
    avg_w = gross_w / w if w else 0
    avg_l = gross_l / (n - w) if (n - w) else 0
    return {"n": n, "wins": w, "WR": round(w / n * 100, 1) if n else 0,
            "net": round(sum(pnls), 0), "PF": round(pf, 3), "avg_win": round(avg_w, 0), "avg_loss": round(avg_l, 0)}

def drawdown(pnls):
    eq = 0.0; peak = 0.0; mdd = 0.0
    for p in pnls:
        eq += p; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    return mdd

def terminal_dd(pnls):
    """Max drawdown measured from the final equity backwards."""
    eq = 0.0; peak = 0.0; mdd = 0.0
    for p in pnls:
        eq += p; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    return mdd  # same as drawdown but we check how often reshuffle gives terminal-like

def main():
    pnls, dates = load()

    # Half-split: H1 = 2025-01..2026-03, H2 = 2026-04..07
    h1 = [p for p, d in zip(pnls, dates) if d.year == 2025 or (d.year == 2026 and d.month <= 3)]
    h2 = [p for p, d in zip(pnls, dates) if d.year == 2026 and d.month >= 4]

    actual_mdd = drawdown(pnls)

    # Monte-Carlo reshuffle: 10k permutations, measure terminal DD distribution
    rng = random.Random(42)
    n_paths = 10000
    perm_dds = []
    for _ in range(n_paths):
        perm = list(pnls)
        rng.shuffle(perm)
        perm_dds.append(drawdown(perm))
    perm_dds.sort()
    p95 = perm_dds[int(0.95 * n_paths)]
    p99 = perm_dds[int(0.99 * n_paths)]
    # How often is a reshuffled DD >= the actual (more negative)?
    count_worse = sum(1 for dd in perm_dds if dd <= actual_mdd)
    p_value = count_worse / n_paths

    report = {
        "actual_max_dd": round(actual_mdd, 2),
        "H1_2025_01_to_2026_03": stats(h1),
        "H2_2026_04_to_07": stats(h2),
        "monte_carlo_reshuffle": {
            "n_paths": n_paths,
            "p95_max_dd": round(p95, 2),
            "p99_max_dd": round(p99, 2),
            "actual_dd_percentile": round(p_value, 4),
            "interpretation": "p_value = fraction of random reshuffles with DD as bad or worse than actual. p<0.05 => temporal clustering is real (regime decay), p>=0.05 => DD is within random variance.",
        },
        "verdict": {
            "regime_decay": "YES" if stats(h2)["PF"] < 1.1 else "NO",
            "h2_pf": stats(h2)["PF"],
            "temporal_clustering_significant": p_value < 0.05,
        },
    }

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    print(f"\nReport written to {REPORT_OUT}")

if __name__ == "__main__":
    main()