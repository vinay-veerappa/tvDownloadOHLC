import asyncio
import json
import os
import sys
import io

# Force standard output and error to use utf-8 on Windows to prevent emoji encoding crashes
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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
        
        # Periodic event logging stats
        self._last_log_time = 0.0
        self._event_counts = {}
        
        # FastAPI for Local Broadcasting
        self.app = FastAPI() if FastAPI else None
        self.active_sockets: list[tuple[WebSocket, asyncio.Queue]] = []
        
        # Local Bus: Queue for internal sub-tasks
        self.broadcast_queue = asyncio.Queue()
        
        # REST Request Queue
        self.rest_queue = asyncio.Queue()
        self.rate_limit_delay = 0.5  # 500ms between REST calls
        
        if self.app:
            @self.app.websocket("/ws")
            async def websocket_endpoint(websocket: WebSocket):
                await websocket.accept()
                client_queue = asyncio.Queue(maxsize=1000)
                self.active_sockets.append((websocket, client_queue))
                
                async def sender():
                    try:
                        while True:
                            msg = await client_queue.get()
                            await websocket.send_json(msg)
                            client_queue.task_done()
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.warning(f"WebSocket send task failed: {e}")

                sender_task = asyncio.create_task(sender())
                try:
                    while True:
                        await websocket.receive_text()
                except WebSocketDisconnect:
                    pass
                finally:
                    sender_task.cancel()
                    for pair in list(self.active_sockets):
                        if pair[0] == websocket:
                            self.active_sockets.remove(pair)

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
        
        # Push to all active WebSockets queues (non-blocking)
        for _, q in list(self.active_sockets):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    pass
            except Exception:
                pass

        # Log periodically (every 10 seconds) instead of spamming every event
        import time
        service = event.get("service")
        if service:
            self._event_counts[service] = self._event_counts.get(service, 0) + 1

        now = time.monotonic()
        if now - self._last_log_time >= 10.0:
            self._last_log_time = now
            stats_str = ", ".join(f"{k}:{v}" for k, v in self._event_counts.items())
            logger.info(f"📊 Stream Event Stats (last 10s): {stats_str or 'None'}")
            self._event_counts.clear()

        # Log detailed events only at DEBUG level to avoid console spam
        if service != "HEARTBEAT":
            logger.debug(f"Received {service} event: {str(event)[:200]}...")
            if service and "TIMESALE" in service:
                logger.debug(f">>>> Raw Trade Event: {event}")

    async def _process_request(self, method_name, params, response_queue):
        try:
            logger.info(f"Worker calling {self.provider.__class__.__name__}.execute_rest for {method_name}")
            result = await self.provider.execute_rest(method_name, params)
            await response_queue.put(result)
        except Exception as e:
            logger.error(f"Error in REST worker ({method_name}): {e}")
            await response_queue.put({"status": "error", "message": str(e)})

    async def _rest_worker(self):
        """Processes REST requests via the provider concurrently with rate-limited launch intervals."""
        logger.info("🚀 REST Worker started (Concurrent Execution, Rate-Limited Launches).")
        while True:
            request_data, response_queue = await self.rest_queue.get()
            method_name = request_data.get("method")
            params = request_data.get("params", {})
            
            # Dispatch to run concurrently
            asyncio.create_task(self._process_request(method_name, params, response_queue))
            
            # Enforce 500ms spacing between the start of consecutive API requests
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
    # Define default symbols to stream if none provided via command line
    symbols_l1 = ["AAPL", "SPY", "QQQ", "/ES", "/NQ", "/YM", "/RTY"]
    symbols_l2 = []
 
    # We wrap start_stream in its own try-except via gather logic or a wrapper
    async def run_stream():
        while True:
            try:
                # RE-INITIALIZE to refresh token before every connection attempt.
                # This ensures we pick up a fresh session after sleep or expiry.
                logger.info("🔄 Refreshing Hub provider credentials...")
                await hub.initialize()
                
                await hub.start_stream(
                    symbols_l1=symbols_l1,
                    symbols_l2=symbols_l2
                )
            except Exception as e:
                logger.warning(f"⚠️ Stream connection lost: {e}. Reconnecting in 15s...")
                await asyncio.sleep(15)

    # Run everything together
    try:
        from scripts.streaming.options.config import HUB_HOST, HUB_PORT
        # FastAPI server
        config = uvicorn.Config(hub.app, host=HUB_HOST, port=HUB_PORT, log_level="info")
        server = uvicorn.Server(config)

        await asyncio.gather(
            server.serve(),
            hub._rest_worker(),
            run_stream()
        )
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Hub shutdown initiated...")
    except Exception as e:
        logger.error(f"Hub catastrophic failure: {e}")
    finally:
        await hub.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass # Already handled in main() or suppressed for clean exit
