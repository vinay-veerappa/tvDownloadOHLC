#!/usr/bin/env python3
"""
TradingView HUD Manager (Python Engine & CLI).

Provides programmatic and CLI control over TradingView Desktop HUD overlays via Chrome DevTools Protocol.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import urllib.request
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent
HUDS_DIR = ROOT_DIR / "huds"


class TvHudManager:
    """Manages TradingView Desktop HUD overlays."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9222):
        self.host = host
        self.port = port
        self.cdp_base_url = f"http://{self.host}:{self.port}"

    def get_chart_target(self) -> Dict[str, Any]:
        """Discovers the active chart page target from CDP."""
        url = f"{self.cdp_base_url}/json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TvHudManager"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                targets = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ConnectionError(
                f"Could not connect to TradingView Desktop at {url}. "
                f"Ensure TradingView is running with --remote-debugging-port={self.port}."
            ) from e

        chart = next(
            (t for t in targets if t.get("type") == "page" and "tradingview.com/chart" in t.get("url", "")),
            None,
        ) or next((t for t in targets if t.get("type") == "page"), None)

        if not chart or not chart.get("webSocketDebuggerUrl"):
            raise RuntimeError("No active TradingView chart page found in CDP targets.")

        return chart

    def list_available_huds(self) -> List[str]:
        """Lists available HUD plugin modules in huds/ folder."""
        if not HUDS_DIR.exists():
            return []
        return [
            f.stem
            for f in HUDS_DIR.glob("*.js")
            if f.is_file() and f.stem != "template_hud"
        ]

    def run_node_manager(self, command: str, hud_name: Optional[str] = None) -> Dict[str, Any]:
        """Dispatches commands to tv_hud_manager.js."""
        import subprocess

        js_manager = ROOT_DIR / "tv_hud_manager.js"
        if not js_manager.exists():
            raise FileNotFoundError(f"tv_hud_manager.js not found at {js_manager}")

        cmd = [sys.executable.replace("python.exe", "node.exe") if os.name == "nt" else "node", str(js_manager), command]
        if hud_name:
            cmd.append(hud_name)

        # Fallback to standard 'node' in PATH
        if not Path(cmd[0]).exists():
            cmd[0] = "node"

        env = os.environ.copy()
        env["TV_CDP_PORT"] = str(self.port)
        env["TV_CDP_HOST"] = self.host

        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise RuntimeError(f"tv_hud_manager.js failed:\n{proc.stderr}")
        return {"stdout": proc.stdout, "returncode": proc.returncode}


def main():
    parser = argparse.ArgumentParser(description="TradingView Desktop Modular HUD Manager")
    parser.add_argument(
        "action",
        nargs="?",
        default="list",
        choices=["list", "inject", "remove", "toggle", "clear", "remove-all"],
        help="Action to perform",
    )
    parser.add_argument(
        "hud",
        nargs="?",
        default="financialjuice",
        help="HUD module name (e.g. financialjuice, nt8_positions)",
    )
    parser.add_argument("--port", type=int, default=9222, help="CDP port (default 9222)")
    parser.add_argument("--host", default="127.0.0.1", help="CDP host (default 127.0.0.1)")

    args = parser.parse_args()
    manager = TvHudManager(host=args.host, port=args.port)

    try:
        res = manager.run_node_manager(args.action, args.hud if args.action != "list" and args.action != "clear" else None)
        print(res["stdout"])
    except Exception as e:
        print(f"[ERR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
