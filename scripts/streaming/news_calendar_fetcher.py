"""
ForexFactory News Calendar Fetcher for NinjaTrader ORB Strategy
================================================================
Fetches today's USD high/medium impact economic events from ForexFactory's
free XML feed and writes a simple CSV that NinjaScript can read at session start.

Usage:
    python news_calendar_fetcher.py                    # Fetch this week + next week (DEFAULT)
    python news_calendar_fetcher.py --day               # Fetch single trading day (Today or Tomorrow if > 5pm ET)
    python news_calendar_fetcher.py --date 2026-02-12  # Fetch specific date

Output: news_blackout.csv in the configured output directory
Format: date,time_et,impact,event_name

Schedule this to run daily before 9:00 AM ET (e.g., Windows Task Scheduler, cron).

Data Source: ForexFactory XML feed (free, no API key required)
    Primary:  https://nfs.faireconomy.media/ff_calendar_thisweek.xml
    Backup:   https://nfs.faireconomy.media/ff_calendar_nextweek.xml
"""

import xml.etree.ElementTree as ET
import requests
import csv
import os
import sys
import argparse
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import asyncio
from dotenv import load_dotenv

# Load env variables from web/.env BEFORE importing and starting Prisma
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../web/.env"))
load_dotenv(dotenv_path)

from prisma import Prisma

# =============================================================================
# CONFIGURATION — Edit these to match your setup
# =============================================================================

# Where to write the CSV that NinjaTrader will read
# Default: NinjaTrader 8 user data directory
OUTPUT_DIR = os.path.expanduser("~/Documents/NinjaTrader 8/bin/Custom")
OUTPUT_FILENAME = "news_blackout.csv"

# Filter settings
CURRENCIES = ["USD"]                    # Only USD events matter for NQ/ES
IMPACT_LEVELS = ["High", "Medium","Low"]      # "High", "Medium", "Low", "Holiday"
                                         # Set to ["High"] for only red-folder events

# Pre/Post buffer defaults (written to CSV header for reference)
DEFAULT_PRE_MINUTES = 1
DEFAULT_POST_MINUTES = 2

# =============================================================================
# FETCHER
# =============================================================================

FF_XML_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"  #,
    #"https://nfs.faireconomy.media/ff_calendar_nextweek.xml",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NewsCalendarFetcher/1.0"
}


