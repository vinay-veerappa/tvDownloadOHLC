import asyncio
import json
import httpx
import websockets
import time

async def test_hub_connectivity():
    print("🔍 Testing Hub Connectivity...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://127.0.0.1:8000/docs")
            if resp.status_code == 200:
                print("✅ Hub REST Server is UP.")
    except Exception as e:
        print(f"❌ Hub REST Server is DOWN: {e}")

async def test_ws_broadcast():
    print("🔍 Testing WebSocket Broadcast...")
    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws") as ws:
            print("✅ Successfully connected to Hub WebSocket.")
            # Wait for 5 seconds to see if any messages come through
            start = time.time()
            while time.time() - start < 5:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    print(f"📥 Received Message: {msg[:100]}...")
                    return True
                except asyncio.TimeoutError:
                    continue
            print("⚠️ Connected but No Data received (is the Hub streaming?).")
    except Exception as e:
        print(f"❌ WebSocket Connection Failed: {e}")
    return False

if __name__ == "__main__":
    asyncio.run(test_hub_connectivity())
    asyncio.run(test_ws_broadcast())
