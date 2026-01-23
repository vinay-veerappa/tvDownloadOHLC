import sqlite3
import argparse
from datetime import datetime, timedelta
import os
import sys

# DB Path
DB_PATH = "c:/Users/vinay/tvDownloadOHLC/web/prisma/dev.db"

def fetch_events(target_date_str):
    """
    Fetch economic events for a specific date from the Prisma SQLite DB.
    target_date_str: YYYY-MM-DD
    """
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

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
        
        query = """
        SELECT datetime, name, impact, actual, forecast, previous 
        FROM EconomicEvent 
        WHERE datetime LIKE ? 
        AND impact IN ('HIGH', 'MEDIUM')
        ORDER BY datetime ASC
        """
        
        date_pattern = f"{target_date_str}%"
        cursor.execute(query, (date_pattern,))
        rows = cursor.fetchall()
        
        print(f"\n📅 ECONOMIC EVENTS FOR {target_date_str}:")
        if not rows:
            # Fallback: Maybe stored as numeric timestamp?
            # Let's not guess too much, just print empty for now.
            print("   (No HIGH/MEDIUM impact events found in DB)")
        else:
            for row in rows:
                dt_raw, name, impact, actual, forecast, prev = row
                
                # Format Time
                time_str = str(dt_raw)
                try:
                    # Attempt to parse ISO string
                    # 2026-01-21T08:30:00.000Z
                   if isinstance(dt_raw, str):
                       dt = datetime.fromisoformat(dt_raw.replace('Z', '+00:00'))
                       # Convert to Local/ET? Assume data is UTC.
                       # Simple hack: just show the time part, maybe subtract 5h for ET if it's UTC.
                       # Better: Just print raw time for now.
                       time_str = dt.strftime("%H:%M") + " (UTC)" 
                   elif isinstance(dt_raw, int):
                       # Timestamp ms
                       dt = datetime.fromtimestamp(dt_raw / 1000.0)
                       time_str = dt.strftime("%H:%M")
                except:
                    pass

                icon = "🔥" if impact == "HIGH" else "🔸"
                print(f"   {time_str:<12} [{icon} {impact:<6}] {name}")
                    
        conn.close()

    except Exception as e:
        print(f"Error querying database: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    fetch_events(args.date)
