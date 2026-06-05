import duckdb
import pandas as pd
import numpy as np
import os

def test_duckdb_merge():
    file_path_str = "test_duckdb_merge.parquet"
    if os.path.exists(file_path_str):
        os.remove(file_path_str)
        
    # Create initial file
    df1 = pd.DataFrame({
        "symbol": ["NQ1", "NQ1", "RTY1"],
        "id": [1, 2, 3],
        "val": ["A", "B", "C"]
    })
    df1.to_parquet(file_path_str)
    
    # New dataframe replacing NQ1 and adding new NQ1
    new_df = pd.DataFrame({
        "symbol": ["NQ1", "NQ1"],
        "id": [4, 5],
        "val": ["X", "Y"]
    })
    
    new_symbols = tuple(new_df["symbol"].unique())
    if len(new_symbols) == 1:
        new_symbols_str = f"('{new_symbols[0]}')"
    else:
        new_symbols_str = str(new_symbols)
        
    con = duckdb.connect()
    con.register('new_df', new_df)
    
    columns_str = ", ".join([f'"{c}"' for c in new_df.columns])
    order_by_str = '"symbol", "id"'
    temp_path = file_path_str + ".tmp"
    
    query = f"""
    COPY (
        SELECT {columns_str} FROM read_parquet('{file_path_str}') 
        WHERE symbol NOT IN {new_symbols_str}
        UNION ALL
        SELECT {columns_str} FROM new_df
        ORDER BY {order_by_str}
    ) TO '{temp_path}' (FORMAT PARQUET)
    """
    
    print(query)
    con.execute(query)
    con.close()
    
    # Read back
    result = pd.read_parquet(temp_path)
    print(result)
    
if __name__ == "__main__":
    test_duckdb_merge()
