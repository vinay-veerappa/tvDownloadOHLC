#!/usr/bin/env python3
"""
export_fixture.py — deterministic parity fixture from live-storage parquet.

Slices a pinned date range of 5m bars (resampled from 1m the same way the
strategy does) into the CSV both harnesses consume:
  - C#: scripts/parity/csharp/CsdEngineHarness (dotnet run)
  - Python reference: scripts/parity/run_signal_parity.py --python-only

The fixture is HASH-STAMPED: the same slice always yields the same bytes, so
a diff in the parity report is attributable to CODE, not data movement.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.libs_py.data.resampler import resample_ohlcv  # noqa: E402

DEFAULT_PARQUET = REPO_ROOT / "data" / "live" / "live_storage_-NQ.parquet"
FIXTURE_DIR = REPO_ROOT / "scripts" / "parity" / "fixtures"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET)
    ap.add_argument("--start", default="2026-06-02")
    ap.add_argument("--end", default="2026-06-06")
    ap.add_argument("--tf", default="5min")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    df = pd.read_parquet(args.parquet)
    df.columns = [c.lower() for c in df.columns]
    # Live storage carries epoch-ms 'time' + UTC 'timestamp'; the strategy layer
    # works in ET wall-clock. Convert, then slice.
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index(df["timestamp"].dt.tz_convert("America/New_York"))
    df = df.loc[args.start:args.end]
    if df.empty:
        print(f"[ERROR] no bars in {args.parquet} between {args.start} and {args.end}")
        return 2

    # The 1m source can carry rows with volume but NaN OHLC (feed gaps). The
    # resampler's dropna(how='all') keeps them (volume is non-NaN), producing
    # 5m bars of pure NaN — which the two platforms treat DIFFERENTLY (Python
    # NaN comparisons vs C# NaN comparisons) and neither is a real bar. Drop
    # any row without a full OHLC before resampling; a parity fixture must be
    # clean bars only.
    n_before = len(df)
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < n_before:
        print(f"[CLEAN] dropped {n_before - len(df)} NaN-OHLC rows")

    htf = resample_ohlcv(df, args.tf)
    # The resampler emits bins for periods with no source bars as NaN OHLC
    # (measured: feed gap after 19:59 on 2026-06-02 produced 36 NaN 5m bars).
    # Neither platform's NaN semantics should be part of the parity contract.
    n_htf = len(htf)
    htf = htf.dropna(subset=["open", "high", "low", "close"])
    if len(htf) < n_htf:
        print(f"[CLEAN] dropped {n_htf - len(htf)} empty resample bins")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    out = args.out or (FIXTURE_DIR / f"nq_{args.tf}_{args.start}_{args.end}.csv")

    lines = ["time,open,high,low,close"]
    for ts, row in htf.iterrows():
        t = ts.tz_localize(None).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{t},{row['open']:G},{row['high']:G},{row['low']:G},{row['close']:G}")
    content = "\n".join(lines) + "\n"
    out.write_text(content, encoding="utf-8")

    h = hashlib.md5(content.encode()).hexdigest()[:12]
    print(f"[FIXTURE] {out}  bars={len(htf)}  md5={h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())