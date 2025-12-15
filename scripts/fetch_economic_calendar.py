import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import uuid
import os
import time

# Configuration
DB_PATH = 'web/prisma/dev.db'
URL = "https://finance.yahoo.com/calendar/economic"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

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

def fetch_details(date_str):
    """
    Fetch economic calendar for a specific date (YYYY-MM-DD)
    """
    params = {'day': date_str}
    headers = {'User-Agent': USER_AGENT}
    
    print(f"Fetching data for {date_str}...")
    try:
        response = requests.get(URL, params=params, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching {date_str}: Status {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Yahoo table structure changes, but typically looking for table rows
        # This is a best-effort scraping logic
        table = soup.find('table')
        if not table:
            print("No table found.")
            return []
            
        rows = table.find_all('tr')
        events = []
        
        for row in rows[1:]: # Skip header
            cols = row.find_all('td')
            if len(cols) < 5:
                continue
                
            # Extract time
            time_str = cols[0].text.strip()
            # Extract country/currency (often in 2nd col or separate)
            # Yahoo format: 12:00 AM EST | Country | Event | Actual | Forecast | Previous
            
            # Simple extraction strategy:
            # col 0: Time
            # col 1: Country (we want US mostly)
            # col 2: Event Name
            # col 3: Event Type/Impact (Not always clear, sometimes implicit)
            # col 4+: Data
            
            country = cols[1].text.strip()
            if country != 'United States':
                continue # Filter for US only for now to reduce noise
                
            event_name = cols[2].text.strip()
            
            # Parse datetime
            # Date is date_str, Time is time_str (e.g. "9:30 AM")
            try:
                dt_str = f"{date_str} {time_str}"
                # Handle "Day 1" or implicit times if needed
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
                # Adjust timezone if needed (Yahoo is usually ET)
                # Storing as naive local or UTC? Prisma usually expects ISO string.
                # Let's import dateutil if complex, else assume basic parsing
            except ValueError:
                # Fallback for "All Day" or weird formats
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")

            # Store event
            events.append({
                'id': str(uuid.uuid4()), # Generate ID
                'datetime': dt.isoformat(),
                'name': event_name,
                'impact': 'MEDIUM', # Default, parsing impact is hard on Yahoo
                'createdAt': datetime.datetime.now().isoformat()
            })
            
        return events

    except Exception as e:
        print(f"Error parsing {date_str}: {e}")
        return []

def save_events(events):
    if not events:
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"Saving {len(events)} events...")
    
    for event in events:
        # Check if exists (duplicate check by name + date roughly)
        # Using a simplistic check or just insert (Prisma DB doesn't have unique constraint on name+date in our schema yet)
        # But let's try to avoid duplicates if possible.
        
        # Schema: id, datetime, name, impact, actual, forecast, previous, createdAt (no updated at?)
        # We need to map to DB columns.
        # DB Table is 'EconomicEvent' (PascalCase in Prisma becomes title case usually, checking schema)
        # Prisma creates tables as 'EconomicEvent' usually (sqlite preserves case?)
        # Let's check table name.
        
        # In SQLite, Prisma defaults: "EconomicEvent"
        
        try:
            # Since we don't have a unique key, we might insert duplicates. 
            # Ideally we check:
            cursor.execute("SELECT id FROM EconomicEvent WHERE name = ? AND datetime = ?", (event['name'], event['datetime']))
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute(
                    "INSERT INTO EconomicEvent (id, datetime, name, impact, createdAt) VALUES (?, ?, ?, ?, ?)",
                    (event['id'], event['datetime'], event['name'], event['impact'], event['createdAt'])
                )
        except Exception as e:
            print(f"Error inserting event {event['name']}: {e}")
            
    conn.commit()
    conn.close()

def main():
    # Fetch for this week
    today = datetime.date.today()
    
    for i in range(5): # Next 5 days
        d = today + datetime.timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        events = fetch_details(date_str)
        save_events(events)
        time.sleep(1) # Be polite

if __name__ == "__main__":
    main()
