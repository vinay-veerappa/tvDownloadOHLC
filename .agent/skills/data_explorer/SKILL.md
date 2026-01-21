---
name: Data Explorer
description: Utilities for inspecting, summarizing, and understanding the contents of Parquet and JSON data files.
---

# Data Explorer

This skill provides tools to quickly introspect the data available in the project, including raw OHLC data and derived analysis files.

## Utilities

### 2. `generate_data_inventory.py`
Scans the `data/` directory and regenerates `DATA_INVENTORY.md` with a summary of all available parquet datasets.

**features:**
- **Auto-Discovery**: Scans all `.parquet` files.
- **Metadata**: Extracts start/end dates and row counts.
- **Reporting**: Updates the main project inventory file.

## Usage Examples

### Inspect a specific data file
See what columns and date range are in the NQ 1-minute data:
```powershell
python scripts/utils/inspect_dataset.py data/NQ1_1m.parquet
```

### Inspect derived classification data
Check schema of the Day Type classifications:
```powershell
python scripts/utils/inspect_dataset.py data/derived/NQ1_daily_classification.parquet
```

### Update Full Data Inventory
Regenerate the `DATA_INVENTORY.md` report for the entire project:
```powershell
python scripts/utils/generate_data_inventory.py
```
