"""
Rebuild corrupted live_storage parquet files.

Strategy:
  1. Restore from JSON backup (live_chart_*.json.bak) — covers up to June 18, 2026
  2. Fetch recent gap (June 18 -> now) from Schwab API via Hub — Schwab keeps ~10-12 days of 1m
  3. Merge + deduplicate + atomic write

Also fixes:
  - NQ: removes bad-epoch first row (1970 timestamp)
  - NVDA: removes all-zero OHLC row

Usage:
  python rebuild_live_parquets.py                  # rebuild corrupt + fix NQ/NVDA
  python rebuild_live_parquets.py --only AAPL,QQQ,SPY
  python rebuild_live_parquets.py --fix-nq
  python rebuild_live_parquets.py --fix-nvda
"""
import os
import sys
import io
import json
import shutil
import asyncio
import httpx
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True, line_buffering=True)

# Fix path: go up 3 levels from scripts/maintenance/ to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIVE_DIR = os.path.join(PROJECT_ROOT, "data", "live")
HUB_URL = "http://127.0.0.1:8080"

REBUILD_SYMBOLS = ["AAPL", "QQQ", "SPY"]

async def hub_request(method, params):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=60.0)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, dict) and "status" not in result:
                    return {"status": "success", "data": result}
                return result
            return {"status": "error", "message": f"Hub Error [{resp.status_code}]: {resp.text}"}
        except Exception as e:
            return {"status": "error", "message": f"Hub Connection Error: {e}"}

def load_json_backup(symbol):
    """Load 1m candles from JSON backup file."""
    path = os.path.join(LIVE_DIR, f"live_chart_{symbol}.json.bak")
    if not os.path.exists(path):
        print(f"  ⚠️ No JSON backup at {path}")
        return []
    with open(path, 'r') as f:
        data = json.load(f)
    candles = data.get("candles", [])
    return [{
        "time": int(c["time"]),
        "open": c.get("open", 0),
        "high": c.get("high", 0),
        "low": c.get("low", 0),
        "close": c.get("close", 0),
        "volume": c.get("volume", 0)
    } for c in candles if c.get("time", 0) > 0]

async def fetch_recent_from_schwab(symbol, start_ms):
    """Fetch 1m bars from Schwab via Hub, from start_ms to now."""
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    resp = await hub_request("get_price_history", {
        "symbol": symbol,
        "period_type": "day",
        "period": 10,  # Max ~10 days of 1m data
        "frequency_type": "minute",
        "frequency": 1,
        "need_extended_hours_data": True
    })
    if resp.get("status") != "success":
        print(f"  ⚠️ Schwab API failed: {resp.get('message')}")
        return []
    candles = resp.get("data", {}).get("candles", [])
    # Filter to only bars after start_ms (avoid overlap with JSON backup)
    return [{
        "time": c.get("datetime", 0),
        "open": c.get("open", 0),
        "high": c.get("high", 0),
        "low": c.get("low", 0),
        "close": c.get("close", 0),
        "volume": c.get("volume", 0)
    } for c in candles if c.get("datetime", 0) > start_ms]

