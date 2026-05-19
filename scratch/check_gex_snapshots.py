import sqlite3
import pandas as pd

def check_gex_snapshots():
    db_path = r"c:\Users\vinay\tvDownloadOHLC\web\prisma\dev.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(GexSnapshot)")
    columns = [col[1] for col in cursor.fetchall()]
    print("GexSnapshot Columns:", columns)
    
    # Let's query the 20 most recent rows based on whatever timestamp/date column is available
    time_col = 'timestamp' if 'timestamp' in columns else ('createdAt' if 'createdAt' in columns else columns[0])
    
    query = f"""
    SELECT *
    FROM GexSnapshot
    ORDER BY {time_col} DESC
    LIMIT 20
    """
    df = pd.read_sql_query(query, conn)
    print("\nLatest GEX Snapshots in DB:")
    print(df.to_string())
        
    conn.close()

if __name__ == "__main__":
    check_gex_snapshots()
