"""Investigate variant signal quality and MAE/MFE analysis."""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import numpy as np
import pandas as pd
from scripts.libs_py.data.loader import DataLoader
from scripts.trading_framework.config.config_loader import load_config
from scripts.strategies.ifvg_cisd.core.ifvg_cisd_strategy import IFVGCISDStrategy

config = load_config("scripts/trading_framework/config/sessions.yaml")
loader = DataLoader(config)
df = loader.load_enriched("NQ1")
df = df[(df.index >= "2025-06-01") & (df.index < "2026-04-01")].copy()
print(f"Loaded {len(df):,d} bars")
s = IFVGCISDStrategy(ticker="NQ1")

for v in ["baseline", "variant1", "variant2"]:
    params = {"resample_tf": "5min", "filter_lunch": True, "max_trades_per_day": 2,
             "r_mult_tp1": 1.0, "r_mult_tp2": 2.5, "atr_risk_mult": 1.8, "variant": v}
    if v == "baseline":
        params["strict_ifvg_only"] = True
    sig = s.hunt(df, params)
    print(f"\n{'='*90}")
    print(f"{v}: {len(sig)} signals")
    if len(sig) == 0:
        continue

    longs = sig[sig.direction == "LONG"]
    shorts = sig[sig.direction == "SHORT"]
    print(f"  LONG: {len(longs)}, SHORT: {len(shorts)}")
    print(f"  Risk: min={sig.risk_pts.min():.1f} max={sig.risk_pts.max():.1f} mean={sig.risk_pts.mean():.1f}")
    clamped = len(sig[sig.risk_pts == 50.0])
    print(f"  Risk clamped to 50: {clamped}/{len(sig)} = {clamped/len(sig)*100:.0f}%")
    print(f"  Risk < 20 (tight): {len(sig[sig.risk_pts < 20])}/{len(sig)} = {len(sig[sig.risk_pts < 20])/len(sig)*100:.0f}%")

    # MAE/MFE analysis: for each signal, look forward N bars on 1m
    # and compute the max adverse excursion (how far price went against us)
    # and max favorable excursion (how far price went in our favor)
    mae_list = []
    mfe_list = []
    tp1_reach = []  # how often price reaches 1R
    tp2_reach = []  # how often price reaches 2.5R

    for _, row in sig.iterrows():
        entry_time = row.signal_time
        entry_price = row.entry_price
        stop_price = row.stop_price
        risk = row.risk_pts
        direction = row.direction

        # Find the entry bar on 1m timeline
        mask = df.index >= entry_time
        if mask.sum() == 0:
            continue
        future = df[mask].head(240)  # 4 hours on 1m
        if len(future) < 5:
            continue

        if direction == "LONG":
            mae = (future["low"].min() - entry_price)  # negative = adverse
            mfe = (future["high"].max() - entry_price)  # positive = favorable
            tp1_hit = any(future["high"] >= entry_price + risk)
            tp2_hit = any(future["high"] >= entry_price + risk * 2.5)
            stop_hit = any(future["low"] <= stop_price)
        else:
            mae = (entry_price - future["high"].max())  # negative = adverse
            mfe = (entry_price - future["low"].min())  # positive = favorable
            tp1_hit = any(future["low"] <= entry_price - risk)
            tp2_hit = any(future["low"] <= entry_price - risk * 2.5)
            stop_hit = any(future["high"] >= stop_price)

        mae_list.append(mae)
        mfe_list.append(mfe)
        tp1_reach.append(int(tp1_hit))
        tp2_reach.append(int(tp2_hit))

    mae_arr = np.array(mae_list)
    mfe_arr = np.array(mfe_list)
    tp1_arr = np.array(tp1_reach)
    tp2_arr = np.array(tp2_reach)

    print(f"\n  MAE (Max Adverse Excursion in points, 240 bars forward):")
    print(f"    Mean: {mae_arr.mean():.1f}, Median: {np.median(mae_arr):.1f}")
    print(f"    25th pct: {np.percentile(mae_arr, 25):.1f}, 75th pct: {np.percentile(mae_arr, 75):.1f}")
    print(f"    MAE > -risk (would hit stop): {(mae_arr < -np.array(sig.risk_pts)).sum()}/{len(mae_arr)}")

    print(f"\n  MFE (Max Favorable Excursion in points, 240 bars forward):")
    print(f"    Mean: {mfe_arr.mean():.1f}, Median: {np.median(mfe_arr):.1f}")
    print(f"    25th pct: {np.percentile(mfe_arr, 25):.1f}, 75th pct: {np.percentile(mfe_arr, 75):.1f}")

    print(f"\n  Target reach rates:")
    print(f"    TP1 (1.0R): {tp1_arr.sum()}/{len(tp1_arr)} = {tp1_arr.mean()*100:.1f}%")
    print(f"    TP2 (2.5R): {tp2_arr.sum()}/{len(tp2_arr)} = {tp2_arr.mean()*100:.1f}%")

    # Optimal stop analysis: what stop distance captures 80% of winners
    # without being stopped out?
    print(f"\n  Optimal stop analysis:")
    for stop_r in [0.5, 1.0, 1.5, 2.0]:
        would_stop = (mae_arr < -stop_r * np.array(sig.risk_pts)).sum()
        print(f"    Stop at {stop_r}R: {would_stop}/{len(mae_arr)} stopped = {would_stop/len(mae_arr)*100:.0f}%")

    # Show first 5 signals
    print(f"\n  First 5 signals:")
    for _, r in sig.head(5).iterrows():
        print(f"    {r.signal_time}  {r.direction:<5} entry={r.entry_price:.2f} stop={r.stop_price:.2f} risk={r.risk_pts:.1f}")

print(f"\n{'='*90}")
print("DIAGNOSIS")
print(f"{'='*90}")