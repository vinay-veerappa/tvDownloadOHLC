"""Fetch daily OHLCV for CBOE volatility indices directly from Cboe's CDN.

Cboe serves flat CSV files off their CDN with no auth and no rate limiting —
a plain GET returns clean `DATE,OPEN,HIGH,LOW,CLOSE` rows. This is the
authoritative source for most CBOE vol indices (VIX back to 1990).

Writes data/<SYMBOL>_1d.parquet matching the existing VIX_1d.parquet /
VVIX_1d.parquet convention: tz-aware UTC index at 20:00 (16:00 ET close),
columns open/high/low/close/volume.

Usage:
    python scripts/market_data/fetch_cboe_indices.py            # all
    python scripts/market_data/fetch_cboe_indices.py VIX OVX    # subset
"""
import os
import sys
from datetime import datetime, timezone
from io import StringIO
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ET_TZ = ZoneInfo("America/New_York")
DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
)
BASE = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"

# App symbol -> Cboe CDN symbol prefix. VOLI is a Nasdaq/Nations product and is
# NOT on Cboe's CDN (403) — it is excluded here; use yfinance (^VOLI) for it.
CBOE_MAP = {
    "VIX": "VIX",
    "VXN": "VXN",
    "OVX": "OVX",
    "RVX": "RVX",
    "VVIX": "VVIX",
    "GVZ": "GVZ",
    "VXSLV": "VXSLV",
    "VXD": "VXD",
    "VIX1D": "VIX1D",
    "VIX9D": "VIX9D",
    "VIX3M": "VIX3M",
}


def get_daily_anchor(date_obj):
    """Align a date to 16:00 ET close, returned as tz-aware UTC (20:00 UTC)."""
    dt_et = datetime.combine(date_obj, datetime.min.time(), tzinfo=ET_TZ)
    dt_et = dt_et.replace(hour=16)
    return dt_et.astimezone(timezone.utc)


def fetch_cboe_index(symbol):
    """Fetch one Cboe index CSV from the CDN.

    Two formats exist on the CDN:
      - OHLC:      DATE,OPEN,HIGH,LOW,CLOSE  (VIX, VXN, RVX, VXSLV, VXD, VIX1D, VIX9D, VIX3M)
      - Close-only: DATE,<SYMBOL>            (OVX, VVIX, GVZ) — open=high=low=close
    """
    url = BASE.format(CBOE_MAP[symbol])
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    df["DATE"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    if "OPEN" not in df.columns:
        close_col = [c for c in df.columns if c != "DATE"][0]
        df["OPEN"] = df["HIGH"] = df["LOW"] = df["CLOSE"] = df[close_col]
    return df[["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]]


def fetch_daily(symbol):
    path = os.path.join(DATA_DIR, f"{symbol}_1d.parquet")
    print(f"Processing {symbol} from Cboe CDN...")

    existing_df = pd.DataFrame()
    if os.path.exists(path):
        existing_df = pd.read_parquet(path)
        print(f"  Existing rows: {len(existing_df)}. Last date: {existing_df.index[-1]}")

    csv_df = fetch_cboe_index(symbol)
    csv_df = csv_df.sort_values("DATE")

    # Align to project anchor: 16:00 ET close stored as tz-aware UTC (20:00 UTC).
    csv_df.index = [get_daily_anchor(d.date()) for d in csv_df["DATE"]]
    csv_df.index.name = "datetime"
    csv_df = csv_df[["OPEN", "HIGH", "LOW", "CLOSE"]].copy()
    csv_df.columns = ["open", "high", "low", "close"]
    csv_df["volume"] = 0.0

    if not existing_df.empty:
        combined = pd.concat([existing_df, csv_df])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = csv_df.sort_index()

    combined.to_parquet(path)
    print(f"  Updated {path}. Total rows: {len(combined)}. Last date: {combined.index[-1]}")


def main():
    args = sys.argv[1:]
    symbols = args if args else list(CBOE_MAP.keys())
    for sym in symbols:
        try:
            fetch_daily(sym)
        except Exception as e:
            print(f"  ERROR {sym}: {e}")


if __name__ == "__main__":
    main()
