"""
Run MTF Strategy Analyzer backtest on NT8 and extract results
"""

import json
import requests
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def main():
    print("Configuring NT8 Strategy Analyzer for 1-minute MTF run...")

    # Step 1: Configure Strategy Analyzer
    payload_cfg = {
        "ui": True,
        "ops": [
            {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
            {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
            {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
            {"op": "getProp", "target": {"$result": "2"}, "member": "SelectedTab"},
            {"op": "getProp", "target": {"$result": "3"}, "member": "TabStrategyProperties"},
            # Strategy
            {"op": "setProp", "target": {"$result": "4"}, "member": "Strategy", "value": "ICTFVGCISDBot"},
            {"op": "setProp", "target": {"$result": "4"}, "member": "InstrumentOrInstrumentList", "value": "NQ 09-26"},
            # Primary series: 1 Minute
            {"op": "getProp", "target": {"$result": "4"}, "member": "BarsPeriod"},
            {"op": "setProp", "target": {"$result": "7"}, "member": "Value", "value": 1},
            # Date Range
            {"op": "setProp", "target": {"$result": "4"}, "member": "From", "value": {"$type": "System.DateTime", "value": "2026-07-01T00:00:00"}},
            {"op": "setProp", "target": {"$result": "4"}, "member": "To", "value": {"$type": "System.DateTime", "value": "2026-07-25T00:00:00"}},
            # Strategy Parameters
            {"op": "getProp", "target": {"$result": "4"}, "member": "StrategyTemplate"},
            {"op": "setProp", "target": {"$result": "11"}, "member": "UseMtfExecution", "value": True},
            {"op": "setProp", "target": {"$result": "11"}, "member": "StopLossBps", "value": 2.5},
            {"op": "setProp", "target": {"$result": "11"}, "member": "QueenTargetBps", "value": 10.0},
            {"op": "setProp", "target": {"$result": "11"}, "member": "RunnerTargetBps", "value": 30.0},
            # Validate
            {"op": "invoke", "target": {"$result": "2"}, "method": "CheckSettingsValid", "args": []}
        ]
    }

    res_cfg = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload_cfg)
    valid = res_cfg.json()["results"][-1].get("value")
    print(f"CheckSettingsValid: {valid}")

    # Baseline entry check
    base_payload = {
        "ui": True,
        "ops": [
            {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
            {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
            {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
            {"op": "getProp", "target": {"$result": "2"}, "member": "LogEntries"},
            {"op": "invoke", "target": {"$result": "3"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 0}]}
        ]
    }
    r_base = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=base_payload)
    baseline_str = r_base.json()["results"][-1].get("toString", "")
    print(f"Current Latest Entry:\n  {baseline_str[:80]}...")

    # Run
    print("\nFiring Strategy Analyzer Run...")
    run_payload = {
        "ui": True,
        "ops": [
            {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
            {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
            {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
            {"op": "invoke", "target": {"$result": "2"}, "method": "OnRun", "args": [None, None]}
        ]
    }
    requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=run_payload)

    # Poll for completion
    print("Polling for backtest completion in NT8...")
    completed = False
    for p in range(30):
        time.sleep(5)
        poll_payload = {
            "ui": True,
            "ops": [
                {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
                {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
                {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
                {"op": "getProp", "target": {"$result": "2"}, "member": "LogEntries"},
                {"op": "invoke", "target": {"$result": "3"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 0}]}
            ]
        }
        res_poll = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=poll_payload)
        cur_str = res_poll.json()["results"][-1].get("toString", "")
        if cur_str and cur_str != baseline_str:
            print(f"\nSUCCESS! Backtest completed at poll {p+1} ({(p+1)*5}s)!")
            print(f"New Entry:\n  {cur_str[:90]}...")
            completed = True
            break
        print(f"  Simulation running... ({(p+1)*5}s)")

    if not completed:
        print("Still waiting or timed out.")


if __name__ == "__main__":
    main()
