import pandas as pd
import asyncio
from prisma import Prisma
import os
import numpy as np

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

async def run_vix_experiment():
    db = Prisma()
    await db.connect()
    
    print("\n=== VIX-based EM vs Straddle EM Experiment ===")
    
    # 1. Fetch SPY EM History (Target)
    spy_recs = await db.expectedmovehistory.find_many(
        where={'ticker': 'SPY'},
        order={'date': 'desc'}
    )
    
    if not spy_recs:
        print("No SPY EM history found for comparison.")
        await db.disconnect()
        return

    # 2. Load VIX Prices
    try:
        vix_df = pd.read_parquet('data/VIX_1d.parquet')
        if 'time' not in vix_df.columns:
            vix_df['time'] = vix_df.index
        vix_df['date_str'] = pd.to_datetime(vix_df['time']).dt.strftime('%Y-%m-%d')
        vix_map = vix_df.set_index('date_str')['close'].to_dict()
    except Exception as e:
        print(f"Error loading VIX data: {e}")
        await db.disconnect()
        return

    print(f"{'Date':<12} | {'SPY EM %':<10} | {'VIX':<8} | {'VIX EM %':<10} | {'Ratio'}")
    print("-" * 65)

    ratios = []
    for r in spy_recs:
        date_str = r.date.strftime('%Y-%m-%d')
        spy_px = r.closePrice
        spy_em = r.emStraddle
        
        if not spy_em or not spy_px: continue
        
        vix_val = vix_map.get(date_str)
        if not vix_val: continue
        
        # VIX EM % (1-day) = (VIX / 100) * sqrt(1/252)
        vix_em_pct = (vix_val / 100.0) * np.sqrt(1/252.0)
        spy_em_pct = spy_em / spy_px
        
        ratio = spy_em_pct / vix_em_pct
        ratios.append(ratio)
        
        print(f"{date_str:<12} | {spy_em_pct*100:<9.2f}% | {vix_val:<8.2f} | {vix_em_pct*100:<9.2f}% | {ratio:.2f}")
        
    if ratios:
        print("\n=== Statistics ===")
        print(f"Average Ratio (Straddle/VIX): {np.mean(ratios):.2f}")
        print(f"Median Ratio: {np.median(ratios):.2f}")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(run_vix_experiment())
