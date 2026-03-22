import asyncio
import json
import logging
import os
import websockets
from datetime import datetime, timezone
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("L2Engine")

HUB_WS = "ws://127.0.0.1:8080/ws"

class L2BookmapEngine:
    """
    Processes L2 Depth and T&S data to generate Heatmap and mHVNs.
    """
    def __init__(self, ticker="/ES"):
        self.ticker = ticker
        self.order_book = {"bid": {}, "ask": {}} # {price: size}
        self.heatmap_history = [] # List of {timestamp, data: {price: size}}
        self.mhvn_weights = defaultdict(float) # price -> weight
        self.last_snapshot_time = 0
        self.snapshot_interval = 1.0 # 1 second snapshots
        
        # Output paths
        self.heatmap_path = f"data/live/heatmap_{ticker.replace('/','')}.json"
        self.mhvn_path = f"data/live/mhvns_{ticker.replace('/','')}.json"
        os.makedirs("data/live", exist_ok=True)

    def _update_depth(self, content):
        for entry in content:
            if entry.get("key") != self.ticker: continue
            
            # Update Bid/Ask depth
            if "BID_L2_SIZE_MAP" in entry:
                for price, size in entry["BID_L2_SIZE_MAP"].items():
                    if size == 0: self.order_book["bid"].pop(price, None)
                    else: self.order_book["bid"][price] = size
            
            if "ASK_L2_SIZE_MAP" in entry:
                for price, size in entry["ASK_L2_SIZE_MAP"].items():
                    if size == 0: self.order_book["ask"].pop(price, None)
                    else: self.order_book["ask"][price] = size

    def _take_snapshot(self):
        now = datetime.now(timezone.utc).timestamp()
        if now - self.last_snapshot_time < self.snapshot_interval:
            return

        # Create snapshot of current book
        snapshot = {
            "t": int(now),
            "b": {p: s for p, s in self.order_book["bid"].items()},
            "a": {p: s for p, s in self.order_book["ask"].items()}
        }
        self.heatmap_history.append(snapshot)
        if len(self.heatmap_history) > 1000: # Keep last ~15 mins
            self.heatmap_history.pop(0)

        # Update mHVN potential (persistence of large orders)
        self._detect_mhvns()
        
        # Write to files
        self._export_data()
        self.last_snapshot_time = now

    def _detect_mhvns(self):
        # Weight levels with high liquidity persistence
        threshold = 50 # Example threshold for /ES
        for side in ["bid", "ask"]:
            for price, size in self.order_book[side].items():
                if size > threshold:
                    self.mhvn_weights[price] += 1
                else:
                    self.mhvn_weights[price] *= 0.95 # Decay if size drops
        
        # Prune low weights
        self.mhvn_weights = {p: w for p, w in self.mhvn_weights.items() if w > 5}

    def _export_data(self):
        try:
            with open(self.heatmap_path, "w") as f:
                json.dump(self.heatmap_history[-300:], f) # Last 5 mins for UI
            
            # Export top mHVNs
            sorted_mhvns = sorted(self.mhvn_weights.items(), key=lambda x: x[1], reverse=True)[:10]
            with open(self.mhvn_path, "w") as f:
                json.dump([{"p": p, "w": w} for p, w in sorted_mhvns], f)
        except Exception as e:
            logger.error(f"Export error: {e}")

    async def run(self):
        logger.info(f"🚀 L2 Engine started for {self.ticker}")
        async with websockets.connect(HUB_WS) as ws:
            while True:
                try:
                    msg_raw = await ws.recv()
                    msg = json.loads(msg_raw)
                    event_data = msg.get("data", {})
                    
                    if event_data.get("service") == "LEVELTWO_FUTURES":
                        self._update_depth(event_data.get("content", []))
                    
                    self._take_snapshot()
                except Exception as e:
                    logger.error(f"Loop error: {e}")
                    await asyncio.sleep(1)

if __name__ == "__main__":
    engine = L2BookmapEngine("/ES")
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        pass
