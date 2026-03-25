import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SubCheck")

async def check():
    uri = "ws://localhost:8000/ws"
    logger.info(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        logger.info("Connected. Waiting for events...")
        count = 0
        while count < 20:
            msg = await ws.recv()
            data = json.loads(msg)
            event = data.get("data", {})
            service = event.get("service")
            key = event.get("key") or event.get("content", [{}])[0].get("key") or event.get("content", [{}])[0].get("0")
            
            if service in ("NASDAQ_BOOK", "NYSE_BOOK", "FUTURES_BOOK", "LEVELTWO_FUTURES"):
                logger.info(f"✅ Received L2: {service} for {key}")
            else:
                logger.info(f"Received {service} for {key}")
            count += 1

if __name__ == "__main__":
    asyncio.run(check())
