import os
import glob
import shutil
import data_utils

def revert_weekly_names():
    files = glob.glob(os.path.join(data_utils.DATA_DIR, "*_1wk.parquet"))
    for f in files:
        new_name = f.replace("_1wk.parquet", "_1W.parquet")
        try:
            shutil.move(f, new_name)
            print(f"Renamed {os.path.basename(f)} -> {os.path.basename(new_name)}")
        except Exception as e:
            print(f"Error renaming {f}: {e}")

if __name__ == "__main__":
    revert_weekly_names()
