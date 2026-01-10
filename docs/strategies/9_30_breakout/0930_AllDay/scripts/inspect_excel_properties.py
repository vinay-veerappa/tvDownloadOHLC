
import pandas as pd
import glob
import os

# Target ALL Excel files
files = glob.glob(r"*.xlsx")
found = False

print(f"Scanning {len(files)} files for Max Daily Loss = 150...")

for f in files:
    try:
        # Quick check without fully loading everything if possible, but pandas needs to read it.
        # We'll just read the Properties sheet.
        xl = pd.ExcelFile(f)
        if "Properties" in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name="Properties")
            # Look for the row
            # Assuming column 0 is name, 1 is value
            if len(df.columns) >= 2:
                # Filter for the row
                row = df[df.iloc[:,0].astype(str).str.contains("Max Daily Loss", case=False, na=False)]
                if not row.empty:
                    val = str(row.iloc[0,1])
                    if "150" in val:
                        print(f"\n[FOUND] File: {os.path.basename(f)}")
                        print(f"Value: {val}")
                        found = True
    except:
        pass

if not found:
    print("\n[NOT FOUND] No file with Max Daily Loss = 150 was found.")
