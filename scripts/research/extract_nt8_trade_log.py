"""
Extract all trades from NT8 Entry 3 (NQ SEP26) and Entry 0 (MES SEP26)
"""

import json
import requests
import pandas as pd
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def extract_entry_trades(entry_idx: int):
    # Call ExtractBacktest on entry_idx
    payload = {
        "ui": True,
        "ops": [
            {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
            {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
            {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
            {"op": "getProp", "target": {"$result": "2"}, "member": "LogEntries"},
            {"op": "invoke", "target": {"$result": "3"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": entry_idx}]},
            # Call ExtractBacktest(entry, 500)
            {
                "op": "invoke",
                "type": "NinjaTrader.NinjaScript.AddOns.McpBridgeAddOn, Custom",
                "method": "ExtractBacktest",
                "args": [{"$result": "4"}, {"$type": "System.Int32", "value": 500}]
            }
        ]
    }
    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    return res.json()

def main():
    print("Extracting full trade list from NT8 LogEntries[3] (NQ SEP26)...")
    data = extract_entry_trades(3)
    print("Extract result keys:", list(data.keys()))
    res_list = data.get("results", [])
    if len(res_list) > 5:
        last_op = res_list[5]
        if "error" in last_op:
            print("ExtractBacktest Error:", last_op["error"])
        else:
            print("Extracted successfully!")
            print(json.dumps(last_op, indent=2)[:500])


if __name__ == "__main__":
    main()
