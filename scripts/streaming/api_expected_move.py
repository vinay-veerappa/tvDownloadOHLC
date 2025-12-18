import schwab
import json
import os
import sys
import datetime
import math
import argparse
import copy

# --- Constants ---
DEFAULT_TICKERS = [
    # Indices/ETFs
    "SPY", "QQQ", "IWM", "DIA", "TLT", "GLD", "SLV", "USO", "UNG",
    # Futures
    "/ES", "/NQ", "/YM", "/RTY", "/GC", "/CL", "/SI", "/NG",
    # Mag 7 / Big Tech
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD",
    # AI / Data Center / Semi / Cloud
    "PLTR", "MU", "SMCI", "ARM", "VRT", "DELL", "ORCL",
    "CRWD", "NBIS", "ANET", "PSTG", "WDC", "SOUN", "AI",
    # Banks / Financials
    "JPM", "GS", "MS", "BAC", "C",
    # High Beta / Popular
    "NFLX", "COIN", "MSTR", "AVGO"
]
CACHE_FILE = "data/expected_moves.json"

# --- Proxy Map ---
# Maps Futures -> { index: UnderlyingIndex, etf: UnderlyingETF }
# For Commodities (Gold, Oil), we map Index to the Future itself (for spot price) and ETF to the liquid ETF.
PROXY_MAP = {
    "/ES": {"index": "$SPX", "etf": "SPY"},
    "/NQ": {"index": "$NDX", "etf": "QQQ"},
    "/YM": {"index": "$DJI", "etf": "DIA"},
    "/RTY": {"index": "$RUT", "etf": "IWM"},
    
    # Commodities
    "/GC": {"index": "/GC", "etf": "GLD"},
    "/CL": {"index": "/CL", "etf": "USO"},
    "/SI": {"index": "/SI", "etf": "SLV"},
    "/NG": {"index": "/NG", "etf": "UNG"},
}

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

def get_closest_expiry_key(call_map, date_obj):
    """Find the expiry key matching the given date."""
    d_str = date_obj.strftime("%Y-%m-%d")
    for k in call_map.keys():
        if k.startswith(d_str):
            return k
    return None

def calculate_straddle_cost(call_map, put_map, expiry_key, strike_price):
    """Calculates ATM straddle cost for a specific strike."""
    if not expiry_key: return 0
    
    raw_calls = call_map.get(expiry_key, {})
    raw_puts = put_map.get(expiry_key, {})
    
    # Schwab structure: { "expiry_key": { "strike_price": [ {option_obj} ] } }
    # Flatten to list of option objects
    calls = []
    for s_key, q_list in raw_calls.items():
        if q_list: calls.append(q_list[0])

    puts = []
    for s_key, q_list in raw_puts.items():
        if q_list: puts.append(q_list[0])
    
    # Find closest strike options
    # Sort by distance to strike_price
    calls.sort(key=lambda x: abs(float(x['strikePrice']) - strike_price))
    puts.sort(key=lambda x: abs(float(x['strikePrice']) - strike_price))
    
    if not calls or not puts: return 0

    atm_call = calls[0]
    atm_put = puts[0]
    
    # Verify strikes are reasonably close (e.g. within 1%)
    # If nearest strike is far away, data might be missing, but we proceed anyway.
    
    call_mark = get_mark(atm_call)
    put_mark = get_mark(atm_put)
    
    return call_mark + put_mark



def calculate_em_values(chain_resp, date_obj, reference_price):
    """
    Calculates Expected Move values based on a reference price.
    Returns dict: { straddle, em_365, em_252, adj_em }
    """
    call_map = chain_resp.get('callExpDateMap', {})
    put_map = chain_resp.get('putExpDateMap', {})
    expiry_key = get_closest_expiry_key(call_map, date_obj)
    
    if not expiry_key or not reference_price or reference_price == 0:
        return {"straddle": 0, "em_365": 0, "em_252": 0, "adj_em": 0}

    # 1. Straddle Cost
    straddle = calculate_straddle_cost(call_map, put_map, expiry_key, reference_price)
    
    # 2. IV Calculation (EM Formula)
    # Get IV from ATM option
    raw_calls = call_map.get(expiry_key, {})
    calls = []
    for s_key, q_list in raw_calls.items():
        if q_list: calls.append(q_list[0])
        
    iv = 0
    dte = 0
    if calls:
        # Re-sort for IV extraction
        calls.sort(key=lambda x: abs(float(x['strikePrice']) - reference_price))
        atm_opt = calls[0]
        iv = get_iv(atm_opt) / 100.0 # Convert to decimal
        
        # Parse DTE from key: "YYYY-MM-DD:Days"
        try:
             parts = expiry_key.split(':')
             if len(parts) > 1:
                 dte = int(parts[1])
             else:
                 # Fallback if DTE missing in key
                 dte = (date_obj - datetime.date.today()).days
        except: dte = 0

    # Avoid div by 0
    em_365 = 0
    em_252 = 0
    
    # Standard Rule of 16 (IV / 16 * Price * Sqrt(DTE)) - roughly
    # Text book: Price * IV * Sqrt(DTE/365)
    if dte >= 0:
        em_365 = reference_price * iv * math.sqrt(dte / 365.0)
        em_252 = reference_price * iv * math.sqrt(dte / 252.0)
    
    # Adjusted EM (85% of Straddle or similar rule of thumb)
    # User's logic: 0.85 * Straddle
    adj_em = straddle * 0.85

    return {
        "straddle": straddle,
        "em_365": round(em_365, 2),
        "em_252": round(em_252, 2),
        "adj_em": round(adj_em, 2)
    }

