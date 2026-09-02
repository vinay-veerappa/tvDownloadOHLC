"""
Verify MTF 5m+1m execution through the Unified Trading Framework
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.trading_framework.core.nt8_parity_backtester import NT8ParityBacktester


def main():
    print("Loading 1m and 5m data...")
    df_1m = pd.read_parquet(_root / "data/NQ1_1m.parquet")
    df_1m = df_1m[df_1m.index >= "2024-01-01"].copy()
    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize("UTC").tz_convert("America/New_York")
    else:
        df_1m.index = df_1m.index.tz_convert("America/New_York")

    df_5m = df_1m.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    # Signals on 5m
    c = df_5m["close"].to_numpy()
    o = df_5m["open"].to_numpy()
    h = df_5m["high"].to_numpy()
    l = df_5m["low"].to_numpy()
    n = len(df_5m)

    df_4h = df_5m.resample("4h").agg({"close": "last"}).dropna()
    df_4h["ema20"] = df_4h["close"].ewm(span=20).mean()
    df_4h_reindexed = df_4h.reindex(df_5m.index, method="ffill")
    htf_bias = np.where(df_4h_reindexed["close"] > df_4h_reindexed["ema20"], 1, -1)

    signals = np.zeros(n, dtype=np.int32)
    vibes = 0
    bagholder = np.nan
    pain = np.nan

    def consult_cb(bias, idx):
        max_lb = min(15, idx)
        ext_o = o[idx - 1]
        for k in range(1, max_lb + 1):
            is_opp = (c[idx - k] < o[idx - k]) if bias == 1 else (c[idx - k] > o[idx - k])
            if is_opp:
                ext_o = o[idx - k]
                break
        return ext_o

    for i in range(50, n):
        c0, o0, h0, l0 = c[i], o[i], h[i], l[i]
        pers = 1 if c0 > o0 else (-1 if c0 < o0 else 0)
        if vibes == 0:
            vibes = pers if pers != 0 else 1
            bagholder = consult_cb(vibes, i)
            pain = h0 if vibes == 1 else l0

        if vibes == 1 and h0 > pain:
            pain = h0
            bagholder = consult_cb(1, i)
        elif vibes == -1 and l0 < pain:
            pain = l0
            bagholder = consult_cb(-1, i)

        if vibes == -1 and c0 > bagholder and htf_bias[i] == 1:
            vibes = 1
            pain = h0
            bagholder = consult_cb(1, i)
            signals[i] = 1
        elif vibes == 1 and c0 < bagholder and htf_bias[i] == -1:
            vibes = -1
            pain = l0
            bagholder = consult_cb(-1, i)
            signals[i] = -1

    sig_series = pd.Series(signals, index=df_5m.index)

    backtester = NT8ParityBacktester(account_size=50000.0, contracts=2)
    res = backtester.run(
        signals=sig_series,
        data=df_5m,
        risk_params={
            "ticker": "NQ1",
            "data_1m": df_1m,
            "stop_loss_bps": 2.5,
            "queen_bps": 10.0,
            "runner_bps": 30.0,
        }
    )

    print(f"\n========================================================")
    print(f"UNIFIED FRAMEWORK MTF 5m+1m EXECUTION RESULTS (2024-2026)")
    print(f"========================================================")
    print(f"Total Trades:       {res['total_trades']}")
    print(f"Win Rate:           {res['win_rate_%']:.1f}%")
    print(f"Profit Factor:      {res['profit_factor']:.2f}")
    print(f"Net Profit:         ${res['net_profit']:,.2f}")
    print(f"Max Drawdown:       ${res['max_drawdown']:,.2f}")
    print(f"========================================================")


if __name__ == "__main__":
    main()
