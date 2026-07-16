import sys
path = r'scripts\trader\daily_narrative.py'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

CRLF = '\r\n'

dedented = (
    '    else:' + CRLF +
    '        log.warning("  No mandated tracks found in briefing data; track mandate enforcement is a no-op.")' + CRLF +
    CRLF +
    '        if session.lower() == "open":' + CRLF +
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

fixed = (
    '    else:' + CRLF +
    '        log.warning("  No mandated tracks found in briefing data; track mandate enforcement is a no-op.")' + CRLF +
    CRLF +
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

if dedented in content:
    content = content.replace(dedented, fixed, 1)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    print('FIXED')
else:
    print('NOT FOUND')
    # investigate
    if 'if session.lower() == "open":' in content:
        print('open-if found in file')
    if 'Open narrative' in content:
        print('comment found')
