import json
import requests

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def main():
    print("Reading exact metrics from StrategyAnalyzerGridEntry.SummaryPerformancesCurrency.All...")

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
                "member": "SummaryPerformancesCurrency"
            },
            {
                "op": "getProp",
                "target": {"$result": "5"},
                "member": "All"
            },
            # Read all key properties from 'All'
            {"op": "getProp", "target": {"$result": "6"}, "member": "TotalNumTrades"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "NumWinningTrades"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "NumLosingTrades"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "PercentProfitable"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "GrossProfit"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "GrossLoss"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "ProfitFactor"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "TotalNetProfit"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "MaxDrawdown"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "LargestWinningTrade"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "LargestLosingTrade"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "SharpeRatio"},
            {"op": "getProp", "target": {"$result": "6"}, "member": "SortinoRatio"},
        ]
    }

    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    results = res.json()["results"]

    entry_info = results[4].get("toString", "")
    trades = results[7].get("value")
    wins = results[8].get("value")
    losses = results[9].get("value")
    win_rate = results[10].get("value")
    gross_profit = results[11].get("value")
    gross_loss = results[12].get("value")
    profit_factor = results[13].get("value")
    net_profit = results[14].get("value")
    max_dd = results[15].get("value")
    largest_win = results[16].get("value")
    largest_loss = results[17].get("value")
    sharpe = results[18].get("value")
    sortino = results[19].get("value")

    print("\n" + "="*85)
    print("NINJATRADER 8 STRATEGY ANALYZER GROUND-TRUTH REPORT")
    print("="*85)
    print(f"Strategy & Run:        {entry_info[:90]}...")
    print(f"Total Completed Trades: {trades} trades (Winners: {wins}, Losers: {losses})")
    print(f"Win Rate:              {float(win_rate)*100.0:.1f}%")
    print(f"Profit Factor:         {float(profit_factor):.3f}")
    print(f"Gross Profit:          ${float(gross_profit):,.2f}")
    print(f"Gross Loss:           -${abs(float(gross_loss)):,.2f}")
    print(f"Net Realized Profit:   ${float(net_profit):,.2f}")
    print(f"Maximum Drawdown:      ${float(max_dd):,.2f}")
    print(f"Largest Win:           ${float(largest_win):,.2f}")
    print(f"Largest Loss:          ${float(largest_loss):,.2f}")
    print(f"Sharpe Ratio:          {float(sharpe):.2f}")
    print(f"Sortino Ratio:         {float(sortino):.2f}")
    print("="*85)


if __name__ == "__main__":
    main()
