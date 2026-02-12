"""
ForexFactory News Calendar Fetcher for NinjaTrader ORB Strategy
================================================================
Fetches today's USD high/medium impact economic events from ForexFactory's
free XML feed and writes a simple CSV that NinjaScript can read at session start.

Usage:
    python news_calendar_fetcher.py                    # Fetch today's events
    python news_calendar_fetcher.py --date 2026-02-12  # Fetch specific date
    python news_calendar_fetcher.py --week              # Fetch full week

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
from pathlib import Path

# =============================================================================
# CONFIGURATION — Edit these to match your setup
# =============================================================================

# Where to write the CSV that NinjaTrader will read
# Default: NinjaTrader 8 user data directory
OUTPUT_DIR = os.path.expanduser("~/Documents/NinjaTrader 8/bin/Custom")
OUTPUT_FILENAME = "news_blackout.csv"

# Filter settings
CURRENCIES = ["USD"]                    # Only USD events matter for NQ/ES
IMPACT_LEVELS = ["High", "Medium"]      # "High", "Medium", "Low", "Holiday"
                                         # Set to ["High"] for only red-folder events

# Pre/Post buffer defaults (written to CSV header for reference)
DEFAULT_PRE_MINUTES = 1
DEFAULT_POST_MINUTES = 2

# =============================================================================
# FETCHER
# =============================================================================

FF_XML_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.xml",
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

        # Parse time (ET) - FF uses "8:30am", "10:00am", "2:00pm", etc.
        # Some events have "All Day" or "Tentative" or empty time
        time_et = ""
        if time_str and time_str.lower() not in ["", "all day", "tentative"]:
            try:
                parsed_time = datetime.strptime(time_str, "%I:%M%p")
                time_et = parsed_time.strftime("%H:%M")  # 24-hour format
            except ValueError:
                try:
                    # Try without minutes: "8am"
                    parsed_time = datetime.strptime(time_str, "%I%p")
                    time_et = parsed_time.strftime("%H:%M")
                except ValueError:
                    time_et = ""

        if not time_et:
            continue  # Skip events without a specific time

        events.append({
            "date": event_date.strftime("%Y-%m-%d"),
            "time_et": time_et,
            "impact": impact,
            "event": title,
            "forecast": forecast,
            "previous": previous,
        })

    # Sort by time
    events.sort(key=lambda x: x["time_et"])
    return events


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
            impact_marker = "🔴" if ev["impact"] == "High" else "🟠" if ev["impact"] == "Medium" else "🟡"
            print(f"    {impact_marker} {ev['date']} {ev['time_et']} ET - {ev['event']} ({ev['impact']})")
    else:
        # Write empty CSV (no blackouts today)
        write_csv([], output_path)
        print(f"\n  No matching events found. Wrote empty CSV (no blackouts).")

    return unique_events


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ForexFactory economic calendar for NinjaTrader news blackout")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD). Default: today")
    parser.add_argument("--week", action="store_true", help="Fetch full week instead of single day")
    parser.add_argument("--output-dir", type=str, default=None, help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_argument("--output-file", type=str, default=None, help=f"Output filename (default: {OUTPUT_FILENAME})")
    parser.add_argument("--impacts", type=str, default=None, help='Comma-separated impact levels (default: "High,Medium")')
    parser.add_argument("--currencies", type=str, default=None, help='Comma-separated currencies (default: "USD")')

    args = parser.parse_args()

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target = date.today()

    if args.impacts:
        IMPACT_LEVELS[:] = [x.strip() for x in args.impacts.split(",")]
    if args.currencies:
        CURRENCIES[:] = [x.strip() for x in args.currencies.split(",")]

    fetch_and_save(
        target_date=target,
        fetch_week=args.week,
        output_dir=args.output_dir,
        output_filename=args.output_file,
    )
