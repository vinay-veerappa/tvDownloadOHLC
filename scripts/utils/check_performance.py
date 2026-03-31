import sqlite3
from datetime import datetime

conn = sqlite3.connect('scripts/trading_framework/research_optuna.db')
c = conn.cursor()
c.execute("SELECT trial_id, datetime_start, datetime_complete FROM trials WHERE state = 'COMPLETE' ORDER BY trial_id DESC LIMIT 5")
rows = c.fetchall()

print(f"{'Trial ID':<10} | {'Duration (s)':<15}")
print("-" * 30)
for row in rows:
    t_id, start, end = row
    if start and end:
        fmt = "%Y-%m-%d %H:%M:%S.%f"
        dt_start = datetime.strptime(start, fmt)
        dt_end = datetime.strptime(end, fmt)
        duration = (dt_end - dt_start).total_seconds()
        print(f"{t_id:<10} | {duration:<15.2f}")
conn.close()
