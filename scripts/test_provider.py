import asyncio
import logging

import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

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
