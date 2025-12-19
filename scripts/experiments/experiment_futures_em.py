import pandas as pd
import asyncio
from prisma import Prisma
import os

# Load Environment
try:
    env_path = os.path.join(os.getcwd(), 'web', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v.strip('"').strip("'")
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

async def run_experiment():
    db = Prisma()
    await db.connect()
    
    print("\n=== Futures EM Proxy Experiment ===")
    
    # 1. Fetch SPY EM History (Base)
    spy_recs = await db.expectedmovehistory.find_many(
        where={'ticker': 'SPY'},
        order={'date': 'desc'}
    )
    
    if not spy_recs:
        print("No SPY EM history found for proxying.")
        await db.disconnect()
        return

    # 2. Load ES1 Prices
    try:
        es_df = pd.read_parquet('data/ES1_1d.parquet')
        
        # Handle index if 'time' not present
        if 'time' not in es_df.columns:
            es_df['time'] = es_df.index
            
        es_df['date_str'] = pd.to_datetime(es_df['time']).dt.strftime('%Y-%m-%d')
        es_map = es_df.set_index('date_str')['close'].to_dict()
    except Exception as e:
        print(f"Error loading ES1 data: {e}")
        await db.disconnect()
        return

    print(f"{'Date':<12} | {'SPY Px':<8} | {'SPY EM %':<10} | {'ES Px':<8} | {'ES Proxy EM':<8}")
    print("-" * 65)

    for r in spy_recs:
        date_str = r.date.strftime('%Y-%m-%d')
        spy_px = r.closePrice
        spy_em = r.emStraddle or r.em365
        
        if not spy_em or not spy_px: continue
        
        em_pct = spy_em / spy_px
        
        es_px = es_map.get(date_str)
        if not es_px:
            continue
            
        es_em = es_px * em_pct
        
        print(f"{date_str:<12} | {spy_px:<8.2f} | {em_pct*100:<9.2f}% | {es_px:<8.2f} | {es_em:<8.2f}")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(run_experiment())
