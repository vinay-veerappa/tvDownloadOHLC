import os
import shutil
import glob
from datetime import datetime
import pandas as pd

# Go up 3 levels: scripts/utils/data_utils.py -> scripts/utils -> scripts -> root
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))
BACKUP_DIR = os.path.join(DATA_DIR, "backup")

def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def create_backup(filepath):
    """
    Creates a timestamped backup of the given file in data/backup/
    Returns the path to the backup file.
    """
    if not os.path.exists(filepath):
        print(f"Warning: File {filepath} does not exist, skipping backup.")
        return None

    ensure_backup_dir()
    
    filename = os.path.basename(filepath)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filename}.{timestamp}.bak"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    try:
        shutil.copy2(filepath, backup_path)
        print(f"✅ Backup created: {backup_name}")
        return backup_path
    except Exception as e:
        print(f"❌ Backup failed for {filename}: {e}")
        raise e

def safe_save_parquet(df, filepath):
    """
    Safely saves a DataFrame to parquet:
    1. Writes to .tmp file
    2. Verifies file exists
    3. Renames to target filepath (atomic-ish on POSIX, replace on Windows)
    """
    tmp_path = filepath + ".tmp"
    try:
        # Write to temp
        df.to_parquet(tmp_path)
        
        # Verify
        if not os.path.exists(tmp_path):
            raise Exception("Temp file write failed")
            
        # Rename (Replace)
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(tmp_path, filepath)
        print(f"✅ Successfully saved: {os.path.basename(filepath)}")
        
    except Exception as e:
        print(f"❌ Save failed: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise e
