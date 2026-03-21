import sys
import logging
from pathlib import Path

# Add the project root to sys.path
root = Path("c:/Users/vinay/tvDownloadOHLC")
sys.path.append(str(root))

logging.basicConfig(level=logging.INFO)

try:
    print("Testing import of run_options_levels...")
    import scripts.streaming.options.run_options_levels as rol
    print("Import successful!")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
