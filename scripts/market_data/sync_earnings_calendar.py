"""
sync_earnings_calendar.py
==========================
Dual-provider earnings calendar synchronizer.
Primary: Nasdaq Earnings API (api.nasdaq.com/api/calendar/earnings)
Fallback: yfinance Calendars
Persists upcoming earnings events into SQLite dev.db (EarningsCalendar model).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
import uuid
import time
import re
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Any, List, Dict, Optional
import requests

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from prisma import Prisma
except Exception:
    Prisma = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("sync_earnings")

# Get project root
REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "web" / "prisma" / "dev.db"

# Core Watchlist that should ALWAYS be included regardless of market cap
CORE_WATCHLIST = {"SPY", "QQQ", "IWM", "SPX", "NDX", "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"}

NASDAQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get_db_connection() -> sqlite3.Connection:
    """Fallback sqlite3 connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_market_cap_str(cap_str: Optional[str]) -> float:
    """Helper to parse market cap strings like '$1,234,567,890' or '$5.2B' to float."""
    if not cap_str or str(cap_str).strip() in {"N/A", "", "0"}:
        return 0.0
    clean = str(cap_str).replace("$", "").replace(",", "").strip()
    try:
        if clean.endswith("B"):
            return float(clean[:-1]) * 1e9
        elif clean.endswith("M"):
            return float(clean[:-1]) * 1e6
        elif clean.endswith("T"):
            return float(clean[:-1]) * 1e12
        return float(clean)
    except ValueError:
        return 0.0


def fetch_nasdaq_earnings_for_date(date_str: str) -> List[Dict[str, Any]]:
    """
    Fetch raw earnings events from Nasdaq Earnings API for a given date (YYYY-MM-DD).
    Returns list of dicts: [{ticker, company, earningsDate, beforeMarket, marketCap, source}]
    """
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={date_str}"
    events = []
    try:
        resp = requests.get(url, headers=NASDAQ_HEADERS, timeout=15)
        if resp.status_code != 200:
            log.warning(f"Nasdaq API returned status code {resp.status_code} for date {date_str}")
            return []
        
        data = resp.json()
        rows = data.get("data", {}).get("rows", [])
        if not rows:
            return []
        
        # Parse date
        target_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        for row in rows:
            ticker = str(row.get("symbol", "")).upper().strip()
            if not ticker or "." in ticker or (len(ticker) == 5 and ticker.endswith("F")):
                continue
            
            company = str(row.get("name", "")).strip()
            timing_str = str(row.get("time", "")).lower()
            
            # Determine BMO vs AMC
            # Nasdaq time formats: "time_before_market", "time_after_hours", "time_not_supplied"
            before_market = True
            if "after" in timing_str or "amc" in timing_str or "post" in timing_str:
                before_market = False
                
            market_cap_raw = row.get("marketCap", "0")
            market_cap = _parse_market_cap_str(market_cap_raw)
            
            events.append({
                "ticker": ticker,
                "earningsDate": target_dt,
                "beforeMarket": before_market,
                "company": company,
                "marketCap": market_cap,
                "source": "nasdaq_api"
            })
    except Exception as e:
        log.warning(f"Failed to fetch Nasdaq earnings for {date_str}: {e}")
        return []
        
    return events


