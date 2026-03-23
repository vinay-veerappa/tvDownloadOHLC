import asyncio
import json
import websockets

async def test_l2():
    uri = "ws://127.0.0.1:8080/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected. Waiting for L2 data...")
            for _ in range(20):
                msg = await websocket.recv()
                data = json.loads(msg)
                event = data.get("data", {})
                service = event.get("service")
                if service == "LEVELTWO_FUTURES":
                    print(f"SUCCESS: Received L2 data for {event.get('content')[0].get('key')}")
                    print(json.dumps(event, indent=2)[:500])
                    return
                else:
                    print(f"Received {service}...")
            print("Finished 20 messages, no L2 data found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_l2())
