import schwab
import json
import os
import sys

def fetch_batch_em():
    symbols = ["NVDA", "TSLA", "AAPL", "SPY"]
    target_date_str = "2025-12-19" # User specified
    # Parse to date object
    from datetime import datetime
    target_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    
    print(f"=== Fetching Expected Moves for {target_date_str} ===")
    
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

    for symbol in symbols:
        print(f"\n--- {symbol} ---")
        
        # 1. Get Price
        try:
            resp = client.get_quote(symbol).json()
            if symbol not in resp:
                print("Quote not found.")
                continue
            current_price = resp[symbol]['quote']['lastPrice']
            print(f"Price: {current_price}")
        except Exception as e:
            print(f"Quote Error: {e}")
            continue

        # 2. Get Chain
        try:
            # We filter by to_date to reduce payload
            # Schwab date format? Usually YYYY-MM-DD
            
            resp = client.get_option_chain(
                symbol,
                strike_count=24,
                strategy='ANALYTICAL',
                # range='NEAR_THE_MONEY', # Removed to be safe
                from_date=target_date_obj,
                to_date=target_date_obj
            ).json()
            
            if 'status' in resp and resp['status'] == 'FAILED':
                 print(f"Chain Failed: {resp}")
                 continue
                 
        except Exception as e:
            print(f"Chain Error: {e}")
            continue

        call_map = resp.get('callExpDateMap', {})
        put_map = resp.get('putExpDateMap', {})
        
        # Find the specific expiration
        # Keys are "YYYY-MM-DD:Days"
        target_key = None
        for k in call_map.keys():
            if k.startswith(target_date_str):
                target_key = k
                break
        
        if not target_key:
            print(f"No expiration found for {target_date_str}. Available: {list(call_map.keys())}")
            continue
            
        # Find ATM
        strikes = []
        for k in call_map[target_key]:
            try: strikes.append(float(k))
            except: pass
            
        if not strikes:
            print("No strikes found.")
            continue
            
        closest_strike = min(strikes, key=lambda x: abs(x - current_price))
        
        # Find exact string key
        strike_key = next((k for k in call_map[target_key] if abs(float(k) - closest_strike) < 0.001), None)
        print(f"ATM Strike: {strike_key}")
        
        # Get Prices
        c_opt = call_map[target_key][strike_key][0]
        p_opt = put_map[target_key][strike_key][0]
        
        def get_mark(o):
            if 'mark' in o: return o['mark']
            return (o.get('bid',0) + o.get('ask',0))/2

        def get_iv(o):
             # Schwab keys for volatility might be 'volatility', 'impliedVolatility', or derived from Greeks
             # Checking likely keys
             if 'volatility' in o: return o['volatility']
             # Sometimes it is not per-option but per-chain? No, usually per option.
             # If missing, we might default to 0
             return 0

        c_val = get_mark(c_opt)
        p_val = get_mark(p_opt)
        straddle = c_val + p_val
        
        # IV Extraction (Average of Call/Put IV)
        c_iv = get_iv(c_opt)
        p_iv = get_iv(p_opt)
        avg_iv = (c_iv + p_iv) / 2 / 100.0 if (c_iv > 0 and p_iv > 0) else 0
        
        # Days to Expiration (DTE)
        # target_date_obj is 2025-12-19
        # Today is... we need to calculate strict DTE
        today_date = datetime.now().date()
        dte = (target_date_obj - today_date).days
        # Use simple DTE or maybe trading days? Formula usually uses calendar days (365) or trading days (252)
        
        print(f"  Call: {c_val:.2f} (IV: {c_iv}%) | Put: {p_val:.2f} (IV: {p_iv}%)")
        print(f"  Straddle (Exp Move): ${straddle:.2f}")
        
        if avg_iv > 0:
            import math
            em_365 = current_price * avg_iv * math.sqrt(dte / 365.0)
            em_252 = current_price * avg_iv * math.sqrt(dte / 252.0)
            
            print(f"  Formula (IV={avg_iv*100:.1f}%, DTE={dte}):")
            print(f"    Base 365: ${em_365:.2f}")
            print(f"    Base 252: ${em_252:.2f}")
            
            # New Custom Metric
            avg_em = (straddle + em_365 + em_252) / 3
            adjusted_em = avg_em * 0.85
            
            print(f"  --- Custom Metric ---")
            print(f"    Avg(Straddle, 365, 252): ${avg_em:.2f}")
            print(f"    Adj Avg (x0.85):         ${adjusted_em:.2f}")
            print(f"    Diff (vs Straddle):      {adjusted_em - straddle:.2f}")
            print(f"    Range (Adj Avg):         {current_price - adjusted_em:.2f} to {current_price + adjusted_em:.2f}")

        else:
            print("  IV not found, cannot calculate formula EM.")

        print(f"  Range (Straddle): {current_price - straddle:.2f} to {current_price + straddle:.2f}")

if __name__ == "__main__":
    fetch_batch_em()
