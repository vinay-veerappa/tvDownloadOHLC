import asyncio
import schwab
import json
import os
import sys
import time
import pandas as pd
from datetime import datetime
from schwab.auth import easy_client
from schwab.client import Client
from schwab.streaming import StreamClient
from schwab_token_sync import sync_token_to_db, restore_token_from_db

# Configuration
SYMBOL = "/NQ" # Futures Ticker
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "live_chart.json")

# Global State
active_subscriptions = {"futures": [], "equities": []}
chart_data = {
    "symbol": SYMBOL,
    "last_update": "",
    "live_price": 0.0,
    "candles": []
}

LIVE_STORAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "live_storage.parquet")

# Ensure data dir exists
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

def deduplicate_candles(candles):
    """Ensures candles are unique by 'time' and sorted."""
    if not candles: return []
    unique = {}
    for c in candles:
        unique[c['time']] = c
    return sorted(unique.values(), key=lambda x: x['time'])

# Restore from Parquet on startup if session exists
if os.path.exists(LIVE_STORAGE_FILE):
    try:
        df = pd.read_parquet(LIVE_STORAGE_FILE)
        if not df.empty:
            # We must drop 'timestamp' because it's a pandas object and not JSON serializable
            # The hot buffer only needs the raw fields like 'time' (int)
            if 'timestamp' in df.columns:
                df = df.drop(columns=['timestamp'])
            chart_data["candles"] = deduplicate_candles(df.to_dict(orient="records"))
            chart_data["last_update"] = datetime.now().isoformat()
            print(f"✅ Restored {len(chart_data['candles'])} bars from session history.")
    except Exception as e:
        print(f"Could not restore session: {e}")

with open(OUTPUT_FILE, "w") as f:
    json.dump(chart_data, f, indent=2)

def get_client():
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Missing credentials")
        return None

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    try:
        return easy_client(
            api_key=secrets["app_key"],
            app_secret=secrets["app_secret"],
            callback_url='https://127.0.0.1:8182',
            token_path='token.json')
    except Exception as e:
        print(f"Auth failed: {e}")
        return None

def fetch_bootstrap_data(client, symbol):
    """
    Fetches the last 2 days of 1-minute history to prime the chart.
    """
    print(f"🚀 Bootstrapping history for {symbol}...")
    try:
        resp = client.get_price_history(symbol, 
                                        period_type=Client.PriceHistory.PeriodType.DAY,
                                        period=Client.PriceHistory.Period.TWO_DAYS,
                                        frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                                        frequency=Client.PriceHistory.Frequency.EVERY_MINUTE)
        
        if resp.status_code != 200:
            print(f"❌ Bootstrap failed: {resp.status_code} - {resp.text}")
            return []

        data = resp.json()
        candles = data.get('candles', [])
        
        if not candles:
            print(f"⚠️ No bootstrap candles returned for {symbol}")
            return []

        # Map Schwab keys to our standard format
        formatted = []
        for c in candles:
            formatted.append({
                "time": c.get("datetime", 0),
                "open": c.get("open", 0),
                "high": c.get("high", 0),
                "low": c.get("low", 0),
                "close": c.get("close", 0),
                "volume": c.get("volume", 0)
            })
        
        print(f"✅ Fetched {len(formatted)} bootstrap bars.")
        return formatted
        
    except Exception as e:
        print(f"❌ Bootstrap exception: {e}")
        return []

