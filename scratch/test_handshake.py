import asyncio
import aiohttp

async def test():
    url = "http://127.0.0.1:8001/stream?symbol=/NQ&timeframe=1m"
    headers = {
        "Origin": "http://localhost:3000",
        "Upgrade": "websocket",
        "Connection": "Upgrade",
        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
        "Sec-WebSocket-Version": "13"
    }
    async with aiohttp.ClientSession() as session:
        try:
            print("Sending handshake request...")
            async with session.get(url, headers=headers) as resp:
                print("Status:", resp.status)
                print("Headers:", dict(resp.headers))
                body = await resp.read()
                print("Body:", body)
        except Exception as e:
            print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(test())
