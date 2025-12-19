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

async def analyze_comprehensive():
    db = Prisma()
    await db.connect()
    
    ticker = 'SPY'
    print(f"\n=== Comprehensive EM Analysis for {ticker} (Outliers, MFE/MAE, Confluence) ===")
    
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
            'em_straddle': r.emStraddle
        } for r in recs
    ]).dropna(subset=['em_straddle'])
    
    # 2. Load Price Data (1d for static levels, 5m for intraday)
    try:
        df_1d = pd.read_parquet(f'data/{ticker}_1d.parquet')
        if df_1d.index.name == 'datetime': df_1d = df_1d.reset_index()
        df_1d['date_str'] = pd.to_datetime(df_1d['datetime']).dt.strftime('%Y-%m-%d')
        
        # Calculate Weekly Close (Previous Week)
        df_1d['week'] = pd.to_datetime(df_1d['datetime']).dt.isocalendar().week
        df_1d['year'] = pd.to_datetime(df_1d['datetime']).dt.isocalendar().year
        
        weekly_close = df_1d.groupby(['year', 'week'])['close'].last().shift(1)
        # Map this back to daily
        df_1d['prev_week_close'] = df_1d.apply(lambda x: weekly_close.get((x['year'], x['week'])), axis=1)
        
        # Daily Open
        df_1d['daily_open'] = df_1d['open']
        
        static_levels = df_1d.set_index('date_str')[['prev_week_close', 'daily_open']].to_dict('index')
        
        df_5m = pd.read_parquet(f'data/{ticker}_5m.parquet')
        if df_5m.index.name == 'datetime': df_5m = df_5m.reset_index()
        df_5m['date_str'] = pd.to_datetime(df_5m['datetime']).dt.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Error loading price data: {e}")
        await db.disconnect()
        return

    # 3. Define Factors (including Fibonacci)
    factors = [0.5, 0.618, 1.0, 1.272, 1.5, 1.618, 2.0]
    
    mfe_data = [] # Distribution of daily max excursions as multiple of EM
    mae_data = [] # Distribution of daily max adverse moves as multiple of EM
    confluence_reversals = 0
    confluence_touches = 0

    print(f"Analyzing {len(em_df)} days...")

    for idx, em_row in em_df.iterrows():
        day = em_row['date_str']
        pc = em_row['prev_close']
        em_val = em_row['em_straddle']
        
        day_bars = df_5m[df_5m['date_str'] == day]
        if day_bars.empty: continue
        
        hod = day_bars['high'].max()
        lod = day_bars['low'].min()
        
        # MFE/MAE: Max distance from Prev Close in direction of max move vs opposite
        # For simplicity, let's just use Max Excursion Multiple
        max_up = (hod - pc) / em_val
        max_down = (pc - lod) / em_val
        
        mfe_data.append(max(max_up, max_down))
        mae_data.append(min(max_up, max_down)) # This will usually be positive here, we want the move against the "trend" of the day
        
        # Static level Confluence
        day_static = static_levels.get(day, {})
        pwc = day_static.get('prev_week_close')
        do = day_static.get('daily_open')
        
        tol = pc * 0.0005 # 5 bps tolerance
        
        for f in factors:
            lvl_u = pc + (em_val * f)
            lvl_l = pc - (em_val * f)
            
            # Check if any static level is near this EM level
            near_u = False
            if pwc and abs(lvl_u - pwc) < tol: near_u = True
            if do and abs(lvl_u - do) < tol: near_u = True
            
            near_l = False
            if pwc and abs(lvl_l - pwc) < tol: near_l = True
            if do and abs(lvl_l - do) < tol: near_l = True
            
            if near_u:
                confluence_touches += 1
                if hod >= lvl_u and day_bars[day_bars['high'] >= lvl_u].iloc[0]['close'] < lvl_u:
                    confluence_reversals += 1
            if near_l:
                confluence_touches += 1
                if lod <= lvl_l and day_bars[day_bars['low'] <= lvl_l].iloc[0]['close'] > lvl_l:
                    confluence_reversals += 1

    # 4. Results Processing
    mfe_arr = np.array(mfe_data)
    
    print("\n=== EM Multiple Distribution (MFE) ===")
    print(f"{'Multiple':<10} | {'Probability of Reaching (%)'}")
    print("-" * 40)
    for f in factors:
        prob = (mfe_arr >= f).mean() * 100
        print(f"{f:<10.3f} | {prob:>25.1f}%")
        
    print("\n=== Confluence Analysis (EM + Weekly Close/Daily Open) ===")
    if confluence_touches > 0:
        conf_rate = (confluence_reversals / confluence_touches) * 100
        print(f"Reversal Rate at Confluence: {conf_rate:.1f}% (vs ~50% baseline)")
    else:
        print("No confluence events found in sample.")

    # 5. Stop Loss / Take Profit Logic Ideas
    # If we are at 1.0x EM, where is the next likely stop?
    # Look at conditional probs: If 1.0x hit, what is prob of 1.272x?
    print("\n=== Conditional Probabilities (Next Multiples) ===")
    if (mfe_arr >= 1.0).sum() > 0:
        p_127 = (mfe_arr >= 1.272).sum() / (mfe_arr >= 1.0).sum() * 100
        p_150 = (mfe_arr >= 1.5).sum() / (mfe_arr >= 1.0).sum() * 100
        p_161 = (mfe_arr >= 1.618).sum() / (mfe_arr >= 1.0).sum() * 100
        print(f"Given 100% EM reached:")
        print(f" - Prob of reaching 127.2% (Fib): {p_127:.1f}%")
        print(f" - Prob of reaching 150.0% (User): {p_150:.1f}%")
        print(f" - Prob of reaching 161.8% (Fib): {p_161:.1f}%")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(analyze_comprehensive())
