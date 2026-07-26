"""Critical verification: test the pilot's main claim across time windows.

Specifically:
1. Is the "all 3 plays positive E[R]" claim stable across years, or is it a
   recent-only artifact of the 12-month pilot window?
2. Compute per-year E[R], WR, PF for each play on NQ1 NY AM IB.
3. Test the same statistics on a longer window (3-5 years).
4. Compare Play 3 (fade) to Play 1 (breakout) — which has more stable edge?
"""
import pandas as pd
import numpy as np
from pathlib import Path

D = Path("data/derived")
p = D / "ib_play_detail_NQ1.parquet"
df = pd.read_parquet(p, columns=["trading_day", "play", "target_lvl", "result", "realized_r", "session_slot"])
df = df[df["session_slot"] == "NY AM IB"].copy()
df["trading_day"] = pd.to_datetime(df["trading_day"])
df["year"] = df["trading_day"].dt.year

print(f"Total NQ1 NY AM IB play-detail rows: {len(df)}")
print(f"Date range: {df['trading_day'].min().date()} to {df['trading_day'].max().date()}")
print(f"Years: {sorted(df['year'].unique())}")
print()


def stats(g, label):
    """Per-group stats: n_active, WR, E[R], PF (active only)."""
    active = g[g["result"] != 0]
    n = len(g)
    n_a = len(active)
    if n_a == 0:
        return
    wins = (active["result"] == 1).sum()
    wr = 100 * wins / n_a
    exp = active["realized_r"].mean()
    pf_pos = active[active["result"] == 1]["realized_r"].sum()
    pf_neg = abs(active[active["result"] == -1]["realized_r"].sum())
    pf = pf_pos / pf_neg if pf_neg > 0 else float('nan')
    pos = "+" if exp > 0 else "-"
    print(f"  {label:<30} N={n:>5} active={n_a:>5} ({100*n_a/n:>4.1f}%)  WR={wr:>5.1f}%  E[R]={pos}{abs(exp):.4f}  PF={pf:>5.2f}")


# ── Per-year breakdown for each play ──
print("=" * 100)
print("PER-YEAR BREAKDOWN (active trades only, all target_lvl combined)")
print("=" * 100)
for play in [1, 2, 3]:
    print(f"\nPlay {play}:")
    g = df[df["play"] == play]
    for year in sorted(g["year"].unique()):
        stats(g[g["year"] == year], f"{year}")
    # also: all-time
    stats(g, "ALL-TIME")


# ── 12-month rolling ──
print("\n" + "=" * 100)
print("12-MONTH ROLLING E[R] (active trades only)")
print("=" * 100)
max_day = df["trading_day"].max()
min_day = max_day - pd.Timedelta(days=12 * 30)
recent = df[df["trading_day"] >= min_day]
print(f"\nLast 12 months: {recent['trading_day'].min().date()} to {recent['trading_day'].max().date()}")
for play in [1, 2, 3]:
    stats(recent[recent["play"] == play], f"Play {play} (12mo)")


# ── 36-month (3-year) rolling ──
print("\n" + "=" * 100)
print("36-MONTH (3-YEAR) E[R] (active trades only)")
print("=" * 100)
min_day_36 = max_day - pd.Timedelta(days=36 * 30)
recent_36 = df[df["trading_day"] >= min_day_36]
print(f"\nLast 36 months: {recent_36['trading_day'].min().date()} to {recent_36['trading_day'].max().date()}")
for play in [1, 2, 3]:
    stats(recent_36[recent_36["play"] == play], f"Play {play} (36mo)")


# ── Pre-2024 vs post-2024 split ──
print("\n" + "=" * 100)
print("REGIME SPLIT: pre-2024 vs 2024+")
print("=" * 100)
pre = df[df["trading_day"] < "2024-01-01"]
post = df[df["trading_day"] >= "2024-01-01"]
print(f"\npre-2024: {pre['trading_day'].min().date()} to {pre['trading_day'].max().date()}  ({len(pre)} rows)")
print(f"post-2024: {post['trading_day'].min().date()} to {post['trading_day'].max().date()}  ({len(post)} rows)")
for play in [1, 2, 3]:
    print(f"\nPlay {play}:")
    stats(pre[pre["play"] == play], "pre-2024")
    stats(post[post["play"] == play], "post-2024")


# ── Per (play, target_lvl) for the 12-month window ──
print("\n" + "=" * 100)
print("12-MONTH: PER (play, target_lvl) — the granular truth")
print("=" * 100)
for play in [1, 2, 3]:
    for lvl in sorted(recent["target_lvl"].unique()):
        g = recent[(recent["play"] == play) & (recent["target_lvl"] == lvl)]
        stats(g, f"Play {play} target={lvl}")


# ── Summary: which (play, target_lvl) combos are CONSISTENTLY positive? ──
print("\n" + "=" * 100)
print("CONSISTENCY CHECK: which (play, target_lvl) cells are positive in BOTH 12mo AND 36mo?")
print("=" * 100)
for play in [1, 2, 3]:
    for lvl in sorted(df["target_lvl"].unique()):
        g_12 = recent_36[(recent_36["play"] == play) & (recent_36["target_lvl"] == lvl) & (recent_36["trading_day"] >= min_day)]
        g_36 = recent_36[(recent_36["play"] == play) & (recent_36["target_lvl"] == lvl)]
        a_12 = g_12[g_12["result"] != 0]
        a_36 = g_36[g_36["result"] != 0]
        if len(a_12) < 10 or len(a_36) < 10:
            continue
        e_12 = a_12["realized_r"].mean()
        e_36 = a_36["realized_r"].mean()
        both = "BOTH POSITIVE" if (e_12 > 0 and e_36 > 0) else ("12mo only" if e_12 > 0 else ("36mo only" if e_36 > 0 else "BOTH NEG"))
        print(f"  Play {play} target={lvl:>4}: 12mo E[R]={e_12:>+.4f}  36mo E[R]={e_36:>+.4f}  -> {both}")