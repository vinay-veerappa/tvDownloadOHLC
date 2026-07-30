#!/usr/bin/env python
"""
Regime kill-switch — ex-ante feature analysis.

Goal: find a market-regime feature (computable BEFORE the session) whose threshold
cleanly separates H1 (2025-01..2026-03, PF 3.19) from H2 (2026-04..07, PF 0.35)
trade days, so we can gate H2 out while keeping H1.

Ex-ante features (NO look-ahead — use data available BEFORE session D opens):
  F1  daily SMA20 trend   : close[D-1] vs SMA20[D-1]  (price > SMA = uptrend)
  F2  SMA20 slope         : (SMA20[D-1] - SMA20[D-2]) / SMA20[D-2]
  F3  ADX(14)            : classic trend strength on daily bars (through D-1)
  F4  IB-range ratio     : IB_range[D] / median(IB_range, D-20..D-1)  [vol expansion]
  F5  realized vol       : ATR(14 daily)/close[D-1]  (normalized)
  F6  daily range pct    : (high[D-1]-low[D-1])/close[D-1]
  F7  prior-day FT       : +1 if D-1 closed in direction of its session open-range break,
                            -1 if reversed, 0 if no break. Follow-through vs reversal.
  F8  prior-day body/rng : |close[D-1]-open[D-1]| / (high[D-1]-low[D-1])  conviction

Pipeline:
  1. Load NQ1_1m.parquet (covers 2025-01..2026-07).
  2. Build ET-localized 1-min bars, resample to daily (RTH session 09:30-16:00 ET).
  3. Compute F1-F3, F5-F8 on daily series (all use data through D-1).
  4. Compute IB range (09:30-10:00 ET) per day; rolling 20-day median -> F4.
  5. Load FVG-filtered backtest (65 trades) -> per-trade-day outcome (WIN/LOSS).
  6. Univariate separation: for each feature, compute point-biserial corr with win,
     and the threshold (median split) that best separates H1 vs H2 win-rate.
  7. Report AUC (Mann-Whitney) for each feature; pick the best.
"""
import json, os, sys, datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HIST_1M = os.path.join(HERE, "..", "data", "NQ1_1m.parquet")
TRADES_JSON = os.path.join(HERE, "nt8_ib_retest_fvg_sep26_full.json")
REPORT_OUT = os.path.join(HERE, "regime_feature_report.json")

ET = "America/New_York"
RTH_OPEN = datetime.time(9, 30)
RTH_CLOSE = datetime.time(16, 0)
IB_END = datetime.time(10, 0)  # IB window 09:30-10:00 (30 min)


def load_minute():
    df = pd.read_parquet(HIST_1M)
    # historical index is naive datetime — localize to ET (per ADR-001 charts use UTC,
    # but historical NQ1_1m index is already ET-naive per prior sessions)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
    df = df[~df.index.isna()]
    df = df.sort_index()
    # restrict to 2025-01 onward (H1 starts here)
    df = df.loc["2024-12-01":]  # keep Dec 2024 for prior-day warmup
    return df[["open", "high", "low", "close", "volume"]].copy()


def daily_rth(df_1m):
    """Resample 1-min to daily RTH bars (09:30-16:00 ET)."""
    # filter to RTH hours
    rth = df_1m.between_time("09:30", "15:59")
    daily = rth.resample("1B").agg({"open": "first", "high": "max", "low": "min",
                                     "close": "last", "volume": "sum"}).dropna()
    return daily


def ib_ranges(df_1m):
    """Compute 09:30-10:00 ET IB range (high-low) per day."""
    ib = df_1m.between_time("09:30", "09:59")
    # group by date
    ib_daily = ib.groupby(ib.index.date).agg({"high": "max", "low": "min"})
    ib_daily["ib_range"] = ib_daily["high"] - ib_daily["low"]
    return ib_daily[["ib_range"]]


