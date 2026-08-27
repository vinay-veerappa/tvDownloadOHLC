"""Fetch daily OHLCV for CBOE volatility indices via the Schwab API.

Writes data/<SYMBOL>_1d.parquet matching the existing VIX_1d.parquet /
VVIX_1d.parquet convention: tz-aware UTC index at 20:00 (16:00 ET close),
columns open/high/low/close/volume.

WHY RAW HTTP (not schwab-py client):
The schwab-py Client.get_price_history / get_quotes methods strip the leading
'$' from index symbols (e.g. '$RVX' -> 'RVX'), which makes the API return
"Missing parameter" / empty. Calling the REST endpoint directly with a
URL-encoded '$' works for every CBOE vol index. This is a confirmed client
library bug, not an API limitation.

Usage:
    python scripts/market_data/fetch_vol_indices_schwab.py            # all
    python scripts/market_data/fetch_vol_indices_schwab.py RVX VXSLV  # subset
"""
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

ET_TZ = ZoneInfo("America/New_York")
DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
)
BASE_URL = "https://api.schwabapi.com/marketdata/v1"

# App symbol -> Schwab index symbol. All are CBOE volatility indices.
VOL_MAP = {
    "VIX": "$VIX",
    "VXN": "$VXN",
    "OVX": "$OVX",
    "RVX": "$RVX",
    "VVIX": "$VVIX",
    "GVZ": "$GVZ",
    "VXSLV": "$VXSLV",
    "VXD": "$VXD",
    "VOLI": "$VOLI",
    "VIX1D": "$VIX1D",
    "VIX9D": "$VIX9D",
}


def get_access_token():
    """Load the Schwab access token from token.json (same file easy_client uses)."""
    with open("token.json") as f:
        tok = json.load(f)
    if "access_token" in tok:
        return tok["access_token"]
    return tok["token"]["access_token"]


def fetch_daily_history(access, symbol, start_ms, end_ms):
    """Fetch daily candles from Schwab price-history endpoint."""
    enc = urllib.parse.quote(symbol, safe="")
    url = (
        f"{BASE_URL}/pricehistory"
        f"?symbol={enc}"
        f"&periodType=year&frequencyType=daily&frequency=1"
        f"&startDate={start_ms}&endDate={end_ms}"
    )
    r = httpx.get(url, headers={"Authorization": f"Bearer {access}"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Schwab pricehistory {symbol}: HTTP {r.status_code} {r.text[:200]}")
    return r.json().get("candles", [])


def get_daily_anchor(date_obj):
    """Align a date to 16:00 ET close, returned as tz-aware UTC (20:00 UTC).

    Matches the existing VIX_1d.parquet / VVIX_1d.parquet convention.
    """
    dt_et = datetime.combine(date_obj, datetime.min.time(), tzinfo=ET_TZ)
    dt_et = dt_et.replace(hour=16)
    return dt_et.astimezone(timezone.utc)


def fetch_daily(symbol, access, years=20):
    schwab_symbol = VOL_MAP.get(symbol)
    if not schwab_symbol:
        print(f"No mapping for {symbol}")
        return

    path = os.path.join(DATA_DIR, f"{symbol}_1d.parquet")
    print(f"Processing {symbol} Daily (Source: {schwab_symbol})...")

    existing_df = pd.DataFrame()
    if os.path.exists(path):
        existing_df = pd.read_parquet(path)
        print(f"  Existing rows: {len(existing_df)}. Last date: {existing_df.index[-1]}")

    # Fetch from Schwab (start = max(existing, years back))
    now = datetime.now(timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    if not existing_df.empty:
        last_dt = existing_df.index.max().tz_convert(timezone.utc)
        # If the existing file already has today's bar, nothing new to fetch.
        if last_dt.date() >= now.date():
            print(f"  Already current through {last_dt.date()}. Skipping.")
            return
        start_ms = int(last_dt.timestamp() * 1000)
    else:
        start_ms = int((now - pd.Timedelta(days=365 * years)).timestamp() * 1000)

    candles = fetch_daily_history(access, schwab_symbol, start_ms, end_ms)
    if not candles:
        print(f"  No candles returned for {schwab_symbol}")
        return

    new_df = pd.DataFrame(candles)
    new_df["dt"] = pd.to_datetime(new_df["datetime"], unit="ms", utc=True)
    new_df = new_df.set_index("dt")
    new_df = new_df[["open", "high", "low", "close", "volume"]]

    # Align to project anchor: 16:00 ET close stored as tz-aware UTC (20:00 UTC).
    new_df.index = [get_daily_anchor(d.date()) for d in new_df.index]
    new_df.index.name = "datetime"

    if not existing_df.empty:
        combined = pd.concat([existing_df, new_df])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_df.sort_index()

    combined.to_parquet(path)
    print(f"  Updated {path}. Total rows: {len(combined)}. Last date: {combined.index[-1]}")


def main():
    access = get_access_token()
    args = sys.argv[1:]
    symbols = args if args else list(VOL_MAP.keys())
    for sym in symbols:
        try:
            fetch_daily(sym, access)
        except Exception as e:
            print(f"  ERROR {sym}: {e}")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
