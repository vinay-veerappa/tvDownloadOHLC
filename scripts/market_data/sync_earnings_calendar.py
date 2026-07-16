"""
sync_earnings_calendar.py
==========================
Fetches upcoming earnings calendar data from yfinance and stores/updates
the high-impact events in the SQLite database.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Any

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


def _get_db_connection() -> sqlite3.Connection:
    """Fallback sqlite3 connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


async def run_sync(days: int, min_market_cap: float, dry_run: bool = False):
    if yf is None:
        log.error("yfinance library not installed. Cannot sync.")
        return

    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)

    log.info(f"Syncing earnings from {start_date.date()} to {end_date.date()} (Min Cap: ${min_market_cap/1e9:.1f}B)")

    try:
        cal = yf.Calendars(start=start_date, end=end_date)
        # Fetch with 10M min cap to catch most tickers, then we filter in python
        df = cal.get_earnings_calendar(market_cap=10_000_000, filter_most_active=False)
    except Exception as e:
        log.error(f"Failed to fetch earnings calendar from yfinance: {e}")
        return

    if df is None or df.empty:
        log.info("No earnings events found in the specified range.")
        return

    log.info(f"Retrieved {len(df)} total raw earnings events from Yahoo.")

    # Process events
    events_to_save = []
    for ticker, row in df.iterrows():
        ticker_str = str(ticker).upper().strip()
        if not ticker_str or ticker_str == "NAN":
            continue

        market_cap = float(row.get("Marketcap", 0.0) or 0.0)
        company = str(row.get("Company", ""))

        # Filtering logic: Keep if in CORE_WATCHLIST or market_cap >= min_market_cap
        # Enforce US stocks only: exclude non-US suffixes or 5-letter tickers ending in 'F' (foreign F-shares)
        if "." in ticker_str:
            continue
        if len(ticker_str) == 5 and ticker_str.endswith("F"):
            continue

        is_watchlist = ticker_str in CORE_WATCHLIST
        is_large_cap = market_cap >= min_market_cap

        if not (is_watchlist or is_large_cap):
            continue

        event_date_raw = row.get("Event Start Date")
        if not event_date_raw:
            continue

        # Parse timing (BMO vs AMC)
        timing_str = str(row.get("Timing", "")).lower()
        before_market = True
        if "after" in timing_str or "amc" in timing_str or "post" in timing_str:
            before_market = False

        # Convert date safely
        if isinstance(event_date_raw, str):
            try:
                event_date = datetime.fromisoformat(event_date_raw.replace("Z", "+00:00"))
            except ValueError:
                # Try simple format YYYY-MM-DD
                event_date = datetime.strptime(event_date_raw.split(" ")[0], "%Y-%m-%d")
        else:
            # Pandas timestamp or datetime
            event_date = event_date_raw.to_pydatetime() if hasattr(event_date_raw, "to_pydatetime") else event_date_raw

        events_to_save.append({
            "ticker": ticker_str,
            "earningsDate": event_date,
            "beforeMarket": before_market,
            "company": company,
            "marketCap": market_cap
        })

    log.info(f"Filtered down to {len(events_to_save)} high-impact/watchlist earnings events.")

    if dry_run:
        log.info("Dry run enabled. The following events would be saved:")
        for ev in events_to_save[:10]:
            timing = "BMO (Pre-Market)" if ev["beforeMarket"] else "AMC (Post-Market)"
            log.info(f" - {ev['ticker']} ({ev['company']}) on {ev['earningsDate'].date()} {timing} [Cap: ${ev['marketCap']/1e9:.1f}B]")
        if len(events_to_save) > 10:
            log.info(f" ... and {len(events_to_save)-10} more.")
        return

    # Persist to database
    saved_count = 0
    if Prisma is not None:
        try:
            db = Prisma()
            await db.connect()
            for ev in events_to_save:
                # Convert datetime to offset-aware UTC timezone if it is naive
                dt = ev["earningsDate"]
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                # Perform Prisma Upsert
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
                            "source": "yfinance",
                            "company": ev["company"],
                            "marketCap": ev["marketCap"]
                        },
                        "update": {
                            "beforeMarket": ev["beforeMarket"],
                            "confirmed": True,
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
        
        # Clear existing entries in the range to prune filtered-out / non-US elements
        start_range_str = start_date.strftime("%Y-%m-%d") + "T00:00:00.000+00:00"
        end_range_str = end_date.strftime("%Y-%m-%d") + "T23:59:59.999+00:00"
        cursor.execute(
            "DELETE FROM EarningsCalendar WHERE earningsDate >= ? AND earningsDate <= ?",
            (start_range_str, end_range_str)
        )
        
        for ev in events_to_save:
            # Format datetime for SQLite
            dt_str = ev["earningsDate"].isoformat()
            if not dt_str.endswith("Z") and "+" not in dt_str:
                dt_str += "+00:00"

            cursor.execute(
                "INSERT INTO EarningsCalendar (id, ticker, earningsDate, beforeMarket, confirmed, source, fetchedAt, company, marketCap) VALUES (?, ?, ?, ?, 1, 'yfinance', ?, ?, ?)",
                (uuid.uuid4().hex, ev["ticker"], dt_str, 1 if ev["beforeMarket"] else 0, now_str, ev["company"], ev["marketCap"])
            )
            saved_count += 1
        conn.commit()
        conn.close()
        log.info(f"Successfully upserted {saved_count} earnings events via fallback SQLite.")
    except Exception as e:
        log.error(f"Failed to write to SQLite: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync earnings calendar to database.")
    parser.add_argument("--days", type=int, default=7, help="Number of days forward to sync.")
    parser.add_argument("--min-cap", type=float, default=5e9, help="Minimum market cap in USD (default: 5B).")
    parser.add_argument("--dry-run", action="store_true", help="Print preview without writing to database.")
    args = parser.parse_args()

    asyncio.run(run_sync(args.days, args.min_cap, args.dry_run))
