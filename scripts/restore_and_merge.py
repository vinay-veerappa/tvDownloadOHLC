
import shutil
import subprocess
from pathlib import Path
import sys

DATA_DIR = Path("data")
BACKUP_DIR = Path("data/backup")

def restore_latest_backup(ticker, timeframe="1m"):
    pattern = f"{ticker}_{timeframe}_pre_merge_*.parquet"
    # Fallback to standard backup pattern if pre_merge not found
    backups = list(BACKUP_DIR.glob(pattern))
    if not backups:
        # Try standard .bak pattern
        backups = list(DATA_DIR.glob(f"{ticker}_{timeframe}.parquet.*.bak"))
        
    if not backups:
        print(f"ERROR: No backup found for {ticker}!")
        return False
        
    # Sort by modification time (newest first)
    latest_backup = sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    target_path = DATA_DIR / f"{ticker}_{timeframe}.parquet"
    
    print(f"Restoring {ticker} from {latest_backup.name}...")
    try:
        shutil.copy(latest_backup, target_path)
        print("Restore successful.")
        return True
    except Exception as e:
        print(f"Restore failed: {e}")
        return False

def run_script(script_path):
    print(f"\nRunning {script_path}...")
    try:
        subprocess.run([sys.executable, str(script_path)], check=True)
        print("Success.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Script failed with code {e.returncode}")
        return False

def main():
    print("=== AUTOMATED RESTORE & MERGE SEQUENCE ===")
    
    # 1. ES Operations
    if restore_latest_backup("ES1"):
        if not run_script("scripts/merge_es_data.py"):
            print("Aborting sequence due to ES merge failure.")
            return

    # 2. NQ Operations
    if restore_latest_backup("NQ1"):
        # NQ merge script is in data_processing subdir
        if not run_script("scripts/data_processing/merge_nq1_data.py"):
            print("Aborting sequence due to NQ merge failure.")
            return

    # 3. Regenerate Derived Data
    print("\n=== REGENERATING DERIVED DATA ===")
    # Assuming there is a master script or we run them individually. 
    # Based on workflows, there is "/regenerate_all_data" which likely points to a script.
    # Let's verify if 'scripts/regenerate_all_data.py' or similar exists, otherwise listed in task.
    
    # Checking for common regeneration scripts
    scripts_to_run = [
        "scripts/generate_hod_lod.py", # Example name, verifying later
        "scripts/profiler/generate_profiles.py" # Example
    ]
    
    # Since I don't know the exact regen script names yet, I will pause here or list what I find.
    # Actually, better to inspect the workflows folder first.
    # For now, this script stops after merge. User can run regen workflow.
    
    print("\nMerge complete. Please run the '/regenerate_all_data' workflow next.")

if __name__ == "__main__":
    main()
