"""
Hub REST smoke tests for futures resolution and quoting.

These tests use the internal Schwab Hub proxy, matching the production
pipeline path, and avoid direct schwabdev or schwab-py streaming clients.

DO NOT add direct schwabdev / schwab-py / schwab.auth calls here. This file
must remain Hub-only so it never prompts for a token.
"""
import json
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


def test_resolve():
    res = _hub_request("resolve", {"symbols": ["/NQ", "/ES"]})
    assert res, "Hub resolve returned no data"
    print(json.dumps(res, indent=2))

    for sym in ["/NQ", "/ES"]:
        mapping = res.get(sym, {})
        assert "active" in mapping, f"Hub did not resolve active contract for {sym}: {mapping}"
        assert mapping["active"], f"Hub returned empty active contract for {sym}"


def test_quotes():
    resolve_data = _hub_request("resolve", {"symbols": ["/NQ"]})
    assert resolve_data, "Hub resolve returned no data"

    nq_active = resolve_data.get("/NQ", {}).get("active")
    assert nq_active, f"Could not resolve /NQ via Hub: {resolve_data}"

    res = _hub_request("get_quotes", {"symbols": [nq_active]})
    assert res, "Hub get_quotes returned no data"
    print(json.dumps(res, indent=2))
    assert nq_active in res, f"Missing quote for {nq_active}: {res}"


if __name__ == "__main__":
    test_resolve()
    test_quotes()
