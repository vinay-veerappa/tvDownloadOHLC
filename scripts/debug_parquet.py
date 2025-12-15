import pyarrow.parquet as pq
import pandas as pd
import os

filepath = os.path.join("data", "ES1_1m.parquet")

try:
    pf = pq.ParquetFile(filepath)
    print("Schema:")
    print(pf.schema)
    
    print("\nMetadata:")
    print(pf.metadata)
    
    print("\nRow Group 0 Statistics (Column 0):")
    rg = pf.metadata.row_group(0)
    col0 = rg.column(0)
    print(f"Name: {col0.path_in_schema}")
    print(f"Stats: {col0.statistics}")
    if col0.statistics:
        print(f"Min: {col0.statistics.min}")
        print(f"Max: {col0.statistics.max}")
        
    # Check if index is separate
    print("\nPandas Metadata (from schema):")
    schema_meta = pf.schema.metadata
    if schema_meta and b'pandas' in schema_meta:
        import json
        pandas_meta = json.loads(schema_meta[b'pandas'].decode('utf-8'))
        print(json.dumps(pandas_meta, indent=2))
        
except Exception as e:
    print(e)
