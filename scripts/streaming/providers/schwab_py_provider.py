import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from schwab.auth import client_from_token_file
from schwab.streaming import StreamClient

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

from scripts.streaming.providers.base_provider import SchwabHubProvider

logger = logging.getLogger("SchwabPyProvider")

class SchwabPyProvider(SchwabHubProvider):
    def __init__(self, secrets_path="secrets.json", token_path="token.json"):
        self.secrets_path = secrets_path
        self.token_path = token_path
        self.client = None
        self.stream_client = None
        self.is_running = False

    async def initialize(self) -> bool:
        if not os.path.exists(self.secrets_path):
            raise FileNotFoundError(f"Secrets file not found: {self.secrets_path}")
            
        with open(self.secrets_path, 'r') as f:
            secrets = json.load(f)
            
        try:
            self.client = client_from_token_file(
                self.token_path,
                secrets["app_key"],
                secrets["app_secret"],
                asyncio=True,
                enforce_enums=False
            )
            if hasattr(self.client, 'enforce_enums'):
                self.client.enforce_enums = False
                
            logger.info("✅ Schwab-Py Provider initialized.")
            
            self.stream_client = StreamClient(self.client)
            await self.stream_client.login()
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Schwab-Py provider: {e}")
            return False

    async def start_stream(self, symbols_l1: list[str] = None, symbols_l2: list[str] = None, on_message_cb=None):
        if not self.stream_client:
            logger.error("Stream client not initialized.")
            return

        async def msg_wrapper(message):
            if on_message_cb:
                await on_message_cb(message)

        # Register handlers
        possible_handlers = [
            "add_level_one_futures_handler",
            "add_level_one_futures_options_handler",
            "add_chart_futures_handler",
            "add_timesale_equities_handler",
            "add_timesale_futures_handler"
        ]
        for h_name in possible_handlers:
            if hasattr(self.stream_client, h_name):
                getattr(self.stream_client, h_name)(msg_wrapper)

        # 1. Level 1 Subscriptions
        if symbols_l1:
            logger.info(f"Subscribing to L1 Futures (root): {symbols_l1}")
            await self.stream_client.level_one_futures_subs(symbols_l1)
            
            # TIMESALE Subscriptions
            equities = [s for s in symbols_l1 if not s.startswith('/')]
            futures = [s for s in symbols_l1 if s.startswith('/')]
            
            if equities:
                logger.info(f"Subscribing to TIMESALE_EQUITIES: {equities}")
                await self.stream_client.timesale_equities_subs(equities)
            if futures:
                resolved_info = await self.resolve_futures_symbols(futures)
                targets = [resolved_info[s]["active"] for s in futures]
                logger.info(f"Subscribing to TIMESALE_FUTURES: {targets}")
                await self.stream_client.timesale_futures_subs(targets)
        
        # 2. Level 2 Subscriptions (dynamic resolution)
        if symbols_l2:
            # Register Manual L2 Handler for Book Data
            class ManualHandler:
                def __init__(self, func, service):
                    self.func = func
                    self.service = service
                    self.field_mapping = {'1': 'snapshot_time', '2': 'bid_side', '3': 'ask_side'}
                def label_message(self, msg):
                    if 'content' in msg:
                        for item in msg['content']:
                            for k in list(item.keys()):
                                if k in self.field_mapping:
                                    item[self.field_mapping[k]] = item.pop(k)
                    return msg
                def __call__(self, msg):
                    relabeled = self.label_message(msg)
                    return self.func(relabeled)

            candidates = ["FUTURES_BOOK", "NASDAQ_BOOK", "NYSE_BOOK", "OPTIONS_BOOK", "LEVELTWO_FUTURES"]
            for svc in candidates:
                self.stream_client._handlers[svc].append(ManualHandler(msg_wrapper, svc))
            
            # Perform subscription
            asyncio.create_task(self.subscribe_level_two(symbols_l2))

        self.is_running = True
        while self.is_running:
            await self.stream_client.handle_message()

    async def subscribe_level_two(self, symbols: list[str]):
        """
        Subscribes to Level 2 (FUTURES_BOOK) with automatic contract resolution.
        """
        if not self.stream_client: return

        # Resolve root symbols
        resolved_info = await self.resolve_futures_symbols(symbols)
        transformed = [resolved_info[s]["active"] for s in symbols]
        
        logger.info(f"Manual L2 SUBS to FUTURES_BOOK for {transformed}...")
        try:
            # We use _service_op to bypass the limited schwab-py high-level methods
            await self.stream_client._service_op(transformed, "FUTURES_BOOK", "SUBS", 
                                               getattr(self.stream_client, "BookFields", None))
        except Exception as e:
            logger.error(f"L2 Subscription failed: {e}")

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
            if not futures:
                return {s: {"direct": s, "mapped": INDEX_MAP.get(s, s), "active": s} for s in root_symbols}
                
            resp = await self.client.get_quotes(futures)
            if resp.status_code != 200:
                return {s: {"direct": s, "mapped": INDEX_MAP.get(s, s), "active": s} for s in root_symbols}
                
            data = resp.json()
            mapping = {}
            for target in root_symbols:
                resolved = None
                if target.startswith('/'):
                    for sym, val in data.items():
                        # Reference section contains the root product code
                        ref = val.get("reference", {})
                        if ref.get("product") == target:
                            resolved = sym
                            break
                
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
        if self.stream_client:
            await self.stream_client.logout()

    async def execute_rest(self, method: str, params: dict) -> dict:
        if not self.client:
            return {"status": "error", "message": "Client not initialized"}
        
        # Convert date strings to date objects for schwab-py
        from datetime import date
        for key in ["from_date", "to_date"]:
            if key in params and isinstance(params[key], str):
                try:
                    params[key] = date.fromisoformat(params[key])
                except: pass

        try:
            if method == "resolve":
                res = await self.resolve_futures_symbols(params.get("symbols", []))
                return {"status": "success", "data": res}

            m = getattr(self.client, method)
            resp = await m(**params)
            if hasattr(resp, 'json'):
                return {"status": "success", "data": resp.json(), "status_code": resp.status_code}
            return {"status": "success", "data": resp, "status_code": 200}
        except Exception as e:
            logger.error(f"Error in schwab-py request ({method}): {e}")
            return {"status": "error", "message": str(e)}
