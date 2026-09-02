"""
Inspect all metadata and exact parameters for each entry in LogEntries
"""

import requests
import json

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
            {"op": "getProp", "target": {"$result": "3"}, "member": "Count"},
        ]
    }
    r = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    count = int(r.json()["results"][-1].get("value", 0))
    print(f"Total LogEntries in Strategy Analyzer grid: {count}")

    for idx in range(min(count, 5)):
        entry_payload = {
            "ui": True,
            "ops": [
                {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
                {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
                {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
                {"op": "getProp", "target": {"$result": "2"}, "member": "LogEntries"},
                {"op": "invoke", "target": {"$result": "3"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": idx}]},
                {"op": "getProp", "target": {"$result": "4"}, "member": "InstrumentOrInstrumentList"},
                {"op": "getProp", "target": {"$result": "4"}, "member": "From"},
                {"op": "getProp", "target": {"$result": "4"}, "member": "To"},
                {"op": "getProp", "target": {"$result": "4"}, "member": "Strategy"},
                {"op": "getProp", "target": {"$result": "4"}, "member": "SummaryPerformancesCurrency"},
                {"op": "getProp", "target": {"$result": "9"}, "member": "All"},
                {"op": "getProp", "target": {"$result": "10"}, "member": "TotalNumTrades"},
                {"op": "getProp", "target": {"$result": "10"}, "member": "PercentProfitable"},
                {"op": "getProp", "target": {"$result": "10"}, "member": "ProfitFactor"},
                {"op": "getProp", "target": {"$result": "10"}, "member": "TotalNetProfit"},
                {"op": "getProp", "target": {"$result": "10"}, "member": "MaxDrawdown"},
            ]
        }
        res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=entry_payload).json()["results"]
        inst = res[5].get("value")
        dt_from = res[6].get("value")
        dt_to = res[7].get("value")
        strat = res[8].get("value")
        trades = res[11].get("value")
        wr = res[12].get("value")
        pf = res[13].get("value")
        net = res[14].get("value")
        dd = res[15].get("value")

        wr_val = float(wr) * 100.0 if wr is not None else 0.0
        pf_val = float(pf) if pf is not None else 0.0
        net_val = float(net) if net is not None else 0.0
        dd_val = float(dd) if dd is not None else 0.0

        print(f"\n[Run #{idx}]")
        print(f"  Strategy:    {strat}")
        print(f"  Instrument:  {inst}")
        print(f"  Date Range:  {dt_from} -> {dt_to}")
        print(f"  Trades:      {trades}")
        print(f"  Win Rate:    {wr_val:.1f}%")
        print(f"  Profit Fac:  {pf_val:.3f}")
        print(f"  Net Profit:  ${net_val:,.2f}")
        print(f"  Max DD:      ${dd_val:,.2f}")

if __name__ == "__main__":
    main()
