import pandas as pd
import numpy as np
import datetime

# Configuration
SYMBOL = 'SPY'
CSV_PATH = 'data/options/options/doltdump/option_chain.csv'
PRICES_PATH = 'data/SPY_1d.parquet'

def load_underlying_prices():
    try:
        df = pd.read_parquet(PRICES_PATH)
        # Ensure index is datetime string YYYY-MM-DD
        # Parquet might have DatetimeIndex or 'Date' column
        # Schema expects 'time' (datetime) and 'close' (float)
        # Convert time to String YYYY-MM-DD
        if 'time' in df.columns:
            df['date_str'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d')
        else:
             # Fallback if index
             df['date_str'] = df.index.astype(str).str[:10]

        # Create lookup map: DateStr -> Close
        price_map = df.set_index('date_str')['close'].to_dict()
        return price_map
    except Exception as e:
        print(f"Error loading prices: {e}")
        return {}

def process_straddle():
    print("Loading underlying prices...")
    price_map = load_underlying_prices()
    if not price_map:
        print("No underlying prices found. Cannot find ATM strike.")
        return

    print(f"Scanning {CSV_PATH} for {SYMBOL}...")
    
    # We want to find Daily Straddle for recent dates
    chunk_size = 1000000
    reader = pd.read_csv(CSV_PATH, chunksize=chunk_size)
    
    results = []

    for i, chunk in enumerate(reader):
        # Filter for Symbol
        # Note: CSV symbol might be 'SPY' or 'SPY '
        chunk = chunk[chunk['act_symbol'] == SYMBOL]
        
        if chunk.empty:
            continue
            
        # Filter for recent dates only (Optimization for POC)
        # Let's look at Dec 2025
        chunk = chunk[chunk['date'] >= '2025-12-01']
        if chunk.empty:
            continue
            
        # Process Day by Day
        days = chunk['date'].unique()
        
        for day in days:
            if day not in price_map:
                continue
                
            underlying_price = price_map[day]
            
            day_data = chunk[chunk['date'] == day]
            
            # Find Next Expiration (Daily EM)
            # Filter expirations >= day
            # If standard options, next expiry is usually same day (0DTE) or next day
            # We want the expiry that is closest but >= today? 
            # Ideally "Next Day" expiry for "Expected Move for Tomorrow".
            # Or "Today's" expiry for "Expected Move for Today".
            # Usually EM implies the move implied by the contracts expiring *soon*.
            # Let's pick the closest expiry.
            
            expirations = sorted(day_data['expiration'].unique())
            # Filter expired? (Exp >= Date)
            valid_exps = [e for e in expirations if e >= day]
            if not valid_exps:
                continue
                
            closest_exp = valid_exps[0] # nearest
            
            # Get Chain for this expiry
            chain = day_data[day_data['expiration'] == closest_exp]
            
            # Find ATM Strike
            strikes = chain['strike'].unique()
            atm_strike = min(strikes, key=lambda x: abs(x - underlying_price))
            
            # Get Call and Put at ATM
            call = chain[(chain['strike'] == atm_strike) & (chain['call_put'] == 'Call')]
            put = chain[(chain['strike'] == atm_strike) & (chain['call_put'] == 'Put')]
            
            if call.empty or put.empty:
                continue
                
            # Mid Price
            call_price = (call['bid'].values[0] + call['ask'].values[0]) / 2
            put_price = (put['bid'].values[0] + put['ask'].values[0]) / 2
            straddle = call_price + put_price
            
            results.append({
                'date': day,
                'expiration': closest_exp,
                'underlying': underlying_price,
                'atm_strike': atm_strike,
                'straddle_price': straddle,
                'em_85': straddle * 0.85
            })
            
    # Deduplicate (chunks might split days? Unlikely if sorted but possible)
    # Convert to DF
    if results:
        res_df = pd.DataFrame(results).drop_duplicates()
        print("\n--- Calculated Straddles (Sample) ---")
        print(res_df.sort_values('date').tail(10))
    else:
        print("No results found.")

if __name__ == "__main__":
    process_straddle()
