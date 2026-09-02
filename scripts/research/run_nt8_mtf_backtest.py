"""
Automated NT8 Strategy Analyzer Multi-Timeframe (5m+1m) Runner
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
    print("Configuring NT8 Strategy Analyzer for 5m Structure + 1m Precision Entry MTF...")

    # Step 1: Configure Strategy Analyzer tab properties for 1-minute with MTF
    config_payload = {
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
                "member": "SelectedTab"
            },
            {
                "op": "getProp",
                "target": {"$result": "3"},
                "member": "TabStrategyProperties"
            },
            # Set Strategy
            {"op": "setProp", "target": {"$result": "4"}, "member": "Strategy", "value": "ICTFVGCISDBot"},
            # Set 1-minute timeframe as primary series
            {"op": "getProp", "target": {"$result": "4"}, "member": "BarsPeriod"},
            {"op": "setProp", "target": {"$result": "6"}, "member": "Value", "value": 1},
            # Get StrategyTemplate to configure parameters
            {"op": "getProp", "target": {"$result": "4"}, "member": "StrategyTemplate"},
            # Set UseMtfExecution = True
            {"op": "setProp", "target": {"$result": "8"}, "member": "UseMtfExecution", "value": True},
            # Set StopLossBps = 2.5
            {"op": "setProp", "target": {"$result": "8"}, "member": "StopLossBps", "value": 2.5},
            # Set QueenTargetBps = 10.0
            {"op": "setProp", "target": {"$result": "8"}, "member": "QueenTargetBps", "value": 10.0},
            # Set RunnerTargetBps = 30.0
            {"op": "setProp", "target": {"$result": "8"}, "member": "RunnerTargetBps", "value": 30.0},
            # Validate Settings
            {"op": "invoke", "target": {"$result": "2"}, "method": "CheckSettingsValid", "args": []}
        ]
    }

    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=config_payload)
    valid = res.json()["results"][-1].get("value")
    print(f"CheckSettingsValid: {valid}")

    if str(valid).lower() != "true":
        print("Settings invalid, aborting.")
    # Get baseline latest entry to detect when new run finishes
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

    # Step 2: Fire RunCommand
    print("\nFiring Strategy Analyzer Backtest Run...")
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

    # Step 3: Wait for backtest completion
    print("Waiting for NinjaTrader 8 Strategy Analyzer to process simulation...")
    for poll in range(24):
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
            print(f"Backtest completed with new entry! (Poll {poll+1}, {(poll+1)*5}s)")
            break
        print(f"Still running simulation in NT8... ({(poll+1)*5}s)")

    # Step 4: Extract exact metrics
    read_payload = {
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
            {"op": "getProp", "target": {"$result": "5"}, "member": "All"},
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

    res_metrics = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=read_payload)
    results = res_metrics.json()["results"]

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

    print("\n" + "="*90)
    print("NINJATRADER 8 STRATEGY ANALYZER: 5m+1m MULTI-TIMEFRAME REPORT")
    print("="*90)
    print(f"Strategy & Run:        {entry_info[:85]}...")
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
    print("="*90)


if __name__ == "__main__":
    main()
