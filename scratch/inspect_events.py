import pandas as pd, sqlite3
from pathlib import Path
conn = sqlite3.connect('web/prisma/dev.db')
events = pd.read_sql("SELECT datetime,name,impact FROM EconomicEvent WHERE impact IN ('HIGH','MEDIUM')", conn)
conn.close()
print(events.head(20))
print('shape', events.shape)
print('impacts', events['impact'].value_counts())
