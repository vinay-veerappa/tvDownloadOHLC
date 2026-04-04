import os
import glob

# Paths to search and replace
replacements = [
    ("scripts.trading_framework.data", "scripts.libs.data"),
    ("scripts.trading_framework.features", "scripts.libs.features"),
    ("scripts.trading_framework.regime", "scripts.libs.regime"),
]

# Find all python files in scripts directory
python_files = glob.glob("scripts/**/*.py", recursive=True)
updated_files_count = 0

for file_path in python_files:
    # Skip the update script itself
    if "tmp_update" in file_path:
        continue
        
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            content = f.read()
        except UnicodeDecodeError:
            continue
            
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated imports in {file_path}")
        updated_files_count += 1

print(f"Total files updated: {updated_files_count}")
