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

async def analyze_accuracy():
    db = Prisma()
    await db.connect()
    
    ticker = 'SPY'
    print(f"\n=== Analyzing Expected Move Accuracy for {ticker} ===")
    
    # 1. Load EM History from DB
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
            'price_at_calc': r.closePrice,
            'em_straddle': r.emStraddle,
            'em_365': r.em365,
            'em_252': r.em252
        } for r in recs
    ])
    
    # 2. Load Price Data (to get actual next-day moves)
    try:
        price_df = pd.read_parquet(f'data/{ticker}_1d.parquet')
        # Handle index for time
        if 'time' not in price_df.columns:
            price_df['time'] = price_df.index
        price_df['date_str'] = pd.to_datetime(price_df['time']).dt.strftime('%Y-%m-%d')
        
        # We need Next Day Close
        price_df = price_df.sort_values('date_str')
        price_df['next_close'] = price_df['close'].shift(-1)
        price_df['next_high'] = price_df['high'].shift(-1)
        price_df['next_low'] = price_df['low'].shift(-1)
        
        # Realized Move: Close-to-Close
        price_df['abs_move'] = (price_df['next_close'] - price_df['close']).abs()
        
        # Realized Excursion: Max of abs(High - PrevClose) or abs(Low - PrevClose)
        price_df['max_excursion'] = price_df.apply(
            lambda x: max(abs(x['next_high'] - x['close']), abs(x['next_low'] - x['close'])),
            axis=1
        )
        
    except Exception as e:
        print(f"Error loading price data: {e}")
        await db.disconnect()
        return

    # 3. Load VIX Data
    try:
        vix_df = pd.read_parquet('data/VIX_1d.parquet')
        if 'time' not in vix_df.columns:
            vix_df['time'] = vix_df.index
        vix_df['date_str'] = pd.to_datetime(vix_df['time']).dt.strftime('%Y-%m-%d')
        vix_map = vix_df.set_index('date_str')['close'].to_dict()
    except Exception as e:
        print(f"Error loading VIX data: {e}")
        vix_map = {}

    # 4. Merge
    df = pd.merge(em_df, price_df[['date_str', 'close', 'abs_move', 'max_excursion']], on='date_str', how='inner')
    
    # Calculate VIX-based EM (Theoretical 1-day)
    # Using the 2.0x scalar found in previous experiments for comparison
    def get_vix_em_scaled(row):
        vix = vix_map.get(row['date_str'])
        if not vix: return None
        # Scale by 2.0 to match straddle behavior
        return row['close'] * (vix/100.0) * np.sqrt(1/252.0) * 2.0

    def get_vix_em_raw(row):
        vix = vix_map.get(row['date_str'])
        if not vix: return None
        return row['close'] * (vix/100.0) * np.sqrt(1/252.0)

    df['em_vix_scaled'] = df.apply(get_vix_em_scaled, axis=1)
    df['em_vix_raw'] = df.apply(get_vix_em_raw, axis=1)

    # 5. Accuracy Metrics
    methods = ['em_straddle', 'em_365', 'em_252', 'em_vix_scaled', 'em_vix_raw']
    results = []
    
    # Filter out rows with missing data for any method being analyzed
    # But analyze each method separately based on its availability
    
    print(f"\nSample Size: {len(df)} days")
    print("-" * 80)
    print(f"{'Method':<16} | {'Count':<6} | {'In (Close)%':<10} | {'In (Excur)%':<10} | {'Avg Error'}")
    print("-" * 80)

    for m in methods:
        valid_df = df.dropna(subset=[m, 'abs_move']).copy()
        if valid_df.empty: continue
        
        # Containment: Realized Move <= EM
        valid_df['contained_close'] = valid_df['abs_move'] <= valid_df[m]
        valid_df['contained_excur'] = valid_df['max_excursion'] <= valid_df[m]
        
        # Error: (Move - EM) / EM -> but let's just use absolute diff or Z
        valid_df['error'] = (valid_df['abs_move'] - valid_df[m]).abs()
        
        in_c_rate = valid_df['contained_close'].mean() * 100
        in_e_rate = valid_df['contained_excur'].mean() * 100
        avg_err = valid_df['error'].mean()
        
        print(f"{m:<16} | {len(valid_df):<6} | {in_c_rate:>9.1f}% | {in_e_rate:>9.1f}% | {avg_err:>9.2f}")
        
    print("-" * 80)
    print("Definitions:")
    print(" - In (Close)%:  % of days where Close-to-Close move stayed inside EM.")
    print(" - In (Excur)%:  % of days where intraday High/Low extremes stayed inside EM.")
    print(" - Avg Error:    Average absolute difference between Move and EM.")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(analyze_accuracy())
