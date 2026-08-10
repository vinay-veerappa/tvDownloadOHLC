import time
import sys
from pathlib import Path
import comtypes.client

symbols = {
    "ES": "/ES",
    "NQ": "/NQ",
    "SPX": "$SPX",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "DIA": "DIA",
    "IWM": "IWM"
}

def test_com():
    print("Connecting to TOS RTD COM Server (Tos.RtdServer)...")
    try:
        rtd = comtypes.client.CreateObject("Tos.RtdServer")
        rtd.ServerStart()
        print("TOS RTD Server Started successfully.")

        topic_id = 1
        topic_map = {}
        for name, sym in symbols.items():
            # Request LAST price
            rtd.ConnectData(topic_id, ["LAST", sym], True)
            topic_map[topic_id] = (name, sym, "LAST")
            topic_id += 1

            # Request IMPL_VOL
            rtd.ConnectData(topic_id, ["IMPL_VOL", sym], True)
            topic_map[topic_id] = (name, sym, "IMPL_VOL")
            topic_id += 1

        print(f"Subscribed to {len(topic_map)} RTD topics. Waiting 2 seconds for data stream...")
        time.sleep(2)

        data = rtd.RefreshData()
        print(f"RefreshData returned: {data}")

        results = {}
        if data and len(data) >= 2:
            topic_ids = data[0]
            topic_values = data[1]
            for tid, val in zip(topic_ids, topic_values):
                if tid in topic_map:
                    name, sym, field = topic_map[tid]
                    if name not in results:
                        results[name] = {}
                    results[name][field] = val

        print("\nTOS RTD Results:")
        for name in symbols:
            res = results.get(name, {})
            print(f"  {name:5s}: LAST={res.get('LAST')}, IMPL_VOL={res.get('IMPL_VOL')}")

        rtd.ServerStop()
    except Exception as e:
        print(f"COM Error: {e}")

if __name__ == "__main__":
    test_com()
