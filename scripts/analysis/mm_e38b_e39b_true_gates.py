"""E38b/E39b — HA & 30m %B gates applied to the TRUE E34L trade set (post-hoc,
causal: gate state at entry timestamp is knowable at entry).

Fixes the E38/E39 script's broken baseline (simplified BB-touch core reproduced
50 trades PF 0.44 instead of true E34L 298 PF 1.38 — those arms are void).

Usage: .\\.venv\\Scripts\\python.exe scripts/analysis/mm_e38b_e39b_true_gates.py
"""
import sys
import warnings

sys.path.insert(0, "C:/Users/vinay/tvDownloadOHLC")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from scripts.analysis.bb_e16_e21_queue import load_nt
from scripts.analysis.mm_e34_battery import run_arm, MMConfig, summarize


def main():
    df1, df5 = load_nt("ES")
    base = run_arm("ES", MMConfig("E34L", "long-only", dir_filter="LONG"),
                   {"ES": df1}, {"ES": df5})
    s = summarize(base)
    print(f"E34L true baseline: {len(base)} trades  WR{s['wr']}  PF{s['pf']}  Net${s['net']}  DD${s['dd']}")

    # --- Heiken Ashi state (recursive EMA-of-trend; prior-bar causal per bar) ---
    ha_c = (df5["open"] + df5["high"] + df5["low"] + df5["close"]) / 4
    ha_o = np.zeros(len(df5))
    ha_o[0] = (df5["open"].iloc[0] + df5["close"].iloc[0]) / 2
    cvals = ha_c.values
    for i in range(1, len(df5)):
        ha_o[i] = (ha_o[i - 1] + cvals[i - 1]) / 2
    ha_bull = pd.Series(cvals > ha_o, index=df5.index)
    ha_bull_lb = ha_bull.rolling(2).max().fillna(0).astype(bool)

    # --- 30m %B (completed HTF bars only: shift(1) then ffill onto 5m) ---
    ohlc = df5.resample("30min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    mid = ohlc["close"].rolling(20).mean()
    sd = ohlc["close"].rolling(20).std(ddof=1).clip(lower=1e-12)
    pb = (ohlc["close"] - (mid - 2 * sd)) / ((mid + 2 * sd) - (mid - 2 * sd)).replace(0, np.nan)
    htf_pb = pb.shift(1).reindex(df5.index, method="ffill")

    b = base.copy()
    b["ha_ok"] = [bool(ha_bull_lb.get(t, False)) for t in b["entry_time"]]
    b["pb30"] = [float(htf_pb.get(t, np.nan)) for t in b["entry_time"]]

    def show(tag, sub):
        s2 = summarize(sub) if len(sub) else dict(trades=0, wr=0, pf=0, net=0, dd=0)
        print(f"  {tag:<40} {s2['trades']:>4} tr  WR{s2['wr']:>5.1f}%  PF{s2['pf']:>5.2f}  "
              f"Net${s2['net']:>6.0f}  DD${s2['dd']:>5.0f}")
        return s2

    print("\n=== E38b: HA gate on TRUE E34L ===")
    show("HA0  no gate (E34L all)", b)
    show("HA1  HA bullish at entry", b[b["ha_ok"]])

    print("\n=== E39b: 30m %B buckets at entry (zero-lookahead) ===")
    for lo, hi_q, tag in [(0.0, 0.25, "D1  0.00-0.25"), (0.25, 0.5, "D2  0.25-0.50"),
                          (0.5, 0.75, "D3  0.50-0.75"), (0.75, 1.01, "D4  0.75-1.00+")]:
        sub = b[(b["pb30"] >= lo) & (b["pb30"] < hi_q)]
        show(tag, sub)
    show("M2  30m%B <= 0.9 only (anti-stretch)", b[b["pb30"] <= 0.9])
    show("M1  30m%B > 0.5 ('bull context')", b[b["pb30"] > 0.5])

    out = "data/derived/mm_e38b_e39b_true_e34l_gates.csv"
    b.to_csv(out, index=False)
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()