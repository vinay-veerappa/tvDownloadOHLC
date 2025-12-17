import schwab
import json
import os
import sys
import datetime
import math
import argparse

# --- Constants ---
DEFAULT_TICKERS = ["NVDA", "TSLA", "AAPL", "SPY", "GOOGL", "AVGO", "META", "NFLX", "QQQ", "/ES", "/NQ"]
CACHE_FILE = "data/expected_moves.json"

def get_iv(o):
    # Schwab keys for volatility
    return o.get('volatility', 0)

def get_mark(o):
    if 'mark' in o: return o['mark']
    return (o.get('bid',0) + o.get('ask',0))/2

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                # Check freshness - simplistic: if generated today
                if 'timestamp' in data:
                     ts = datetime.datetime.fromisoformat(data['timestamp'])
                     if ts.date() == datetime.date.today():
                         return data['data']
        except: pass
    return None

def save_cache(data):
    try:
        payload = {
            "timestamp": datetime.datetime.now().isoformat(),
            "data": data
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        print(f"Cache Save Error: {e}", file=sys.stderr)

def fetch_expected_moves(tickers=None, force_refresh=False):
    if not tickers:
        tickers = DEFAULT_TICKERS
    
    # Standardize tickers (caps)
    tickers = [t.upper() for t in tickers]
    
    cached_data = [] # List of dicts
    if not force_refresh:
        loaded = load_cache()
        if loaded:
            cached_data = loaded
            
    # Map cache by ticker for easy lookup
    cache_map = {item['ticker']: item for item in cached_data}
    
    missing_tickers = []
    final_results = []
    
    for t in tickers:
        if t in cache_map:
            final_results.append(cache_map[t])
        else:
            missing_tickers.append(t)
            
    if not missing_tickers:
        # print("All tickers served from cache.")
        return final_results

    print(f"Fetching missing tickers: {missing_tickers}", file=sys.stderr)
    
    # ... Fetch logic for missing_tickers ...
    # Reuse existing fetch logic but only for missing_tickers
    
    # Define paths
    # Script is now in scripts/streaming/, so root is ../../..
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR = os.path.join(ROOT_DIR, "data")
    # Load Secrets
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        return {"error": "Missing credentials"}

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
        return {"error": f"Auth failed: {str(e)}"}

    today = datetime.date.today()
    friday = today + datetime.timedelta(days=(4 - today.weekday() + 7) % 7)
    
    current_weekday = today.weekday() 
    if current_weekday >= 4:
        target_friday = today + datetime.timedelta(days=(4 - current_weekday + 7))
    else:
        target_friday = friday

    print(f"Targeting Week Ending: {target_friday}", file=sys.stderr)
    
    new_results = []
    for symbol in missing_tickers:
        print(f"Processing {symbol}...", file=sys.stderr)
        
        # ... COPY PASTE FETCH LOGIC BELOW (Simplified for diff) ...
        # I need to preserve the fetch body.
        # Ideally I would have refactored fetch_one() but I will just inline for now or careful edit.
        
        if symbol == 'SPX' and not symbol.startswith('$'):
            symbol = '$SPX'
        
        # 1. Get Quote
        try:
            resp = client.get_quote(symbol).json()
            
            # Handle list response
            if isinstance(resp, list):
                 found_key = None
                 if len(resp) > 0: found_key = list(resp[0].keys())[0] # Maybe?
                 # Actually list usually implies error or search results
                 # Let's skip list for now or assume first item
                 # print(f"Quote returned list for {symbol}, handling incomplete")
                 pass

            found_key = None
            if isinstance(resp, dict):
                for k in resp.keys():
                    if k.upper() == symbol.upper():
                        found_key = k
                        break
                if not found_key and len(resp) > 0:
                    found_key = list(resp.keys())[0]
            
            if not found_key:
                print(f"  Quote not found for {symbol}", file=sys.stderr)
                continue
            
            quote_val = resp[found_key]
            if not isinstance(quote_val, dict): continue
            
            quote_obj = quote_val.get('quote', {})
            current_price = quote_obj.get('lastPrice')
            
            if not current_price:
                 continue

        except Exception as e:
            print(f"  Quote Error {symbol}: {e}", file=sys.stderr)
            continue

        # 2. Get Chain
        # Loop over days to ensure we get data (Range requests failing)
        symbol_results = []
        
        # Calculate days to iterate
        # from today to target_friday
        delta = (target_friday - today).days
        date_list = [today + datetime.timedelta(days=i) for i in range(delta + 1)]
        
        for d in date_list:
            if d.weekday() >= 5: continue # Skip weekend
            
            # print(f"  Fetching for {d}...")
            try:
                # Reuse working logic from batch script
                chain_resp = client.get_option_chain(
                    symbol,
                    strike_count=20, 
                    strategy='ANALYTICAL',
                    from_date=d,
                    to_date=d # Single Day
                ).json()
                
                if chain_resp.get('status') == 'FAILED':
                    print(f"    Failed for {d}: {chain_resp}", file=sys.stderr)
                    continue
                
                call_map = chain_resp.get('callExpDateMap', {})
                put_map = chain_resp.get('putExpDateMap', {})
                # print(f"    Raw Keys for {d}: {list(call_map.keys())}", file=sys.stderr)
                
                # Check for expirations on THIS day
                # Keys are "YYYY-MM-DD:Days"
                d_str = d.strftime("%Y-%m-%d")
                target_key = None
                for k in call_map.keys():
                    if k.startswith(d_str):
                        target_key = k
                        break
                
                if not target_key: 
                    # print(f"    No match for {d_str} in {list(call_map.keys())}")
                    continue
                
                # print(f"    Found {target_key} for {d_str}")
                
                # ... Calculation Logic ...
                strikes = []
                # call_map[target_key] is Dict[Strike, List[Option]]
                for k in call_map[target_key]:
                    try: strikes.append(float(k))
                    except: pass
                
                if not strikes: 
                    # print(f"    No strikes found for {target_key}", file=sys.stderr)
                    continue
                
                closest_strike = min(strikes, key=lambda x: abs(x - current_price))
                # print(f"    Target Found: {target_key}. Closest Strike: {closest_strike} (Price: {current_price})", file=sys.stderr)
                
                strike_key = next((k for k in call_map[target_key] if abs(float(k) - closest_strike) < 0.001), None)
                if not strike_key: 
                    # print(f"    Strike Key not found for {closest_strike}", file=sys.stderr)
                    continue
                
                c_opt = call_map[target_key][strike_key][0]
                if target_key in put_map and strike_key in put_map[target_key]:
                    p_opt = put_map[target_key][strike_key][0]
                else: 
                     # print(f"    Put Map Missing Key: {target_key} in {list(put_map.keys())} OR Strike {strike_key}", file=sys.stderr)
                     continue

                straddle = get_mark(c_opt) + get_mark(p_opt)
                c_iv = get_iv(c_opt) 
                p_iv = get_iv(p_opt)
                avg_iv = (c_iv + p_iv) / 2 / 100.0 if (c_iv > 0 and p_iv > 0) else 0
                
                dte = (d - today).days
                if dte == 0: dte = 0.5 
                
                em_365 = 0; em_252 = 0
                if avg_iv > 0:
                    em_365 = current_price * avg_iv * math.sqrt(dte / 365.0)
                    em_252 = current_price * avg_iv * math.sqrt(dte / 252.0)
                
                if dte < 1:
                    if em_365 == 0: em_365 = straddle
                    if em_252 == 0: em_252 = straddle

                avg_em = (straddle + em_365 + em_252) / 3
                adj_em = avg_em * 0.85
                
                symbol_results.append({
                    "date": d_str,
                    "dte": dte,
                    "straddle": round(straddle, 2),
                    "em_365": round(em_365, 2),
                    "em_252": round(em_252, 2),
                    "adj_em": round(adj_em, 2)
                })

            except Exception as e:
                 print(f"    Error {d}: {e}", file=sys.stderr)
                 continue

        new_results.append({
            "ticker": symbol,
            "price": round(current_price, 2),
            "expirations": symbol_results
        })


    # Merge and Save
    # We update the cache_map with new results
    for item in new_results:
        cache_map[item['ticker']] = item
        
    # Re-construct list
    final_data = list(cache_map.values())
    
    if new_results:
        save_cache(final_data)
        
    # Filter return to only requested tickers
    output = [cache_map[t] for t in tickers if t in cache_map]
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", help="List of tickers to fetch")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Force refresh cache")
    args = parser.parse_args()
    
    data = fetch_expected_moves(tickers=args.tickers, force_refresh=args.refresh)
    
    if args.json:
        print(json.dumps(data))
    else:
        # Pretty Print
        print(f"Source: {'Cache/Partial' if not args.refresh else 'Live API'}")
        for item in data:
            print(f"\n=== {item['ticker']} (${item['price']}) ===")
            print(f"{'Date':<12} {'DTE':<4} {'Straddle':<10} {'EM365':<10} {'EM252':<10} {'Adj(85%)':<10}")
            print("-" * 60)
            for exp in item['expirations']:
                print(f"{exp['date']:<12} {exp['dte']:<4} ${exp['straddle']:<9} ${exp['em_365']:<9} ${exp['em_252']:<9} ${exp['adj_em']:<9}")
