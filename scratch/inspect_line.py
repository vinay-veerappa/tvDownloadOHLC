with open(r'c:\Users\vinay\tvDownloadOHLC\scripts\indicators\daily-ny-levels\DailyNYLevelsAnalytics.pine', 'rb') as f:
    lines = f.readlines()
    line = lines[567]
    print(f"Line 568: {repr(line)}")
    print(f"Char at 131: {repr(line[130:131])}")
