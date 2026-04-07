import json
import os
import sys
import datetime
import math
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.streaming.options.options_fetcher import (
    create_client,
    fetch_futures_option_chain_data,
    fetch_option_chain_data,
    _today_ny,
)

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
    "/ES": {"index": "SPX", "etf": "SPY"},
    "/NQ": {"index": "NDX", "etf": "QQQ"},
    "/YM": {"index": "DJX", "etf": "DIA"},
    "/RTY": {"index": "RUT", "etf": "IWM"},
    
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

def is_positive_number(value):
    return isinstance(value, (int, float)) and value > 0

def has_usable_em_payload(item):
    if not isinstance(item, dict):
        return False
    if not is_positive_number(item.get('price')):
        return False
    expirations = item.get('expirations') or []
    if not isinstance(expirations, list) or len(expirations) == 0:
        return False
    return True

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                # Check freshness - simplistic: if generated today
                if 'timestamp' in data:
                     ts = datetime.datetime.fromisoformat(data['timestamp'])
                     if ts.date() == datetime.date.today():
                         return [item for item in data['data'] if has_usable_em_payload(item)]
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
        return {"straddle": None, "em_365": None, "em_252": None, "adj_em": None}

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
    em_365 = None
    em_252 = None
    
    # Standard Rule of 16 (IV / 16 * Price * Sqrt(DTE)) - roughly
    # Text book: Price * IV * Sqrt(DTE/365)
    if dte > 0 and iv > 0:
        em_365 = reference_price * iv * math.sqrt(dte / 365.0)
        em_252 = reference_price * iv * math.sqrt(dte / 252.0)
    
    # Adjusted EM (85% of Straddle or similar rule of thumb)
    # User's logic: 0.85 * Straddle
    adj_em = straddle * 0.85 if is_positive_number(straddle) else None

    return {
        "straddle": straddle,
        "em_365": round(em_365, 2) if is_positive_number(em_365) else None,
        "em_252": round(em_252, 2) if is_positive_number(em_252) else None,
        "adj_em": round(adj_em, 2) if is_positive_number(adj_em) else None
    }


def _dte_targets_for_dates(target_dates):
    logical_today = _today_ny()
    targets = []
    for target_date in target_dates:
        try:
            dte = max((target_date - logical_today).days, 0)
        except Exception:
            continue
        if dte not in targets:
            targets.append(dte)
    return targets or [0]


def _chain_to_quote(chain):
    spot = getattr(chain, "spot_price", 0.0) or getattr(chain, "spot", 0.0) or 0.0
    spot_open = getattr(chain, "spot_open", 0.0) or spot
    return {
        "lastPrice": spot,
        "openPrice": spot_open,
        "closePrice": spot,
    }


def _chain_to_exp_maps(chain):
    call_map = {}
    put_map = {}
    logical_today = _today_ny()

    for contract in getattr(chain, "calls", []):
        expiry = getattr(contract, "expiry", None)
        if not expiry:
            continue
        expiry_date = expiry if isinstance(expiry, datetime.date) else None
        if expiry_date is None and hasattr(expiry, "date"):
            expiry_date = expiry.date()
        if expiry_date is None:
            continue
        dte = int(getattr(contract, "dte", 0) or max((expiry_date - logical_today).days, 0))
        expiry_key = f"{expiry_date.isoformat()}:{dte}"
        strike_key = str(float(getattr(contract, "strike", 0.0) or 0.0))
        call_map.setdefault(expiry_key, {}).setdefault(strike_key, []).append({
            "strikePrice": getattr(contract, "strike", 0.0),
            "volatility": (getattr(contract, "iv", 0.0) or 0.0) * 100.0,
            "mark": getattr(contract, "mark", 0.0),
            "bid": getattr(contract, "bid", 0.0),
            "ask": getattr(contract, "ask", 0.0),
            "last": getattr(contract, "last", 0.0),
        })

    for contract in getattr(chain, "puts", []):
        expiry = getattr(contract, "expiry", None)
        if not expiry:
            continue
        expiry_date = expiry if isinstance(expiry, datetime.date) else None
        if expiry_date is None and hasattr(expiry, "date"):
            expiry_date = expiry.date()
        if expiry_date is None:
            continue
        dte = int(getattr(contract, "dte", 0) or max((expiry_date - logical_today).days, 0))
        expiry_key = f"{expiry_date.isoformat()}:{dte}"
        strike_key = str(float(getattr(contract, "strike", 0.0) or 0.0))
        put_map.setdefault(expiry_key, {}).setdefault(strike_key, []).append({
            "strikePrice": getattr(contract, "strike", 0.0),
            "volatility": (getattr(contract, "iv", 0.0) or 0.0) * 100.0,
            "mark": getattr(contract, "mark", 0.0),
            "bid": getattr(contract, "bid", 0.0),
            "ask": getattr(contract, "ask", 0.0),
            "last": getattr(contract, "last", 0.0),
        })

    return {
        "callExpDateMap": call_map,
        "putExpDateMap": put_map,
    }

def fetch_ticker_data(_client, symbol, target_fridays):
    """
    Fetches Quote and Chain for a symbol. 
    Returns: { quote_obj, chain_obj_map } where chain_obj_map is keyed by date.
    """
    dte_targets = _dte_targets_for_dates(target_fridays)
    quote_obj = {}
    chain_obj_map = {}

    try:
        if symbol.startswith("/"):
            chain = fetch_futures_option_chain_data(symbol, dte_targets)
        else:
            client = create_client()
            chain = fetch_option_chain_data(client, symbol, dte_targets)

        quote_obj = _chain_to_quote(chain)
        chain_resp = _chain_to_exp_maps(chain)
        for target_date in target_fridays:
            expiry_key = get_closest_expiry_key(chain_resp.get("callExpDateMap", {}), target_date)
            if expiry_key:
                chain_obj_map[target_date] = chain_resp
    except Exception as e:
        print(f"  Shared Fetch Error {symbol}: {e}", file=sys.stderr)

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

    # Date Logic
    today = _today_ny()
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
            idx_quote, idx_chains = fetch_ticker_data(None, idx_sym, target_dates)
            # Fetch ETF
            etf_quote, etf_chains = fetch_ticker_data(None, etf_sym, target_dates)
            
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
                    if not is_positive_number(val) or not is_positive_number(etf_ref) or not is_positive_number(idx_ref):
                        return None
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
                if is_positive_number(idx_close) and any(
                    is_positive_number(exp_data.get(k)) for k in ("adj_em", "em_252", "em_365", "straddle")
                ):
                    output_item['expirations'].append(exp_data)
                
        else:
            # Standard Ticker
            quote, chains = fetch_ticker_data(None, req_ticker, target_dates)
            
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
                if is_positive_number(cls) and any(
                    is_positive_number(exp_data.get(k)) for k in ("adj_em", "em_252", "em_365", "straddle")
                ):
                    output_item['expirations'].append(exp_data)
                 
        if has_usable_em_payload(output_item):
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
