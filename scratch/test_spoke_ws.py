import asyncio
import websockets
import json

async def main():
    uri = "ws://localhost:8001/stream?symbol=/NQ&timeframe=1m"
    print(f"Connecting to Spoke WS at {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected! Waiting for messages...")
            # We'll listen for 15 seconds
            try:
                while True:
                    msg_raw = await asyncio.wait_for(ws.recv(), timeout=15)
                    msg = json.loads(msg_raw)
                    print(f"WS Msg: {msg.get('type')} - {msg}")
            except asyncio.TimeoutError:
                print("No message received for 15 seconds (timeout)")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
