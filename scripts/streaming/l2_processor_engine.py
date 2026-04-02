import asyncio
import json
import logging
import os
import websockets
import httpx
import socket
from datetime import datetime, timezone
from collections import defaultdict, deque

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("L2Engine")

from scripts.streaming.options.config import HUB_WS_ENDPOINT as HUB_WS, HUB_RESOLVE_ENDPOINT

class L2BookmapEngine:
    """
    Processes L2 Depth (resting) and T&S (market) data to generate Heatmap and Trades.
    """
    def __init__(self, tickers=None):
        if tickers is None:
            tickers = ["/ES", "SPY", "QQQ"]
        self.tickers = tickers
        self.resolved_map = {t: t for t in tickers} # root -> active/ready
        
        # State: Use deques for efficient FIFO memory
        self.states = {}
        for t in tickers:
            self.states[t] = {
                "order_book": {"bid": {}, "ask": {}},
                "heatmap_history": deque(maxlen=1000), # 1000 snapshots
                "trades": deque(maxlen=500), # Unprocessed trades buffer
                "mhvn_weights": defaultdict(float),
                "last_snapshot_time": 0,
                "last_valid_spot": None,
                "heatmap_path": f"data/live/heatmap_{t.replace('/','')}.json",
                "mhvn_path": f"data/live/mhvns_{t.replace('/','')}.json"
            }
        
        # 250ms interval for high-resolution visual flow
        self.snapshot_interval = 0.25
        os.makedirs("data/live", exist_ok=True)

    async def _resolve_tickers(self):
        """Resolve root tickers (e.g. /ES) to active contracts via Hub."""
        roots = [t for t in self.tickers if t.startswith("/")]
        if not roots: return
            
        logger.info(f"Resolving tickers: {roots}...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(HUB_RESOLVE_ENDPOINT, json={"symbols": roots}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success":
                        for root in roots:
                            resolved = data["data"].get(root, {}).get("active")
                            if resolved:
                                self.resolved_map[root] = resolved
                                logger.info(f"✅ Resolved {root} -> {resolved}")
        except Exception as e:
            logger.warning(f"Failed to resolve tickers: {e}")

    def _update_trades(self, content):
        """Processes executed trades (Time & Sales)."""
        for entry in content:
            key = entry.get("key") or entry.get("0")
            target_ticker = next((root for root, res in self.resolved_map.items() if key in (root, res)), None)
            if not target_ticker: continue

            # Schwab typically uses Field 2 for Price, 3 for Size, 4 for Time
            # Some feeds use PRICE/SIZE keys.
            logger.debug(f"Trade Entry: {entry}")
            p = entry.get("2") or entry.get("PRICE") or entry.get("1")
            v = entry.get("3") or entry.get("SIZE") or entry.get("2")
            if p is not None and v is not None:
                logger.info(f"✅ Trade Captured for {target_ticker}: {v} @ {p}")
                self.states[target_ticker]["trades"].append({
                    "p": float(p),
                    "v": int(v),
                    "t": entry.get("4") or entry.get("3") or int(datetime.now(timezone.utc).timestamp() * 1000)
                })

    def _update_depth(self, content):
        """Processes Level 2 incremental updates."""
        for entry in content:
            key = entry.get("key") or entry.get("0")
            target_ticker = next((root for root, res in self.resolved_map.items() if key in (root, res)), None)
            if not target_ticker: continue

            state = self.states[target_ticker]
            
            # Bids (Field 2 or BID_L2_SIZE_MAP)
            bids = entry.get("2", entry.get("BID_L2_SIZE_MAP"))
            if bids:
                levels = bids if isinstance(bids, list) else bids.items() if isinstance(bids, dict) else []
                for level in levels:
                    p, s = (str(level[0]), level[1]) if not isinstance(level, dict) else (str(level.get("0")), level.get("1"))
                    if s == 0: state["order_book"]["bid"].pop(p, None)
                    else: state["order_book"]["bid"][p] = s

            # Asks (Field 3 or ASK_L2_SIZE_MAP)
            asks = entry.get("3", entry.get("ASK_L2_SIZE_MAP"))
            if asks:
                levels = asks if isinstance(asks, list) else asks.items() if isinstance(asks, dict) else []
                for level in levels:
                    p, s = (str(level[0]), level[1]) if not isinstance(level, dict) else (str(level.get("0")), level.get("1"))
                    if s == 0: state["order_book"]["ask"].pop(p, None)
                    else: state["order_book"]["ask"][p] = s

    def _prune_order_book(self, state, spot):
        """Intelligent Ghost Level Prevention (Ticker Agnostic)."""
        if not spot: return
        
        # --- 1. Crossed-Book Purging ---
        # If a bid is significantly higher than the best ask (or vice versa), 
        # it is a ghost level left behind by a missed size=0 packet during a sweep.
        bids = [float(p) for p in state["order_book"]["bid"].keys()]
        asks = [float(p) for p in state["order_book"]["ask"].keys()]
        
        if bids and asks:
            best_bid = max(bids)
            best_ask = min(asks)
            
            # Use a tiny 0.25% tolerance to allow for momentary L2 feed crossed-book glitches,
            # while aggressively deleting obvious trailing ghost levels.
            cross_tolerance = spot * 0.0025 
            
            for p_str in list(state["order_book"]["bid"].keys()):
                if float(p_str) > (best_ask + cross_tolerance):
                    del state["order_book"]["bid"][p_str]
                    
            for p_str in list(state["order_book"]["ask"].keys()):
                if float(p_str) < (best_bid - cross_tolerance):
                    del state["order_book"]["ask"][p_str]

        # --- 2. Depth Capping (Rank-based pruning) ---
        # Retail feeds usually send < 100 levels. Retaining the closest 150 levels 
        # guarantees we keep all valid feed data while preventing infinite memory bloat.
        max_depth = 150
        
        for side in ["bid", "ask"]:
            levels = state["order_book"][side]
            if len(levels) > max_depth:
                # Sort levels by absolute distance from the spot price
                sorted_levels = sorted(levels.keys(), key=lambda p: abs(float(p) - spot))
                
                # Delete anything further away than our max_depth allowance
                for p_str in sorted_levels[max_depth:]:
                    del levels[p_str]
        
    def _export_file(self, path, data):
        """Blocking write helper to be run in thread."""
        try:
            temp = path + ".tmp"
            with open(temp, "w") as f:
                json.dump(data, f)
            os.replace(temp, path)
        except Exception as e:
            logger.error(f"Threaded export failed for {path}: {e}")

    async def _take_snapshots(self):
        now_ts = datetime.now(timezone.utc).timestamp()
        
        for t, state in self.states.items():
            if now_ts - state["last_snapshot_time"] < self.snapshot_interval:
                continue

            # Calculate Spot with Stability Guard
            bids = [float(p) for p in state["order_book"]["bid"].keys()]
            asks = [float(p) for p in state["order_book"]["ask"].keys()]
            best_bid = max(bids) if bids else None
            best_ask = min(asks) if asks else None
            
            spot = None
            if best_bid and best_ask:
                spot = (best_bid + best_ask) / 2
                state["last_valid_spot"] = spot
            else:
                spot = state["last_valid_spot"] or best_bid or best_ask

            if not spot: continue
            
            # Prune Ghost Levels
            self._prune_order_book(state, spot)

            # Snap Trades
            current_trades = list(state["trades"])
            state["trades"].clear()

            snapshot = {
                "t": int(now_ts * 1000),
                "b": {p: s for p, s in state["order_book"]["bid"].items()},
                "a": {p: s for p, s in state["order_book"]["ask"].items()},
                "spot": spot,
                "trades": current_trades
            }
            state["heatmap_history"].append(snapshot)

            # mHVN Logic with bloat cleanup
            decay = 0.95
            for p_str in list(state["mhvn_weights"].keys()):
                state["mhvn_weights"][p_str] *= decay
                if state["mhvn_weights"][p_str] < 1.0:
                    del state["mhvn_weights"][p_str]
            
            for p, s in state["order_book"]["bid"].items(): state["mhvn_weights"][float(p)] += s
            for p, s in state["order_book"]["ask"].items(): state["mhvn_weights"][float(p)] += s

            sorted_bids = sorted([(p, w) for p, w in state["mhvn_weights"].items() if p < spot], key=lambda x: x[1], reverse=True)[:5]
            sorted_asks = sorted([(p, w) for p, w in state["mhvn_weights"].items() if p > spot], key=lambda x: x[1], reverse=True)[:5]
            
            top_mhvns = {
                "timestamp": int(now_ts * 1000), "spot": spot,
                "bids": [{"price": p, "weight": int(w)} for p, w in sorted_bids],
                "asks": [{"price": p, "weight": int(w)} for p, w in sorted_asks]
            }

            # Non-blocking Export via asyncio.to_thread
            await asyncio.to_thread(self._export_file, state["heatmap_path"], list(state["heatmap_history"]))
            await asyncio.to_thread(self._export_file, state["mhvn_path"], top_mhvns)
            
            state["last_snapshot_time"] = now_ts

    def _get_target_ticker(self, key):
        """Helper to match incoming key (might have $ or resolved symbols) to original ticker."""
        if key in self.states: return key
        # Try stripping $ or /
        clean = key.strip("$/")
        if clean in self.states: return clean
        # Fallback to resolved map
        return next((root for root, res in self.resolved_map.items() if key in (root, res)), None)

    def _update_spot(self, content):
        """Processes Level 1 updates to get the latest spot price."""
        for entry in content:
            key = entry.get("key") or entry.get("0")
            target = self._get_target_ticker(key)
            if not target: continue
            
            # Robust mapping: check multiple fields as Schwab indices vary by service
            for f in ["1", "2", "3", "LAST", "CLOSE"]:
                price = entry.get(f)
                if price and isinstance(price, (int, float)) and price > 0:
                    self.states[target]["spot"] = float(price)
                    break

    def _update_depth(self, content):
        """Processes Level 2 book updates."""
        for entry in content:
            key = entry.get("key") or entry.get("0")
            target = self._get_target_ticker(key)
            if not target: continue
            
            # For NASDAQ_BOOK: 1=Timestamp, 2=Bids, 3=Asks
            bids_data = entry.get("2") or entry.get("BIDS", [])
            asks_data = entry.get("3") or entry.get("ASKS", [])
            
            state = self.states.get(target)
            if not state: continue

            # Update spot if bids/asks are available
            if bids_data and isinstance(bids_data, list) and len(bids_data) > 0:
                best_bid = float(bids_data[0].get("0", 0))
                state["spot"] = best_bid

            # Full Refresh if BIDS/ASKS are provided as lists
            if bids_data: state["order_book"]["bid"] = {float(b["0"]): int(b["1"]) for b in bids_data}
            if asks_data: state["order_book"]["ask"] = {float(a["0"]): int(a["1"]) for a in asks_data}

    async def run(self):
        logger.info(f"🚀 L2 Engine (High-Performance) started for {', '.join(self.tickers)}")
        
        retry_delay = 5  # Start with 5s delay
        max_retry_delay = 60 # Max delay of 60s
        
        while True:
            try:
                # 1. Resolve Root Tickers (/ES -> Active Contract) inside the loop 
                # so we can recover from contract expiration during long hub downtime.
                await self._resolve_tickers()
                
                logger.info(f"🔄 Connecting to Hub at {HUB_WS} (Timeout: 30s)...")
                async with websockets.connect(HUB_WS, open_timeout=30) as ws:
                    logger.info("✅ Connection established to L2 Hub.")
                    retry_delay = 5 # Reset delay on success
                    
                    while True:
                        try:
                            msg_raw = await ws.recv()
                            msg = json.loads(msg_raw)
                            event_data = msg.get("data", {})
                            if not isinstance(event_data, dict): continue
                                
                            service = event_data.get("service")
                            if service in ("NASDAQ_BOOK", "NYSE_BOOK", "LEVELTWO_FUTURES", "FUTURES_BOOK"):
                                self._update_depth(event_data.get("content", []))
                            elif service in ("TIMESALE_EQUITY", "TIMESALE_FUTURES", "TIMESALE"):
                                self._update_trades(event_data.get("content", []))
                            elif service in ("LEVELONE_EQUITIES", "LEVELONE_INDICES"):
                                self._update_spot(event_data.get("content", []))
                            
                            await self._take_snapshots()

                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("⚠️ L2 Hub connection closed. Reconnecting...")
                            break
                        except Exception as e:
                            logger.error(f"Loop error: {e}")
                            await asyncio.sleep(0.1)

            except (asyncio.TimeoutError, TimeoutError) as e:
                logger.warning(f"⏳ Hub connection timed out during handshake: {e}. Retrying in {retry_delay}s...")
            except (ConnectionRefusedError, socket.error) as e:
                logger.warning(f"❌ Hub connection refused at {HUB_WS}: {e}. Ensure Hub is running. Retrying in {retry_delay}s...")
            except Exception as e:
                logger.error(f"🚨 Unexpected L2 Engine error: {e}. Retrying in {retry_delay}s...")
            
            await asyncio.sleep(retry_delay)
            # Simple exponential backoff up to max_retry_delay
            retry_delay = min(retry_delay * 1.5, max_retry_delay)

if __name__ == "__main__":
    import argparse
    import sys

    # Use AAPL for comparison as requested by user. AAPL/SPY/QQQ for L2. SPX for L1 spot.
    default_tickers = "AAPL,SPY,QQQ,SPX"
    parser = argparse.ArgumentParser(description="L2 Heatmap Processor")
    parser.add_argument("tickers", type=str, nargs="?", default=default_tickers, help="Comma separated tickers")
    args = parser.parse_args()

    tickers = [s.strip().upper() for s in args.tickers.split(",")]
    engine = L2BookmapEngine(tickers)
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        pass
