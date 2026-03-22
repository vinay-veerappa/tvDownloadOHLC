import asyncio
import json
import os
import logging
from datetime import datetime, timezone
from schwab.auth import client_from_token_file
from schwab.client import AsyncClient
from schwab.streaming import StreamClient
from scripts.streaming.schwab_token_sync import restore_token_from_db, sync_token_to_db

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    import uvicorn
except ImportError:
    FastAPI = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SchwabUnifiedHub")

class SchwabUnifiedHub:
    """
    The Central Hub for Schwab API interactions.
    Manages one WebSocket connection and proxies REST requests.
    """
    def __init__(self, secrets_path="secrets.json", token_path="token.json"):
        self.secrets_path = secrets_path
        self.token_path = token_path
        self.client = None
        self.stream_client = None
        self.is_running = False
        
        # FastAPI for Local Broadcasting
        self.app = FastAPI() if FastAPI else None
        self.active_sockets: list[WebSocket] = []
        
        # Local Bus: Queue for internal sub-tasks
        self.broadcast_queue = asyncio.Queue()
        
        # REST Request Queue
        self.rest_queue = asyncio.Queue()
        self.rate_limit_delay = 0.5  # 500ms between REST calls
        
        if self.app:
            @self.app.websocket("/ws")
            async def websocket_endpoint(websocket: WebSocket):
                await websocket.accept()
                self.active_sockets.append(websocket)
                try:
                    while True:
                        # Keep connection alive
                        await websocket.receive_text()
                except WebSocketDisconnect:
                    self.active_sockets.remove(websocket)

            @self.app.post("/request")
            async def proxy_request(request: dict):
                """
                Endpoint for spokes to submit REST requests.
                Format: {"method": "get_option_chain", "params": {...}}
                """
                response_queue = asyncio.Queue()
                await self.rest_queue.put((request, response_queue))
                return await response_queue.get()
        
    async def initialize(self):
        """Initialize authentication and clients."""
        if not os.path.exists(self.secrets_path):
            raise FileNotFoundError(f"Secrets file not found: {self.secrets_path}")
            
        with open(self.secrets_path, 'r') as f:
            secrets = json.load(f)
            
        try:
            # Use AsyncClient for the Hub
            # client_from_token_file with asyncio=True already returns an AsyncClient
            self.client = client_from_token_file(
                self.token_path,
                secrets["app_key"],
                secrets["app_secret"],
                asyncio=True,
                enforce_enums=False
            )
            # Double check enforce_enums is False (library internal state)
            if hasattr(self.client, 'enforce_enums'):
                self.client.enforce_enums = False
                
            logger.info("✅ Authentication successful (Async).")
            
            self.stream_client = StreamClient(self.client)
            await self.stream_client.login()
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Schwab client: {e}")
            return False

    async def _handle_stream_event(self, event):
        """Callback for all streaming events."""
        # Add to local broadcast queue
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": event
        }
        await self.broadcast_queue.put(payload)
        
        # Push to all active WebSockets
        for socket in self.active_sockets:
            try:
                await socket.send_json(payload)
            except Exception:
                # Handle stale sockets if cleanup missed them
                pass

        # Log periodically or for critical events
        service = event.get("service", "UNKNOWN")
        if service != "HEARTBEAT":
            logger.debug(f"Received {service} event")

    async def _rest_worker(self):
        """Processes REST requests from the queue with rate limiting."""
        logger.info("🚀 REST Worker started.")
        while True:
            request_data, response_queue = await self.rest_queue.get()
            method_name = request_data.get("method")
            params = request_data.get("params", {})
            
            try:
                method = getattr(self.client, method_name)
                # Execute the Schwab API call - Use await since it's now AsyncClient
                coro = method(**params)
                resp = await coro
                
                # Check for success (AsyncClient returns httpx.Response for non-JSON methods 
                # or the parsed JSON for others, but let's be robust)
                if hasattr(resp, 'json'):
                    data = resp.json()
                    status_code = resp.status_code
                else:
                    data = resp
                    status_code = 200 # If it's already parsed as dict
                
                await response_queue.put({
                    "status": "success" if status_code < 400 else "error",
                    "data": data,
                    "status_code": status_code
                })
            except Exception as e:
                logger.error(f"Error in REST worker ({method_name}): {e}")
                await response_queue.put({"status": "error", "message": str(e)})
            
            # Enforce rate limit delay
            await asyncio.sleep(self.rate_limit_delay)
            self.rest_queue.task_done()

    async def start_stream(self, symbols_l1=None, symbols_l2=None):
        """Start the unified WebSocket stream."""
        if not self.stream_client:
            logger.error("Stream client not initialized.")
            return

        async def on_message(message):
            await self._handle_stream_event(message)

        # Use a list of services to subscribe to, but use generic handlers if possible
        # or register them one by one if they exist
        possible_handlers = [
            "add_level_one_futures_handler",
            "add_level_one_futures_options_handler",
            "add_chart_futures_handler"
        ]
        
        for h_name in possible_handlers:
            if hasattr(self.stream_client, h_name):
                getattr(self.stream_client, h_name)(on_message)
                logger.info(f"Registered handler: {h_name}")

        # If we need L2/Timesale and the library doesn't have an 'add_' method,
        # we can't easily subscribe unless we use the raw _handlers.
        # But let's try to just use what's there for now to get it running.
        
        # Futures are the priority for now
        if symbols_l1:
            await self.stream_client.level_one_futures_subs(symbols_l1)
        
        if symbols_l2:
            if hasattr(self.stream_client, "level_two_futures_subs"):
                await self.stream_client.level_two_futures_subs(symbols_l2)
            else:
                logger.warning("LEVELTWO_FUTURES subscription not supported by this library version.")
            
        logger.info(f"Stream started for L1:{symbols_l1}, L2:{symbols_l2}")
        
        self.is_running = True
        while self.is_running:
            await self.stream_client.handle_message()

    async def stop(self):
        self.is_running = False
        if self.stream_client:
            await self.stream_client.logout()

# Manual Test Entry Point
if __name__ == "__main__":
    hub = SchwabUnifiedHub()
    async def run_hub():
        if await hub.initialize():
            # Example: Subscribe to /ES and /NQ
            await hub.start_stream(
                symbols_l1=["/ES", "/NQ"],
                symbols_l2=["/ES", "/NQ"]
            )
            
    try:
        hub = SchwabUnifiedHub()
        
        async def main():
            if not await hub.initialize():
                return
                
            # Start FastAPI in background
            config = uvicorn.Config(hub.app, host="127.0.0.1", port=8080, log_level="info")
            server = uvicorn.Server(config)
            
            # Run everything concurrently
            await asyncio.gather(
                server.serve(),
                hub._rest_worker(),
                hub.start_stream(
                    symbols_l1=["/ES", "/NQ"],
                    symbols_l2=["/ES", "/NQ"]
                )
            )

        asyncio.run(main())
    except KeyboardInterrupt:
        pass
