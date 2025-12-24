
import asyncio
from prisma import Prisma
import pandas as pd
import subprocess
import os
import json
import datetime
import sys
import numpy as np

# Configuration
DOLT_DIR = "data/options/options"
BACKUP_DIR = "data/backups"

# Load Environment
try:
    with open('web/.env', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v.strip('"').strip("'")
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

async def backup_current_db(db):
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(BACKUP_DIR, f"em_history_backup_{timestamp}.json")
    
    print(f"Backing up ExpectedMoveHistory to {filename}...")
    records = await db.expectedmovehistory.find_many()
    
    # Convert to JSON-serializable
    data = []
    for r in records:
        item = r.dict()
        # Handle datetime
        for k, v in item.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                item[k] = v.isoformat()
        data.append(item)
        
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Backup complete. {len(data)} records saved.")

def update_dolt_db():
    print(f"Updating Dolt DB in {DOLT_DIR}...")
    try:
        # Run dolt pull
        # result = subprocess.run(["dolt", "pull"], cwd=DOLT_DIR, capture_output=True, text=True)
        # For now, just print status/log as pull might require auth or be slow.
        # Check status first
        subprocess.run(["dolt", "status"], cwd=DOLT_DIR, check=True)
        
        # User requested update:
        print("Running 'dolt pull'...")
        res = subprocess.run(["dolt", "pull"], cwd=DOLT_DIR, capture_output=True, text=True)
        print(res.stdout)
        if res.returncode != 0:
            print(f"Warning: Dolt pull failed: {res.stderr}")
    except Exception as e:
        print(f"Dolt Update Error: {e}")

def query_dolt_straddles(target_date_str=None):
    print("Querying Dolt for Option Chain data...")
    
    if not target_date_str:
        target_date_str = datetime.date.today().strftime("%Y-%m-%d")
        
    # We want to find the straddle for the target date.
    # But usually Dolt has historical data. 
    # Let's find the MOST RECENT date in Dolt.
    
    sql_max_date = 'dolt sql -q "SELECT MAX(date) FROM option_chain" -r csv'
    res = subprocess.run(sql_max_date, cwd=DOLT_DIR, shell=True, capture_output=True, text=True)
    last_date_available = res.stdout.strip().split('\n')[-1] # simplistic parsing
    print(f"Latest Dolt Data Date: {last_date_available}")
    
    # Query Data for that User-specified date OR latest
    query_date = target_date_str if target_date_str <= last_date_available else last_date_available
    print(f"Using Query Date: {query_date}")
    
    # SQL to get Straddles efficiently is complex in one go.
    # Use pandas to load chunk of raw data for that date and process in python is easier given CLI limits.
    
    sql = f"""
    SELECT date, act_symbol, expiration, strike, call_put, bid, ask 
    FROM option_chain 
    WHERE date = '{query_date}' 
    AND call_put IN ('Call', 'Put')
    """
    
    # Run query and load to DF
    # Use -r csv
    cmd = ['dolt', 'sql', '-q', sql, '-r', 'csv']
    print("Executing SQL extraction...")
    try:
        res = subprocess.run(cmd, cwd=DOLT_DIR, capture_output=True, text=True) # check=True might fail if empty
        if res.returncode != 0:
            print("SQL Error:", res.stderr)
            return pd.DataFrame()
            
        from io import StringIO
        df = pd.read_csv(StringIO(res.stdout))
        return df
    except Exception as e:
        print(f"Query Error: {e}")
        return pd.DataFrame()

async def compare_and_sync():
    db = Prisma()
    await db.connect()
    
    # 1. Backup
    await backup_current_db(db)
    
    # 2. Update Dolt
    update_dolt_db()
    
    # 3. Query Dolt
    # Determine "Today" or specific date? 
    # For sync, we probably want to sync the LATEST Dolt data to our History.
    df = query_dolt_straddles()
    
    if df.empty:
        print("No data retrieved from Dolt.")
        await db.disconnect()
        return

    print(f"Processing {len(df)} rows from Dolt...")
    
    # Logic similar to build_unified
    # Group by symbol, expiration...
    # We need Underlying Price to find ATM? 
    # Dolt 'option_chain' usually doesn't have underlying price in every row.
    # We might need to query 'underlying_chain' or similar if exists, or infer from somewhere.
    # OR assume we just find the strike with minimum |Call-Put| delta (Price roughly equals strike where C=P)
    # OR just take the strike where C+P is minimized? No.
    # Approximation: Strike where Abs(CallPrice - PutPrice) is minimized is the ATM strike.
    
    processed_ems = []
    
    # Filter for tickers we care about
    TICKERS = ["SPY", "QQQ", "IWM", "SPX", "NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "GOOGL", "META"] # Add more as needed
    
    df = df[df['act_symbol'].isin(TICKERS)]
    
    for symbol, group in df.groupby('act_symbol'):
        # Need closest expiry
        # Find min expiry >= date
        date_val = group['date'].iloc[0] # String YYYY-MM-DD
        
        # Sort expirations
        exps = sorted(group['expiration'].unique())
        # Filter exps >= date
        valid_exps = [e for e in exps if e >= date_val]
        if not valid_exps: continue
        target_exp = valid_exps[0]
        
        chain = group[group['expiration'] == target_exp]
        
        # Find ATM Strike (Min Abs(Call-Put))
        # Pivot
        calls = chain[chain['call_put'] == 'Call'].set_index('strike')[['bid', 'ask']]
        puts = chain[chain['call_put'] == 'Put'].set_index('strike')[['bid', 'ask']]
        
        # Inner join on strike
        merged = calls.join(puts, lsuffix='_c', rsuffix='_p', how='inner')
        if merged.empty: continue
        
        # Mid prices
        merged['mid_c'] = (merged['bid_c'] + merged['ask_c']) / 2
        merged['mid_p'] = (merged['bid_p'] + merged['ask_p']) / 2
        
        # Delta
        merged['diff'] = abs(merged['mid_c'] - merged['mid_p'])
        
        # ATM Row
        atm_row = merged.loc[merged['diff'].idxmin()]
        atm_strike = atm_row.name
        
        straddle_price = atm_row['mid_c'] + atm_row['mid_p']
        # Estimated Underlying Price (Strike + Diff? roughly Strike)
        # Better: From Put-Call Parity: C - P = S - K (ignoring r, div) => S = C - P + K
        est_spot = atm_row['mid_c'] - atm_row['mid_p'] + atm_strike
        
        # EM Calc
        em_straddle = straddle_price * 0.85
        
        print(f"{symbol} ({date_val}): Spot~{est_spot:.2f}, Straddle={straddle_price:.2f}, EM={em_straddle:.2f}")
        
        processed_ems.append({
            'ticker': symbol,
            'date': datetime.datetime.strptime(date_val, "%Y-%m-%d"),
            'price': est_spot,
            'straddle': straddle_price,
            'em': em_straddle
        })

    # 4. Compare and Update
    print("\n--- Comparing with DB ---")
    for item in processed_ems:
        # Fetch existing
        existing = await db.expectedmovehistory.find_unique(
            where={'ticker_date': {'ticker': item['ticker'], 'date': item['date']}}
        )
        
        if existing:
            diff = abs(existing.emStraddle - item['em']) if existing.emStraddle else item['em']
            print(f"{item['ticker']}: DB={existing.emStraddle:.2f} vs Dolt={item['em']:.2f} (Diff: {diff:.2f})")
            
            # Update logic: Only if Dolt is significantly different or if user enforced?
            # User said "update the expected move". 
            # Let's update source to 'dolt_sync'
            
            await db.expectedmovehistory.update(
                where={'id': existing.id},
                data={
                    'straddlePrice': item['straddle'],
                    'emStraddle': item['em'],
                    'source': 'dolt_sync_v1'
                }
            )
        else:
            print(f"{item['ticker']}: New Record from Dolt")
            await db.expectedmovehistory.create(
                data={
                    'ticker': item['ticker'],
                    'date': item['date'],
                    'closePrice': item['price'],
                    'straddlePrice': item['straddle'],
                    'emStraddle': item['em'],
                    'source': 'dolt_sync_v1'
                }
            )

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(compare_and_sync())