def fetch_ticker_data(client, symbol, target_fridays):
    """
    Fetches Quote and Chain for a symbol. 
    Returns: { quote_obj, chain_obj_map } where chain_obj_map is keyed by date.
    """
    # 1. Get Quote
    quote_obj = {}
    try:
        resp = client.get_quote(symbol).json()
        found_key = None
        if isinstance(resp, dict):
            for k in resp.keys():
                if k.upper() == symbol.upper(): found_key = k; break
            if not found_key and len(resp) > 0: found_key = list(resp.keys())[0]
        
        if found_key and isinstance(resp[found_key], dict):
             quote_obj = resp[found_key].get('quote', {})
    except Exception as e:
        print(f"  Quote Error {symbol}: {e}", file=sys.stderr)

    # 2. Get Chain for target dates
    chain_obj_map = {}
    for d in target_fridays:
        try:
            chain_resp = client.get_option_chain(
                symbol, strike_count=20, strategy='ANALYTICAL', from_date=d, to_date=d
            ).json()
            if chain_resp.get('status') == 'SUCCESS':
                chain_obj_map[d] = chain_resp
        except Exception as e:
            print(f"  Chain Error {symbol} {d}: {e}", file=sys.stderr)
            
    return quote_obj, chain_obj_map


def fetch_expected_moves(tickers=None, force_refresh=False):
    if not tickers: tickers = DEFAULT_TICKERS
    tickers = [t.upper() for t in tickers]
    
    # Cache Check
    if not force_refresh:
        loaded = load_cache()
        if loaded:
             # Check if ALL requested tickers are present
             loaded_tickers = set(item['ticker'] for item in loaded)
             requested = set(tickers)
             if requested.issubset(loaded_tickers):
                 # Filter and return only requested
                 return [item for item in loaded if item['ticker'] in requested]
             # If missing some, we could partial return, but simpler to just refresh all or missing.
             # For now, let's just proceed to fetch if we need specific tickers not in cache.
             pass

    # Setup Client
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        return {"error": "Missing credentials"}
    with open("secrets.json", "r") as f: secrets = json.load(f)
    
    try:
        client = schwab.auth.client_from_token_file(
            token_path="token.json", api_key=secrets["app_key"], app_secret=secrets["app_secret"], enforce_enums=False
        )
    except Exception as e:
         return {"error": f"Auth failed: {str(e)}"}

    # Date Logic
    today = datetime.date.today()
    friday = today + datetime.timedelta(days=(4 - today.weekday() + 7) % 7)
    current_weekday = today.weekday() 
    target_friday = today + datetime.timedelta(days=(4 - current_weekday + 7)) if current_weekday >= 4 else friday
    
    # We will fetch only ONE Friday for now as per original script logic
    target_dates = [target_friday]

    final_results = []
    
    for req_ticker in tickers:
        print(f"Processing {req_ticker}...", file=sys.stderr)
        
        is_proxy = req_ticker in PROXY_MAP
        
        # Prepare data containers
        # We need data for: 
        # 1. The ticker itself (if not proxy, or if explicitly requested)
        # 2. The Index Proxy (if proxy)
        # 3. The ETF Proxy (if proxy)
        
        output_item = {
            "ticker": req_ticker,
            "price": 0,
            "expirations": []
        }
        
        if is_proxy:
            # Dual Proxy Mode
            p_map = PROXY_MAP[req_ticker]
            idx_sym = p_map['index']
            etf_sym = p_map['etf']
            
            # Fetch Index
            idx_quote, idx_chains = fetch_ticker_data(client, idx_sym, target_dates)
            # Fetch ETF
            etf_quote, etf_chains = fetch_ticker_data(client, etf_sym, target_dates)
            
            # Reference Prices (Index)
            idx_last = idx_quote.get('lastPrice', 0)
            idx_open = idx_quote.get('openPrice', idx_last) # Fallback
            idx_close = idx_quote.get('closePrice', idx_last) # Settlement
            
            output_item['price'] = idx_last # Main display price is Index Spot
            
            # Reference Prices (ETF)
            etf_last = etf_quote.get('lastPrice', 1) # Avoid div0
            etf_open = etf_quote.get('openPrice', etf_last)
            etf_close = etf_quote.get('closePrice', etf_last)
            
            for d in target_dates:
                # 1. Index Calcs (Primary)
                idx_chain = idx_chains.get(d, {})
                idx_res_last = calculate_em_values(idx_chain, d, idx_last)
                idx_res_open = calculate_em_values(idx_chain, d, idx_open)
                idx_res_close = calculate_em_values(idx_chain, d, idx_close)
                
                # 2. ETF Calcs (Secondary)
                etf_chain = etf_chains.get(d, {})
                etf_res_last = calculate_em_values(etf_chain, d, etf_last)
                etf_res_open = calculate_em_values(etf_chain, d, etf_open)
                etf_res_close = calculate_em_values(etf_chain, d, etf_close)
                
                # 3. Normalization (ETF % -> Index Price)
                # Form: ETF_EM / ETF_Ref * Index_Ref
                
                def normalize(val, etf_ref, idx_ref):
                    if etf_ref == 0: return 0
                    pct = val / etf_ref
                    return round(pct * idx_ref, 2)

                # Normalized Values
                norm_open = normalize(etf_res_open['adj_em'], etf_open, idx_open)
                norm_close = normalize(etf_res_close['adj_em'], etf_close, idx_close)
                norm_last = normalize(etf_res_last['adj_em'], etf_last, idx_last)
                
                # Construct Expiration Object
                # Base fields use Index-Close/Last (Standard)
                # Extended fields inside 'details'
                
                dte = 0
                # Extract DTE from one of the results or recalc
                if d >= today: dte = (d - today).days

                exp_data = {
                    "date": d.strftime("%Y-%m-%d"),
                    "dte": dte,
                    
                    # Standard View (Index Close/Settlement is usually the benchmark)
                    "straddle": idx_res_close['straddle'], 
                    "em_365": idx_res_close['em_365'],
                    "em_252": idx_res_close['em_252'], 
                    "adj_em": idx_res_close['adj_em'], 
                    
                    # Extended Data
                    "basis": {
                        "open": {
                            "price": idx_open,
                            "index_em": idx_res_open['adj_em'],
                            "etf_em": norm_open
                        },
                        "close": {
                            "price": idx_close,
                            "index_em": idx_res_close['adj_em'],
                            "etf_em": norm_close
                        },
                        "last": {
                            "price": idx_last,
                            "index_em": idx_res_last['adj_em'],
                            "etf_em": norm_last
                        }
                    },
                    "note": f"Proxies: {idx_sym} & {etf_sym}"
                }
                output_item['expirations'].append(exp_data)
                
        else:
            # Standard Ticker
            quote, chains = fetch_ticker_data(client, req_ticker, target_dates)
            
            last = quote.get('lastPrice', 0)
            opn = quote.get('openPrice', last)
            cls = quote.get('closePrice', last)
            
            output_item['price'] = last
            
            for d in target_dates:
                 chain = chains.get(d, {})
                 
                 res_last = calculate_em_values(chain, d, last)
                 res_open = calculate_em_values(chain, d, opn)
                 res_close = calculate_em_values(chain, d, cls)
                 
                 dte = (d - today).days if d >= today else 0

                 exp_data = {
                    "date": d.strftime("%Y-%m-%d"),
                    "dte": dte,
                    "straddle": res_close['straddle'], # Default to Close/Settlement
                    "em_365": res_close['em_365'],
                    "em_252": res_close['em_252'],
                    "adj_em": res_close['adj_em'],
                    
                    "basis": {
                        "open": { "price": opn, "index_em": res_open['adj_em'] },
                        "close": { "price": cls, "index_em": res_close['adj_em'] },
                        "last": { "price": last, "index_em": res_last['adj_em'] }
                    }
                 }
                 output_item['expirations'].append(exp_data)
                 
        final_results.append(output_item)
        
    save_cache(final_results)
    
    return final_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", help="Tickers to fetch")
    parser.add_argument("--refresh", action="store_true", help="Force refresh cache")
    args = parser.parse_args()
    
    data = fetch_expected_moves(args.tickers, args.refresh)
    print(json.dumps(data))
