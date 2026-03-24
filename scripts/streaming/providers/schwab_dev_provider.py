import asyncio
import json
import logging
import os
import time
from schwabdev import Client, Stream
from scripts.streaming.providers.base_provider import SchwabHubProvider

logger = logging.getLogger("SchwabDevProvider")

class SchwabDevProvider(SchwabHubProvider):
    def __init__(self, secrets_path="secrets.json", token_path="token.json"):
        self.secrets_path = secrets_path
        self.token_path = token_path
        self.client = None
        self.is_running = False
        self._on_message = None

    async def initialize(self) -> bool:
        if not os.path.exists(self.secrets_path):
            raise FileNotFoundError(f"Secrets file not found: {self.secrets_path}")
            
        with open(self.secrets_path, 'r') as f:
            secrets = json.load(f)
            
        try:
            # Initialize schwabdev Client with the synced tokens.db
            self.client = Client(
                secrets["app_key"], 
                secrets["app_secret"], 
                secrets["callback_url"],
                tokens_db="tokens.db",
                timeout=30
            )
            self.stream = Stream(self.client)
            
            # Test account fetch to verify token
            resp = self.client.linked_accounts()
            if resp.status_code == 200:
                logger.info("✅ Schwab-Dev Provider initialized and authenticated.")
                return True
            else:
                logger.error(f"❌ Schwab-Dev Auth failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to initialize Schwab-Dev provider: {e}")
            return False

    def _internal_receiver(self, message):
        """Thread-safe bridge from schwabdev's thread to asyncio."""
        if not self._on_message:
            return

        # schwabdev calls this from a background thread
        # 1. Parse string if needed
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except Exception as e:
                logger.error(f"Failed to parse streaming message: {e}")
                return

        # 2. Get the loop
        loop = asyncio.get_event_loop()
        if not loop.is_running():
            return

        # 3. Flatten 'data' list if present (emulates schwab-py handler behavior)
        if isinstance(message, dict) and "data" in message and isinstance(message["data"], list):
            for item in message["data"]:
                asyncio.run_coroutine_threadsafe(self._on_message(item), loop)
        else:
            # Send other messages (notify, response, heartbeat) as-is (but now parsed)
            asyncio.run_coroutine_threadsafe(self._on_message(message), loop)

    async def execute_rest(self, method_name: str, params: dict):
        logger.info(f"DEBUG: Entering execute_rest with {method_name}")
        if not self.client:
            return {"status": "error", "message": "Client not initialized"}
        
        # Translation map for common methods (schwabdev vs standard/schwab-py)
        translations = {
            "get_option_chain": "option_chains",
            "get_quotes": "quotes",
            "get_price_history": "price_history",
            "get_account_numbers": "linked_accounts",
            "get_market_hours": "market_hours"
        }
        
        target_method = translations.get(method_name, method_name)
        
        # Generic Parameter translation (snake_case -> camelCase for schwabdev)
        final_params = {}
        for k, v in params.items():
            if "_" in k:
                parts = k.split("_")
                camel_k = parts[0] + "".join(p.title() for p in parts[1:])
                final_params[camel_k] = v
            else:
                final_params[k] = v

        logger.info(f"Schwab-Dev REST request: {method_name} -> {target_method} (params: {list(final_params.keys())})")
        
        try:
            if target_method == "resolve":
                # Special internal method for resolving futures roots
                res = await self.resolve_futures_symbols(final_params.get("symbols", []))
                return {"status": "success", "data": res}

            method = getattr(self.client, target_method, None)
            if not method:
                logger.error(f"Method {target_method} NOT FOUND on schwabdev Client.")
                return {"status": "error", "message": f"Method {target_method} not found on Client"}
            
            # Safety check for symbols parameter (must be list[str], no None)
            if "symbols" in final_params and isinstance(final_params["symbols"], list):
                final_params["symbols"] = [s for s in final_params["symbols"] if isinstance(s, str)]
                if not final_params["symbols"]:
                    return {"status": "error", "message": "Symbols list is empty after filtering NoneType"}
            
            resp = method(**final_params)
            if resp is None:
                return {"status": "error", "message": "Method returned None (check if async/await needed or if method exists)"}

            if hasattr(resp, "status_code"):
                if resp.status_code == 200:
                    return {"status": "success", "data": resp.json()}
                else:
                    return {"status": "error", "code": resp.status_code, "message": resp.text}
            return resp
        except Exception as e:
            logger.error(f"Error in Schwab-Dev REST request ({target_method}): {e}")
            return {"status": "error", "message": str(e)}

    async def start_stream(self, symbols_l1: list[str], symbols_l2: list[str], on_message_cb=None):
        """
        Starts the Schwab stream and subscribes to requested symbols.
        For Equities, we use NASDAQ_BOOK and TIMESALE_EQUITY.
        """
        self._on_message = on_message_cb
        
        if not self.stream:
            logger.error("Stream not initialized. Call initialize() first.")
            return

        logger.info("Starting Schwab-Dev Stream...")
        self.stream.start(receiver=self._internal_receiver)
        
        # Wait for login/startup
        await asyncio.sleep(3)
        
        # 1. Level 1 Subscriptions (SPX/Indices vs Equities)
        if symbols_l1:
            indices = [s for s in symbols_l1 if s == "SPX" or s.startswith("$")]
            equities = [s for s in symbols_l1 if s not in indices]
            
            if equities:
                logger.info(f"Subscribing to LEVELONE_EQUITIES: {equities}")
                self.stream.send(self.stream.level_one_equities(equities, "0,1,2,8,9"))
            if indices:
                logger.info(f"Subscribing to LEVELONE_INDICES: {indices}")
                # Try adding $SPX if SPX is requested
                if "SPX" in indices and "$SPX" not in indices:
                    indices.append("$SPX")
                self.stream.send(self.stream.level_one_indices(indices, "0,1,2,3"))

        # 2. Time & Sales (Trade Bubbles)
        equities = [s for s in symbols_l2 if not s.startswith("/")]
        if equities:
            logger.info(f"Subscribing to TIMESALE: {equities}")
            # Numeric fields for TIMESALE: 0(Symbol), 1(Time), 2(Price), 3(Size)
            self.stream.send(self.stream.basic_request("TIMESALE", "SUBS", parameters={
                "keys": ",".join(equities),
                "fields": "0,1,2,3,4"
            }))

        # 3. Level 2 (Book)
        if symbols_l2:
            asyncio.create_task(self.subscribe_level_two(symbols_l2))

        self.is_running = True
        while self.is_running:
            await asyncio.sleep(1)

    async def subscribe_level_two(self, symbols: list[str]):
        """
        Subscribes to Level 2 (Equities only for now).
        """
        if not self.stream: return

        equities = [s for s in symbols if not s.startswith("/")]
        if equities:
            s_list = ",".join(equities)
            logger.info(f"Subscribing to NASDAQ_BOOK: {s_list}")
            # Fields: 0(Symbol), 1(Bids), 2(Asks)
            self.stream.send(self.stream.basic_request("NASDAQ_BOOK", "SUBS", parameters={
                "keys": s_list,
                "fields": "0,1,2"
            }))



    async def resolve_futures_symbols(self, root_symbols: list[str]) -> dict:
        """
        Resolve root symbols (e.g. /ES) to actual active contracts (e.g. /ESM26)
        and their mapped index counterparts (e.g. SPX).
        Returns: { root: {"direct": contract, "mapped": index, "active": contract} }
        """
        INDEX_MAP = {
            "/ES": "SPX",
            "/NQ": "QQQ",
            "/RTY": "IWM",
            "/YM": "DIA",
            "/CL": "USO",
            "/GC": "GLD",
            "/SI": "SLV"
        }
        
        if not self.client:
            return {s: {"direct": s, "mapped": INDEX_MAP.get(s, s), "active": s} for s in root_symbols}
            
        try:
            futures = [s for s in root_symbols if s.startswith('/')]
            
            data = {}
            if futures:
                resp = self.client.quotes(futures)
                if resp.status_code == 200:
                    data = resp.json()
            mapping = {}
            for target in root_symbols:
                resolved = None
                if target.startswith('/'):
                    for sym, val in data.items():
                        ref = val.get("reference", {})
                        if ref.get("product") == target:
                            resolved = sym
                            break
                elif target in INDEX_MAP.values(): # It's a mapped index
                    # Check for prefixes like $SPX
                    from scripts.streaming.options.config import SCHWAB_INDEX_PREFIX
                    resolved = SCHWAB_INDEX_PREFIX.get(target, target)
                
                mapping[target] = {
                    "direct": resolved if resolved else target,
                    "mapped": INDEX_MAP.get(target, target),
                    "active": resolved if resolved else target
                }
            return mapping
        except Exception as e:
            logger.warning(f"Failed to resolve futures symbols: {e}")
            return {s: {"direct": s, "mapped": INDEX_MAP.get(s, s), "active": s} for s in root_symbols}

    async def stop(self):
        self.is_running = False
        if self.client and self.stream:
            self.stream.stop()

    async def send_rest_request(self, method: str, params: dict) -> dict:
        if not self.client:
            return {"status": "error", "message": "Client not initialized"}
        try:
            # schwabdev calls are synchronous
            m = getattr(self.client, method)
            resp = m(**params)
            return {
                "status": "success" if resp.status_code < 400 else "error",
                "data": resp.json() if hasattr(resp, 'json') else resp.text,
                "status_code": resp.status_code
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
