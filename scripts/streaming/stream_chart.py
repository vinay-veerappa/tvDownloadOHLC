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

# Configuration
SYMBOL = "/NQ" # Futures Ticker
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "live_chart.json")

# Global Buffer
chart_data = {
    "symbol": SYMBOL,
    "last_update": "",
    "live_price": 0.0,
    "candles": []
}

LIVE_STORAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "live_storage.parquet")

# Ensure data dir exists
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# Restore from Parquet on startup if session exists
if os.path.exists(LIVE_STORAGE_FILE):
    try:
        df = pd.read_parquet(LIVE_STORAGE_FILE)
        if not df.empty:
            # We must drop 'timestamp' because it's a pandas object and not JSON serializable
            # The hot buffer only needs the raw fields like 'time' (int)
            if 'timestamp' in df.columns:
                df = df.drop(columns=['timestamp'])
            chart_data["candles"] = df.to_dict(orient="records")
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

async def main():
    client = get_client()
    if not client: return

    # Force a token refresh if needed by making a lightweight call
    try:
        print("Verifying session...")
        client.get_account_numbers()
        print("Session verified.")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Session check failed: {e}")
        print("Your 'token.json' access token is expired and could not be refreshed.")
        print("Please re-generate your token (delete token.json and run your auth script again).")
        return

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
    # Register Handlers
    stream_client.add_chart_futures_handler(chart_handler)
    stream_client.add_level_one_futures_handler(level_one_handler)

    # Subscribe
    await stream_client.chart_futures_subs([SYMBOL])
    await stream_client.level_one_futures_subs([SYMBOL])

    print(f"Streaming {SYMBOL} to {OUTPUT_FILE}...")
    
    while True:
        await stream_client.handle_message()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping stream...")
