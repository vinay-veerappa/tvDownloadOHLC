import pandas as pd
import glob
import os

INPUT_PATTERN = r"ORBv6-Tanja*.xlsx"

def load_properties(filepath):
    props = {}
    try:
        xl = pd.ExcelFile(filepath)
        # Look for sheet with properties
        sheet = next((s for s in xl.sheet_names if any(x in s.lower() for x in ['propert', 'setting', 'input'])), None)
        if sheet:
            # TradingView usually puts properties in Key | Value columns
            df = pd.read_excel(xl, sheet_name=sheet)
            if len(df.columns) >= 2:
                # Iterate rows assuming col 0 is Key, col 1 is Value
                for index, row in df.iterrows():
                    key = str(row[0]).strip()
                    val = str(row[1]).strip()
                    props[key] = val
    except Exception as e:
        print(f"Error reading {os.path.basename(filepath)}: {e}")
    return props

def main():
    files = glob.glob(INPUT_PATTERN)
    if not files:
        print("No files found.")
        return

    all_data = []
    all_keys = set()

    print(f"Found {len(files)} files. Extracting settings...")

    for f in files:
        file_id = os.path.basename(f).split('_')[-1].replace('.xlsx', '')
        props = load_properties(f)
        
        # Filter for relevant Tanja/ORB keys to reduce noise
        # We want to see differences in Mode, Wick, TP/SL, etc.
        relevant_props = {k: v for k, v in props.items() if any(x in k for x in ['Tanja', 'Mode', 'Wick', 'Entry', 'TP', 'SL', 'Stop'])}
        
        # If no specific mapping, just take all to be safe, then we'll filter unique columns later
        if not relevant_props: 
            relevant_props = props

        entry = {'FileID': file_id}
        entry.update(relevant_props)
        all_data.append(entry)
        all_keys.update(relevant_props.keys())

    # Create DataFrame
    df = pd.DataFrame(all_data)
    df = df.set_index('FileID', inplace=False)

    # Remove columns where all values are the same (to highlight differences)
    nunique = df.apply(pd.Series.nunique)
    cols_to_keep = nunique[nunique > 1].index
    
    if len(cols_to_keep) > 0:
        print("\n--- DIFFERENCES FOUND ---")
        diff_df = df[cols_to_keep]
        print(diff_df.to_string())
    else:
        print("\nNo differences found in settings! (Are they duplicates?)")
        print("\nHere are the common settings:")
        print(df.iloc[0].to_string())

    # Save to file for easy reading
    df.to_csv("settings_comparison.csv")
    print(f"\nFull settings dump saved to settings_comparison.csv")

if __name__ == "__main__":
    main()