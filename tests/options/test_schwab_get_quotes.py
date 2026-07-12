"""
Hub REST option-chain smoke test.

The internal pipeline no longer uses a direct Schwab REST client
(options_fetcher.create_client() returns None), so this test routes
ALL requests through the Schwab Hub proxy instead.

DO NOT add direct schwabdev / schwab-py / schwab.auth calls here. This file
must remain Hub-only so it never prompts for a token.
"""
import logging
import os
import requests

from scripts.streaming.options.config import HUB_URL

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


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


def test_legacy_futures_symbols():
    if not os.path.exists("secrets.json"):
        log.info("secrets.json not found")
        return

    # Legacy TOS roots are not accepted by the Hub/Schwab API.
    # Verify the production path: root -> active contract -> quote,
    # plus a small cash option chain (the only kind the Hub REST path pulls).
    resolve_data = _hub_request("resolve", {"symbols": ["/NQ"]})
    assert resolve_data, "Hub resolve returned no data"

    nq_active = resolve_data.get("/NQ", {}).get("active")
    assert nq_active, f"Could not resolve /NQ via Hub: {resolve_data}"

    log.info("Resolved /NQ to active contract: %s", nq_active)

    quotes = _hub_request("get_quotes", {"symbols": [nq_active]})
    assert quotes, "Hub get_quotes returned no data"
    assert nq_active in quotes, f"Missing quote for {nq_active}: {quotes}"

    log.info("[✓] Hub returned quote for %s", nq_active)

    payload = _hub_request(
        "get_option_chain",
        {
            "symbol": "SPY",
            "fromDate": "2026-07-11",
            "toDate": "2026-07-18",
            "strikeCount": 5,
        },
    )
    assert payload, "Hub get_option_chain returned no data"

    status = payload.get("status")
    call_map = payload.get("callExpDateMap", {})
    assert status == "SUCCESS", f"Option chain status was {status}: {payload}"
    assert call_map, f"Option chain had no callExpDateMap: {payload}"

    first_exp = list(call_map.keys())[0]
    log.info("[✓] Hub returned SPY option chain")
    log.info("  ↳ Returned %d expiration dates.", len(call_map))
    log.info("  ↳ First available expiry: %s", first_exp)


if __name__ == "__main__":
    test_legacy_futures_symbols()