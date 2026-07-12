"""
Hub REST health probe.

The internal Schwab Hub does not expose a streaming socket, so this test
replaces the legacy schwab-py StreamClient smoke test with REST-only checks
that mirror the production code path.

DO NOT add direct schwabdev / schwab-py / schwab.auth calls here. This file
must remain Hub-only so it never prompts for a token.
"""
import os
import requests

from scripts.streaming.options.config import HUB_URL


def _hub_request(method: str, params: dict) -> dict:
    """Mirror the production Hub request helper."""
    resp = requests.post(
        f"{HUB_URL}/request",
        json={"method": method, "params": params},
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    if isinstance(result, dict) and "status" in result:
        if result.get("status") != "success":
            raise RuntimeError(f"Hub proxy error: {result.get('message')}")
        return result.get("data") or {}
    return result or {}


def test_l2():
    if not os.path.exists("secrets.json"):
        print("secrets.json not found")
        return

    # Resolve and quote equities and futures
    symbols = ["AAPL", "/ES", "/NQ"]
    resolved = _hub_request("resolve", {"symbols": symbols})
    assert resolved, "Hub resolve returned no data"

    active_symbols = []
    for sym in symbols:
        mapping = resolved.get(sym, {})
        active = mapping.get("active", sym)
        active_symbols.append(active)

    quotes = _hub_request("get_quotes", {"symbols": active_symbols})
    assert quotes, "Hub get_quotes returned no data"
    for sym in active_symbols:
        assert sym in quotes, f"Missing quote for {sym}: {quotes}"


if __name__ == "__main__":
    test_l2()
