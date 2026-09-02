import json
import requests
import time

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def main():
    print("Triggering Strategy Analyzer run directly via WPF Command...")

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
                "member": "RunCommand"
            },
            {
                "op": "invoke",
                "target": {"$result": "3"},
                "method": "Execute",
                "args": [None]
            }
        ]
    }

    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    print("Execute result:", json.dumps(res.json(), indent=2))

    # Wait 10 seconds and check LogEntries
    print("\nWaiting 10 seconds for backtest to start / complete...")
    time.sleep(10)

    check_payload = {
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
            }
        ]
    }

    res2 = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=check_payload)
    items = res2.json()["results"][3].get("items", [])
    print(f"LogEntries Count: {len(items)}")
    if items:
        print("Most recent LogEntry:", items[0])


if __name__ == "__main__":
    main()
