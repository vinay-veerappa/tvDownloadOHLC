import time
import comtypes.client
from comtypes import COMError

symbols = [
    "SPY", "QQQ", "DIA", "IWM",
    "$SPX", "$SPX.X", "SPX",
    "/ES", "/ES:XCME", "/NQ", "/NQ:XCME"
]

def test_tos_rtd_symbols():
    print("Testing TOS RTD COM Object (Tos.RTD)...")
    try:
        rtd = comtypes.client.CreateObject("Tos.RTD")
        print("Tos.RTD created successfully!")
        
        # Test ServerStart
        # Create dummy update event handler if needed
        class DummyEvent:
            def Disconnect(self): pass
            def UpdateNotify(self): pass
            
        rtd.ServerStart(DummyEvent())
        print("ServerStart called successfully.")
        
        topic_id = 1
        sub_map = {}
        for sym in symbols:
            for field in ["LAST", "MARK", "IMPL_VOL"]:
                try:
                    rtd.ConnectData(topic_id, [field, sym], True)
                    sub_map[topic_id] = (sym, field)
                    topic_id += 1
                except Exception as e:
                    print(f"Error subscribing {sym} {field}: {e}")

        print(f"Subscribed to {len(sub_map)} topics. Waiting 3 seconds for RTD stream...")
        time.sleep(3)

        data = rtd.RefreshData()
        print(f"RefreshData raw: {data}")

        if data and len(data) >= 2:
            ids, vals = data[0], data[1]
            results = {}
            for tid, val in zip(ids, vals):
                if tid in sub_map:
                    sym, field = sub_map[tid]
                    if sym not in results: results[sym] = {}
                    results[sym][field] = val
                    
            print("\n--- TOS RTD Stream Results ---")
            for sym, fdict in results.items():
                print(f"  {sym:12s}: {fdict}")

        rtd.ServerStop()
    except Exception as e:
        print(f"TOS RTD Test Exception: {e}")

if __name__ == "__main__":
    test_tos_rtd_symbols()
