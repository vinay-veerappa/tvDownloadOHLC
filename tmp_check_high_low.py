"""Check difference between daily_high and hod_price."""
import json, urllib.request

with urllib.request.urlopen('http://127.0.0.1:8000/stats/daily-hod-lod/NQ1?unadjusted=true', timeout=30) as resp:
    unadj = json.loads(resp.read().decode())

# Check first 5 dates
for i in range(5):
    d = unadj["dates"][i]
    opn = unadj["daily_open"][i]
    hp = unadj["hod_price"][i]
    lp = unadj["lod_price"][i]
    dh = unadj["daily_high"][i]
    dl = unadj["daily_low"][i]
    print(f"{d}: open={opn} hod_price={hp} lod_price={lp} daily_high={dh} daily_low={dl}")
    print(f"  hod%={round((hp/opn-1)*100, 4)} daily_high%={round((dh/opn-1)*100, 4)}")
    print(f"  lod%={round((lp/opn-1)*100, 4)} daily_low%={round((dl/opn-1)*100, 4)}")
    print(f"  Match: {hp == dh and lp == dl}")
    print()