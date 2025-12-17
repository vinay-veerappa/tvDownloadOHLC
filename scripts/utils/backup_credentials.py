
import os
import shutil
from datetime import datetime
from pathlib import Path

def backup_credentials():
    print("=== Schwab Credentials Backup ===")
    
    # 1. Source Files
    files_to_backup = ["secrets.json", "token.json", "token_backup.json"]
    
    # 2. Local Backup
    local_backup_dir = Path("backup/credentials")
    local_backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. G Drive Backup
    g_drive_dir = Path("G:/My Drive/TradingBackups/Credentials")
    try:
        g_drive_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"⚠️ G: Drive backup skipped (unreachable): {e}")
        g_drive_dir = None

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    
    for filename in files_to_backup:
        src = Path(filename)
        if not src.exists():
            continue
            
        # Local copy (timestamped for history)
        ts_filename = f"{src.stem}_{timestamp}{src.suffix}"
        shutil.copy2(src, local_backup_dir / ts_filename)
        # Also maintain a 'latest' copy
        shutil.copy2(src, local_backup_dir / filename)
        
        print(f"✅ Local backup: {filename}")
        
        # G Drive copy
        if g_drive_dir:
            try:
                shutil.copy2(src, g_drive_dir / ts_filename)
                shutil.copy2(src, g_drive_dir / filename)
                print(f"✅ G Drive backup: {filename}")
            except Exception as e:
                print(f"⚠️ Failed to copy {filename} to G Drive: {e}")

    print("\nBackup process complete.")

if __name__ == "__main__":
    backup_credentials()
