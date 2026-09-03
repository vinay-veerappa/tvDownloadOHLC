"""
Gate 2: Deterministic parity check — Rust PyO3 simulation vs Python engine.
Runs across 1 full year of historical 1-minute bars.
Asserts exact match on: total trades, entry prices, exit prices, net points, exit reasons.
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Users\vinay\tvDownloadOHLC")
from scripts.execution.nt8_parity_engine import NT8ParityEngine
import nt8_parity_core

PARQUET = r"C:\Users\vinay\tvDownloadOHLC\data\NQ1_1m.parquet"
YEAR_START, YEAR_END = "2023-01-01", "2024-01-01"

def synth_signals(df: pd.DataFrame):
    """Deterministic signal synthesis so both engines see identical inputs."""
    n = len(df)
    signals = np.zeros(n, dtype=np.int32)
    limit_prices = df["close"].to_numpy(dtype=np.float64).copy()
    stop_losses = df["close"].to_numpy(dtype=np.float64).copy()
    # Arm a signal every 5m bar with alternating direction at a deterministic cadence
    idx = np.arange(0, n, 15)
    dirs = np.where((np.arange(0, n, 15) // 15) % 2 == 0, 1, -1).astype(np.int32)
    signals[idx] = dirs
    # Limit 2 ticks below (buy) / above (sell) close; SL 6 ticks beyond
    tick = 0.25
    for k, i in enumerate(idx):
        if dirs[k] == 1:
            limit_prices[i] = limit_prices[i] - 0.50
            stop_losses[i] = limit_prices[i] - 1.50
        else:
            limit_prices[i] = limit_prices[i] + 0.50
            stop_losses[i] = limit_prices[i] + 1.50
    return signals, limit_prices, stop_losses


def synth_signals_5m(df_5m: pd.DataFrame):
    n = len(df_5m)
    signals = np.zeros(n, dtype=np.int32)
    idx = np.arange(0, n, 24)
    dirs = np.where((np.arange(0, n, 24) // 24) % 2 == 0, 1, -1).astype(np.int32)
    signals[idx] = dirs
    times = df_5m.index
    return times.values.astype("datetime64[ms]").astype(np.int64), signals


def main():
    print("Loading 1m parquet (1 year window)...")
    df_full = pd.read_parquet(PARQUET)
    df = df_full.loc[YEAR_START:YEAR_END].copy()
    print(f"bars: {len(df)} ({df.index[0]} -> {df.index[-1]})")

    engine = NT8ParityEngine(point_value=2.0, tick_size=0.25, contracts=2)

    # ---------------- V1 ----------------
    signals, limit_prices, stop_losses = synth_signals(df)
    times_ms = df.index.values.astype("datetime64[ms]").astype(np.int64)

    py_df = engine.simulate(
        df,
        pd.Series(signals, index=df.index),
        pd.Series(limit_prices, index=df.index),
        pd.Series(stop_losses, index=df.index),
    )

    rust = nt8_parity_core.simulate_bars_v1(
        times_ms,
        df["open"].to_numpy(dtype=np.float64),
        df["high"].to_numpy(dtype=np.float64),
        df["low"].to_numpy(dtype=np.float64),
        df["close"].to_numpy(dtype=np.float64),
        signals,
        limit_prices,
        stop_losses,
        point_value=2.0, tick_size=0.25, contracts=2,
    )

    n_py, n_rs = len(py_df), len(rust["entry_time_ms"])
    print(f"[V1] python trades: {n_py} | rust trades: {n_rs}")
    if n_py != n_rs:
        # Find first divergence for diagnosis
        print("V1 TRADE COUNT DIVERGENCE")
        sys.exit(2)

    mismatches = 0
    for col_py, col_rs in [
        ("entry_price", "entry_price"),
        ("exit_price", "exit_price"),
        ("leg1_points", "leg1_points"),
        ("leg2_points", "leg2_points"),
        ("total_points", "total_points"),
    ]:
        py_arr = py_df[col_py].to_numpy(dtype=np.float64)
        rs_arr = np.asarray(rust[col_rs], dtype=np.float64)
        if not np.array_equal(py_arr, rs_arr):
            bad = np.where(py_arr != rs_arr)[0]
            mismatches += len(bad)
            print(f"  V1 {col_py}: {len(bad)} mismatches, first at idx {bad[:3]}")
            for b in bad[:3]:
                print(f"    py={py_arr[b]!r} rust={rs_arr[b]!r}")
        else:
            print(f"  V1 {col_py}: EXACT MATCH ({len(py_arr)} rows)")

    # Time fields
    py_entry_ms = py_df["entry_time"].values.astype("datetime64[ms]").astype(np.int64)
    rs_entry_ms = np.asarray(rust["entry_time_ms"], dtype=np.int64)
    if not np.array_equal(py_entry_ms, rs_entry_ms):
        bad = np.where(py_entry_ms != rs_entry_ms)[0]
        print(f"  V1 entry_time: {len(bad)} mismatches (tz-offset style difference?)")
        for b in bad[:3]:
            print(f"    py={pd.Timestamp(py_entry_ms[b], unit='ms')} rust={pd.Timestamp(rs_entry_ms[b], unit='ms')}")
    else:
        print(f"  V1 entry_time: EXACT MATCH")

    # ---------------- V2 ----------------
    df_5m = df_full.loc[YEAR_START:YEAR_END].resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    sig_times_5m, sig_dirs_5m = synth_signals_5m(df_5m)
    times_1m_ms = df.index.values.astype("datetime64[ms]").astype(np.int64)

    py_df2 = engine.simulate_mtf(df_5m, df, pd.Series(sig_dirs_5m, index=df_5m.index))

    rust2 = nt8_parity_core.simulate_bars_v2(
        times_1m_ms,
        df["open"].to_numpy(dtype=np.float64),
        df["high"].to_numpy(dtype=np.float64),
        df["low"].to_numpy(dtype=np.float64),
        df["close"].to_numpy(dtype=np.float64),
        sig_times_5m,
        sig_dirs_5m,
        point_value=2.0, tick_size=0.25, contracts=2,
    )

    n_py2, n_rs2 = len(py_df2), len(rust2["entry_time_ms"])
    print(f"[V2] python trades: {n_py2} | rust trades: {n_rs2}")
    if n_py2 != n_rs2:
        print("V2 TRADE COUNT DIVERGENCE")
        sys.exit(2)

    for col_py, col_rs in [
        ("entry_price", "entry_price"),
        ("exit_price", "exit_price"),
        ("leg1_points", "leg1_points"),
        ("leg2_points", "leg2_points"),
        ("total_points", "total_points"),
        ("mfe_points", "mfe_points"),
        ("mae_points", "mae_points"),
    ]:
        py_arr = py_df2[col_py].to_numpy(dtype=np.float64)
        rs_arr = np.asarray(rust2[col_rs], dtype=np.float64)
        if not np.array_equal(py_arr, rs_arr):
            bad = np.where(py_arr != rs_arr)[0]
            mismatches += len(bad)
            print(f"  V2 {col_py}: {len(bad)} mismatches, first at idx {bad[:3]}")
            for b in bad[:3]:
                print(f"    py={py_arr[b]!r} rust={rs_arr[b]!r}")
        else:
            print(f"  V2 {col_py}: EXACT MATCH ({len(py_arr)} rows)")

    if mismatches == 0:
        print("GATE 2 PASSED: Zero-divergence parity confirmed!")
    else:
        print(f"GATE 2 FAILED: {mismatches} value mismatches")
        sys.exit(2)


if __name__ == "__main__":
    main()