import asyncio
from prisma import Prisma
import datetime
import math
import os
import httpx
import sys

# Ensure repository root is in sys.path so scripts can find top-level packages
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Load Environment
try:
    with open('web/.env', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v.strip('"').strip("'")
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

from scripts.streaming.options.config import HUB_URL

def get_mark(o):
    if 'mark' in o: return o['mark']
    return (o.get('bid',0) + o.get('ask',0))/2

def get_iv(o):
    return o.get('volatility', 0)

async def hub_request(method, params):
    """Send a REST request through the Hub's proxy."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=30.0)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, dict) and "status" not in result:
                    return {"status": "success", "data": result}
                return result
            else:
                return {"status": "error", "message": f"Hub Error [{resp.status_code}]: {resp.text}"}
        except Exception as e:
            return {"status": "error", "message": f"Hub Connection Error: {str(e)}"}

async def capture_rth_metrics():
    print("Connecting to DB...")
    db = Prisma()
    await db.connect()
    
    # 2. Tickers to Track
    TICKERS = ["SPY", "QQQ", "IWM", "SPX", "NVDA", "TSLA", "AAPL", "AMD", "AMZN", "MSFT", "GOOGL", "META"]
    
    # Date Logic: Target Expiry
    today = datetime.date.today()
    friday = today + datetime.timedelta(days=(4 - today.weekday() + 7) % 7)
    current_weekday = today.weekday() 
    target_friday = today + datetime.timedelta(days=(4 - current_weekday + 7)) if current_weekday >= 4 else friday
    
    print(f"Target Expiry: {target_friday}")
    
    # Volatility Index Mapping
    VOL_MAP = {
        "SPY": "$VIX", "SPX": "$VIX",
        "QQQ": "$VXN", "NQ": "$VXN", "NDX": "$VXN",
        "IWM": "$RVX", "RTY": "$RVX", "RUT": "$RVX"
    }
    
    # 1. Fetch All Volatility Indices
    vol_symbols = list(set(VOL_MAP.values()))
    search_symbols = []
    for s in vol_symbols:
        search_symbols.append(s)
        search_symbols.append(s.replace('$', '')) # Try "VIX" too
        
    print(f"Fetching Volatility Indices: {search_symbols}")
    
    vol_values = {} # Symbol -> Value
    
    # Batch fetch via Hub
    v_resp_raw = await hub_request("get_quotes", {"symbols": search_symbols})
    if v_resp_raw.get("status") == "success":
        v_resp = v_resp_raw.get("data", {})
        for k, v in v_resp.items():
            if isinstance(v, dict) and 'quote' in v and 'lastPrice' in v['quote']:
                val = v['quote']['lastPrice']
                clean_key = k.upper().replace('$','')
                vol_values[k] = val
                vol_values[clean_key] = val
                if not k.startswith('$'): vol_values[f"${k}"] = val
                print(f"  Captured {k}: {val}")
    else:
        print(f"Error fetching volatility indices: {v_resp_raw.get('message')}")
            
    print(f"Final Vol Indices: {vol_values}")
            
    for ticker in TICKERS:
        try:
            print(f"Processing {ticker}...")
            # Spot Price
            search_ticker = "$SPX" if ticker == "SPX" else ticker
            q_resp_raw = await hub_request("get_quotes", {"symbols": [search_ticker]})
            
            if q_resp_raw.get("status") != "success":
                print(f"  Quote fetch failed for {ticker}: {q_resp_raw.get('message')}")
                continue
                
            q_resp = q_resp_raw.get("data", {})
            
            quote = {}
            for k in q_resp.keys():
                if k.upper().replace('$','') == ticker.upper(): 
                    quote = q_resp[k]['quote']
                    break
            if not quote and len(q_resp) > 0:
                 first_val = list(q_resp.values())[0]
                 if isinstance(first_val, dict) and 'quote' in first_val: 
                     quote = first_val['quote']
            
            price = quote.get('lastPrice')
            if not price: 
                print(f"  No price for {ticker}")
                continue
                
            # Chain
            chain_resp_raw = await hub_request("get_option_chain", {
                "symbol": search_ticker,
                "strike_count": 20,
                "strategy": "ANALYTICAL",
                "from_date": target_friday.strftime("%Y-%m-%d"),
                "to_date": target_friday.strftime("%Y-%m-%d")
            })
            
            if chain_resp_raw.get('status') != 'success':
                print(f"  Chain fetch failed for {ticker}: {chain_resp_raw.get('message')}")
                continue
                
            chain_resp = chain_resp_raw.get("data", {})
            
            if chain_resp.get('status') and chain_resp.get('status') != 'SUCCESS':
                continue
                
            # Find Expiry Map
            call_map = chain_resp.get('callExpDateMap', {})
            put_map = chain_resp.get('putExpDateMap', {})
            
            expiry_key = None
            date_str = target_friday.strftime("%Y-%m-%d")
            for k in call_map.keys():
                if k.startswith(date_str):
                    expiry_key = k
                    break
            
            if not expiry_key: continue
            
            # Extract lists
            calls = [opt_list[0] for opt_list in call_map[expiry_key].values() if opt_list]
            puts = [opt_list[0] for opt_list in put_map[expiry_key].values() if opt_list]
            
            calls.sort(key=lambda x: abs(float(x['strikePrice']) - price))
            puts.sort(key=lambda x: abs(float(x['strikePrice']) - price))
            
            if not calls or not puts: continue
            
            atm_call = calls[0]
            atm_put = puts[0]
            
            straddle = get_mark(atm_call) + get_mark(atm_put)
            iv = get_iv(atm_call) / 100.0
            
            # Calcs
            raw_days = (target_friday - today).days
            dte = max(1, raw_days)
            if dte < 0: dte = 1 # Safety fix, though max(1) covers it
            time_factor = math.sqrt(dte / 365.0)
            
            # 1. Straddle EM
            em_straddle = straddle * 0.85
            
            # 2. IV EM
            em_iv = price * iv * time_factor
            
            # 3. VIX EM (Use Mapped Index)
            # Default to VIX if not mapped
            vol_idx_sym = VOL_MAP.get(ticker, "$VIX")
            # Try to get value (try symbol, then symbol w/o $)
            vix_used = vol_values.get(vol_idx_sym)
            if not vix_used:
                 vix_used = vol_values.get(vol_idx_sym.replace('$',''))
            # Fallback to standard VIX if specific not found
            if not vix_used:
                 vix_used = vol_values.get('VIX') or vol_values.get('$VIX')
            
            em_vix = 0
            if vix_used:
                em_vix = price * (vix_used / 100.0) * time_factor
            
            print(f"  Price: {price:.2f} | EM(S): {em_straddle:.2f} | EM(IV): {em_iv:.2f} | EM({vol_idx_sym}): {em_vix:.2f}")
            
            # DB Upsert RthExpectedMove
            # Use strict today date
            today_dt = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            data = {
                'ticker': ticker,
                'date': today_dt,
                'openPrice': float(price),
                'vixValue': float(vix_used) if vix_used else None,
                'straddlePrice': float(straddle),
                'emStraddle': float(em_straddle),
                'ivAtOpen': float(iv),
                'emIv': float(em_iv),
                'emVix': float(em_vix)
            }
            
            # Upsert
            await db.rthexpectedmove.upsert(
                where={
                    'ticker_date': {'ticker': ticker, 'date': today_dt}
                },
                data={
                    'create': data,
                    'update': data
                }
            )
            
        except Exception as e:
            print(f"  Error {ticker}: {e}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(capture_rth_metrics())
