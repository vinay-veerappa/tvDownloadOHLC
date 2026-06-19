import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8080/ws"
    try:
        print(f"Connecting to Hub at {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Connected! Waiting for messages...")
            for i in range(5):
                msg = await websocket.recv()
                data = json.loads(msg)
                print(f"Msg {i}: {list(data.keys())} - {data.get('data', {}).get('service')}")
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(test())
