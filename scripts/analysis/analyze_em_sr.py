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

async def analyze_sr():
    db = Prisma()
    await db.connect()
    
    ticker = 'SPY'
    print(f"\n=== Analyzing EM as Intraday S/R for {ticker} ===")
    
    # 1. Load EM History
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
            'em_straddle': r.emStraddle,
            'em_365': r.em365,
            'em_252': r.em252
        } for r in recs
    ])
    
    # 2. Load 5m Price & VIX Data
    try:
        data_path = f'data/{ticker}_5m.parquet'
        df_5m = pd.read_parquet(data_path)
        if df_5m.index.name == 'datetime':
            df_5m = df_5m.reset_index()
        elif 'datetime' not in df_5m.columns:
            df_5m['datetime'] = df_5m.index
        df_5m['date_str'] = pd.to_datetime(df_5m['datetime']).dt.strftime('%Y-%m-%d')
        
        vix_df = pd.read_parquet('data/VIX_1d.parquet')
        if 'time' not in vix_df.columns: vix_df['time'] = vix_df.index
        vix_df['date_str'] = pd.to_datetime(vix_df['time']).dt.strftime('%Y-%m-%d')
        vix_map = vix_df.set_index('date_str')['close'].to_dict()
    except Exception as e:
        print(f"Error loading ancillary data: {e}")
        await db.disconnect()
        return

    # 3. Methodologies to compare
    methods = ['em_straddle', 'em_365', 'em_252', 'em_vix_scaled']
    factor = 1.0 # Looking at 100% of the EM for the head-to-head comparison
    
    final_results = {}

    print(f"Comparing methodologies for {len(em_df)} days at 100% EM level...")

    for method in methods:
        matches = 0
        reversals = 0
        hod_lod_hits = 0
        
        for idx, em_row in em_df.iterrows():
            day = em_row['date_str']
            pc = em_row['prev_close']
            
            # Resolve EM value for this method
            if method == 'em_vix_scaled':
                vix = vix_map.get(day)
                if not vix: em_val = None
                else: em_val = pc * (vix/100.0) * np.sqrt(1/252.0) * 2.0
            else:
                em_val = em_row.get(method)
                
            if not em_val: continue
            
            day_bars = df_5m[df_5m['date_str'] == day]
            if day_bars.empty: continue
            
            hod, lod = day_bars['high'].max(), day_bars['low'].min()
            tol = pc * 0.0002
            
            lvl_u = pc + em_val
            lvl_l = pc - em_val
            
            t_u, t_l = False, False
            r_u, r_l = False, False
            h_u, h_l = False, False
            
            for b_idx, bar in day_bars.iterrows():
                h, l, c = bar['high'], bar['low'], bar['close']
                if h >= lvl_u >= l:
                    if not t_u:
                        t_u = True
                        if c < lvl_u: r_u = True
                        if abs(hod - lvl_u) < tol: h_u = True
                if h >= lvl_l >= l:
                    if not t_l:
                        t_l = True
                        if c > lvl_l: r_l = True
                        if abs(lod - lvl_l) < tol: h_l = True
            
            matches += (1 if t_u else 0) + (1 if t_l else 0)
            reversals += (1 if r_u else 0) + (1 if r_l else 0)
            hod_lod_hits += (1 if h_u else 0) + (1 if h_l else 0)
            
        final_results[method] = {
            'touches': matches,
            'rev_rate': (reversals / matches * 100) if matches > 0 else 0,
            'sr_quality': (hod_lod_hits / matches * 100) if matches > 0 else 0
        }

    # 4. Final Summary Table
    print("\n=== EM Methodology Comparison (Intraday S/R) ===")
    print(f"{'Method':<18} | {'Touches':<8} | {'Rev Rate %':<12} | {'S/R Quality %'}")
    print("-" * 60)
    for m in methods:
        res = final_results[m]
        print(f"{m:<18} | {res['touches']:<8} | {res['rev_rate']:>10.1f}% | {res['sr_quality']:>10.1f}%")
        
    print("-" * 60)
    print("Interpretation:")
    print(" - Touches: Frequency of interaction. Higher = tighter range.")
    print(" - Rev Rate %: Tendency to reject immediately. Higher = better local S/R.")
    print(" - S/R Quality %: Accuracy in picking session HOD/LOD. Higher = better global S/R.")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(analyze_sr())
