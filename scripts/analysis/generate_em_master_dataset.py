import pandas as pd
import numpy as np
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

async def generate_master_dataset():
    db = Prisma()
    await db.connect()
    
    ticker = 'SPY'
    print(f"Generating Master EM Dataset for {ticker}...")
    
    # 1. Fetch EM History from DB
    recs = await db.expectedmovehistory.find_many(
        where={'ticker': ticker},
        order={'date': 'asc'}
    )
    
    if not recs:
        print("No EM history found.")
        await db.disconnect()
        return
        
    em_df = pd.DataFrame([
        {
            'date_str': r.date.strftime('%Y-%m-%d'),
            'prev_close': r.closePrice,
            'straddle_price': r.straddlePrice,
            'em_365_iv': r.em365,
            'em_252_iv': r.em252,
            'iv_30': r.iv365 # VIX-style IV
        } for r in recs
    ])
    
    # 2. Load Price Data (Daily)
    price_df = pd.read_parquet(f'data/{ticker}_1d.parquet')
    if price_df.index.name == 'datetime': price_df = price_df.reset_index()
    price_df['date_str'] = pd.to_datetime(price_df['datetime']).dt.strftime('%Y-%m-%d')
    
    # 3. Load VIX Data
    try:
        vix_df = pd.read_parquet('data/VIX_1d.parquet')
        if 'time' not in vix_df.columns: vix_df['time'] = vix_df.index
        vix_df['date_str'] = pd.to_datetime(vix_df['time']).dt.strftime('%Y-%m-%d')
        vix_map_1d = vix_df.set_index('date_str')['close'].to_dict()
        
        # Load VIX 5m for synthetic open straddles
        vix_5m = pd.read_parquet('data/VIX_5m.parquet')
        if vix_5m.index.name == 'datetime' or 'datetime' not in vix_5m.columns:
            vix_5m['dt'] = pd.to_datetime(vix_5m.index)
        else:
            vix_5m['dt'] = pd.to_datetime(vix_5m['datetime'])
            
        # Extract 9:30 AM EST (13:30 or 14:30 UTC)
        # Simplify: Market Open is the first bar of the session in this dataset
        vix_5m['date_str'] = vix_5m['dt'].dt.strftime('%Y-%m-%d')
        # Get first bar of each day (Open)
        vix_open_map = vix_5m.groupby('date_str')['open'].first().to_dict()
        
    except Exception as e:
        print(f"Error loading VIX data: {e}")
        vix_map_1d = {}
        vix_open_map = {}

    # 4. Merge
    df = pd.merge(em_df, price_df[['date_str', 'open', 'high', 'low', 'close']], on='date_str', how='inner')
    
    # 5. Calculate Variants
    
    # A. Straddle-based (Close Anchor) - Traditional
    df['em_close_straddle_085'] = df['straddle_price'] * 0.85
    df['em_close_straddle_100'] = df['straddle_price'] * 1.0
    
    # B. Straddle-based (Open Anchor) 
    # Logic: Using the EOD Straddle Pct applied to Open
    df['straddle_pct_085'] = df['em_close_straddle_085'] / df['prev_close']
    df['straddle_pct_100'] = df['em_close_straddle_100'] / df['prev_close']
    df['em_open_straddle_085'] = df['open'] * df['straddle_pct_085']
    df['em_open_straddle_100'] = df['open'] * df['straddle_pct_100']
    
    # C. Synthetic 9:30 AM Straddle (Using VIX at the Open)
    # Formula: Open * (VIX_Open / 100) * sqrt(1/252) * 2.0
    def get_synth_open_em(row):
        vo = vix_open_map.get(row['date_str'])
        if not vo: return None
        return row['open'] * (vo/100.0) * np.sqrt(1/252.0) * 2.0
        
    df['em_open_vix_synth_100'] = df.apply(get_synth_open_em, axis=1)
    df['em_open_vix_synth_085'] = df['em_open_vix_synth_100'] * 0.85
    
    # D. VIX Scaled (2.0x) - Close Anchor (Traditional)
    df['em_close_vix_20'] = df.apply(lambda x: x['close'] * (vix_map_1d.get(x['date_str'], 0)/100.0) * np.sqrt(1/252.0) * 2.0, axis=1)
    
    # 6. Include Realized Performance (MFE/MAE)
    # MFE = Max High excursion from anchor
    # MAE = Max Low excursion from anchor
    
    # Close-to-High/Low (Traditional)
    df['mfe_close'] = (df['high'] - df['prev_close']) / df['em_close_straddle_085']
    df['mae_close'] = (df['prev_close'] - df['low']) / df['em_close_straddle_085']
    
    # Open-to-High/Low (EOD-derived)
    df['mfe_open'] = (df['high'] - df['open']) / df['em_open_straddle_085']
    df['mae_open'] = (df['open'] - df['low']) / df['em_open_straddle_085']
    
    # Open-to-High/Low (9:30 AM Synthetic)
    df['mfe_open_synth'] = (df['high'] - df['open']) / df['em_open_vix_synth_085']
    df['mae_open_synth'] = (df['open'] - df['low']) / df['em_open_vix_synth_085']
    
    # 7. Cleanup and Save
    os.makedirs('data/analysis', exist_ok=True)
    out_path = 'data/analysis/em_master_dataset.csv'
    df.to_csv(out_path, index=False)
    
    print(f"Master Dataset created at: {out_path}")
    print(f"Total Rows: {len(df)}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(generate_master_dataset())
