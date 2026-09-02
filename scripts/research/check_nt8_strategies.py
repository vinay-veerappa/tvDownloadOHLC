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
                "type": "NinjaTrader.Gui.NinjaScript.StrategyAnalyzer.StrategyAnalyzerViewModel, NinjaTrader.Gui",
                "member": "AvailableStrategies"
            }
        ]
    }

    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    items = res.json()["results"][0].get("items", [])
    print(f"Total Available Strategies in NT8: {len(items)}")
    for s in items:
        if "CISD" in s or "ICT" in s or "Vinay" in s:
            print("  ->", s)


if __name__ == "__main__":
    main()
