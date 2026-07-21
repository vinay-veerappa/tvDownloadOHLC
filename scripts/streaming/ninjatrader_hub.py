#!/usr/bin/env python3
"""
ninjatrader_hub.py — NinjaTrader 8 Unified Hub & Local Event Streamer

Architecture:
  NT8 McpBridge (http://127.0.0.1:7890/api/events/stream - SSE)
        |
        v
  NinjaTraderUnifiedHub (http://127.0.0.1:7891)
        |
        +---> Local WebSocket Broadcast Bus (ws://127.0.0.1:7891/ws)
        |     (Subscribers: Trading Second Brain, Discord Notifier, Dashboards)
        |
        +---> REST Proxy & Event Replay (http://127.0.0.1:7891/events/history)

Run:
  python scripts/streaming/ninjatrader_hub.py --port 7891
"""

import asyncio
import json
import os
import sys
import io
import logging
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NinjaTraderHub")

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    import uvicorn
    import httpx
except ImportError:
    logger.error("FastAPI, uvicorn, or httpx missing. Please install dependencies.")
    FastAPI = None

NT8_BRIDGE_URL = os.environ.get("NT8_BRIDGE_URL", "http://127.0.0.1:7890")
NT8_MCP_TOKEN = os.environ.get("NT8_MCP_TOKEN", "")
HUB_PORT = int(os.environ.get("NT8_HUB_PORT", "7891"))

class NinjaTraderHub:
    def __init__(self):
        self.active_websockets: list[WebSocket] = []
        self.event_history: list[dict] = []
        self.max_history = 500
        self.is_connected = False
        self.last_event_time = None
        self._sse_task = None

    async def connect_websocket(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.append(websocket)
        logger.info(f"New spoke connected to NT8 Hub. Total spokes: {len(self.active_websockets)}")
        # Send initial status handshake
        await websocket.send_json({
            "type": "handshake",
            "hub": "NinjaTraderHub",
            "version": "1.4.0",
            "status": "connected" if self.is_connected else "reconnecting",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def disconnect_websocket(self, websocket: WebSocket):
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)
            logger.info(f"Spoke disconnected from NT8 Hub. Remaining spokes: {len(self.active_websockets)}")

    async def broadcast_event(self, event: dict):
        # Store in history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)

        self.last_event_time = datetime.now(timezone.utc).isoformat()

        # Broadcast to all connected WebSocket spokes
        disconnected = []
        for ws in self.active_websockets:
            try:
                await ws.send_json(event)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect_websocket(ws)

    async def start_sse_listener(self):
        """Continuously listens to NT8 McpBridge's SSE stream and broadcasts to spokes."""
        logger.info(f"Connecting to NinjaTrader McpBridge SSE stream at {NT8_BRIDGE_URL}/api/events/stream...")
        headers = {}
        if NT8_MCP_TOKEN:
            headers["Authorization"] = f"Bearer {NT8_MCP_TOKEN}"

        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", f"{NT8_BRIDGE_URL}/api/events/stream", headers=headers) as response:
                        if response.status_code == 200:
                            self.is_connected = True
                            logger.info("Successfully connected to NT8 McpBridge event stream!")
                            buffer = ""
                            async for chunk in response.aiter_text():
                                buffer += chunk
                                while "\n\n" in buffer:
                                    line_block, buffer = buffer.split("\n\n", 1)
                                    for line in line_block.split("\n"):
                                        if line.startswith("data: "):
                                            raw_data = line[6:].strip()
                                            try:
                                                payload = json.loads(raw_data)
                                                event = {
                                                    "type": payload.get("event", "fill"),
                                                    "data": payload,
                                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                                }
                                                await self.broadcast_event(event)
                                            except json.JSONDecodeError:
                                                pass
                        else:
                            self.is_connected = False
                            logger.warning(f"NT8 McpBridge returned status {response.status_code}. Retrying in 5s...")
            except Exception as ex:
                self.is_connected = False
                logger.warning(f"NT8 McpBridge SSE connection lost: {ex}. Retrying in 5s...")

            await asyncio.sleep(5)

hub = NinjaTraderHub()

if FastAPI:
    app = FastAPI(title="NinjaTrader Unified Hub", version="1.4.0")

    @app.on_event("startup")
    async def startup_event():
        hub._sse_task = asyncio.create_task(hub.start_sse_listener())

    @app.get("/status")
    async def get_status():
        return {
            "status": "online",
            "hub": "NinjaTraderUnifiedHub",
            "version": "1.4.0",
            "nt8_connected": hub.is_connected,
            "connected_spokes": len(hub.active_websockets),
            "last_event_time": hub.last_event_time,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @app.get("/events/history")
    async def get_event_history(limit: int = 50):
        return {
            "count": min(limit, len(hub.event_history)),
            "events": hub.event_history[-limit:]
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await hub.connect_websocket(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                # Respond to ping messages from spokes
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            hub.disconnect_websocket(websocket)

if __name__ == "__main__":
    if not FastAPI:
        print("FastAPI is required to run the hub server.")
        sys.exit(1)
    
    print(f"[NT8 Hub] Starting NinjaTrader Unified Hub on http://127.0.0.1:{HUB_PORT}")
    uvicorn.run(app, host="127.0.0.1", port=HUB_PORT)
