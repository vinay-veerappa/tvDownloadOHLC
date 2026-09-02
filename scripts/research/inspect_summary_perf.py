import json
import requests

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def main():
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
                "target": {"$result": "4"},
                "member": "Executions"
            }
        ]
    }

    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    results = res.json()["results"]
    for idx, r in enumerate(results):
        print(f"Op {idx}: {r.get('type') or r.get('error') or r.get('value')}")
    print("\nSummaryPerformancesCurrency details:")
    print(json.dumps(results[5], indent=2))
    print("\nExecutions details:")
    print(json.dumps(results[6], indent=2))


if __name__ == "__main__":
    main()
