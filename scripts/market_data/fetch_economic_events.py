import sqlite3
import argparse
from datetime import datetime, timedelta
import os
import sys
import pytz

# DB Path
DB_PATH = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"

def fetch_events(target_date_str, print_output=True, us_only=False):
    """
    Fetch economic events for a specific date from the Prisma SQLite DB.
    target_date_str: YYYY-MM-DD
    Returns list of event strings.
    """
    if not os.path.exists(DB_PATH):
        if print_output: print(f"Error: Database not found at {DB_PATH}")
        return []
    
    event_list = []
    
    # Non-US keywords to exclude if us_only is True
    EXCLUDE_KEYWORDS = [
        "German", "French", "Spanish", "Italian", "Eurozone", 
        "UK ", "JPY", "AUD", "CAD", "CNY", "Swiss", "ECB President", 
        "EU ", "Australian", "British", "Canadian", "Japanese", "Chinese"
    ]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Prisma usually stores DateTimes as milliseconds since epoch or ISO strings.
        # Checking the schema, it's 'DateTime', which in SQLite via Prisma is typically milliseconds (BigInt) or textual ISO.
        # Let's assume text ISO or check. If it fails, we might need to adjust.
        # A common Prismal/SQLite pattern is storing as Real or Integer, but let's try string matching YYYY-MM-DD first.
        # Actually proper way: range query.
        
        # Convert target date to range
        # We'll try a generous text match first as it's easiest for debugging 
        # but if stored as unix timestamp we need conversion.
        # Let's inspect ONE row to see format if possible? 
        # No, let's write robust code.
        
        # Try finding ANY events to deduce format? No, stick to pattern.
        # We will try LIKE first.
        
        # Convert target date string to start and end millisecond timestamps
        day_start = datetime.strptime(target_date_str, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
        
        start_ms = int(day_start.timestamp() * 1000)
        end_ms = int(day_end.timestamp() * 1000)
        
        query = """
        SELECT datetime, name, impact, actual, forecast, previous 
        FROM EconomicEvent 
        WHERE (
            (datetime >= ? AND datetime < ?) -- Integer ms match
            OR (datetime LIKE ?)             -- String ISO match
        )
        AND impact IN ('HIGH', 'MEDIUM')
        ORDER BY datetime ASC
        """
        
        date_pattern = f"{target_date_str}%"
        cursor.execute(query, (start_ms, end_ms, date_pattern))
        rows = cursor.fetchall()
        
        if print_output: print(f"\n📅 ECONOMIC EVENTS FOR {target_date_str}:")
        if not rows:
            if print_output: print("   (No HIGH/MEDIUM impact events found in DB)")
        else:
            local_tz = pytz.timezone('US/Eastern')
            for row in rows:
                dt_raw, name, impact, actual, forecast, prev = row
                
                # Convert to US/Eastern
                try:
                    if isinstance(dt_raw, str):
                        # ISO format usually ends in Z for UTC
                        dt_utc = datetime.fromisoformat(dt_raw.replace('Z', '+00:00'))
                        dt_local = dt_utc.astimezone(local_tz)
                    else:
                        # Timestamp ms
                        dt_utc = datetime.fromtimestamp(dt_raw / 1000.0, tz=pytz.UTC)
                        dt_local = dt_utc.astimezone(local_tz)
                    
                    time_str = dt_local.strftime("%H:%M")
                except Exception as e:
                    time_str = str(dt_raw)[:10] # Fallback
                
                if us_only:
                    if any(kw in name for kw in EXCLUDE_KEYWORDS):
                        continue

                icon = "🔥" if impact == "HIGH" else "🔸"
                msg = f"{time_str:<8} [{icon} {impact:<6}] {name}"
                if print_output: print(f"   {msg}")
                event_list.append(msg)
                    
        conn.close()
        return event_list

    except Exception as e:
        print(f"Error querying database: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--us-only", action="store_true", help="Filter for US news only")
    args = parser.parse_args()
    fetch_events(args.date, us_only=args.us_only)
