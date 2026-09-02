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
                "op": "listMembers",
                "type": "NinjaTrader.Gui.NinjaScript.StrategyAnalyzer.StrategyAnalyzerViewModel, NinjaTrader.Gui"
            }
        ]
    }

    res = requests.post("http://localhost:7890/api/dev/reflect", headers=HEADERS, json=payload)
    print("SAVM Members:", json.dumps(res.json(), indent=2))


if __name__ == "__main__":
    main()
