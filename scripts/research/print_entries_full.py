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
            {"op": "getStatic", "type": "NinjaTrader.Core.Globals, NinjaTrader.Core", "member": "AllWindows"},
            {"op": "invoke", "target": {"$result": "0"}, "method": "get_Item", "args": [{"$type": "System.Int32", "value": 4}]},
            {"op": "getProp", "target": {"$result": "1"}, "member": "ViewModel"},
            {"op": "getProp", "target": {"$result": "2"}, "member": "LogEntries"},
        ]
    }
    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    items = res.json()["results"][3].get("items", [])
    for i in range(min(4, len(items))):
        print(f"\n--- ENTRY {i} ---")
        print(items[i])


if __name__ == "__main__":
    main()
