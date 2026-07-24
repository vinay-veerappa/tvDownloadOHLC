import sqlite3
import datetime
import uuid
import os
import time
from zoneinfo import ZoneInfo
import requests

# Configuration
DB_PATH = 'web/prisma/dev.db'
API_URL = "https://endpoints.investing.com/pd-instruments/v1/calendars/economic/events/occurrences"
CALENDAR_URL = "https://www.investing.com/economic-calendar/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
DEFAULT_COUNTRY_IDS = "25,32,6,37,72,22,17,39,14,10,35,43,36,110,11,26,12,4,5,56"
US_COUNTRY_ID = 5

def get_db_connection():
    # Adjust path if script is run from root or scripts dir
    if os.path.exists(DB_PATH):
        return sqlite3.connect(DB_PATH)
    elif os.path.exists(f'../{DB_PATH}'):
        return sqlite3.connect(f'../{DB_PATH}')
    elif os.path.exists('prisma/dev.db'):
        return sqlite3.connect('prisma/dev.db')
    else:
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

def normalize_name(meta: dict) -> str:
    name = (
        meta.get("event_translated")
        or meta.get("short_name")
        or meta.get("event_meta_title")
        or meta.get("long_name")
        or "Unknown Event"
    )
    name = str(name).strip()
    prefixes = ["U.S. ", "US ", "United States "]
    for p in prefixes:
        if name.startswith(p):
            return name[len(p) :].strip()
    return name

def normalize_importance(raw: str) -> str:
    v = (raw or "low").strip().lower()
    if v in {"high", "medium", "low"}:
        return v.upper()
    return "LOW"

def et_parts(iso_utc: str) -> tuple[str, str, datetime.datetime]:
    dt_utc = datetime.datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
    return dt_et.strftime("%Y-%m-%d"), dt_et.strftime("%H:%M ET"), dt_et

def fetch_events(start_date: datetime.date, end_date: datetime.date) -> list[dict]:
    session = requests.Session()
    session.get(CALENDAR_URL, headers={"User-Agent": USER_AGENT}, timeout=30)

    params = {
        "domain_id": 1,
        "limit": 500,
        "country_ids": "5",
    }

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Referer": CALENDAR_URL,
        "Origin": "https://www.investing.com",
    }

    # Convert start/end dates to UTC datetimes for the API
    start_dt = datetime.datetime.combine(start_date, datetime.time.min).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(datetime.timezone.utc)
    end_dt = datetime.datetime.combine(end_date, datetime.time.max).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(datetime.timezone.utc)
    
    query = dict(params)
    query["start_date"] = start_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    query["end_date"] = end_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    
    print(f"Fetching occurrences from {start_date} to {end_date}...")
    
    payload = None
    for attempt in range(1, 6):
        try:
            resp = session.get(API_URL, params=query, headers=headers, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception as e:
            if attempt == 5:
                print(f"Failed to fetch: {e}")
                return []
            time.sleep(0.8 * attempt)

    if payload is None:
        return []

    event_map = {}
    for e in payload.get("events", []):
        eid = e.get("event_id")
        if not isinstance(eid, int):
            continue
        event_map[eid] = {
            "country_id": int(e.get("country_id") or -1),
            "name": normalize_name(e),
            "importance": normalize_importance(str(e.get("importance") or "")),
        }

    events = []
    seen_occurrence_ids = set()
    for occ in payload.get("occurrences", []):
        oid = occ.get("occurrence_id")
        if not isinstance(oid, int) or oid in seen_occurrence_ids:
            continue
        seen_occurrence_ids.add(oid)

        eid = occ.get("event_id")
        meta = event_map.get(eid)
        if not meta or meta["country_id"] != US_COUNTRY_ID:
            continue

        occ_time = occ.get("occurrence_time")
        if not isinstance(occ_time, str):
            continue

        date_str, time_et, dt_et = et_parts(occ_time)
        
        events.append({
            'id': str(uuid.uuid4()),
            'datetime_ms': int(dt_et.timestamp() * 1000),
            'name': meta["name"],
            'impact': meta["importance"],
            'country': 'USD',  # This fetcher only fetches US (country_id=5)
            'createdAt_ms': int(datetime.datetime.now().timestamp() * 1000)
        })

    return events

def save_events(events):
    if not events:
        print("No events to save.")
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"Saving {len(events)} US events...")
    
    added = 0
    for event in events:
        try:
            # Check if an event with this exact time and name already exists to prevent duplicates
            cursor.execute("SELECT id FROM EconomicEvent WHERE name = ? AND datetime = ?", (event['name'], event['datetime_ms']))
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute(
                    "INSERT INTO EconomicEvent (id, datetime, name, impact, country, createdAt) VALUES (?, ?, ?, ?, ?, ?)",
                    (event['id'], event['datetime_ms'], event['name'], event['impact'], event.get('country', 'USD'), event['createdAt_ms'])
                )
                added += 1
            else:
                # Upsert: update the impact and country if it changed
                cursor.execute(
                    "UPDATE EconomicEvent SET impact = ?, country = COALESCE(country, ?) WHERE id = ?",
                    (event['impact'], event.get('country', 'USD'), exists[0])
                )
        except Exception as e:
            print(f"Error saving event {event['name']}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Added {added} new events, updated others.")

def main():
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=14)
    
    events = fetch_events(today, end_date)
    save_events(events)

if __name__ == "__main__":
    main()
