#!/usr/bin/env python
"""Forensic trade-level analysis for IBRetestBot Play 2 H2 collapse.
Confirms/refutes counter-trend-break hypothesis (mechanism a) with actual numbers.
Reads scratch/nt8_ib_retest_fvg_sep26_full.json + data/NQ1_1m.parquet.
Writes scratch/forensic_retest_report.json + prints tables.
"""
import json, os, datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ET = "America/New_York"
TRADES = os.path.join(HERE, "nt8_ib_retest_fvg_sep26_full.json")
PARQUET = os.path.join(HERE, "..", "data", "NQ1_1m.parquet")
OUT = os.path.join(HERE, "forensic_retest_report.json")


def load_1m():
    df = pd.read_parquet(PARQUET)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
    df = df[~df.index.isna()].sort_index()
    return df[["open", "high", "low", "close"]].copy()


def load_trades():
    d = json.load(open(TRADES, encoding="utf-8-sig"))
    rows = []
    for t in d["trades"]:
        et = pd.to_datetime(t["entryTime"]).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
        xt = pd.to_datetime(t["exitTime"]).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
        rows.append(dict(date=et.date(), entry_dt=et, exit_dt=xt,
                         side=t["marketPosition"], entry=float(t["entryPrice"]),
                         exit=float(t["exitPrice"]), pnl=float(t["profitCurrency"]),
                         pts=float(t["profitPoints"]), exit_name=t["exitName"],
                         win=int(float(t["profitCurrency"]) > 0)))
    return pd.DataFrame(rows)


def daily_trend_prior(df_1m, sma_period=20):
    """trend_dir[D] = sign(close[D-1] - SMA20[D-1]) — prior-day trend entering D's session."""
    rth = df_1m.between_time("09:30", "15:59")
    daily = rth.resample("1B").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    sma20 = daily["close"].rolling(sma_period).mean()
    trend = np.sign(daily["close"] - sma20)
    trend_prior = trend.shift(1)  # trend entering today = yesterday's trend
    return trend_prior


