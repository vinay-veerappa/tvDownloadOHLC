"""Fix the GEX block variable order in intraday_blocks.py"""
import re

with open('scripts/trader/signals/intraday_blocks.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the section between live_unified and is_overnight
old = r'        live_unified = load_macro_levels\(session="live"\)\s*\n\s*# Session-aware.*?\n\s*is_overnight = session in'
new = '''        live_unified = load_macro_levels(session="live")

        # Determine which ticker to use for GEX
        is_es = "ES" in ticker.upper()
        gex_key = "ES" if is_es else "NQ"
        alt_key = "SPY" if is_es else "QQQ"

        is_overnight = session in'''

content = re.sub(old, new, content, flags=re.DOTALL, count=1)

with open('scripts/trader/signals/intraday_blocks.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')