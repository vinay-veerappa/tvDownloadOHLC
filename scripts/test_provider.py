import asyncio
import logging
from scripts.streaming.providers.schwab_dev_provider import SchwabDevProvider

logging.basicConfig(level=logging.INFO)

async def handle_msg(msg):
    # Filter out heartbeats for cleaner output
    if isinstance(msg, dict) and msg.get('service') == 'HEARTBEAT':
        return
    print(f"MSG: {str(msg)[:200]}...")

async def test():
    provider = SchwabDevProvider()
    if await provider.initialize():
        print("Initialized")
        await provider.start_stream(
            symbols_l1=["AAPL", "/NQ"],
            symbols_l2=["AAPL"],
            on_message_cb=handle_msg
        )

if __name__ == "__main__":
    asyncio.run(test())
