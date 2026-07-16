import sys
path = r'scripts\trader\daily_narrative.py'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Read the actual chunk we want to replace
idx = content.rfind('if session.lower() == "open":')
end = content.find('await extract_and_save_trade_plan(summary, mandated_tracks=mandated_tracks)\r\n\r\n    # Store in DB', idx)
actual_old = content[idx:end + len('await extract_and_save_trade_plan(summary, mandated_tracks=mandated_tracks)')]

CRLF = '\r\n'
new = (
    '    if session.lower() == "open":' + CRLF +
    '        # Open narrative \u2192 morning plan for today\u2019s session.' + CRLF +
    '        # Tag with TRADE_SOURCE_OPEN so the EOD\u2019s same-structure' + CRLF +
    '        # EOD_TOMORROW plan is NOT treated as a duplicate (audit \u00a72.2).' + CRLF +
    '        await extract_and_save_trade_plan(' + CRLF +
    '            summary,' + CRLF +
    '            mandated_tracks=mandated_tracks,' + CRLF +
    '            source=TRADE_SOURCE_OPEN,' + CRLF +
    '        )' + CRLF +
    '    elif session.lower() == "eod":' + CRLF +
    '        # EOD narrative \u2192 tomorrow\u2019s plan. Tagged with' + CRLF +
    '        # TRADE_SOURCE_EOD_TOMORROW so re-running the EOD with the' + CRLF +
    '        # same plan_json does not create duplicate PENDING rows.' + CRLF +
    '        await extract_and_save_trade_plan(' + CRLF +
    '            summary,' + CRLF +
    '            mandated_tracks=mandated_tracks,' + CRLF +
    '            source=TRADE_SOURCE_EOD_TOMORROW,' + CRLF +
    '        )'
)

if actual_old not in content:
    print('NOT FOUND')
    sys.exit(1)

content = content.replace(actual_old, new, 1)
with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print('OK')
