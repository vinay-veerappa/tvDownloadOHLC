
import sqlite3
import pandas as pd
import json
import os

# Paths
PRISMA_DB = r"web\prisma\dev.db"
PROFILER_JSON = r"data\NQ1_profiler.json"
VWAP_PARQUET = r"data\indicators\NQ1_1m_vwap.parquet"
OPENING_RANGE = r"data\NQ1_opening_range.json"

print("--- Data Source Probe ---")

# 1. Prisma DB (News)
print(f"\n1. Probing Prisma DB: {PRISMA_DB}")
print(f"Exists? {os.path.exists(PRISMA_DB)}")
if os.path.exists(PRISMA_DB):
    try:
        conn = sqlite3.connect(PRISMA_DB)
        # Check tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables found: {len(tables)}")
        
        if 'EconomicEvent' in tables:
            print("Table 'EconomicEvent' found.")
            cursor.execute("SELECT count(*) FROM EconomicEvent")
            count = cursor.fetchone()[0]
            print(f"Events count: {count}")
            # Sample
            cursor.execute("SELECT * FROM EconomicEvent LIMIT 1")
            print(f"Sample: {cursor.fetchone()}")
        else:
            print("WARNING: 'EconomicEvent' table NOT found.")
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

# 2. Profiler JSON
print(f"\n2. Probing Profiler JSON: {PROFILER_JSON}")
try:
    with open(PROFILER_JSON, 'r') as f:
        data = json.load(f)
        print(f"Records loaded: {len(data)}")
        print(f"Sample Status: {data[0].get('status')}")
except Exception as e:
    print(f"JSON Error: {e}")

# 3. Opening Range JSON
print(f"\n3. Probing Opening Range JSON: {OPENING_RANGE}")
try:
    with open(OPENING_RANGE, 'r') as f:
        data = json.load(f)
        print(f"Records loaded: {len(data)}")
        print(f"Sample Range: {data[0].get('range_pts')}")
except Exception as e:
    print(f"JSON Error: {e}")

# 4. VWAP Parquet
print(f"\n4. Probing VWAP Parquet: {VWAP_PARQUET}")
try:
    df = pd.read_parquet(VWAP_PARQUET)
    print(f"Rows loaded: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    print("Sample:\n", df.head(1))
except Exception as e:
    print(f"Parquet Error: {e}")
