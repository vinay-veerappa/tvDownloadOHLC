from tvDatafeed import TvDatafeed
tv = TvDatafeed()
try:
    print("--- _TvDatafeed__ws_headers ---")
    print(tv._TvDatafeed__ws_headers)
except Exception as e:
    print(e)
