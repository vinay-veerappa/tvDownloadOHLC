import duckdb
con = duckdb.connect()
print(con.execute("DESCRIBE SELECT * FROM 'data/derived/macro_records.parquet'").df().to_string())
