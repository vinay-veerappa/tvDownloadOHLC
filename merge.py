
from pathlib import Path

parts = ["scripts/pine_gen/gen_part1.py", "scripts/pine_gen/gen_part2.py", "scripts/pine_gen/gen_part3.py"]
outfile = Path("scripts/pine_gen/generate_profiler_pine.py")

full_content = ""
for p in parts:
    try:
        # Try UTF-8 first
        txt = Path(p).read_text(encoding='utf-8')
    except UnicodeDecodeError:
        # Fallback to UTF-16 if previous tool wrote BOM?
        try:
             txt = Path(p).read_text(encoding='utf-16')
        except:
             txt = Path(p).read_text(encoding='latin-1')
    full_content += txt + "\n"

outfile.write_text(full_content, encoding='utf-8')
print(f"Merged {len(parts)} files to {outfile}")
