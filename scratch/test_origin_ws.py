import asyncio
import websockets

async def test():
    uri = "ws://127.0.0.1:8001/stream?symbol=/NQ&timeframe=1m"
    headers = {
        "Origin": "http://localhost:3000"
    }
    try:
        print(f"Connecting to {uri} with Origin: http://localhost:3000 ...")
        async with websockets.connect(uri, extra_headers=headers) as websocket:
            print("Connected successfully with Origin!")
            msg = await websocket.recv()
            print("Received:", msg[:100])
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(test())
