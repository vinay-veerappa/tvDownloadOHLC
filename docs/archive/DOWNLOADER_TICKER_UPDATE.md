# Downloader Ticker-Agnostic Update

## Problem Fixed
The selenium downloader was hardcoded to save all downloaded data with "ES1" prefix, regardless of which ticker was actually being downloaded. This meant downloading NQ1!, CL1!, or any other ticker would incorrectly name the files as ES1 files.

## Changes Made

### 1. **Dynamic Ticker Detection**
```python
# Determine ticker - use provided or default to ES1!
ticker = args.ticker if args.ticker else "ES1!"
# Clean ticker for file/folder naming (remove special chars)
ticker_clean = ticker.replace("!", "").replace("^", "").replace("/", "_")
```

### 2. **Ticker-Specific Directories**
Old:
```python
download_dir = os.path.join(os.getcwd(), "data", "downloads_es_futures")
```

New:
```python
download_dir = os.path.join(os.getcwd(), "data", f"downloads_{ticker_clean.lower()}")
if not os.path.exists(download_dir):
    os.makedirs(download_dir)
```

### 3. **Dynamic File Naming**
Old:
```python
new_filename = f"ES1_1m_{timestamp}_{task['type']}_{iteration}.csv"
```

New:
```python
new_filename = f"{ticker_clean}_1m_{timestamp}_{task['type']}_{iteration}.csv"
```

## Benefits

1. **Multi-Ticker Support**: Can now download different futures without file conflicts
2. **Organized Data**: Each ticker gets its own directory
3. **Clear Identification**: Files are named based on actual ticker downloaded
4. **Automatic Directory Creation**: Creates ticker-specific folders as needed

## Examples

### ES Futures (default)
```bash
python selenium_downloader/download_ohlc_selenium_enhanced.py --resume
# Creates: data/downloads_es1/
# Files: ES1_1m_20251203_133000_history_1.csv
```

### NQ Futures
```bash
python selenium_downloader/download_ohlc_selenium_enhanced.py --ticker "NQ1!" --resume
# Creates: data/downloads_nq1/
# Files: NQ1_1m_20251203_133000_history_1.csv
```

### CL Crude Oil
```bash
python selenium_downloader/download_ohlc_selenium_enhanced.py --ticker "CL1!" --resume
# Creates: data/downloads_cl1/
# Files: CL1_1m_20251203_133000_history_1.csv
```

## Directory Structure

```
data/
├── downloads_es1/          # ES futures data
│   ├── ES1_1m_20251203_133000_history_1.csv
│   └── ES1_1m_20251203_133500_history_2.csv
├── downloads_nq1/          # NQ futures data
│   ├── NQ1_1m_20251203_134000_history_1.csv
│   └── NQ1_1m_20251203_134500_history_2.csv
└── downloads_cl1/          # CL futures data
    ├── CL1_1m_20251203_135000_history_1.csv
    └── CL1_1m_20251203_135500_history_2.csv
```

## Character Cleaning

Special characters in ticker symbols are cleaned for file/folder names:
- `!` → removed (NQ1! → NQ1)
- `^` → removed (VIX^ → VIX)  
- `/` → `_` (SPX/USD → SPX_USD)

## Backward Compatibility

- Default ticker is still ES1! if no `--ticker` argument provided
- Existing scripts that don't specify ticker will still work
- Old hardcoded directory `downloads_es_futures` is no longer created/used

## Next Steps

Update `stitch_and_validate.py` and `convert_to_parquet.py` to:
1. Accept ticker parameter
2. Look in correct ticker-specific directory
3. Output ticker-specific parquet files

This ensures the complete pipeline is ticker-agnostic!
