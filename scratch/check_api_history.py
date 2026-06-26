import requests
import datetime

url = "http://127.0.0.1:8001/history?symbol=/NQ"
try:
    resp = requests.get(url)
    print("Status code:", resp.status_code)
    data = resp.json()
    if "candles" in data:
        candles = data["candles"]
        print("Total candles returned:", len(candles))
        # Print candles since 21:50 UTC (or equivalent)
        # The candles are returned in milliseconds
        for c in candles:
            # Check if time is in seconds or milliseconds
            t_val = c["time"]
            if t_val > 10000000000:
                t_sec = t_val / 1000
            else:
                t_sec = t_val
            utc_time = datetime.datetime.fromtimestamp(t_sec, tz=datetime.timezone.utc)
            if utc_time >= datetime.datetime(2026, 6, 23, 21, 50, tzinfo=datetime.timezone.utc):
                print(f"Time: {utc_time} | MS/Sec: {t_val} | O: {c['open']} | H: {c['high']} | L: {c['low']} | C: {c['close']} | V: {c['volume']}")
    else:
        print("Error:", data.get("error"))
except Exception as e:
    print("Exception:", e)
