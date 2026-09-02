"""
Extract all trades from LogEntries[0] in NT8 Strategy Analyzer
"""

import json
import requests
import sys
import pandas as pd

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def main():
    payload = {
        "ui": True,
        "ops": [
            {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
            {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
            {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
            {"op": "getProp", "target": {"$result": "2"}, "member": "LogEntries"},
            {"op": "invoke", "target": {"$result": "3"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 0}]},
            {"op": "getProp", "target": {"$result": "4"}, "member": "Performance"},
            {"op": "getProp", "target": {"$result": "5"}, "member": "AllTrades"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "Count"},
        ]
    }
    r = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    count = r.json()["results"][-1].get("value", 0)
    print(f"Total trades in latest NT8 run: {count}")

    # Extract sample trades
    trades = []
    chunk_size = min(count, 50)
    for i in range(0, chunk_size, 10):
        ops = [
            {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
            {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
            {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
            {"op": "getProp", "target": {"$result": "2"}, "member": "LogEntries"},
            {"op": "invoke", "target": {"$result": "3"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 0}]},
            {"op": "getProp", "target": {"$result": "4"}, "member": "Performance"},
            {"op": "getProp", "target": {"$result": "5"}, "member": "AllTrades"},
        ]
        for idx in range(i, min(i + 10, chunk_size)):
            res_id = len(ops)
            ops.append({"op": "invoke", "target": {"$result": "6"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": idx}]})
            ops.append({"op": "getProp", "target": {"$result": str(res_id)}, "member": "EntryExecution"})
            ops.append({"op": "getProp", "target": {"$result": str(res_id + 1)}, "member": "Time"})
            ops.append({"op": "getProp", "target": {"$result": str(res_id + 1)}, "member": "Price"})
            ops.append({"op": "getProp", "target": {"$result": str(res_id)}, "member": "ProfitCurrency"})
            ops.append({"op": "getProp", "target": {"$result": str(res_id)}, "member": "ExitExecution"})
            ops.append({"op": "getProp", "target": {"$result": str(res_id + 5)}, "member": "Order"})
            ops.append({"op": "getProp", "target": {"$result": str(res_id + 6)}, "member": "Name"})

        resp = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json={"ui": True, "ops": ops})
        res_list = resp.json()["results"]
        # parse out trades
        base_ptr = 7
        while base_ptr < len(res_list):
            t_entry = res_list[base_ptr + 2].get("value")
            p_entry = res_list[base_ptr + 3].get("value")
            pnl = res_list[base_ptr + 4].get("value")
            exit_name = res_list[base_ptr + 7].get("value")
            trades.append({"entry_time": t_entry, "entry_price": p_entry, "pnl": pnl, "exit_name": exit_name})
            base_ptr += 8

    df = pd.DataFrame(trades)
    print("\nSample Trades from NT8 Strategy Analyzer:")
    print(df.to_string())

if __name__ == "__main__":
    main()
