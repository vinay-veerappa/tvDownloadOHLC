import asyncio
import websockets
import time
import json

async def test():
    uri = "ws://127.0.0.1:8001/stream?symbol=/NQ&timeframe=1m"
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Connected successfully! Listening for messages for 30s...")
            start_time = time.time()
            while time.time() - start_time < 30:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(msg)
                    mtype = data.get("type")
                    if mtype == "snapshot":
                        print(f"Received snapshot with {len(data.get('candles', []))} candles")
                    elif mtype == "quote":
                        print(f"Quote: {data.get('price')} at {data.get('time')}")
                    elif mtype == "candle":
                        print(f"Candle: {data.get('candle')}")
                    else:
                        print(f"Unknown: {msg}")
                except asyncio.TimeoutError:
                    pass
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(test())