def fetch_xml(url: str, timeout: int = 15) -> str:
    """Fetch XML content from URL."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_ff_xml(xml_text: str, target_date: date = None,
                 currencies: list = None, impacts: list = None) -> list:
    """
    Parse ForexFactory XML and return filtered events.
    
    ForexFactory XML format:
    <weeklyevents>
      <event>
        <title>CPI m/m</title>
        <country>USD</country>
        <date>02-12-2026</date>
        <time>8:30am</time>
        <impact>High</impact>
        <forecast>0.3%</forecast>
        <previous>0.4%</previous>
      </event>
      ...
    </weeklyevents>
    """
    if currencies is None:
        currencies = CURRENCIES
    if impacts is None:
        impacts = IMPACT_LEVELS

    root = ET.fromstring(xml_text)
    events = []

    for event_el in root.findall(".//event"):
        title = event_el.findtext("title", "").strip()
        country = event_el.findtext("country", "").strip()
        date_str = event_el.findtext("date", "").strip()
        time_str = event_el.findtext("time", "").strip()
        impact = event_el.findtext("impact", "").strip()
        forecast = event_el.findtext("forecast", "").strip()
        previous = event_el.findtext("previous", "").strip()

        # Filter by currency
        if currencies and country not in currencies:
            continue

        # Filter by impact
        if impacts and impact not in impacts:
            continue

        # Parse date (MM-DD-YYYY format from FF)
        try:
            event_date = datetime.strptime(date_str, "%m-%d-%Y").date()
        except ValueError:
            continue

        # Filter by target date if specified
        if target_date and event_date != target_date:
            continue

        # Parse time (ET) - FF XML times are effectively GMT
        # Some events have "All Day" or "Tentative" or empty time
        time_et = ""
        final_date_str = event_date.strftime("%Y-%m-%d")

        if time_str and time_str.lower() not in ["", "all day", "tentative"]:
            pt = None
            try:
                pt = datetime.strptime(time_str, "%I:%M%p").time()
            except ValueError:
                try:
                    # Try without minutes: "8am"
                    pt = datetime.strptime(time_str, "%I%p").time()
                except ValueError:
                    pass

            if pt:
                # Combine with date (GMT) and convert to Eastern
                dt_gmt = datetime.combine(event_date, pt).replace(tzinfo=ZoneInfo("UTC"))
                dt_est = dt_gmt.astimezone(ZoneInfo("America/New_York"))
                
                time_et = dt_est.strftime("%H:%M")  # 24-hour format
                final_date_str = dt_est.strftime("%Y-%m-%d")

        if not time_et:
            continue  # Skip events without a specific time

        events.append({
            "date": final_date_str,
            "time_et": time_et,
            "impact": impact,
            "event": title,
            "country": country,  # Store the currency code (e.g. "USD", "EUR")
            "forecast": forecast,
            "previous": previous,
        })

    # Sort by time
    events.sort(key=lambda x: x["time_et"])
    return events


async def save_to_prisma(events: list):
    """Save events to the Prisma EconomicEvent model."""
    db = Prisma()
    try:
        await db.connect()
        count = 0
        for ev in events:
            # Create datetime in UTC for storage
            # Note: ev['date'] is YYYY-MM-DD, ev['time_et'] is HH:MM
            dt_str = f"{ev['date']} {ev['time_et']}"
            dt_et = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/New_York"))
            dt_utc = dt_et.astimezone(ZoneInfo("UTC"))

            # Check for existing event to avoid duplicates
            # (Simple check: same name and same timestamp)
            existing = await db.economicevent.find_first(
                where={
                    'name': ev['event'],
                    'datetime': dt_utc
                }
            )

            if not existing:
                await db.economicevent.create(
                    data={
                        'name': ev['event'],
                        'datetime': dt_utc,
                        'impact': ev['impact'].upper(),
                        'country': ev.get('country', 'USD'),  # Store the currency/country
                        'forecast': float(ev['forecast'].replace('%','')) if ev['forecast'] and '%' in ev['forecast'] else None,
                        'previous': float(ev['previous'].replace('%','')) if ev['previous'] and '%' in ev['previous'] else None,
                    }
                )
                count += 1
        return count
    except Exception as e:
        print(f"    Error saving to Prisma: {e}")
        return 0
    finally:
        await db.disconnect()

def write_csv(events: list, output_path: str):
    """
    Write events to CSV in format NinjaScript can easily parse.
    
    Format:
    # News Blackout Calendar - Generated 2026-02-12 08:00:00
    # Pre-buffer: 1 min, Post-buffer: 2 min
    date,time_et,impact,event
    2026-02-12,08:30,High,CPI m/m
    2026-02-12,09:45,Medium,Flash Manufacturing PMI
    2026-02-12,10:00,High,CB Consumer Confidence
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="") as f:
        f.write(f"# News Blackout Calendar - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Pre-buffer: {DEFAULT_PRE_MINUTES} min, Post-buffer: {DEFAULT_POST_MINUTES} min\n")

        writer = csv.DictWriter(f, fieldnames=["date", "time_et", "impact", "event"])
        writer.writeheader()
        for event in events:
            writer.writerow({
                "date": event["date"],
                "time_et": event["time_et"],
                "impact": event["impact"],
                "event": event["event"],
            })

    return len(events)


