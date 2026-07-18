"""Check daily_open differences between adjusted and unadjusted for LT dates."""
import json

raw_unadj = json.load(open(r'C:\Users\vinay\tvDownloadOHLC\data\NQ1_daily_hod_lod_unadjusted.json'))
raw_adj = json.load(open(r'C:\Users\vinay\tvDownloadOHLC\data\NQ1_daily_hod_lod.json'))

lt_dates = [
    '2006-08-02', '2007-11-13', '2008-03-18', '2010-03-17', '2012-11-01',
    '2014-12-18', '2015-08-27', '2017-04-17', '2018-06-20', '2019-03-11',
    '2020-04-22', '2021-03-09', '2022-03-29', '2022-06-24', '2022-08-12',
    '2023-07-28', '2026-03-16'
]

print(f"{'Date':<12} {'Adj Open':<12} {'Unadj Open':<12} {'Match':<6} {'Adj Low%':<10} {'Unadj Low%':<10}")
for d in lt_dates:
    if d in raw_adj and d in raw_unadj:
        a = raw_adj[d]
        u = raw_unadj[d]
        a_open = a.get("daily_open", 0)
        u_open = u.get("daily_open", 0)
        a_low = a.get("daily_low", 0)
        u_low = u.get("daily_low", 0)
        a_high = a.get("daily_high", 0)
        u_high = u.get("daily_high", 0)
        
        a_low_pct = round((a_low / a_open - 1) * 100, 4) if a_open else 0
        u_low_pct = round((u_low / u_open - 1) * 100, 4) if u_open else 0
        
        match = "✅" if a_open == u_open else "❌"
        pct_match = "✅" if abs(a_low_pct - u_low_pct) < 0.001 else "❌"
        print(f"{d:<12} {a_open:<12} {u_open:<12} {match:<6} {a_low_pct:<10} {u_low_pct:<10} {pct_match}")