def fetch_earnings_range(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """
    Dual-provider range fetcher.
    Tries Nasdaq API date-by-date first, falls back to yfinance if Nasdaq returns empty results.
    """
    all_events = []
    curr_date = start_date
    nasdaq_success = False
    
    log.info(f"Fetching earnings events via Nasdaq API from {start_date} to {end_date}...")
    while curr_date <= end_date:
        # Skip weekends for Nasdaq API
        if curr_date.weekday() < 5:
            date_str = curr_date.strftime("%Y-%m-%d")
            day_events = fetch_nasdaq_earnings_for_date(date_str)
            if day_events:
                all_events.extend(day_events)
                nasdaq_success = True
            time.sleep(0.3) # Rate limit delay
        curr_date += timedelta(days=1)
        
    if nasdaq_success and len(all_events) > 0:
        log.info(f"Retrieved {len(all_events)} total earnings events from Nasdaq API.")
        return all_events

    # Fallback to yfinance if Nasdaq API returned nothing
    if yf is not None:
        log.info("Nasdaq API returned no results or failed. Falling back to yfinance...")
        try:
            cal = yf.Calendars(start=start_date, end=end_date)
            df = cal.get_earnings_calendar(market_cap=10_000_000, filter_most_active=False)
            if df is not None and not df.empty:
                for ticker, row in df.iterrows():
                    ticker_str = str(ticker).upper().strip()
                    if not ticker_str or "." in ticker_str or (len(ticker_str) == 5 and ticker_str.endswith("F")):
                        continue
                    
                    company = str(row.get("Company", ""))
                    market_cap = float(row.get("Marketcap", 0.0) or 0.0)
                    event_date_raw = row.get("Event Start Date")
                    if not event_date_raw:
                        continue
                    
                    timing_str = str(row.get("Timing", "")).lower()
                    before_market = True
                    if "after" in timing_str or "amc" in timing_str or "post" in timing_str:
                        before_market = False
                        
                    if isinstance(event_date_raw, str):
                        try:
                            event_date = datetime.fromisoformat(event_date_raw.replace("Z", "+00:00"))
                        except ValueError:
                            event_date = datetime.strptime(event_date_raw.split(" ")[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    else:
                        event_date = event_date_raw.to_pydatetime() if hasattr(event_date_raw, "to_pydatetime") else event_date_raw
                        if event_date.tzinfo is None:
                            event_date = event_date.replace(tzinfo=timezone.utc)
                            
                    all_events.append({
                        "ticker": ticker_str,
                        "earningsDate": event_date,
                        "beforeMarket": before_market,
                        "company": company,
                        "marketCap": market_cap,
                        "source": "yfinance"
                    })
        except Exception as e:
            log.error(f"Fallback yfinance fetch failed: {e}")

    return all_events


async def run_sync(days: int, min_market_cap: float, dry_run: bool = False):
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=days)

    log.info(f"Syncing earnings from {start_date} to {end_date} (Min Cap: ${min_market_cap/1e9:.1f}B)")

    raw_events = fetch_earnings_range(start_date, end_date)
    if not raw_events:
        log.info("No earnings events found in the specified range.")
        return

    # Process and filter events
    events_to_save = []
    seen = set()
    
    for ev in raw_events:
        ticker_str = ev["ticker"]
        key = (ticker_str, ev["earningsDate"].date())
        if key in seen:
            continue
        seen.add(key)

        market_cap = ev["marketCap"]
        is_watchlist = ticker_str in CORE_WATCHLIST
        is_large_cap = market_cap >= min_market_cap

        # If market cap is unknown (0.0), include it if in watchlist or if Nasdaq API provided it
        if not (is_watchlist or is_large_cap or market_cap == 0.0):
            continue

        events_to_save.append(ev)

    log.info(f"Filtered down to {len(events_to_save)} target earnings events.")

    if dry_run:
        log.info("Dry run enabled. The following events would be saved:")
        for ev in events_to_save[:10]:
            timing = "BMO (Pre-Market)" if ev["beforeMarket"] else "AMC (Post-Market)"
            log.info(f" - {ev['ticker']} ({ev['company']}) on {ev['earningsDate'].date()} {timing} [Source: {ev['source']}]")
        if len(events_to_save) > 10:
            log.info(f" ... and {len(events_to_save)-10} more.")
        return

    # Persist to database via Prisma
    saved_count = 0
    if Prisma is not None:
        try:
            db = Prisma()
            await db.connect()
            for ev in events_to_save:
                dt = ev["earningsDate"]
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                await db.earningscalendar.upsert(
                    where={
                        "ticker_earningsDate": {
                            "ticker": ev["ticker"],
                            "earningsDate": dt
                        }
                    },
                    data={
                        "create": {
                            "id": uuid.uuid4().hex,
                            "ticker": ev["ticker"],
                            "earningsDate": dt,
                            "beforeMarket": ev["beforeMarket"],
                            "confirmed": True,
                            "source": ev["source"],
                            "company": ev["company"],
                            "marketCap": ev["marketCap"]
                        },
                        "update": {
                            "beforeMarket": ev["beforeMarket"],
                            "confirmed": True,
                            "source": ev["source"],
                            "fetchedAt": datetime.now(timezone.utc),
                            "company": ev["company"],
                            "marketCap": ev["marketCap"]
                        }
                    }
                )
                saved_count += 1
            await db.disconnect()
            log.info(f"Successfully upserted {saved_count} earnings events via Prisma.")
            return
        except Exception as e:
            log.warning(f"Prisma sync failed: {e}. Falling back to direct SQLite...")

    # Fallback to direct sqlite3
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        
        start_range_str = start_date.strftime("%Y-%m-%d") + "T00:00:00.000+00:00"
        end_range_str = end_date.strftime("%Y-%m-%d") + "T23:59:59.999+00:00"
        cursor.execute(
            "DELETE FROM EarningsCalendar WHERE earningsDate >= ? AND earningsDate <= ?",
            (start_range_str, end_range_str)
        )
        
        for ev in events_to_save:
            dt_str = ev["earningsDate"].isoformat()
            if not dt_str.endswith("Z") and "+" not in dt_str:
                dt_str += "+00:00"

            cursor.execute(
                "INSERT INTO EarningsCalendar (id, ticker, earningsDate, beforeMarket, confirmed, source, fetchedAt, company, marketCap) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)",
                (uuid.uuid4().hex, ev["ticker"], dt_str, 1 if ev["beforeMarket"] else 0, ev["source"], now_str, ev["company"], ev["marketCap"])
            )
            saved_count += 1
        conn.commit()
        conn.close()
        log.info(f"Successfully upserted {saved_count} earnings events via fallback SQLite.")
    except Exception as e:
        log.error(f"Failed to write to SQLite: {e}")


def has_upcoming_earnings(ticker: str, window_days: int = 7) -> bool:
    """
    Checks dev.db EarningsCalendar for upcoming earnings for a given ticker within window_days.
    """
    if not DB_PATH.exists():
        return False
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        now_dt = datetime.now(timezone.utc)
        future_dt = now_dt + timedelta(days=window_days)
        
        now_str = now_dt.strftime("%Y-%m-%d")
        future_str = future_dt.strftime("%Y-%m-%d") + "T23:59:59"
        
        cursor.execute(
            "SELECT count(*) FROM EarningsCalendar WHERE ticker = ? AND earningsDate >= ? AND earningsDate <= ?",
            (ticker.upper(), f"{now_str}%", f"{future_str}%")
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        log.warning(f"Failed to check upcoming earnings for {ticker}: {e}")
        return False


def is_episodic_pivot_catalyst(ticker: str, window_days: int = 3) -> bool:
    """
    Checks if ticker had an earnings event within the past window_days.
    """
    if not DB_PATH.exists():
        return False
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        now_dt = datetime.now(timezone.utc)
        past_dt = now_dt - timedelta(days=window_days)
        
        past_str = past_dt.strftime("%Y-%m-%d")
        now_str = now_dt.strftime("%Y-%m-%d") + "T23:59:59"
        
        cursor.execute(
            "SELECT count(*) FROM EarningsCalendar WHERE ticker = ? AND earningsDate >= ? AND earningsDate <= ?",
            (ticker.upper(), f"{past_str}%", f"{now_str}%")
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        log.warning(f"Failed to check earnings catalyst for {ticker}: {e}")
        return False



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync earnings calendar to database.")
    parser.add_argument("--days", type=int, default=7, help="Number of days forward to sync.")
    parser.add_argument("--min-cap", type=float, default=5e9, help="Minimum market cap in USD (default: 5B).")
    parser.add_argument("--dry-run", action="store_true", help="Print preview without writing to database.")
    args = parser.parse_args()

    asyncio.run(run_sync(args.days, args.min_cap, args.dry_run))
