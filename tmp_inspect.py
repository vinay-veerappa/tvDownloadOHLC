data = open(r'scripts\trader\daily_narrative.py', 'rb').read().decode('utf-8')
idx = data.rfind('if session.lower() == "open":')
print(idx)
if idx != -1:
    print(repr(data[idx:idx+600]))
