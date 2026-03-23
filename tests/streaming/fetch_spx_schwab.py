import schwab
import json
import os
import pprint

def fetch_spx_em():
    print("=== Fetching SPX Expected Move (Schwab) ===")
    
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Error: secrets.json or token.json missing.")
        return

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    try:
        client = schwab.auth.client_from_token_file(
            token_path="token.json",
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            enforce_enums=False
        )
    except Exception as e:
        print(f"Auth Error: {e}")
        return

    # Try "SPX" first
    symbol = "$SPX" # Try $SPX first based on docs
    
    print(f"Fetching Quote for {symbol}...")
    try:
        resp = client.get_quote(symbol).json()
        print("Quote Response keys:", resp.keys())
        if symbol in resp:
            quote = resp[symbol]['quote']
            print(f"Price: {quote['lastPrice']}")
            current_price = quote['lastPrice']
        else:
            print("Symbol not in response. Trying 'SPX'...")
            symbol = "SPX"
            resp = client.get_quote(symbol).json()
            if symbol in resp:
                 quote = resp[symbol]['quote']
                 print(f"Price: {quote['lastPrice']}")
                 current_price = quote['lastPrice']
            else:
                 print("Failed to get quote.")
                 return
                 
    except Exception as e:
        print(f"Quote failed: {e}")
        return

    print("\nFetching Option Chain...")
    try:
        # returns simple dict based on library, but let's see
        resp = client.get_option_chain(
            symbol,
            strike_count=20,
            strategy='ANALYTICAL'
            # range is causing issues, removing for now or check docs
        ).json()
        
        # print("Chain Keys:", resp.keys())
        
        if 'status' in resp and resp['status'] == 'FAILED':
             print(f"Chain Fetch Failed: {resp}")
             return

    except Exception as e:
        print(f"Chain Error: {e}")
        return

    call_map = resp.get('callExpDateMap', {})
    
    # Sort keys: "2025-12-17:1"
    # We need to sort by DATE string primarily
    exp_keys = sorted(call_map.keys())
    
    print(f"\nFound {len(exp_keys)} expirations.")
    
    for exp_key in exp_keys[:3]:
        date_str, days_str = exp_key.split(':')
        days = int(days_str)
        print(f"\n--- Expiry: {date_str} ({days} days) ---")
        
        # Strikes are keys in the map
        strikes = []
        for k in call_map[exp_key]:
            try:
                strikes.append(float(k))
            except: pass
            
        if not strikes: continue
        
        closest_strike_val = min(strikes, key=lambda x: abs(x - current_price))
        
        # Find exact string key
        strike_key = next((k for k in call_map[exp_key] if abs(float(k) - closest_strike_val) < 0.001), None)
        
        print(f"ATM Strike: {strike_key}")
        
        # Check chain data structure
        # Schwab often returns list of options for a strike
        call_opt = call_map[exp_key][strike_key][0]
        
        # For puts, we assume same structure
        put_map = resp.get('putExpDateMap', {})
        if exp_key in put_map and strike_key in put_map:
             put_opt = put_map[exp_key][strike_key][0]
        else:
             print("Missing Put side.")
             continue
             
        # Extract Price
        # Prefer 'mark' > (bid+ask)/2 > 'closePrice'
        def get_price(o):
            # Inspect keys for Greeks/IV
            if 'gamma' not in o: # Just print once/spam prevention if needed, or just print
                 pass 
            # pprint.pprint(o) # Uncomment to see full object
            if 'mark' in o: return o['mark']
            if 'bid' in o and 'ask' in o: return (o['bid'] + o['ask']) / 2
            return o.get('closePrice', 0)
            
        c_price = get_price(call_opt)
        p_price = get_price(put_opt)
        straddle = c_price + p_price
        
        em = straddle * 0.85
        if days <= 1: em = straddle
        
        print(f"  Call: {c_price:.2f} | Put: {p_price:.2f}")
        print(f"  Straddle: {straddle:.2f}")
        print(f"  Exp Move: +/- {em:.2f}")
        print(f"  Range: {current_price - em:.0f} to {current_price + em:.0f}")

if __name__ == "__main__":
    fetch_spx_em()

