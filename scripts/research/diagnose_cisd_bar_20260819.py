"""
Diagnose the CISD/FVG/entry state bar-by-bar for NQ on Wed Aug 19 2026.
This reproduces the Pine/C# Variant2 behavior and the Python Variant2 behavior
to see whether the missed CISD was a real divergence or intended 2nd-FVG logic.
"""
from __future__ import annotations

import sys
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.libs_py.cisd import compute_cisd
from scripts.libs_py.fvg import compute_fvg
from scripts.libs_py.ifvg import compute_ifvg
from scripts.libs_py.bpr import compute_bpr
from scripts.libs_py.data.resampler import resample_ohlcv


def main():
    ticker = "NQ"
    live_path = ROOT / "data" / "live" / f"live_storage_-{ticker}.parquet"
    if not live_path.exists():
        print(f"Live storage not found: {live_path}")
        return

    df_1m = pd.read_parquet(live_path)
    if "timestamp" in df_1m.columns:
        df_1m["timestamp"] = pd.to_datetime(df_1m["timestamp"], utc=True)
        df_1m = df_1m.set_index("timestamp")
    elif not isinstance(df_1m.index, pd.DatetimeIndex):
        df_1m.index = pd.to_datetime(df_1m.index, utc=True)
    df_1m.index = df_1m.index.tz_convert("America/New_York").tz_localize(None)

    # Focus on Aug 19 2026 RTH-ish, plus overnight for context
    day = pd.Timestamp("2026-08-19").date()
    df_day = df_1m[df_1m.index.date == day]
    print(f"1m rows for {day}: {len(df_day)}")
    if len(df_day) == 0:
        print("Available dates:", sorted(set(df_1m.index.date))[-5:])
        return

    for tf in ["3min", "5min", "nt8_csv"]:
        print(f"\n{'=' * 80}\nTIMEFRAME: {tf}\n{'=' * 80}")
        if tf == "nt8_csv":
            # Load the C# diagnostic CSV so bar grouping matches NT8 exactly
            csv_dir = Path("C:/Users/vinay/AppData/Local/Temp")
            csv_files = sorted(csv_dir.glob("ictfvgcisd_diag_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not csv_files:
                print("No NT8 diagnostic CSV found in temp dir")
                continue
            df_htf = pd.read_csv(csv_files[0], parse_dates=["Time"]).set_index("Time")
            df_htf = df_htf.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
            df_htf = df_htf[["open", "high", "low", "close"]]
            df_htf = df_htf[df_htf.index.date == day]
            print(f"Using NT8 CSV: {csv_files[0]}")
        else:
            df_htf = resample_ohlcv(df_day, tf)
        cisd = compute_cisd(df_htf)
        fvg = compute_fvg(df_htf, include_vi=True)
        ifvg = compute_ifvg(df_htf, include_vi=True)
        bpr = compute_bpr(df_htf, align_to_base=False)

        print("cisd cols:", list(cisd.columns))
        print("fvg cols:", list(fvg.columns))
        print("ifvg cols:", list(ifvg.columns))
        print("bpr cols:", list(bpr.columns))
        df = pd.concat([df_htf, cisd.add_suffix("_cisd"), fvg.add_suffix("_fvg"), ifvg.add_suffix("_ifvg"), bpr.add_suffix("_bpr")], axis=1)
        df = df.dropna(subset=["open", "high", "low", "close"])
        print("concat cols:", [c for c in df.columns if "event" in c or "state" in c or "fvg" in c or "bpr" in c])

        # Replicate Pine/C# state machine exactly
        current_regime = 0
        armed_bull = False
        armed_bear = False
        armed_bull_level = np.nan
        armed_bear_level = np.nan
        armed_bull_low = np.nan
        armed_bear_high = np.nan
        bull_count = 0
        bear_count = 0
        v2_triggered = False
        leg_origin_low = np.nan
        leg_origin_high = np.nan
        leg_cisd_level = np.nan

        rows = []
        vals = df[["open", "high", "low", "close"]].values
        idxs = df.index
        n = len(df)

        for i in range(2, n):
            ts = idxs[i]
            o, h, l, c = vals[i]
            o1, h1, l1, c1 = vals[i - 1]
            o2, h2, l2, c2 = vals[i - 2]

            is_low_pivot = (l1 < l2) and (l1 < l)
            is_high_pivot = (h1 > h2) and (h1 > h)

            cisd_event = int(df.iloc[i]["cisd_event_cisd"])
            cisd_state = int(df.iloc[i]["cisd_state_cisd"])
            fvg_event = int(df.iloc[i]["fvg_event_fvg"])
            ifvg_event = int(df.iloc[i]["ifvg_event_ifvg"])
            bpr_event = int(df.iloc[i]["bpr_event_bpr"])

            # Arm on low/high pivot (matches Pine/C#)
            if is_low_pivot and current_regime != 1:
                run_open = o1
                run_low = l1
                for k in range(1, min(25, i)):
                    cc = vals[i - k][3]
                    oo = vals[i - k][0]
                    if k == 1 or cc <= oo:
                        run_open = oo
                        run_low = min(run_low, vals[i - k][2])
                    else:
                        break
                armed_bull_level = run_open
                armed_bull_low = run_low
                armed_bull = True
                bull_count = 0  # Pine resets at arming bar

            if is_high_pivot and current_regime != -1:
                run_open = o1
                run_high = h1
                for k in range(1, min(25, i)):
                    cc = vals[i - k][3]
                    oo = vals[i - k][0]
                    if k == 1 or cc >= oo:
                        run_open = oo
                        run_high = max(run_high, vals[i - k][1])
                    else:
                        break
                armed_bear_level = run_open
                armed_bear_high = run_high
                armed_bear = True
                bear_count = 0

            # Count FVGs while armed or in regime
            if armed_bull or current_regime == 1:
                if fvg_event == 1:
                    bull_count += 1
            if armed_bear or current_regime == -1:
                if fvg_event == -1:
                    bear_count += 1

            # Trigger CISD
            bull_cisd_trigger = False
            bear_cisd_trigger = False
            if armed_bull and not np.isnan(armed_bull_level) and c > armed_bull_level:
                armed_bull = False
                bull_cisd_trigger = True
                current_regime = 1
                leg_origin_low = armed_bull_low
                leg_cisd_level = armed_bull_level
                v2_triggered = False

            if armed_bear and not np.isnan(armed_bear_level) and c < armed_bear_level:
                armed_bear = False
                bear_cisd_trigger = True
                current_regime = -1
                leg_origin_high = armed_bear_high
                leg_cisd_level = armed_bear_level
                v2_triggered = False

            # Variant 2 signal
            signal_long = False
            signal_short = False
            if (current_regime == 1 or bull_cisd_trigger) and not v2_triggered and fvg_event == 1 and bull_count >= 2:
                signal_long = True
                v2_triggered = True
            if (current_regime == -1 or bear_cisd_trigger) and not v2_triggered and fvg_event == -1 and bear_count >= 2:
                signal_short = True
                v2_triggered = True

            # Time filters
            t_local = ts.time()
            in_rth = time(9, 45) <= t_local <= time(15, 30)
            in_lunch = time(11, 30) <= t_local <= time(13, 30)

            rows.append({
                "time": ts,
                "o": round(o, 2),
                "h": round(h, 2),
                "l": round(l, 2),
                "c": round(c, 2),
                "low_pivot": is_low_pivot,
                "high_pivot": is_high_pivot,
                "armed_bull": armed_bull,
                "armed_bull_level": round(armed_bull_level, 2) if not np.isnan(armed_bull_level) else None,
                "cisd_event": cisd_event,
                "cisd_state": cisd_state,
                "fvg_event": fvg_event,
                "ifvg_event": ifvg_event,
                "bpr_event": bpr_event,
                "bull_count": bull_count,
                "bear_count": bear_count,
                "bull_trigger": bull_cisd_trigger,
                "signal_long": signal_long,
                "signal_short": signal_short,
                "in_rth": in_rth,
                "in_lunch": in_lunch,
            })
            # Ensure all boolean columns are real bools, not 0/1 ints
            rows[-1]["low_pivot"] = bool(rows[-1]["low_pivot"])
            rows[-1]["high_pivot"] = bool(rows[-1]["high_pivot"])
            rows[-1]["bull_trigger"] = bool(rows[-1]["bull_trigger"])
            rows[-1]["signal_long"] = bool(rows[-1]["signal_long"])
            rows[-1]["signal_short"] = bool(rows[-1]["signal_short"])
            rows[-1]["in_rth"] = bool(rows[-1]["in_rth"])
            rows[-1]["in_lunch"] = bool(rows[-1]["in_lunch"])

        diag = pd.DataFrame(rows)
        print("DEBUG columns:", list(diag.columns))
        # Show only interesting bars: pivots, CISD triggers, FVGs, signals
        interesting = diag[
            diag["low_pivot"] | diag["high_pivot"] |
            (diag["cisd_event"] != 0) | (diag["fvg_event"] != 0) |
            diag["signal_long"] | diag["signal_short"]
        ].copy()

        # Restrict to morning session where the screenshot CISD appears
        interesting = interesting[
            (interesting["time"] >= pd.Timestamp("2026-08-19 09:30:00")) &
            (interesting["time"] <= pd.Timestamp("2026-08-19 12:00:00"))
        ]

        print(interesting.to_string(index=False))

        # Summary of entries
        entries = diag[diag["signal_long"] | diag["signal_short"]]
        if not entries.empty:
            print(f"\nVariant 2 entries on {tf}:")
            print(entries[["time", "signal_long", "signal_short", "bull_count", "fvg_event"]].to_string(index=False))
        else:
            print(f"\nNo Variant 2 entries on {tf}")


if __name__ == "__main__":
    main()
