import asyncio
import schwab
import json
import os
import sys
import time
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
    "candles": []
}

def get_client():
    if not os.path.exists("secrets.json") or not os.path.exists("token.json"):
        print("Missing credentials")
        return None

    with open("secrets.json", "r") as f:
        secrets = json.load(f)
        
    try:
        # return schwab.auth.client_from_token_file(
        #     token_path="token.json",
        #     api_key=secrets["app_key"],
        #     app_secret=secrets["app_secret"],
        #     enforce_enums=False
        # )
        return easy_client(
            api_key='h0R0afB9sjKVRZsjmgoQTtsXwLM6z0ffq9LOAarsA0d7dl0d',
            app_secret='P9G0ZzUyGtYFrVX9UPwenDBtn8EljzCmNa5PmspBxdARfpn1D5N0lQt3Y4cqlBSm',
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

    stream_client = StreamClient(client, account_id=1234567890) #schwab.streaming.StreamClient(client)

    async def chart_handler(msg):
        # Format of msg for Chart Futures is similar to Equity
        # { "service": "CHART_FUTURES", "content": [ { "key": "/NQ", "1": 21000.0 ... } ] }
        # Fields: 0=key, 1=Open, 2=High, 3=Low, 4=Close, 5=Volume, 6=Seq, 7=Time
        
        # print(f"Received: {json.dumps(msg, indent=2)}") 
        
        if 'content' in msg:
            for c in msg['content']:
                if c.get('key') == SYMBOL:
                    # Parse candle
                    # Based on ChartFuturesFields: 
                    # 0=Symbol, 1=Time, 2=Open, 3=High, 4=Low, 5=Close, 6=Vol
                    
                    time_val = c.get("1", 0)
                    
                    candle = {
                        "time": time_val, # Epoch ms
                        "open": c.get("2", 0),
                        "high": c.get("3", 0),
                        "low": c.get("4", 0),
                        "close": c.get("5", 0),
                        "volume": c.get("6", 0)
                    }
                    
                    # Update Buffer
                    if chart_data["candles"] and chart_data["candles"][-1]["time"] == candle["time"]:
                        chart_data["candles"][-1] = candle
                    else:
                        chart_data["candles"].append(candle)
                        if len(chart_data["candles"]) > 500:
                            chart_data["candles"].pop(0)
                        
                    chart_data["last_update"] = datetime.now().isoformat()
                    
                    try:
                        with open(OUTPUT_FILE, "w") as f:
                            json.dump(chart_data, f, indent=2)
                        print(f"Updated chart: {candle['time']} C:{candle['close']}")
                    except Exception as e:
                        print(f"Write error: {e}")

    

    # Login & Start
    await stream_client.login()
    await stream_client.quality_of_service(schwab.streaming.StreamClient.QOSLevel.EXPRESS)
    # Register Futures Handler
    stream_client.add_chart_futures_handler(chart_handler)
    # Subscribe to 1-minute bars for Futures
    # Fields: 0=Symbol, 1=Time, 2=Open, 3=High, 4=Low, 5=Close, 6=Vol
    await stream_client.chart_futures_subs([SYMBOL], fields=[0, 1, 2, 3, 4, 5, 6])

    print(f"Streaming {SYMBOL} to {OUTPUT_FILE}...")
    
    while True:
        await stream_client.handle_message()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping stream...")
