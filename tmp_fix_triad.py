"""Add delivery triad 1-liner to all 3 intraday bias blocks."""

with open('scripts/trader/signals/intraday_blocks.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern: after "Session direction: {session_dir}" line + sections.append, add delivery triad
# There are 3 occurrences (NY AM, NY Lunch, NY PM)
old_pattern = 'lines.append(f"Session direction: {session_dir}")\n        sections.append("\\n".join(lines))'
new_pattern = '''lines.append(f"Session direction: {session_dir}")
        _triad_1l = _format_delivery_triad_1liner(ticker, ticker_current, target_date, now_et)
        if _triad_1l:
            lines.append(_triad_1l)
        sections.append("\\n".join(lines))'''

count = content.count(old_pattern)
print(f"Found {count} occurrences of the pattern")
content = content.replace(old_pattern, new_pattern)

with open('scripts/trader/signals/intraday_blocks.py', 'w', encoding='utf-8') as f:
    f.write(content)
print(f"Replaced {count} occurrences")