async def rebuild_symbol(symbol):
    """Rebuild one symbol's parquet from JSON backup + Schwab API."""
    filepath = os.path.join(LIVE_DIR, f"live_storage_{symbol}.parquet")

    print(f"\n{'='*80}")
    print(f"  Rebuilding {symbol}")
    print(f"{'='*80}")

    # Step 1: Load JSON backup
    print(f"  Step 1: Loading JSON backup...", end=" ", flush=True)
    json_candles = load_json_backup(symbol)
    if not json_candles:
        print("FAILED — no JSON data")
        return False
    json_last_ms = max(c["time"] for c in json_candles)
    print(f"{len(json_candles)} bars, ending {pd.Timestamp(json_last_ms, unit='ms')}")

    # Step 2: Fetch recent from Schwab
    print(f"  Step 2: Fetching recent bars from Schwab API...", end=" ", flush=True)
    schwab_candles = await fetch_recent_from_schwab(symbol, json_last_ms)
    print(f"{len(schwab_candles)} new bars")

    # Step 3: Merge
    all_candles = json_candles + schwab_candles
    df = pd.DataFrame(all_candles)
    df['time'] = df['time'].astype('int64')
    df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
    df = df.sort_values('time').drop_duplicates(subset=['time'], keep='last').reset_index(drop=True)

    # Remove any zero-OHLC rows
    zero_mask = (df['open'] == 0) & (df['high'] == 0) & (df['low'] == 0) & (df['close'] == 0)
    if zero_mask.any():
        print(f"  Removing {zero_mask.sum()} all-zero OHLC rows")
        df = df[~zero_mask].reset_index(drop=True)

    # Step 4: Backup corrupted file
    if os.path.exists(filepath):
        bak = filepath + '.corrupt_bak'
        if not os.path.exists(bak):
            shutil.move(filepath, bak)
            print(f"  Backed up corrupted file -> {os.path.basename(bak)}")
        else:
            os.remove(filepath)

    # Step 5: Atomic write
    tmp = filepath + '.tmp'
    df.to_parquet(tmp, index=False)
    os.replace(tmp, filepath)

    print(f"  ✅ Wrote {len(df)} rows to live_storage_{symbol}.parquet")
    print(f"     Range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

    # Verify
    verify = pd.read_parquet(filepath)
    assert len(verify) == len(df), "Verification failed!"
    print(f"  ✅ Verified: {len(verify)} rows readable")
    return True

def fix_nq_bad_epoch():
    """Remove the first row of NQ parquet that has a 1970-epoch timestamp."""
    filepath = os.path.join(LIVE_DIR, "live_storage_-NQ.parquet")
    print(f"\n{'='*80}")
    print(f"  Fixing NQ: removing bad-epoch row(s)")
    print(f"{'='*80}")

    df = pd.read_parquet(filepath)
    before = len(df)

    # Remove any row where time < year 2000 (bad epoch)
    bad_mask = df['time'] < 946684800000  # ms epoch for 2000-01-01
    bad_count = bad_mask.sum()

    if bad_count == 0:
        print(f"  No bad-epoch rows found. Nothing to fix.")
        return

    print(f"  Found {bad_count} bad-epoch row(s). Removing...")
    df = df[~bad_mask].reset_index(drop=True)

    # Atomic write
    tmp = filepath + '.tmp'
    df.to_parquet(tmp, index=False)
    os.replace(tmp, filepath)

    print(f"  ✅ Removed {bad_count} row(s). {before} -> {len(df)} rows")
    print(f"     New first bar: {pd.to_datetime(df['time'].min(), unit='ms')}")

def fix_nvda_zero_row():
    """Remove all-zero OHLC row from NVDA parquet."""
    filepath = os.path.join(LIVE_DIR, "live_storage_NVDA.parquet")
    print(f"\n{'='*80}")
    print(f"  Fixing NVDA: removing all-zero OHLC row(s)")
    print(f"{'='*80}")

    df = pd.read_parquet(filepath)
    before = len(df)

    zero_mask = (df['open'] == 0) & (df['high'] == 0) & (df['low'] == 0) & (df['close'] == 0)
    bad_count = zero_mask.sum()

    if bad_count == 0:
        print(f"  No zero rows found. Nothing to fix.")
        return

    print(f"  Found {bad_count} all-zero OHLC row(s). Removing...")
    df = df[~zero_mask].reset_index(drop=True)

    # Atomic write
    tmp = filepath + '.tmp'
    df.to_parquet(tmp, index=False)
    os.replace(tmp, filepath)

    print(f"  ✅ Removed {bad_count} row(s). {before} -> {len(df)} rows")

async def main():
    args = sys.argv[1:]
    only_symbols = None
    fix_nq = False
    fix_nvda = False
    do_rebuild = True

    for arg in args:
        if arg.startswith("--only="):
            only_symbols = arg.split("=")[1].split(",")
        elif arg == "--fix-nq":
            fix_nq = True
            do_rebuild = False
        elif arg == "--fix-nvda":
            fix_nvda = True
            do_rebuild = False
        elif arg == "--fix-all":
            fix_nq = True
            fix_nvda = True
            do_rebuild = True

    # Check Hub is running
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{HUB_URL}/health", timeout=5.0)
            if r.status_code != 200:
                raise Exception(f"status {r.status_code}")
            print(f"Hub running at {HUB_URL}")
    except Exception:
        print(f"⚠️ Hub not running at {HUB_URL} — will use JSON backup only (no recent data)")
        print(f"   Start Hub with start_hub.bat for full recovery")

    # Rebuild corrupted files
    if do_rebuild:
        targets = only_symbols if only_symbols else REBUILD_SYMBOLS
        for symbol in targets:
            success = await rebuild_symbol(symbol)
            if not success:
                print(f"  ⚠️ {symbol} rebuild failed")

    # Fix NQ bad epoch
    if fix_nq or do_rebuild:
        fix_nq_bad_epoch()

    # Fix NVDA zero row
    if fix_nvda or do_rebuild:
        fix_nvda_zero_row()

    print(f"\n{'='*80}")
    print(f"  DONE")
    print(f"{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())