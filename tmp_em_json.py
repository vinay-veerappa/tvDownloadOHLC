import json
import sqlite3
from datetime import datetime, timezone

# Check daily_levels.json for futures-translated entries
d = json.load(open('data/options/daily_levels.json'))
ms = d.get('market_structure', [])
print(f"Total market_structure entries: {len(ms)}")
print()
print("Looking for futures (/ES, /NQ, /GC, /CL) or RTD entries:")
for m in ms:
    asset = m.get('asset', '?')
    cash = m.get('cash_ticker', '?')
    if '/' in asset or '/' in cash or 'ES' in asset or 'NQ' in asset or 'GC' in asset or 'CL' in asset or 'RTD' in str(m.get('translation_mode','')):
        ems = m.get('expected_moves', [])
        em0 = ems[0] if ems else {}
        print(f"  asset={asset:10} cash={cash:8} mode={m.get('translation_mode','?'):12} "
              f"EMs={len(ems)} em_upper={em0.get('em_upper','N/A')} "
              f"em_lower={em0.get('em_lower','N/A')}")

# Check all entries for futures_symbol field
print("\nAll entries with futures_symbol:")
for m in ms:
    fs = m.get('futures_symbol', m.get('futuresSymbol', ''))
    if fs and fs != 'null':
        ems = m.get('expected_moves', [])
        em0 = ems[0] if ems else {}
        print(f"  asset={m.get('asset','?'):10} cash={m.get('cash_ticker','?'):8} "
              f"futures_sym={fs:10} mode={m.get('translation_mode','?')} "
              f"EMs={len(ems)} em_upper={em0.get('em_upper','N/A')}")

# Check GexSnapshot table for futures
print("\n=== GexSnapshot table (recent) ===")
con = sqlite3.connect('web/prisma/dev.db')
cur = con.cursor()
tabs = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='GexSnapshot'").fetchall()
if tabs:
    cnt = cur.execute("SELECT COUNT(*) FROM GexSnapshot").fetchone()[0]
    print(f"Total rows: {cnt}")
    rows = cur.execute(
        "SELECT ticker, futuresSymbol, futuresTranslationMode, tradingDate, "
        "spotPrice, totalGex, createdAt FROM GexSnapshot "
        "ORDER BY createdAt DESC LIMIT 15"
    ).fetchall()
    for r in rows:
        td = datetime.fromtimestamp(r[3]/1000, tz=timezone.utc).strftime('%Y-%m-%d') if r[3] else '?'
        ct = datetime.fromtimestamp(r[6]/1000, tz=timezone.utc).strftime('%m-%d %H:%M') if r[6] else '?'
        print(f"  ticker={r[0]:8} fut_sym={str(r[1] or '-'):8} mode={str(r[2] or '-'):14} "
              f"date={td} spot={r[4] or 0:.0f} gex={r[5] or 0:.0f} written={ct}")
else:
    print("GexSnapshot table not found")
con.close()