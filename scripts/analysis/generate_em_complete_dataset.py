"""
Complete EM Dataset Generator

This script generates comprehensive Expected Move datasets for intraday trading analysis.
It includes ALL EM calculation methods and outputs multiple CSVs for downstream analysis.

OUTPUT FILES:
1. em_daily_levels.csv - Daily EM levels for each method at each multiple
2. em_daily_performance.csv - Daily realized performance vs each EM level
3. em_level_touches.csv - Intraday touch/reversal data for each level
4. em_method_summary.csv - Summary statistics for each method/level combo
"""

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

async def generate_complete_dataset():
    db = Prisma()
    await db.connect()
    
    ticker = 'SPY'
    print(f"\n{'='*80}")
    print(f"=== COMPLETE EM DATASET GENERATION FOR {ticker} ===")
    print(f"{'='*80}")
    
    # ==========================================
    # 1. Load All Source Data
    # ==========================================
    
    print("\n[1] Loading source data...")
    
    # EM History from DB
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
            'date': r.date.strftime('%Y-%m-%d'),
            'prev_close': r.closePrice,
            'straddle_price': r.straddlePrice,
            'iv_365': r.iv365,
            'em_365_db': r.em365,
            'iv_252': r.iv252,
            'em_252_db': r.em252
        } for r in recs
    ])
    
    # Daily Price Data
    price_df = pd.read_parquet(f'data/{ticker}_1d.parquet')
    if price_df.index.name == 'datetime': price_df = price_df.reset_index()
    price_df['date'] = pd.to_datetime(price_df['datetime']).dt.strftime('%Y-%m-%d')
    
    # Weekly Close (for confluence)
    price_df['week'] = pd.to_datetime(price_df['datetime']).dt.isocalendar().week
    price_df['year'] = pd.to_datetime(price_df['datetime']).dt.isocalendar().year
    weekly_close = price_df.groupby(['year', 'week'])['close'].last().shift(1)
    price_df['prev_week_close'] = price_df.apply(lambda x: weekly_close.get((x['year'], x['week'])), axis=1)
    
    # VIX Data (Daily and 5m)
    vix_1d = pd.read_parquet('data/VIX_1d.parquet')
    if vix_1d.index.name == 'datetime' or 'time' not in vix_1d.columns: vix_1d['time'] = vix_1d.index
    vix_1d['date'] = pd.to_datetime(vix_1d['time']).dt.strftime('%Y-%m-%d')
    vix_close_map = vix_1d.set_index('date')['close'].to_dict()
    
    vix_5m = pd.read_parquet('data/VIX_5m.parquet')
    if vix_5m.index.name == 'datetime' or 'datetime' not in vix_5m.columns:
        vix_5m['dt'] = pd.to_datetime(vix_5m.index)
    else:
        vix_5m['dt'] = pd.to_datetime(vix_5m['datetime'])
    vix_5m['date'] = vix_5m['dt'].dt.strftime('%Y-%m-%d')
    vix_open_map = vix_5m.groupby('date')['open'].first().to_dict()
    
    # 5m Price Data for intraday analysis
    df_5m = pd.read_parquet(f'data/{ticker}_5m.parquet')
    if df_5m.index.name == 'datetime': df_5m = df_5m.reset_index()
    df_5m['date'] = pd.to_datetime(df_5m['datetime']).dt.strftime('%Y-%m-%d')
    
    # Merge base data
    df = pd.merge(em_df, price_df[['date', 'open', 'high', 'low', 'close', 'prev_week_close']], on='date', how='inner')
    
    print(f"  Loaded {len(df)} days of data")
    
    # ==========================================
    # 2. Calculate ALL EM Methods
    # ==========================================
    
    print("\n[2] Calculating all EM methods...")
    
    # Method 1: Straddle-based (Close Anchor)
    df['em_straddle_085_close'] = df['straddle_price'] * 0.85
    df['em_straddle_100_close'] = df['straddle_price'] * 1.0
    
    # Method 2: IV-365 (Close Anchor)
    df['em_iv365_close'] = df['em_365_db']
    
    # Method 3: IV-252 (Close Anchor)
    df['em_iv252_close'] = df['em_252_db']
    
    # Method 4: VIX Raw (Close Anchor) - 1-day theoretical
    df['em_vix_raw_close'] = df.apply(
        lambda x: x['prev_close'] * (vix_close_map.get(x['date'], 0)/100.0) * np.sqrt(1/252.0), axis=1
    )
    
    # Method 5: VIX Scaled 2.0x (Close Anchor)
    df['em_vix_scaled_close'] = df['em_vix_raw_close'] * 2.0
    
    # Method 6: Straddle-based (Open Anchor - EOD pct)
    df['straddle_pct'] = df['em_straddle_085_close'] / df['prev_close']
    df['em_straddle_085_open'] = df['open'] * df['straddle_pct']
    df['em_straddle_100_open'] = df['open'] * (df['em_straddle_100_close'] / df['prev_close'])
    
    # Method 7: Synth VIX (Open Anchor - 9:30 AM VIX)
    df['em_synth_vix_100_open'] = df.apply(
        lambda x: x['open'] * (vix_open_map.get(x['date'], 0)/100.0) * np.sqrt(1/252.0) * 2.0, axis=1
    )
    df['em_synth_vix_085_open'] = df['em_synth_vix_100_open'] * 0.85
    
    # Method 8: IV-252 (Open Anchor)
    df['em_iv252_open'] = df.apply(
        lambda x: x['open'] * (x['iv_252']/100.0) * np.sqrt(1/252.0) if x['iv_252'] else None, axis=1
    )
    
    # ==========================================
    # 3. Generate CSV 1: Daily Levels
    # ==========================================
    
    print("\n[3] Generating em_daily_levels.csv...")
    
    methods = {
        'straddle_085_close': 'em_straddle_085_close',
        'straddle_100_close': 'em_straddle_100_close',
        'iv365_close': 'em_iv365_close',
        'iv252_close': 'em_iv252_close',
        'vix_raw_close': 'em_vix_raw_close',
        'vix_scaled_close': 'em_vix_scaled_close',
        'straddle_085_open': 'em_straddle_085_open',
        'straddle_100_open': 'em_straddle_100_open',
        'synth_vix_085_open': 'em_synth_vix_085_open',
        'synth_vix_100_open': 'em_synth_vix_100_open',
        'iv252_open': 'em_iv252_open'
    }
    
    multiples = [0.5, 0.618, 1.0, 1.272, 1.5, 1.618, 2.0]
    
    level_rows = []
    for idx, row in df.iterrows():
        base = {
            'date': row['date'],
            'prev_close': row['prev_close'],
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'prev_week_close': row['prev_week_close']
        }
        
        for method_name, col in methods.items():
            em_val = row.get(col)
            if not em_val or pd.isna(em_val): continue
            
            anchor = row['open'] if 'open' in method_name else row['prev_close']
            
            for mult in multiples:
                level_upper = anchor + (em_val * mult)
                level_lower = anchor - (em_val * mult)
                
                level_rows.append({
                    **base,
                    'method': method_name,
                    'em_value': em_val,
                    'anchor': anchor,
                    'multiple': mult,
                    'level_upper': level_upper,
                    'level_lower': level_lower
                })
    
    levels_df = pd.DataFrame(level_rows)
    levels_df.to_csv('data/analysis/em_daily_levels.csv', index=False)
    print(f"  Saved {len(levels_df)} rows to em_daily_levels.csv")
    
    # ==========================================
    # 4. Generate CSV 2: Daily Performance
    # ==========================================
    
    print("\n[4] Generating em_daily_performance.csv...")
    
    perf_rows = []
    for idx, row in df.iterrows():
        anchor_close = row['prev_close']
        anchor_open = row['open']
        
        # MFE/MAE from Close
        mfe_close = row['high'] - anchor_close
        mae_close = anchor_close - row['low']
        
        # MFE/MAE from Open
        mfe_open = row['high'] - anchor_open
        mae_open = anchor_open - row['low']
        
        for method_name, col in methods.items():
            em_val = row.get(col)
            if not em_val or pd.isna(em_val): continue
            
            anchor = anchor_open if 'open' in method_name else anchor_close
            mfe = mfe_open if 'open' in method_name else mfe_close
            mae = mae_open if 'open' in method_name else mae_close
            
            mfe_mult = mfe / em_val
            mae_mult = mae / em_val
            
            for mult in multiples:
                contained = (mfe_mult <= mult) and (mae_mult <= mult)
                touched_upper = row['high'] >= anchor + (em_val * mult)
                touched_lower = row['low'] <= anchor - (em_val * mult)
                
                perf_rows.append({
                    'date': row['date'],
                    'method': method_name,
                    'multiple': mult,
                    'em_value': em_val,
                    'mfe_mult': round(mfe_mult, 4),
                    'mae_mult': round(mae_mult, 4),
                    'contained': contained,
                    'touched_upper': touched_upper,
                    'touched_lower': touched_lower
                })
    
    perf_df = pd.DataFrame(perf_rows)
    perf_df.to_csv('data/analysis/em_daily_performance.csv', index=False)
    print(f"  Saved {len(perf_df)} rows to em_daily_performance.csv")
    
    # ==========================================
    # 5. Generate CSV 3: Level Touches (5m)
    # ==========================================
    
    print("\n[5] Generating em_level_touches.csv (5m analysis)...")
    
    touch_rows = []
    sample_days = df.head(100) # Limit for performance
    
    for idx, row in sample_days.iterrows():
        day = row['date']
        day_bars = df_5m[df_5m['date'] == day].sort_values('datetime')
        if day_bars.empty: continue
        
        for method_name, col in methods.items():
            em_val = row.get(col)
            if not em_val or pd.isna(em_val): continue
            
            anchor = row['open'] if 'open' in method_name else row['prev_close']
            
            for mult in [0.5, 1.0, 1.5]:  # Key levels only
                lvl_u = anchor + (em_val * mult)
                lvl_l = anchor - (em_val * mult)
                
                touched_u, touched_l = False, False
                reversed_u, reversed_l = False, False
                touch_time_u, touch_time_l = None, None
                
                for b_idx, bar in day_bars.iterrows():
                    h, l, c = bar['high'], bar['low'], bar['close']
                    
                    if h >= lvl_u >= l and not touched_u:
                        touched_u = True
                        touch_time_u = bar['datetime']
                        if c < lvl_u: reversed_u = True
                    
                    if h >= lvl_l >= l and not touched_l:
                        touched_l = True
                        touch_time_l = bar['datetime']
                        if c > lvl_l: reversed_l = True
                
                touch_rows.append({
                    'date': day,
                    'method': method_name,
                    'multiple': mult,
                    'level_upper': lvl_u,
                    'level_lower': lvl_l,
                    'touched_upper': touched_u,
                    'touched_lower': touched_l,
                    'reversed_upper': reversed_u,
                    'reversed_lower': reversed_l,
                    'touch_time_upper': touch_time_u,
                    'touch_time_lower': touch_time_l
                })
    
    touch_df = pd.DataFrame(touch_rows)
    touch_df.to_csv('data/analysis/em_level_touches.csv', index=False)
    print(f"  Saved {len(touch_df)} rows to em_level_touches.csv")
    
    # ==========================================
    # 6. Generate CSV 4: Method Summary
    # ==========================================
    
    print("\n[6] Generating em_method_summary.csv...")
    
    summary_rows = []
    for method_name in methods.keys():
        method_perf = perf_df[perf_df['method'] == method_name]
        
        for mult in multiples:
            mult_perf = method_perf[method_perf['multiple'] == mult]
            if mult_perf.empty: continue
            
            containment = mult_perf['contained'].mean() * 100
            touch_upper_rate = mult_perf['touched_upper'].mean() * 100
            touch_lower_rate = mult_perf['touched_lower'].mean() * 100
            median_mfe = mult_perf['mfe_mult'].median()
            median_mae = mult_perf['mae_mult'].median()
            
            summary_rows.append({
                'method': method_name,
                'multiple': mult,
                'containment_pct': round(containment, 2),
                'touch_upper_pct': round(touch_upper_rate, 2),
                'touch_lower_pct': round(touch_lower_rate, 2),
                'median_mfe': round(median_mfe, 4),
                'median_mae': round(median_mae, 4),
                'sample_size': len(mult_perf)
            })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv('data/analysis/em_method_summary.csv', index=False)
    print(f"  Saved {len(summary_rows)} rows to em_method_summary.csv")
    
    print(f"\n{'='*80}")
    print("=== DATA GENERATION COMPLETE ===")
    print(f"{'='*80}")
    print("\nOutput Files:")
    print("  1. data/analysis/em_daily_levels.csv")
    print("  2. data/analysis/em_daily_performance.csv")
    print("  3. data/analysis/em_level_touches.csv")
    print("  4. data/analysis/em_method_summary.csv")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(generate_complete_dataset())
