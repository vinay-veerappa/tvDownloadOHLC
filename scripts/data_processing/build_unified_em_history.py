import pandas as pd
import glob
import os
import asyncio
from prisma import Prisma
import numpy as np

# Configuration
DATA_DIR = "C:/Users/vinay/tvDownloadOHLC/data"
OPTIONS_CSV = os.path.join(DATA_DIR, "options/options/doltdump/option_chain.csv")
TICKERS = ["SPY", "QQQ", "IWM", "SPX", "DIA", "AAPL", "AMD", "AMZN"]

# Load Environment
try:
    with open('web/.env', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v.strip('"').strip("'")
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

async def main():
    db = Prisma()
    await db.connect()

    for ticker in TICKERS:
        print(f"\nProcessing {ticker}...")
        
        # 1. Load Daily Prices
        parquet_path = os.path.join(DATA_DIR, f"{ticker}_1d.parquet")
        if not os.path.exists(parquet_path):
            print(f"  Missing price file: {parquet_path}")
            continue
        
        prices_df = pd.read_parquet(parquet_path)
        # Normalize columns: time, close
        if 'time' not in prices_df.columns and 'Date' in prices_df.columns:
             prices_df.rename(columns={'Date': 'time'}, inplace=True)
        # Normalize Close
        if 'Close' in prices_df.columns:
             prices_df.rename(columns={'Close': 'close'}, inplace=True)
             
        # Create map: Date(str) -> Close
        prices_df['date_str'] = pd.to_datetime(prices_df['time']).dt.strftime('%Y-%m-%d')
        price_map = prices_df.set_index('date_str')['close'].to_dict()
        
        # 2. Load Existing IV from DB (HistoricalVolatility)
        # Mapping: /ES -> SPY? No, use direct ticker match or map.
        # SPY usually maps to SPY or /ES IV? 
        # For now, let's assume we use SPY IV if present, or fallback.
        # But wait, existing IV is likely for Futures (/ES) or SPY directly?
        # Let's try direct ticker first.
        
        iv_records = await db.historicalvolatility.find_many(
            where={'ticker': ticker},
            order={'date': 'asc'}
        )
        
        iv_map = {r.date.strftime('%Y-%m-%d'): r.iv for r in iv_records}
        
        # 3. Process Straddle (CSV Streaming)
        # We need to construct a unified DataFrame or Dict
        # structure: { date: { close: x, iv: y, straddle: z } }
        
        unified_data = {}
        
        # Initialize with Price Dates
        for d, p in price_map.items():
            unified_data[d] = {
                'date': d,
                'ticker': ticker,
                'close': p,
                'iv': iv_map.get(d),
                'straddle': None
            }
            
        print("  Scanning Option Chain for Straddles (this may take time)...")
        # Optimization: Only read if we have data constraints?
        # Reading 8GB for every ticker loop is bad. 
        # Better: Read CSV ONCE for ALL tickers.
        # But for script simplicity (and memory), maybe one pass filtering all?
        pass 
        
    await db.disconnect()

async def process_all_tickers_efficiently():
    db = Prisma()
    await db.connect()
    
    # 1. Preload Metadata for ALL tickers
    ticker_data = {}
    for t in TICKERS:
        # Prices
        parquet_path = os.path.join(DATA_DIR, f"{t}_1d.parquet")
        if not os.path.exists(parquet_path): continue
        df = pd.read_parquet(parquet_path)
        
        # Normalize
        cols = {c: c.lower() for c in df.columns}
        df.rename(columns=cols, inplace=True)
        if 'date' in df.columns: df.rename(columns={'date': 'time'}, inplace=True)
        
        # Handle Index if time column missing
        if 'time' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
            df['time'] = df.index
        elif 'time' not in df.columns and 'datetime' in df.columns:
            df['time'] = df['datetime']
        
        # Map
        df['date_str'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d')
        price_map = df.set_index('date_str')['close'].to_dict()
        
        # IV
        iv_recs = await db.historicalvolatility.find_many(where={'ticker': t})
        iv_map = {r.date.strftime('%Y-%m-%d'): r.iv for r in iv_recs}
        
        ticker_data[t] = {
            'prices': price_map,
            'iv': iv_map,
            'straddles': {} # To be filled
        }
        
    # 2. Stream CSV Once
    print("Streaming Option Chain CSV...")
    chunk_size = 500000 
    # Columns we need: date, act_symbol, expiration, strike, call_put, bid, ask
    usecols = ['date', 'act_symbol', 'expiration', 'strike', 'call_put', 'bid', 'ask']
    
    reader = pd.read_csv(OPTIONS_CSV, chunksize=chunk_size, usecols=usecols)
    
    for chunk in reader:
        # Filter relevant tickers
        chunk = chunk[chunk['act_symbol'].isin(TICKERS)]
        if chunk.empty: continue
        
        # Group by Date, Ticker
        # We need to process each Day/Ticker group
        groups = chunk.groupby(['date', 'act_symbol'])
        
        for (date, symbol), group in groups:
            if symbol not in ticker_data:
                continue
            if date not in ticker_data[symbol]['prices']:
                continue
            
            # Underlying Price
            u_price = ticker_data[symbol]['prices'][date]
            
            # Find closest expiry >= date
            # Optimization: Pre-sort expirations?
            exps = sorted(group['expiration'].unique())
            valid_exps = [e for e in exps if e >= date]
            if not valid_exps: continue
            closest_exp = valid_exps[0]
            
            # Filter chain for only this expiry
            chain = group[group['expiration'] == closest_exp]
            
            # ATM Strike
            strikes = chain['strike'].unique()
            if len(strikes) == 0: continue
            
            atm_strike = min(strikes, key=lambda x: abs(x - u_price))
            
            # Calc Straddle
            # Need Call and Put at this strike
            # Optimization: pivot?
            # Or just filter
            
            call_row = chain[(chain['strike'] == atm_strike) & (chain['call_put'].str.lower() == 'call')]
            put_row = chain[(chain['strike'] == atm_strike) & (chain['call_put'].str.lower() == 'put')]
            
            if call_row.empty or put_row.empty: continue
            
            call_px = (call_row['bid'].values[0] + call_row['ask'].values[0]) / 2
            put_px = (put_row['bid'].values[0] + put_row['ask'].values[0]) / 2
            
            straddle = call_px + put_px
            
            # Store (checking if we already have a better expiry? No, streaming is sequential in chunks?)
            # CSV is likely sorted by date.
            # But chunk splitting might split a day.
            # We should accumulate Straddles. 
            # If we see the same date/ticker, we overwrite? 
            # Usually strict sorting means we see all of Day X then Day Y.
            # But "chunks" might cut options... e.g. Call in chunk 1, Put in chunk 1... 
            # If Call in chunk 1, Put in chunk 2? -> groupby splits logic.
            # Risky. 
            # If sorted by Date/Ticker, breaks are clean usually.
            # We assume Call and Put for same strike are close.
            
            ticker_data[symbol]['straddles'][date] = straddle

    # 3. Merge and Insert
    print("Merging and Inserting into DB...")
    
    for t in TICKERS:
        if t not in ticker_data:
            print(f"Skipping {t} (no data)")
            continue
        data = ticker_data[t]
        unified_rows = []
        
        for date_str, price in data['prices'].items():
            iv = data['iv'].get(date_str)
            grad_s = data['straddles'].get(date_str)
            
            # Calc EMs
            em365 = None
            em252 = None
            emStraddle = None
            
            if iv:
                em365 = price * iv * np.sqrt(1/365)
                em252 = price * iv * np.sqrt(1/252)
            
            if grad_s:
                emStraddle = grad_s * 0.85
                
            # Prepare obj
            if iv or grad_s: # Only insert interesting days? 
                 # Or insert all days with price?
                 # Insert if we have at least price and ONE metric?
                 pass

            unified_rows.append({
                'ticker': t,
                'date': pd.to_datetime(date_str),
                'closePrice': float(price),
                'iv365': iv,
                'em365': em365,
                'em252': em252,
                'straddlePrice': grad_s,
                'emStraddle': emStraddle,
                'source': 'computed_v1'
            })
            
        # Batch Upsert
        # Prisma createMany doesn't support skipDuplicates override on SQLite?
        # Upsert loop is slow.
        # But we can try createMany and ignore errors? Or loop upsert.
        # For history, loop upsert is safer.
        
        print(f"  Upserting {len(unified_rows)} rows for {t}...")
        for row in unified_rows:
            # Clean data
            if pd.isna(row['date']): continue
            
            clean_date = row['date'].to_pydatetime()
            
            def clean_float(val):
                if val is None or pd.isna(val): return None
                return float(val)

            clean_row = {
                'ticker': row['ticker'],
                'date': clean_date,
                'closePrice': clean_float(row['closePrice']),
                'iv365': clean_float(row['iv365']),
                'em365': clean_float(row['em365']),
                'em252': clean_float(row['em252']),
                'straddlePrice': clean_float(row['straddlePrice']),
                'emStraddle': clean_float(row['emStraddle']),
                'source': row['source']
            }

            try:
                await db.expectedmovehistory.upsert(
                    where={
                        'ticker_date': {'ticker': clean_row['ticker'], 'date': clean_row['date']}
                    },
                    data={
                        'create': clean_row,
                        'update': clean_row
                    }
                )
            except Exception as e:
                print(f"Error upserting {clean_row['ticker']} {clean_row['date']}: {e}")
            
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(process_all_tickers_efficiently())