def adx(daily, period=14):
    """Compute ADX (Wilder) on daily bars. Returns Series aligned to daily index."""
    high, low, close = daily["high"], daily["low"], daily["close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    cond = plus_dm > minus_dm
    plus_dm = np.where(cond, plus_dm, 0.0)
    minus_dm = np.where(~cond, minus_dm, 0.0)
    tr = pd.concat([high - low, (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=daily.index).ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=daily.index).ewm(alpha=1/period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx_val


def prior_day_ft(daily):
    """Prior-day follow-through: did D-1 close continue its open-drive direction?

    open-drive direction = sign(close_first_30m - open_0930) on D-1.
    FT = +1 if D-1 close continued open-drive, -1 if reversed, 0 if flat.
    We approximate open-drive with sign(close[D-1]-open[D-1]) vs close direction:
    For daily only we use: dir_open = sign(close - open); continuation if |close-open| drives
    the day and close is beyond the day's midpoint in that direction.
    Simpler: FT = sign(close-open) * sign(close - (high+low)/2). +1 follow-through.
    """
    body = daily["close"] - daily["open"]
    mid = (daily["high"] + daily["low"]) / 2
    ft = np.sign(body) * np.sign(daily["close"] - mid)
    return ft


def build_features(df_1m):
    daily = daily_rth(df_1m)
    # SMA20
    sma20 = daily["close"].rolling(20).mean()
    sma20_prev = sma20.shift(1)
    sma20_prev2 = sma20.shift(2)
    close_prev = daily["close"].shift(1)

    feats = pd.DataFrame(index=daily.index)
    # F1 price vs SMA20 (through D-1)
    feats["f1_price_vs_sma20"] = (close_prev - sma20_prev) / sma20_prev
    # F2 SMA20 slope
    feats["f2_sma20_slope"] = (sma20_prev - sma20_prev2) / sma20_prev2
    # F3 ADX (through D-1)
    adx_series = adx(daily).shift(1)
    feats["f3_adx14"] = adx_series
    # F5 realized vol (ATR14/close) through D-1
    atr14 = (pd.concat([daily["high"] - daily["low"],
                        (daily["high"] - daily["close"].shift()).abs(),
                        (daily["low"] - daily["close"].shift()).abs()], axis=1)
             .max(axis=1)).rolling(14).mean().shift(1)
    feats["f5_rv"] = atr14 / close_prev
    # F6 prior-day range pct
    feats["f6_prior_range_pct"] = (daily["high"] - daily["low"]).shift(1) / close_prev
    # F7 prior-day FT
    feats["f7_prior_ft"] = prior_day_ft(daily).shift(1)
    # F8 prior-day body/range
    rng1 = (daily["high"] - daily["low"]).shift(1).replace(0, np.nan)
    feats["f8_prior_body_rng"] = (daily["close"] - daily["open"]).abs().shift(1) / rng1

    # F4 IB range ratio (today's IB / median prior 20 IB ranges)
    ib = ib_ranges(df_1m)
    ib_aligned = ib.reindex(daily.index.date).set_axis(daily.index)
    ib_median20 = ib_aligned["ib_range"].rolling(20).median().shift(1)
    feats["f4_ib_range_ratio"] = ib_aligned["ib_range"] / ib_median20

    return feats, daily


def load_trades():
    with open(TRADES_JSON, encoding="utf-8-sig") as f:
        d = json.load(f)
    ts = d["trades"]
    rows = []
    for t in ts:
        et = pd.to_datetime(t["entryTime"]).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
        rows.append({"date": et.date(), "entry_dt": et,
                     "win": 1 if float(t["profitCurrency"]) > 0 else 0,
                     "pnl": float(t["profitCurrency"]),
                     "side": t["marketPosition"]})
    return pd.DataFrame(rows)


def auc_score(y, x):
    """Mann-Whitney U / AUC for binary y vs continuous x."""
    y = np.asarray(y); x = np.asarray(x)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(np.unique(y)) < 2 or len(x) < 4:
        return np.nan
    pos = x[y == 1]; neg = x[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    # rank-based AUC
    ranks = pd.Series(x).rank().values
    n_pos, n_neg = len(pos), len(neg)
    sum_pos = ranks[y == 1].sum()
    u = sum_pos - n_pos * (n_pos + 1) / 2
    return u / (n_pos * n_neg)


def main():
    print("Loading 1-min NQ historical...")
    df_1m = load_minute()
    print(f"  {len(df_1m)} bars, {df_1m.index.min()} -> {df_1m.index.max()}")

    print("Building ex-ante regime features...")
    feats, daily = build_features(df_1m)
    print(f"  {len(feats)} feature-days")

    print("Loading FVG-filtered trades...")
    trades = load_trades()
    print(f"  {len(trades)} trades")

    # join features by trade date (features indexed by daily date)
    feats["trade_date"] = feats.index.date
    feats_by_date = feats.set_index(feats.index.date)
    merged = trades.set_index("date").join(feats_by_date, how="left")

    # H1/H2 split
    h1_mask = np.array([d < datetime.date(2026, 4, 1) for d in merged.index])
    h2_mask = ~h1_mask
    print(f"\nH1: {h1_mask.sum()} trades, WR {merged.loc[h1_mask,'win'].mean()*100:.1f}%")
    print(f"H2: {h2_mask.sum()} trades, WR {merged.loc[h2_mask,'win'].mean()*100:.1f}%")

    feature_cols = [c for c in feats.columns if c.startswith("f")]
    print("\n=== Univariate separation (point-biserial corr with WIN, AUC) ===")
    report = {"h1": {"n": int(h1_mask.sum()), "wr": float(merged.loc[h1_mask, "win"].mean())},
              "h2": {"n": int(h2_mask.sum()), "wr": float(merged.loc[h2_mask, "win"].mean())},
              "features": {}}

    for f in feature_cols:
        x = merged[f].values
        y = merged["win"].values
        mask = ~np.isnan(x)
        if mask.sum() < 10:
            continue
        # correlation
        corr = np.corrcoef(x[mask], y[mask])[0, 1] if mask.sum() > 4 else np.nan
        auc = auc_score(y, x)
        # H1 vs H2 feature means
        h1_mean = float(np.nanmean(x[h1_mask & mask]))
        h2_mean = float(np.nanmean(x[h2_mask & mask]))
        # threshold sweep: for each candidate threshold t, compute WR above/below
        lo, hi = np.nanpercentile(x, 10), np.nanpercentile(x, 90)
        best = None
        for t in np.linspace(lo, hi, 41):
            above = y[mask & (x >= t)]
            below = y[mask & (x < t)]
            if len(above) < 5 or len(below) < 5:
                continue
            # want: below = "trade" (keep), above = "skip" -> maximize below WR * count retention
            wr_below = below.mean() if len(below) else 0
            wr_above = above.mean() if len(above) else 0
            # separation score: WR(kept) - WR(skipped), weighted by kept count
            kept_frac = len(below) / mask.sum()
            sep = wr_below - wr_above
            if best is None or sep > best["sep"]:
                best = {"threshold": float(t), "wr_kept": float(wr_below),
                        "wr_skipped": float(wr_above), "n_kept": int(len(below)),
                        "n_skipped": int(len(above)), "sep": float(sep),
                        "kept_frac": float(kept_frac)}
        report["features"][f] = {"corr_win": float(corr) if not np.isnan(corr) else None,
                                  "auc": float(auc) if not np.isnan(auc) else None,
                                  "h1_mean": h1_mean, "h2_mean": h2_mean,
                                  "best_split": best}
        print(f"  {f:20s} corr={corr:+.3f}  AUC={auc:.3f}  H1={h1_mean:+.3f}  H2={h2_mean:+.3f}"
              + (f"  best@{best['threshold']:+.3f}: keepWR={best['wr_kept']:.2f}({best['n_kept']}) skipWR={best['wr_skipped']:.2f}({best['n_skipped']})" if best else "  no split"))

    # H1-only retention check for best feature per feature
    print("\n=== H1-retention at best H2-gating threshold ===")
    for f in feature_cols:
        info = report["features"].get(f)
        if not info or info.get("best_split") is None:
            continue
        t = info["best_split"]["threshold"]
        x = merged[f].values
        y = merged["win"].values
        # apply as a SKIP gate: skip trades where feature >= t (if H2 mean > H1 mean) or <= t
        h2_mean = info["h2_mean"]; h1_mean = info["h1_mean"]
        skip_above = h2_mean > h1_mean
        if skip_above:
            kept = y[(~np.isnan(x)) & (x < t)]
            skipped_h1 = y[h1_mask & (~np.isnan(x)) & (x >= t)]
        else:
            kept = y[(~np.isnan(x)) & (x >= t)]
            skipped_h1 = y[h1_mask & (~np.isnan(x)) & (x < t)]
        h1_kept = y[h1_mask & (~np.isnan(x)) & (x < t if skip_above else x >= t)]
        info["h1_retention"] = {"wr_kept": float(h1_kept.mean()) if len(h1_kept) else None,
                                "n_kept": int(len(h1_kept)),
                                "n_h1_skipped": int(len(skipped_h1))}
        print(f"  {f:20s} H1 kept WR={info['h1_retention']['wr_kept']} n={info['h1_retention']['n_kept']} (skipped {info['h1_retention']['n_h1_skipped']} H1)")

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport -> {REPORT_OUT}")


if __name__ == "__main__":
    main()