def analyze():
    df = load_1m()
    tr = load_trades()
    trend_prior = daily_trend_prior(df)
    rows = []
    for _, t in tr.iterrows():
        d = t["date"]
        day_mask = df.index.date == d
        ib_mask = day_mask & (df.index.time >= datetime.time(9, 30)) & (df.index.time <= datetime.time(9, 59))
        ib = df[ib_mask]
        if len(ib) == 0:
            continue
        ib_high, ib_low = ib["high"].max(), ib["low"].min()
        ib_mid = (ib_high + ib_low) / 2
        ib_range = ib_high - ib_low
        seg = df.loc[t["entry_dt"]:t["exit_dt"]]
        if len(seg) == 0:
            continue
        side = t["side"]
        # MAE/MFE in points (entry at mid)
        if side == "Long":
            mae = t["entry"] - seg["low"].min()
            mfe = seg["high"].max() - t["entry"]
            stop_level = ib_low
            target_level = ib_high + 0.5 * ib_range
        else:
            mae = seg["high"].max() - t["entry"]
            mfe = t["entry"] - seg["low"].min()
            stop_level = ib_high
            target_level = ib_low - 0.5 * ib_range
        # retest depth (max excursion past mid before entry, in break dir)
        pre = df.loc[ib.index[-1]:t["entry_dt"]].iloc[1:-1]
        if side == "Long":
            depth = (pre["high"].max() - ib_mid) if len(pre) else 0
        else:
            depth = (ib_mid - pre["low"].min()) if len(pre) else 0
        depth_ratio = depth / ib_range if ib_range > 0 else 0
        entry_min = t["entry_dt"].hour * 60 + t["entry_dt"].minute - 9 * 60
        trend_dir = trend_prior.get(d, 0)
        if np.isnan(trend_dir):
            trend_dir = 0
        trend_dir = int(trend_dir)
        counter = (side == "Long" and trend_dir < 0) or (side == "Short" and trend_dir > 0)
        if side == "Long":
            reversal = seg["low"].min() <= ib_low
        else:
            reversal = seg["high"].max() >= ib_high
        target_dist = abs(target_level - t["entry"])
        achieved = mfe / target_dist if target_dist > 0 else 0
        h1 = d < datetime.date(2026, 4, 1)
        stop_dist = abs(t["entry"] - stop_level)
        rows.append(dict(date=str(d), h1=h1, side=side, win=t["win"], pnl=t["pnl"],
                         ib_range=round(ib_range, 1), entry=round(t["entry"], 1),
                         entry_min=entry_min, counter=counter, trend_dir=trend_dir,
                         depth_ratio=round(depth_ratio, 3), mae=round(mae, 1), mfe=round(mfe, 1),
                         stop_dist=round(stop_dist, 1), target_dist=round(target_dist, 1),
                         achieved=round(achieved, 2), reversal=reversal,
                         exit_name=t["exit_name"]))
    out = pd.DataFrame(rows)

    def summ(g, label):
        if len(g) == 0:
            return dict(label=label, n=0)
        return dict(label=label, n=len(g), wr=round(float(g["win"].mean()), 3),
                    median_ib=round(float(g["ib_range"].median()), 1),
                    median_mae=round(float(g.loc[g.win == 0, "mae"].median()), 1) if (g.win == 0).any() else None,
                    median_mfe=round(float(g["mfe"].median()), 1),
                    counter_frac=round(float(g["counter"].mean()), 3),
                    reversal_frac=round(float(g["reversal"].mean()), 3),
                    median_depth=round(float(g["depth_ratio"].median()), 3),
                    median_entry_min=round(float(g["entry_min"].median()), 1),
                    median_achieved=round(float(g["achieved"].median()), 3))
    rep = dict(
        h1=summ(out[out.h1], "H1"),
        h2=summ(out[~out.h1], "H2"),
        h1_loss=summ(out[out.h1 & (out.win == 0)], "H1-loss"),
        h2_loss=summ(out[~out.h1 & (out.win == 0)], "H2-loss"),
        h2_win=summ(out[~out.h1 & (out.win == 1)], "H2-win"),
        h1_win=summ(out[out.h1 & (out.win == 1)], "H1-win"),
        trades=out.to_dict("records"),
    )
    json.dump(rep, open(OUT, "w"), indent=2, default=str)

    print("=== Per-group medians ===")
    for k in ["h1", "h2", "h1_win", "h1_loss", "h2_win", "h2_loss"]:
        print(f"  {rep[k]['label']:10s} n={rep[k]['n']:3d} WR={rep[k]['wr']} ib={rep[k]['median_ib']} "
              f"counter={rep[k]['counter_frac']} reversal={rep[k]['reversal_frac']} depth={rep[k]['median_depth']} "
              f"mae={rep[k]['median_mae']} mfe={rep[k]['median_mfe']} achieved={rep[k]['median_achieved']} entry_min={rep[k]['median_entry_min']}")

    print("\n=== Counter-trend contingency (THE KEY TEST) ===")
    for h, lab in [(out.h1, "H1"), (~out.h1, "H2")]:
        g = out[h]
        ct = g[g.counter]; wt = g[~g.counter]
        wr_wt = round(float(wt.win.mean()), 3) if len(wt) else "n/a"
        wr_ct = round(float(ct.win.mean()), 3) if len(ct) else "n/a"
        print(f"  {lab}: with-trend n={len(wt):3d} WR={wr_wt} | counter-trend n={len(ct):3d} WR={wr_ct}")

    print("\n=== Counter-trend filter SIMULATION (skip counter-trend) ===")
    kept = out[~out.counter]
    k_h1 = kept[kept.h1]; k_h2 = kept[~kept.h1]
    all_h1 = out[out.h1]; all_h2 = out[~out.h1]
    print(f"  H1: keep {len(k_h1)}/{len(all_h1)}  WR={round(float(k_h1.win.mean()),3) if len(k_h1) else 'n/a'}  "
          f"net=${int(k_h1.pnl.sum()) if len(k_h1) else 0}")
    print(f"  H2: keep {len(k_h2)}/{len(all_h2)}  WR={round(float(k_h2.win.mean()),3) if len(k_h2) else 'n/a'}  "
          f"net=${int(k_h2.pnl.sum()) if len(k_h2) else 0}")
    print(f"  TOTAL kept: {len(kept)} trades WR={round(float(kept.win.mean()),3)} net=${int(kept.pnl.sum())}")

    print("\n=== IB-range floor sweep (skip ib_range < x pts) ===")
    for x in [80, 100, 120, 140, 160, 200]:
        k = out[out.ib_range >= x]
        if len(k) == 0:
            continue
        k_h1 = k[k.h1]; k_h2 = k[~k.h1]
        wr1 = round(float(k_h1.win.mean()), 3) if len(k_h1) else "n/a"
        wr2 = round(float(k_h2.win.mean()), 3) if len(k_h2) else "n/a"
        print(f"  floor {x}: H1 {len(k_h1)}/{len(all_h1)} WR={wr1} | H2 {len(k_h2)}/{len(all_h2)} WR={wr2}")

    print("\n=== Retest-depth gate (skip depth_ratio > x) ===")
    for x in [0.3, 0.5, 0.75, 1.0]:
        k = out[out.depth_ratio <= x]
        k_h1 = k[k.h1]; k_h2 = k[~k.h1]
        wr1 = round(float(k_h1.win.mean()), 3) if len(k_h1) else "n/a"
        wr2 = round(float(k_h2.win.mean()), 3) if len(k_h2) else "n/a"
        print(f"  depth<={x}: H1 {len(k_h1)}/{len(all_h1)} WR={wr1} | H2 {len(k_h2)}/{len(all_h2)} WR={wr2}")

    print(f"\nReport -> {OUT}")


if __name__ == "__main__":
    analyze()