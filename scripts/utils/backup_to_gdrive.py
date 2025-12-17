import os
import shutil
import glob
from datetime import datetime
from pathlib import Path
import data_utils

def backup_to_gdrive():
    # 1. Determine Source and Destination
    source_dir = Path(data_utils.DATA_DIR)
    
    # Try getting the G Drive Root
    g_drive_root = Path("G:/My Drive")
    if not g_drive_root.exists():
        g_drive_root = Path("G:/")
        if not g_drive_root.exists():
            print("❌ G: Drive not found. Please ensure Google Drive is running.")
            return

    # Create Backup Folder
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    dest_folder_name = f"TradingBackups/tvDownloadOHLC_{timestamp}"
    dest_dir = g_drive_root / dest_folder_name
    
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        print(f"📂 Created backup folder: {dest_dir}")
    except Exception as e:
        print(f"❌ Failed to create folder on G: Drive: {e}")
        return

    # 2. Select Files (Parquet + Derived JSONs)
    patterns = [
        "*.parquet", 
        "*_profiler.json", 
        "*_level_stats.json", 
        "*_level_touches.json",
        "*_hod_lod.json", 
        "*_daily_hod_lod.json",
        "*_range_dist.json"
    ]
    files_to_copy = []
    
    for pattern in patterns:
        files_to_copy.extend(source_dir.glob(pattern))
    
    files_to_copy = sorted(list(set(files_to_copy))) # Dedup
    
    print(f"found {len(files_to_copy)} files to backup...")

    # 3. Copy Files
    success_count = 0
    total_size = 0
    
    for src_file in files_to_copy:
        try:
            dest_file = dest_dir / src_file.name
            shutil.copy2(src_file, dest_file) # copy2 preserves metadata
            size = src_file.stat().st_size
            total_size += size
            success_count += 1
            print(f"  ✅ {src_file.name} ({size/1024/1024:.1f} MB)")
        except Exception as e:
            print(f"  ⚠️ Failed to copy {src_file.name}: {e}")

    print(f"\n=== Backup Complete ===")
    print(f"Files Copied: {success_count}/{len(files_to_copy)}")
    print(f"Total Size:   {total_size / (1024*1024):.1f} MB")
    print(f"Location:     {dest_dir}")

if __name__ == "__main__":
    backup_to_gdrive()
