"""Add GEX positioning to open mode — handle cache_control artifacts"""

with open('scripts/trader/briefing_core.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the exact pattern including the cache_control artifact
import re

# Match: GEX regime change failed ... Expected Move
pattern = r'log\.warning\("\[cheat_sheet\] GEX regime change failed: %s", e\)\s*\n\s*# Expected Move'
replacement = '''log.warning("[cheat_sheet] GEX regime change failed: %s", e)

    # GEX positioning verdict (session-aware, pre-computed for LLM)
    try:
        from scripts.trader.signals.intraday_blocks import _format_gex_block
        _es_spot = ticker_spot if ticker == "ES1" else 0
        sections.append(_format_gex_block(ticker_spot, _es_spot, ticker, session="OPEN", target_date=target_date))
    except Exception as e:
        log.warning("[cheat_sheet] GEX positioning failed for %s: %s", ticker, e)

    # Expected Move'''

content_new = re.sub(pattern, replacement, content, count=1)
if content_new != content:
    print("✓ GEX positioning added to open mode")
else:
    print("✗ Could not find pattern")
    # Try a simpler match
    idx = content.find('log.warning("[cheat_sheet] GEX regime change failed')
    if idx >= 0:
        # Find the next "# Expected Move" after this point
        em_idx = content.find("# Expected Move", idx)
        if em_idx >= 0:
            # Insert GEX block between
            insert_point = content.rfind('\n', idx, em_idx) + 1
            gex_block = '''
    # GEX positioning verdict (session-aware, pre-computed for LLM)
    try:
        from scripts.trader.signals.intraday_blocks import _format_gex_block
        _es_spot = ticker_spot if ticker == "ES1" else 0
        sections.append(_format_gex_block(ticker_spot, _es_spot, ticker, session="OPEN", target_date=target_date))
    except Exception as e:
        log.warning("[cheat_sheet] GEX positioning failed for %s: %s", ticker, e)

'''
            content = content[:insert_point] + gex_block + content[insert_point:]
            print("✓ GEX positioning added to open mode (fallback method)")
        else:
            print("✗ Could not find Expected Move after GEX regime")
    else:
        print("✗ Could not find GEX regime change at all")

with open('scripts/trader/briefing_core.py', 'w', encoding='utf-8') as f:
    f.write(content if content_new == content else content_new)