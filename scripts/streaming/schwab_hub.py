import asyncio
import json
import os
import logging
from datetime import datetime, timezone

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    import uvicorn
except ImportError:
    FastAPI = None

from scripts.streaming.providers.schwab_py_provider import SchwabPyProvider
from scripts.streaming.providers.schwab_dev_provider import SchwabDevProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SchwabUnifiedHub")

class SchwabUnifiedHub:
    """
    The Central Hub for Schwab API interactions.
    This version delegates to a Provider (schwab-py or schwabdev).
    """
    def __init__(self, secrets_path="secrets.json", token_path="token.json"):
        self.secrets_path = secrets_path
        self.token_path = token_path
        self.provider = None
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
                        await websocket.receive_text()
                except WebSocketDisconnect:
                    if websocket in self.active_sockets:
                        self.active_sockets.remove(websocket)

            @self.app.post("/request")
            async def proxy_request(request: dict):
                response_queue = asyncio.Queue()
                await self.rest_queue.put((request, response_queue))
                return await response_queue.get()

            @self.app.post("/resolve")
            async def resolve_symbols(request: dict):
                """Resolve root symbols to active contracts."""
                symbols = request.get("symbols", [])
                if not self.provider:
                    return {"status": "error", "message": "Provider not initialized"}
                mapping = await self.provider.resolve_futures_symbols(symbols)
                return {"status": "success", "data": mapping}
        
    async def initialize(self):
        """Initialize chosen provider based on secrets.json."""
        if not os.path.exists(self.secrets_path):
            raise FileNotFoundError(f"Secrets file not found: {self.secrets_path}")
            
        with open(self.secrets_path, 'r') as f:
            secrets = json.load(f)
            
        provider_name = secrets.get("hub_provider", "schwab-py")
        logger.info(f"Loading provider: {provider_name}")

        if provider_name == "schwab-py":
            self.provider = SchwabPyProvider(self.secrets_path, self.token_path)
        elif provider_name == "schwabdev":
            self.provider = SchwabDevProvider(self.secrets_path, self.token_path)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

        return await self.provider.initialize()

    async def _handle_stream_event(self, event):
        """Callback for all streaming events."""
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": event,
            "provider": self.provider.__class__.__name__
        }
        await self.broadcast_queue.put(payload)
        
        # Push to all active WebSockets
        for socket in self.active_sockets:
            try:
                await socket.send_json(payload)
            except Exception:
                pass

        # Log periodically
        if event.get("service") != "HEARTBEAT":
            logger.debug(f"Received {event.get('service')} event")

    async def _rest_worker(self):
        """Processes REST requests via the provider."""
        logger.info("🚀 REST Worker started.")
        while True:
            request_data, response_queue = await self.rest_queue.get()
            method_name = request_data.get("method")
            params = request_data.get("params", {})
            try:
                logger.info(f"Worker calling {self.provider.__class__.__name__}.execute_rest for {method_name}")
                result = await self.provider.execute_rest(method_name, params)
                await response_queue.put(result)
            except Exception as e:
                logger.error(f"Error in REST worker ({method_name}): {e}")
                await response_queue.put({"status": "error", "message": str(e)})
            
            await asyncio.sleep(self.rate_limit_delay)
            self.rest_queue.task_done()

    async def start_stream(self, symbols_l1=None, symbols_l2=None):
        """Delegate streaming to the provider."""
        if not self.provider:
            logger.error("Provider not initialized.")
            return

        self.is_running = True
        await self.provider.start_stream(
            symbols_l1=symbols_l1,
            symbols_l2=symbols_l2,
            on_message_cb=self._handle_stream_event
        )

    async def stop(self):
        self.is_running = False
        if self.provider:
            await self.provider.stop()

# Main Entry Point
async def main():
    hub = SchwabUnifiedHub()
    success = await hub.initialize()
    if not success:
        logger.error("Failed to initialize Hub. Exiting.")
        return

    # Subscriptions from environment or defaults
    symbols_l1 = ["/ES", "/NQ"]
    symbols_l2 = ["/ES", "/NQ", "AAPL", "SPY"] # Hub now resolves these!

    # Run everything together
    # We wrap start_stream in its own try-except via gather logic or a wrapper
    async def run_stream():
        try:
            await hub.start_stream(
                symbols_l1=symbols_l1,
                symbols_l2=symbols_l2
            )
        except Exception as e:
            logger.warning(f"⚠️ Stream exited: {e}. REST services will continue.")
            # Keep the coroutine alive so gather doesn't exit
            while True:
                await asyncio.sleep(60)

    try:
        # FastAPI server
        config = uvicorn.Config(hub.app, host="127.0.0.1", port=8080, log_level="info")
        server = uvicorn.Server(config)

        await asyncio.gather(
            server.serve(),
            hub._rest_worker(),
            run_stream()
        )
    except Exception as e:
        logger.error(f"Hub catastrophic failure: {e}")
    finally:
        await hub.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Hub stopped by user.")
