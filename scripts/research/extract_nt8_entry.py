import json
import requests

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def main():
    print("Extracting live NT8 Strategy Analyzer backtest metrics...")

    payload = {
        "ui": True,
        "ops": [
            {
                "op": "getStatic",
                "type": "NinjaTrader.Core.Globals, NinjaTrader.Core",
                "member": "AllWindows"
            },
            {
                "op": "invoke",
                "target": {"$result": "0"},
                "method": "get_Item",
                "args": [{"$type": "System.Int32", "value": 4}]
            },
            {
                "op": "getProp",
                "target": {"$result": "1"},
                "member": "ViewModel"
            },
            {
                "op": "getProp",
                "target": {"$result": "2"},
                "member": "LogEntries"
            },
            {
                "op": "invoke",
                "target": {"$result": "3"},
                "method": "get_Item",
                "args": [{"$type": "System.Int32", "value": 0}]
            },
            {
                "op": "getProp",
                "target": {"$result": "4"},
                "member": "Results"
            },
            {
                "op": "getProp",
                "target": {"$result": "5"},
                "member": "AllTrades"
            },
            {
                "op": "getProp",
                "target": {"$result": "6"},
                "member": "TradesPerformance"
            },
            {
                "op": "getProp",
                "target": {"$result": "7"},
                "member": "GrossProfit"
            },
            {
                "op": "getProp",
                "target": {"$result": "7"},
                "member": "GrossLoss"
            },
            {
                "op": "getProp",
                "target": {"$result": "7"},
                "member": "TradesCount"
            },
            {
                "op": "getProp",
                "target": {"$result": "7"},
                "member": "Currency"
            },
            {
                "op": "getProp",
                "target": {"$result": "11"},
                "member": "CumProfit"
            },
            {
                "op": "getProp",
                "target": {"$result": "11"},
                "member": "Drawdown"
            }
        ]
    }

    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    print("Full Reflect Results:", json.dumps(res.json(), indent=2))
    return
    gl = results[9].get("value")
    trades_count = results[10].get("value")
    cum_profit = results[12].get("value")
    max_dd = results[13].get("value")

    print(f"\nTarget Entry: {entry_str}")
    print(f"Total Trades:       {trades_count}")
    print(f"Gross Profit:       ${float(gp):,.2f}" if gp else "Gross Profit: None")
    print(f"Gross Loss:        -${abs(float(gl)):,.2f}" if gl else "Gross Loss: None")
    if gp and gl and float(gl) != 0:
        pf = float(gp) / abs(float(gl))
        print(f"Profit Factor:      {pf:.2f}")
    print(f"Net Realized P&L:   ${float(cum_profit):,.2f}" if cum_profit else "Net Profit: None")
    print(f"Maximum Drawdown:   ${float(max_dd):,.2f}" if max_dd else "Drawdown: None")


if __name__ == "__main__":
    main()
