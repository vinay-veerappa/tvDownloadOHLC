"""
api_client.py — Base WebUI API client.

Provides a generic HTTP client for calling the WebUI FastAPI backend.
Each feature can extend this with feature-specific endpoints.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, Dict, Optional


API_BASE = "http://127.0.0.1:8000"


class WebUIClient:
    """
    Generic HTTP client for the WebUI FastAPI backend.

    Usage:
        client = WebUIClient()
        data = client.post("/stats/filtered-stats", payload={...})
    """

    def __init__(self, base_url: str = API_BASE, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Send a GET request to the WebUI backend."""
        url = f"{self.base_url}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
            url = f"{url}?{qs}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.read().decode()}"}
        except Exception as e:
            return {"error": str(e)}

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a POST request to the WebUI backend."""
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.read().decode()}"}
        except Exception as e:
            return {"error": str(e)}

    def health_check(self) -> bool:
        """Check if the backend is running."""
        try:
            with urllib.request.urlopen(f"{self.base_url}/docs", timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False
