"""
Hub REST futures resolution test.

Replaces the direct schwab-py provider path with the internal Schwab Hub
proxy used by the production pipeline.

DO NOT add direct schwabdev / schwab-py / schwab.auth calls here. This file
must remain Hub-only so it never prompts for a token.
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


def test_futures_resolution():
    if not os.path.exists("secrets.json"):
        print("secrets.json not found")
        return

    symbols = ["/ES", "/NQ"]
    result = _hub_request("resolve", {"symbols": symbols})
    assert result, "Hub resolve returned no data"

    print(json.dumps(result, indent=2))

    for sym in symbols:
        mapping = result.get(sym, {})
        assert "active" in mapping, f"Hub did not resolve active contract for {sym}: {mapping}"
        assert mapping["active"], f"Hub returned empty active contract for {sym}"


if __name__ == "__main__":
    test_futures_resolution()
