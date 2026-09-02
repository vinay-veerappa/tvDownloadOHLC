"""
Extract and report all 4 NinjaTrader 8 Strategy Analyzer ground-truth runs
"""

import json
import requests
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

def get_entry_metrics(entry_idx: int):
    payload = {
        "ui": True,
        "ops": [
            {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
            {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
            {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
            {"op": "getProp", "target": {"$result": "2"}, "member": "LogEntries"},
            {"op": "invoke", "target": {"$result": "3"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": entry_idx}]},
            {"op": "getProp", "target": {"$result": "4"}, "member": "SummaryPerformancesCurrency"},
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
    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    results = res.json()["results"]
    return {
        "raw_string": results[4].get("toString", ""),
        "total_trades": results[7].get("value"),
        "winners": results[8].get("value"),
        "losers": results[9].get("value"),
        "win_rate": float(results[10].get("value", 0.0)) * 100.0,
        "gross_profit": float(results[11].get("value", 0.0)),
        "gross_loss": float(results[12].get("value", 0.0)),
        "profit_factor": float(results[13].get("value", 0.0)),
        "net_profit": float(results[14].get("value", 0.0)),
        "max_drawdown": float(results[15].get("value", 0.0)),
        "largest_win": float(results[16].get("value", 0.0)),
        "largest_loss": float(results[17].get("value", 0.0)),
        "sharpe": float(results[18].get("value", 0.0)),
        "sortino": float(results[19].get("value", 0.0)),
    }

def main():
    print("="*115)
    print("NINJATRADER 8 STRATEGY ANALYZER GROUND-TRUTH BACKTEST AUDIT (LIVE FROM NT8 RUN GRID)")
    print("="*115)

    entries = [
        (0, "MES SEP26 (Full Year 2026)"),
        (1, "ES SEP26  (Full Year 2026)"),
        (2, "ES SEP26  (Summer 2026)"),
        (3, "NQ SEP26  (Summer 2026)"),
    ]

    for idx, label in entries:
        m = get_entry_metrics(idx)
        print(f"\n[{idx}] {label}")
        print(f"    Raw Header:      {m['raw_string'][:90]}...")
        print(f"    Total Trades:    {m['total_trades']} trades (Winners: {m['winners']}, Losers: {m['losers']})")
        print(f"    Win Rate:        {m['win_rate']:.1f}%")
        print(f"    Profit Factor:   {m['profit_factor']:.3f}")
        print(f"    Gross Profit:    ${m['gross_profit']:,.2f}")
        print(f"    Gross Loss:     -${abs(m['gross_loss']):,.2f}")
        print(f"    Net P&L:         ${m['net_profit']:,.2f}")
        print(f"    Max Drawdown:    ${m['max_drawdown']:,.2f}")
        print(f"    Largest Win:     ${m['largest_win']:,.2f}")
        print(f"    Largest Loss:    ${m['largest_loss']:,.2f}")
        print(f"    Sharpe / Sortino:{m['sharpe']:.2f} / {m['sortino']:.2f}")

    print("\n" + "="*115)


if __name__ == "__main__":
    main()
