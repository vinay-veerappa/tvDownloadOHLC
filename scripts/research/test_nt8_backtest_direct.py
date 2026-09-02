"""
Direct NT8 HTTP API Strategy Analyzer Runner
"""

import json
import requests
import sys

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def main():
    print("Testing NT8 Strategy Analyzer directly via HTTP API...")

    # First check health
    r = requests.get("http://localhost:7890/api/health", headers=HEADERS)
    print("Health:", r.status_code, r.json())

    # Check SA Windows
    r_insp = requests.get("http://localhost:7890/api/sa/inspect", headers=HEADERS)
    print("SA Inspect:", r_insp.status_code, len(r_insp.json().get("dateProps", [])))

    # Run backtest with 5m period on NQ 09-26
    # Keep timeout at 240s to allow full run
    payload = {
        "strategy": "ICTFVGCISDBot",
        "symbol": "NQ 09-26",
        "period": "Minute",
        "periodValue": 5,
        "from": "2026-06-01",
        "to": "2026-08-01",
        "timeoutSec": 240,
        "maxTrades": 100,
        "params": {
            "Variant": 2,
            "EntryMode": 1,
            "UseHtfFilter": True,
            "FilterLunch": True,
            "QueenTargetBps": 10.0,
            "RunnerTargetBps": 30.0,
            "StopLossBps": 5.0,
        }
    }

    print("\nSending /api/backtest request to NT8...")
    res = requests.post("http://localhost:7890/api/backtest", headers=HEADERS, json=payload, timeout=260)
    print(f"Status Code: {res.status_code}")
    data = res.json()

    if "error" in data:
        print("ERROR:", data["error"])
        return

    if data.get("status") == "timeout":
        print("TIMEOUT:", data.get("message"))
        return

    print("\n========================================================")
    print("NINJATRADER 8 STRATEGY ANALYZER BACKTEST RESULTS")
    print("========================================================")
    metrics = data.get("metrics", {})
    for k, v in metrics.items():
        print(f"  {k:<25}: {v}")

    trades = data.get("trades", [])
    print(f"\nTotal Extracted Trades: {len(trades)}")
    if trades:
        print("First 3 trades:")
        for t in trades[:3]:
            print(" ", t)


if __name__ == "__main__":
    main()
