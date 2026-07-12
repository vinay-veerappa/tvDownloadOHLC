"""
Hub REST health probe for Schwab market data.

This test intentionally avoids the legacy schwabdev streaming client and
routes ALL requests through the internal Schwab Hub proxy, matching the
production code path in scripts/streaming/options/options_fetcher.py.

DO NOT add direct schwabdev / schwab-py / schwab.auth calls here. If the
Hub is down this test will fail fast instead of prompting for a token.
"""
import json
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


def test_schwab_hub_rest():
    if not os.path.exists("secrets.json"):
        print("secrets.json not found")
        return

    # 1. Resolve root futures symbols to active contracts
    resolve_data = _hub_request("resolve", {"symbols": ["/ES", "/NQ"]})
    assert resolve_data, "Hub resolve returned no data"

    es_active = resolve_data.get("/ES", {}).get("active")
    nq_active = resolve_data.get("/NQ", {}).get("active")
    assert es_active, f"Could not resolve /ES via Hub: {resolve_data}"
    assert nq_active, f"Could not resolve /NQ via Hub: {resolve_data}"

    # 2. Quote active contracts
    quotes = _hub_request("get_quotes", {"symbols": [es_active, nq_active]})
    assert quotes, "Hub get_quotes returned no data"
    assert es_active in quotes, f"Missing quote for {es_active}: {quotes}"
    assert nq_active in quotes, f"Missing quote for {nq_active}: {quotes}"

    # 3. Pull a small option chain for a cash-settled ticker (production path)
    chain = _hub_request(
        "get_option_chain",
        {
            "symbol": "SPY",
            "fromDate": "2026-07-11",
            "toDate": "2026-07-18",
            "strikeCount": 3,
        },
    )
    assert chain, "Hub get_option_chain returned no data"
    assert (
        chain.get("callExpDateMap") or chain.get("putExpDateMap")
    ), f"Option chain missing expiration map: {chain}"


if __name__ == "__main__":
    test_schwab_hub_rest()
