"""Fetch VX futures daily settlement history from CBOE CFE and stitch continuous VX1/VX2.

Source: CFE Price and Volume Detail per-expiry CSVs:
  https://cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_YYYY-MM-DD.csv
Each CSV is one expiry (Wednesday) with rows per Trade Date: Open/High/Low/Close/Settle/Volume/OI.
The page https://www.cboe.com/markets/us/futures/market-statistics/historical-data/futures
lists all VX expiries (2013→present, ~618). This script enumerates via the same
CDN pattern discovered via Playwright (Year dropdown scraped, 618 URLs) and stitches
a continuous front-month (VX1) and second-month (VX2) daily series.

Run:
  python scripts/market_data/fetch_cboe_vx_futures.py           # full backfill
  python scripts/market_data/fetch_cboe_vx_futures.py --dry-run  # list URLs only
"""
import argparse
import re
import time
from datetime import datetime, timezone, date
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

ET_TZ = ZoneInfo("America/New_York")
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BASE_LIST_URL = "https://www.cboe.com/markets/us/futures/market-statistics/historical-data/futures"

# Fallback: if Playwright enumeration fails, brute-force weekly Wednesdays 2013→2028
# But we now know the URL pattern, so we can enumerate via HTTP HEAD probing.
# Instead, do a Playwright-free enumeration: scrape the page's static links for 2027
# then generate weekly Wednesdays for other years and probe. Simpler: just probe
# the discovered 618 URLs via the same loop that Playwright used — but we can also
# re-scrape with httpx by fetching the page and parsing? The page is Next.js and
# links are rendered client-side, so httpx alone won't see them. So we keep the
# Playwright-discovered list as fallback and also brute-force by iterating expiries.

def get_daily_anchor(d: date):
    dt_et = datetime.combine(d, datetime.min.time(), tzinfo=ET_TZ).replace(hour=16)
    return dt_et.astimezone(timezone.utc)

def fetch_expiry_csv(url: str, expiry_date: date) -> pd.DataFrame | None:
    try:
        r = httpx.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        df = pd.read_csv(StringIO(r.text))
        # Expected cols: Trade Date,Futures,Open,High,Low,Close,Settle,Change,Total Volume,EFP,Open Interest
        if "Trade Date" not in df.columns or "Settle" not in df.columns:
            return None
        df["Trade Date"] = pd.to_datetime(df["Trade Date"])
        df["expiry"] = expiry_date
        # Keep only rows where there's actual trading (Settle != 0 or Volume > 0) and Trade Date < expiry
        df = df[df["Trade Date"].dt.date < expiry_date]
        # Drop rows where Settle is 0 and Volume is 0 (no market)
        df = df[~((df["Settle"] == 0) & (df["Total Volume"] == 0))]
        return df[["Trade Date", "expiry", "Open", "High", "Low", "Close", "Settle", "Total Volume", "Open Interest"]]
    except Exception as e:
        print(f"  WARN {url}: {e}")
        return None

def enumerate_expiries() -> list[tuple[str, date]]:
    """All Wednesday expiries 2013→2027 (weekly since 2015, monthly before).
    We return every Wednesday; the fetch step will 404-filter to the real
    618 expiries (no HEAD probe — one GET per Wednesday is the same cost).
    """
    from datetime import timedelta
    start = date(2013, 1, 1)
    end = date(2027, 12, 31)
    d = start
    while d.weekday() != 2:
        d += timedelta(days=1)
    urls = []
    while d <= end:
        url = f"https://cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_{d.isoformat()}.csv"
        urls.append((url, d))
        d += timedelta(days=7)
    print(f"Enumerated {len(urls)} Wednesday expiries (GET will filter to ~618 real).")
    return urls

def stitch_continuous(all_expiry_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    if not all_expiry_dfs:
        return pd.DataFrame()
    combined = pd.concat(all_expiry_dfs, ignore_index=True)
    # For each Trade Date, pick VX1 = nearest expiry (min days to expiry) and VX2 = second nearest
    combined = combined.sort_values(["Trade Date", "expiry"])
    # Group by Trade Date
    vx1_rows = []
    vx2_rows = []
    for trade_date, g in combined.groupby("Trade Date"):
        g = g.sort_values("expiry")
        if len(g) >= 1:
            vx1_rows.append(g.iloc[0])
        if len(g) >= 2:
            vx2_rows.append(g.iloc[1])
    vx1 = pd.DataFrame(vx1_rows)
    vx2 = pd.DataFrame(vx2_rows)
    return vx1, vx2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="list URLs only")
    parser.add_argument("--limit", type=int, default=0, help="limit expiries for testing")
    args = parser.parse_args()

    urls = enumerate_expiries()
    if args.limit:
        urls = urls[:args.limit]
    print(f"Total VX expiries to probe: {len(urls)}")

    if args.dry_run:
        for u, d in urls[:20]:
            print(u)
        return

    # Fetch all expiry CSVs (404s are skipped; ~618 of 783 will succeed)
    all_dfs = []
    for i, (url, exp) in enumerate(urls):
        if (i+1) % 50 == 0:
            print(f"[{i+1}/{len(urls)}] fetching {exp} ...")
        df = fetch_expiry_csv(url, exp)
        if df is not None and not df.empty:
            all_dfs.append(df)
        # tiny throttle to avoid hammering CDN
        if (i+1) % 100 == 0:
            time.sleep(0.3)

    print(f"Fetched {len(all_dfs)} expiries with data, total rows {sum(len(d) for d in all_dfs)}")
    vx1, vx2 = stitch_continuous(all_dfs)

    # Build parquet: index at 16:00 ET (20:00 UTC), columns open/high/low/close/settle/volume
    for name, df in [("VX1", vx1), ("VX2", vx2)]:
        if df.empty:
            print(f"  {name}: no data")
            continue
        df = df.copy()
        df["anchor"] = [get_daily_anchor(d.date()) for d in df["Trade Date"]]
        df = df.set_index("anchor").sort_index()
        df.index.name = "datetime"
        # Map to OHLCV: use Settle as close for futures settlement series, keep OHLC for reference
        out = pd.DataFrame({
            "open": df["Open"].astype(float),
            "high": df["High"].astype(float),
            "low": df["Low"].astype(float),
            "close": df["Settle"].astype(float),  # settlement is the mark
            "settle": df["Settle"].astype(float),
            "volume": df["Total Volume"].astype(float),
            "open_interest": df["Open Interest"].astype(float),
            "expiry": df["expiry"].astype(str),
        })
        out = out[~out.index.duplicated(keep="last")].sort_index()
        # Also build futures continuous close series using Close where Settle is zero? Settle is authoritative
        path = DATA_DIR / f"{name}_1d.parquet"
        out.to_parquet(path)
        print(f"  Wrote {path} rows {len(out)} last {out.index[-1]} expiry {out['expiry'].iloc[-1]}")

    # Also write volume/OI sidecar for audit
    print("Done. Columns for sessions.parquet: vx1_close (Settle), vx2_close, vx_basis_spot = VX1 - VIX, vx_curve_1_2 = VX2 - VX1")

if __name__ == "__main__":
    main()