async def main():
    # 1. Attempt token restoration if file is missing
    restore_token_from_db()

    client = get_client()
    if not client: return

    # Force a token refresh if needed and sync back to DB
    try:
        print("Verifying session...")
        client.get_account_numbers()
        sync_token_to_db() # Sync any refresh back to SQLite
        print("Session verified and synced to DB.")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Session check failed: {e}")
        print("Your 'token.json' access token is expired and could not be refreshed.")
        print("Please re-generate your token (delete token.json and run your auth script again).")
        return

    # Bootstrap History
    bootstrap_candles = fetch_bootstrap_data(client, SYMBOL)
    if bootstrap_candles:
        # Merge bootstrap with any existing restored session data
        existing_times = {c["time"] for c in chart_data["candles"]}
        new_candles = [c for c in bootstrap_candles if c["time"] not in existing_times]
        
        # Prepend new historical candles
        chart_data["candles"] = deduplicate_candles(chart_data["candles"] + bootstrap_candles)
        
        # Keep buffer size in check
        if len(chart_data["candles"]) > 5000:
            chart_data["candles"] = chart_data["candles"][-5000:]
            
        chart_data["last_update"] = datetime.now().isoformat()
        with open(OUTPUT_FILE, "w") as f:
            json.dump(chart_data, f, indent=2)
        print(f"🔥 Hot start: {len(chart_data['candles'])} total bars in buffer.")

    stream_client = StreamClient(client, account_id='BB4E515511E76B8B035DC72194CA615919766D183922871CF062DB9ACA6E0EBD') 

    async def level_one_handler(msg):
        if 'content' in msg:
            for c in msg['content']:
                if c.get('key') == SYMBOL:
                    # Field 3 is usually Last Price for Level 1 Futures
                    last_price = c.get("3") or c.get("LAST_PRICE")
                    if last_price:
                        chart_data["live_price"] = last_price
                        chart_data["last_update"] = datetime.now().isoformat()
                        
                        # We don't necessarily need to write to file on EVERY tick if it's too fast,
                        # but for "seeing it move" we should write it.
                        with open(OUTPUT_FILE, "w") as f:
                            json.dump(chart_data, f, indent=2)

    async def chart_handler(msg):
        if 'content' in msg:
            for c in msg['content']:
                if c.get('key') == SYMBOL:
                    candle = {
                        "time": c.get("CHART_TIME_MILLIS", 0),
                        "open": c.get("OPEN_PRICE", 0),
                        "high": c.get("HIGH_PRICE", 0),
                        "low": c.get("LOW_PRICE", 0),
                        "close": c.get("CLOSE_PRICE", 0),
                        "volume": c.get("VOLUME", 0)
                    }
                    
                    # If this is a NEW bar starting, we flush the PREVIOUS bar to Parquet
                    new_bar = False
                    if chart_data["candles"] and chart_data["candles"][-1]["time"] != candle["time"]:
                        new_bar = True
                        completed_candle = chart_data["candles"][-1]
                        
                        # Append to Parquet
                        try:
                            df = pd.DataFrame([completed_candle])
                            # Convert time to datetime for standard storage
                            df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
                            
                            if not os.path.exists(LIVE_STORAGE_FILE):
                                df.to_parquet(LIVE_STORAGE_FILE, index=False)
                            else:
                                # Simple append for small data; for large data pandas.read_parquet then to_parquet is slow
                                # but fine for our "separate session file" use case.
                                existing_df = pd.read_parquet(LIVE_STORAGE_FILE)
                                pd.concat([existing_df, df]).drop_duplicates(subset=['time']).to_parquet(LIVE_STORAGE_FILE, index=False)
                            print(f"📁 Archived bar {completed_candle['time']} to Parquet")
                        except Exception as e:
                            print(f"Error saving to Parquet: {e}")

                    # Update Buffer
                    if chart_data["candles"] and chart_data["candles"][-1]["time"] == candle["time"]:
                        chart_data["candles"][-1] = candle
                    else:
                        chart_data["candles"].append(candle)
                        # Keep up to ~3.5 days of 1-minute data in the hot buffer
                        if len(chart_data["candles"]) > 5000:
                            chart_data["candles"].pop(0)
                        
                    chart_data["last_update"] = datetime.now().isoformat()
                    
                    # FINAL DEDUPE before write
                    chart_data["candles"] = deduplicate_candles(chart_data["candles"])
                    
                    # Also keep live_price in sync with last candle close if no L1 yet
                    if chart_data["live_price"] == 0:
                        chart_data["live_price"] = candle["close"]
                    
                    try:
                        with open(OUTPUT_FILE, "w") as f:
                            json.dump(chart_data, f, indent=2)
                        print(f"Updated chart: {candle['time']} C:{candle['close']}")
                    except Exception as e:
                        print(f"Write error: {e}")

    

    # Login & Start
    await stream_client.login()
    # await stream_client.quality_of_service(schwab.streaming.StreamClient.QOSLevel.EXPRESS) 
    # Detect Asset Type
    is_future = SYMBOL.startswith("/") or SYMBOL.endswith("!")
    
    # Register Handlers
    if is_future:
        print(f"📡 Registering Futures handlers for {SYMBOL}...")
        stream_client.add_chart_futures_handler(chart_handler)
        stream_client.add_level_one_futures_handler(level_one_handler)
    else:
        print(f"📡 Registering Equity handlers for {SYMBOL}...")
        # Note: Handlers for equities might need slight adjustments to chart_handler if fields differ,
        # but schwab-py tries to normalize them.
        stream_client.add_chart_equity_handler(chart_handler)
        stream_client.add_level_one_equity_handler(level_one_handler)

    # Subscribe & Track
    if is_future:
        await stream_client.chart_futures_subs([SYMBOL])
        await stream_client.level_one_futures_subs([SYMBOL])
        active_subscriptions["futures"] = list(set(active_subscriptions["futures"] + [SYMBOL]))
    else:
        await stream_client.chart_equity_subs([SYMBOL])
        await stream_client.level_one_equity_subs([SYMBOL])
        active_subscriptions["equities"] = list(set(active_subscriptions["equities"] + [SYMBOL]))

    print(f"Streaming {SYMBOL} to {OUTPUT_FILE}...")
    
    last_sync = time.time()
    
    while True:
        try:
            await stream_client.handle_message()
            
            # Periodic sync (every 30 mins)
            if time.time() - last_sync > 1800:
                print("⏳ Periodic token sync to DB...")
                sync_token_to_db()
                last_sync = time.time()
                
        except Exception as e:
            print(f"⚠️ Stream error: {e}. Attempting recovery in 5s...")
            await asyncio.sleep(5)
            try:
                print("🔄 Reconnecting...")
                await stream_client.login()
                
                # Re-subscribe to all active
                if active_subscriptions["futures"]:
                    await stream_client.chart_futures_subs(active_subscriptions["futures"])
                    await stream_client.level_one_futures_subs(active_subscriptions["futures"])
                if active_subscriptions["equities"]:
                    await stream_client.chart_equity_subs(active_subscriptions["equities"])
                    await stream_client.level_one_equity_subs(active_subscriptions["equities"])
                
                print("✅ Recovery successful.")
            except Exception as re:
                print(f"❌ Recovery failed: {re}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping stream...")
