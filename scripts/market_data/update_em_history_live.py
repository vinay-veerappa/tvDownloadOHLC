
import asyncio
from prisma import Prisma
import datetime
import sys
import os
import math

# Ensure repository root is in sys.path so scripts can find top-level packages
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)


# Load Environment (for Prisma)
try:
    with open('web/.env', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ[k] = v.strip('"').strip("'")
except Exception as e:
    print(f"Warning: Could not load .env: {e}")

# Import Schwab (Assuming installed)
import schwab

from scripts.market_data.schwab_options_utils import (
    create_schwab_client,
    fetch_option_chain,
    find_expiration_key,
    first_contracts_for_expiration,
    get_option_iv,
    get_option_mark,
    normalize_option_chain_symbol,
)


async def update_live_em():
    print("Connecting to DB...")
    db = Prisma()
    await db.connect()

    # Tickers to update
    TICKERS = ["SPY", "QQQ", "IWM", "SPX", "DIA", "AAPL", "AMD", "AMZN", "NVDA", "TSLA", "MSFT", "GOOGL", "META"]
    
    # Setup Client
    try:
        client = create_schwab_client(".")
    except Exception as e:
        print(f"Auth failed: {e}")
        return

    # Date Logic
    today = datetime.date.today()
    friday = today + datetime.timedelta(days=(4 - today.weekday() + 7) % 7)
    current_weekday = today.weekday() 
    # If today is Friday, use today. If Weekend, use next Friday? 
    # Usually we want "This Week's Expiry" or "Next Week's".
    # Logic from api_expected_move: 
    target_friday = today + datetime.timedelta(days=(4 - current_weekday + 7)) if current_weekday >= 4 else friday
    
    print(f"Target Expiry for EM Calculation: {target_friday}")
    
    # Note: History table uses 'date' as the RECORD date (i.e. Today), not Expiry Date.
    # We record: On [Today], the EM for [Target] was X.
    
    for ticker in TICKERS:
        print(f"Processing {ticker}...")
        try:
            # 1. Quote
            api_symbol = normalize_option_chain_symbol(ticker)
            resp = client.get_quote(api_symbol).json()
            # Handle different response structures
            quote = {}
            if isinstance(resp, dict):
                # Try finding exact match
                for k, v in resp.items():
                    if k.upper() == api_symbol.upper() and isinstance(v, dict) and 'quote' in v:
                        quote = v['quote']
                        break
                # Fallback to first dict with 'quote'
                if not quote:
                    for v in resp.values():
                        if isinstance(v, dict) and 'quote' in v:
                            quote = v['quote']
                            break
            
            price = quote.get('lastPrice', 0)
            if price == 0:
                print(f"  Warning: No price found for {ticker} (API symbol {api_symbol})")
                continue

            
            # 2. Chain
            try:
                chain_result = fetch_option_chain(
                    client,
                    ticker,
                    strike_count=20,
                    strategy='ANALYTICAL',
                    from_date=target_friday,
                    to_date=target_friday,
                )
            except Exception as e:
                print(f"  Chain failed for {ticker}: {e}")
                continue

            chain_resp = chain_result.payload

            call_map = chain_resp.get('callExpDateMap', {})
            put_map = chain_resp.get('putExpDateMap', {})
            
            # Find key
            expiry_key = find_expiration_key(call_map, target_friday)
            
            if not expiry_key: 
                print(f"  No expiry key found for {ticker}")
                continue
                
            # Calc Logic
            # Flatten: call_map[expiry] is Dict[Strike, List[Option]]
            # We want the first option from each list
            calls = first_contracts_for_expiration(call_map, expiry_key)
            puts = first_contracts_for_expiration(put_map, expiry_key)
            
            # Sort by strike diff
            calls.sort(key=lambda x: abs(float(x['strikePrice']) - price))
            puts.sort(key=lambda x: abs(float(x['strikePrice']) - price))
            
            if not calls or not puts: continue
            
            atm_call = calls[0]
            atm_put = puts[0]
            
            straddle = get_option_mark(atm_call) + get_option_mark(atm_put)
            iv = get_option_iv(atm_call) / 100.0
            
            # DTE
            dte = (target_friday - today).days
            if dte < 0: dte = 0
            
            em365 = price * iv * math.sqrt(dte/365.0) if dte > 0 else 0
            em252 = price * iv * math.sqrt(dte/252.0) if dte > 0 else 0
            em_straddle = straddle * 0.85
            
            print(f"  Price: {price:.2f}, Straddle: {straddle:.2f}, EM(Adj): {em_straddle:.2f}")
            
            # DB Insert
            # We insert/update for TODAY (date=today)
            # Use strict datetime for today
            today_dt = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            data = {
                'ticker': ticker,
                'date': today_dt,
                'closePrice': float(price),
                'straddlePrice': float(straddle),
                'emStraddle': float(em_straddle),
                'iv365': float(iv),
                'em365': float(em365),
                'em252': float(em252),
                'source': 'live_update'
            }
            
            await db.expectedmovehistory.upsert(
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
    asyncio.run(update_live_em())
