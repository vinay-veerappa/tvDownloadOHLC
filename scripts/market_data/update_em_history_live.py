
import asyncio
from prisma import Prisma
import datetime
import sys
import os
import json
import math

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

def get_iv(o):
    return o.get('volatility', 0)

def get_mark(o):
    if 'mark' in o: return o['mark']
    return (o.get('bid',0) + o.get('ask',0))/2

async def update_live_em():
    print("Connecting to DB...")
    db = Prisma()
    await db.connect()

    # Tickers to update
    TICKERS = ["SPY", "QQQ", "IWM", "SPX", "DIA", "AAPL", "AMD", "AMZN", "NVDA", "TSLA", "MSFT", "GOOGL", "META"]
    
    # Setup Client
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Error: Missing credentials")
        return

    with open("secrets.json", "r") as f: secrets = json.load(f)
    
    try:
        client = schwab.auth.client_from_token_file(
            token_path="token.json", api_key=secrets["app_key"], app_secret=secrets["app_secret"], enforce_enums=False
        )
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
            resp = client.get_quote(ticker).json()
            # Handle different response structures
            quote = {}
            for k in resp.keys():
                if k.upper() == ticker.upper(): 
                    quote = resp[k]['quote']
                    break
            if not quote and len(resp) > 0: quote = list(resp.values())[0]['quote']
            
            price = quote.get('lastPrice', 0)
            if price == 0: continue
            
            # 2. Chain
            chain_resp = client.get_option_chain(
                ticker, strike_count=20, strategy='ANALYTICAL', from_date=target_friday, to_date=target_friday
            ).json()
            
            if chain_resp.get('status') != 'SUCCESS':
                print(f"  Chain failed for {ticker}")
                continue

            call_map = chain_resp.get('callExpDateMap', {})
            put_map = chain_resp.get('putExpDateMap', {})
            
            # Find key
            expiry_key = None
            date_str = target_friday.strftime("%Y-%m-%d")
            for k in call_map.keys():
                if k.startswith(date_str):
                    expiry_key = k
                    break
            
            if not expiry_key: 
                print(f"  No expiry key found for {ticker}")
                continue
                
            # Calc Logic
            # Flatten: call_map[expiry] is Dict[Strike, List[Option]]
            # We want the first option from each list
            calls = [opt_list[0] for opt_list in call_map[expiry_key].values() if opt_list]
            puts = [opt_list[0] for opt_list in put_map[expiry_key].values() if opt_list]
            
            # Sort by strike diff
            calls.sort(key=lambda x: abs(float(x['strikePrice']) - price))
            puts.sort(key=lambda x: abs(float(x['strikePrice']) - price))
            
            if not calls or not puts: continue
            
            atm_call = calls[0]
            atm_put = puts[0]
            
            straddle = get_mark(atm_call) + get_mark(atm_put)
            iv = get_iv(atm_call) / 100.0
            
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