def fetch_and_save(target_date: date = None, fetch_week: bool = False,
                   output_dir: str = None, output_filename: str = None):
    """Main entry point: fetch, filter, and save."""
    if target_date is None:
        target_date = date.today()

    if output_dir is None:
        output_dir = OUTPUT_DIR
    if output_filename is None:
        output_filename = OUTPUT_FILENAME

    output_path = os.path.join(output_dir, output_filename)

    print(f"Fetching ForexFactory calendar...")
    print(f"  Target date: {target_date if not fetch_week else 'Full week'}")
    print(f"  Currencies:  {CURRENCIES}")
    print(f"  Impact:      {IMPACT_LEVELS}")
    print(f"  Output:      {output_path}")
    print()

    all_events = []

    for url in FF_XML_URLS:
        try:
            print(f"  Fetching {url}...")
            xml_text = fetch_xml(url)
            events = parse_ff_xml(
                xml_text,
                target_date=None if fetch_week else target_date,
                currencies=CURRENCIES,
                impacts=IMPACT_LEVELS,
            )
            all_events.extend(events)
            print(f"    Found {len(events)} matching events")

            # If we found events for today in thisweek, skip nextweek
            if events and not fetch_week:
                break
        except Exception as e:
            print(f"    Error: {e}")
            continue

    # Deduplicate by (date, time, event)
    seen = set()
    unique_events = []
    for ev in all_events:
        key = (ev["date"], ev["time_et"], ev["event"])
        if key not in seen:
            seen.add(key)
            unique_events.append(ev)

    unique_events.sort(key=lambda x: (x["date"], x["time_et"]))

    if unique_events:
        count = write_csv(unique_events, output_path)
        print(f"\n  Wrote {count} events to {output_path}")
        print("\n  Events:")
        for ev in unique_events:
            impact_marker = "[High]" if ev["impact"] == "High" else "[Medium]" if ev["impact"] == "Medium" else "[Low]"
            try:
                emoji = "🔴" if ev["impact"] == "High" else "🟠" if ev["impact"] == "Medium" else "🟡"
                print(f"    {emoji} {ev['date']} {ev['time_et']} ET - {ev['event']} ({ev['impact']})")
            except UnicodeEncodeError:
                print(f"    {impact_marker} {ev['date']} {ev['time_et']} ET - {ev['event']} ({ev['impact']})")
    else:
        # Write empty CSV (no blackouts today)
        write_csv([], output_path)
        print(f"\n  No matching events found. Wrote empty CSV (no blackouts).")

    return unique_events


# =============================================================================
# CLI
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description="Fetch ForexFactory economic calendar for NinjaTrader news blackout")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD). If set, fetches this specific date.")
    parser.add_argument("--day", action="store_true", help="Fetch single trading day (Today, or Tomorrow if > 17:00 ET). Default is FULL WEEK.")
    parser.add_argument("--week", action="store_true", help="Deprecated: Weekly fetch is now default.")
    parser.add_argument("--output-dir", type=str, default=None, help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_argument("--output-file", type=str, default=None, help=f"Output filename (default: {OUTPUT_FILENAME})")
    parser.add_argument("--impacts", type=str, default=None, help='Comma-separated impact levels (default: "High,Medium")')
    parser.add_argument("--currencies", type=str, default=None, help='Comma-separated currencies (default: "USD")')

    args = parser.parse_args()

    # Determine mode:
    # 1. Specific Date text provided -> Fetch that date
    # 2. --day flag provided -> Fetch single trading day (Today or Tomorrow)
    # 3. Default -> Fetch full week (This Week + Next Week)
    
    fetch_week_mode = True
    target = None

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
        fetch_week_mode = False
    elif args.day:
        fetch_week_mode = False
        # Determine "Trading Day" based on ET time (rollover at 17:00 / 5pm)
        now_utc = datetime.now(ZoneInfo("UTC"))
        now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
        
        # If it's 5:00 PM ET or later, use tomorrow's date
        if now_et.hour >= 17:
            target = now_et.date() + timedelta(days=1)
            print(f"Current time is {now_et.strftime('%H:%M')} ET (>= 17:00). Fetching for Trading Day: {target}")
        else:
            target = now_et.date()
            print(f"Current time is {now_et.strftime('%H:%M')} ET (< 17:00). Fetching for Trading Day: {target}")
    else:
        # Default: Fetch week
        fetch_week_mode = True
        target = date.today()  # Placeholder, won't be used for filtering in week mode
        print("Fetching full week schedule (Default)...")

    if args.impacts:
        IMPACT_LEVELS[:] = [x.strip() for x in args.impacts.split(",")]
    if args.currencies:
        CURRENCIES[:] = [x.strip() for x in args.currencies.split(",")]

    events = fetch_and_save(
        target_date=target,
        fetch_week=fetch_week_mode,
        output_dir=args.output_dir,
        output_filename=args.output_file,
    )

    if events:
        db_count = await save_to_prisma(events)
        print(f"  Added {db_count} new events to Prisma DB.")

if __name__ == "__main__":
    asyncio.run(main())
