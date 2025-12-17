import yfinance as yf
import pandas as pd
from datetime import datetime

def get_spx_expected_move():
    print("Fetching SPX data...")
    spx = yf.Ticker("^SPX")
    
    # Get current price
    try:
        history = spx.history(period="1d")
        if history.empty:
            print("No price history found. Market might be closed or ticker is wrong.")
            current_price = 6000 # Fallback for testing if yfinance fails on price
        else:
            current_price = history['Close'].iloc[-1]
            print(f"Current SPX Price: {current_price:.2f}")
    except Exception as e:
        print(f"Error fetching price: {e}")
        return

    # Get Expirations
    try:
        expirations = spx.options
        if not expirations:
            print("No option expirations found.")
            return
        
        print(f"\nFound {len(expirations)} expirations.")
        
        # Look at the next 3 expirations
        for exp_date in expirations[:3]:
            print(f"\n--- Expiry: {exp_date} ---")
            
            # Fetch Chain
            chain = spx.option_chain(exp_date)
            calls = chain.calls
            puts = chain.puts
            
            # Find ATM Strike (Closest to Current Price)
            # Filter for strikes reasonable close
            calls = calls[(calls['strike'] > current_price * 0.9) & (calls['strike'] < current_price * 1.1)]
            puts = puts[(puts['strike'] > current_price * 0.9) & (puts['strike'] < current_price * 1.1)]
            
            # Find closest strike
            # We want the same strike for Call and Put (Straddle)
            # Find strike with min distance to current price
            
            # Combine unique strikes
            all_strikes = sorted(set(calls['strike']).union(set(puts['strike'])))
            
            closest_strike = min(all_strikes, key=lambda x: abs(x - current_price))
            print(f"ATM Strike: {closest_strike}")
            
            # Get Call & Put Price at this strike
            atm_call = calls[calls['strike'] == closest_strike]
            atm_put = puts[puts['strike'] == closest_strike]
            
            if atm_call.empty or atm_put.empty:
                print("Missing data for ATM options.")
                continue
                
            call_price = (atm_call['bid'].iloc[0] + atm_call['ask'].iloc[0]) / 2
            put_price = (atm_put['bid'].iloc[0] + atm_put['ask'].iloc[0]) / 2
            
            straddle_price = call_price + put_price
            
            # Rule of Thumb Expected Move: 0.85 * Straddle (or just Straddle for full)
            # For 0DTE/1DTE, usually just the Straddle Cost is the move.
            expected_move = straddle_price * 0.85
            
            print(f"  Call Price: {call_price:.2f}")
            print(f"  Put Price:  {put_price:.2f}")
            print(f"  Straddle:   {straddle_price:.2f}")
            print(f"  Exp. Move:  +/- {expected_move:.2f} points")
            print(f"  Range:      {current_price - expected_move:.0f} to {current_price + expected_move:.0f}")

    except Exception as e:
        print(f"Error fetching options: {e}")

if __name__ == "__main__":
    get_spx_expected_move()
