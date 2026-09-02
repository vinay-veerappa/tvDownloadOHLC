import json
import requests

HEADERS = {
    "Authorization": "Bearer d0b837223cab4653",
    "Content-Type": "application/json",
}

def main():
    print("Calling RunEntryDetails in same batch...")

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
                "member": "SelectedTab"
            },
            {
                "op": "getProp",
                "target": {"$result": "2"},
                "member": "LogEntries"
            },
            {
                "op": "invoke",
                "target": {"$result": "4"},
                "method": "get_Item",
                "args": [{"$type": "System.Int32", "value": 0}]
            },
            {
                "op": "invoke",
                "target": {"$result": "2"},
                "method": "RunEntryDetails",
                "args": [
                    {"$result": "3"},  # tab
                    {"$result": "5"}   # entry (LogEntries[0])
                ]
            },
            {
                "op": "getProp",
                "target": {"$result": "3"},
                "member": "SelectedResult"
            }
        ]
    }

    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    results = res.json()["results"]
    for idx, r in enumerate(results):
        print(f"Op {idx}: {r.get('op', 'ok')} -> {r.get('type') or r.get('error') or r.get('value')}")


if __name__ == "__main__":
    main()
