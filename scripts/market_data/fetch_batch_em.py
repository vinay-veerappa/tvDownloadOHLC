import json
import os
import sys
import asyncio
import httpx
from datetime import datetime

# Ensure repository root is in sys.path so scripts can find top-level packages
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from scripts.streaming.options.config import HUB_URL
from scripts.market_data.schwab_options_utils import (
    find_expiration_key,
    get_option_iv,
    get_option_mark,
)

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

async def fetch_batch_em():
    symbols = ["NVDA", "TSLA", "AAPL", "SPY"]
    target_date_str = "2025-12-19" # User specified
    # Parse to date object
    target_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    
    print(f"=== Fetching Expected Moves for {target_date_str} via Hub ===")
    
    for symbol in symbols:
        print(f"\n--- {symbol} ---")
        
        # 1. Get Price
        try:
            resp_raw = await hub_request("get_quotes", {"symbols": [symbol]})
            if resp_raw.get("status") != "success":
                print(f"Quote fetch failed: {resp_raw.get('message')}")
                continue
                
            resp = resp_raw.get("data", {})
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
            chain_resp_raw = await hub_request("get_option_chain", {
                "symbol": symbol,
                "strike_count": 24,
                "strategy": "ANALYTICAL",
                "from_date": target_date_obj.strftime("%Y-%m-%d"),
                "to_date": target_date_obj.strftime("%Y-%m-%d")
            })
            
            if chain_resp_raw.get("status") != "success":
                print(f"Chain Error: {chain_resp_raw.get('message')}")
                continue
                
            resp = chain_resp_raw.get("data", {})
            
            if resp.get('status') and resp.get('status') != 'SUCCESS':
                print(f"Chain Status Failed: {resp.get('status')}")
                continue
                 
        except Exception as e:
            print(f"Chain Error: {e}")
            continue

        call_map = resp.get('callExpDateMap', {})
        put_map = resp.get('putExpDateMap', {})
        
        # Find the specific expiration
        # Keys are "YYYY-MM-DD:Days"
        target_key = find_expiration_key(call_map, target_date_obj)
        
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
        
        c_val = get_option_mark(c_opt)
        p_val = get_option_mark(p_opt)
        straddle = c_val + p_val
        
        # IV Extraction (Average of Call/Put IV)
        c_iv = get_option_iv(c_opt)
        p_iv = get_option_iv(p_opt)
        avg_iv = (c_iv + p_iv) / 2 / 100.0 if (c_iv > 0 and p_iv > 0) else 0
        
        # Days to Expiration (DTE)
        today_date = datetime.now().date()
        dte = (target_date_obj - today_date).days
        
        print(f"  Call: {c_val:.2f} (IV: {c_iv}%) | Put: {p_val:.2f} (IV: {p_iv}%)")
        print(f"  Straddle (Exp Move): ${straddle:.2f}")
        
        if avg_iv > 0:
            import math
            em_365 = current_price * avg_iv * math.sqrt(dte / 365.0) if dte > 0 else 0
            em_252 = current_price * avg_iv * math.sqrt(dte / 252.0) if dte > 0 else 0
            
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
    asyncio.run(fetch_batch_em())
