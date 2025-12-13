# Debugging and Validation Tools

This directory contains utility scripts used for debugging the application and validating data integrity.

## validation/

Scripts in this folder are used to verify the accuracy of calculations, data ingestion, and feature behavior against reference data.

| Script | Purpose |
| :--- | :--- |
| `generate_verification_csv.py` | Generates CSV reports (e.g., `Verification_NY1.csv`) comparing system output against reference data for hit rates and session stats. |
| `compare_reference_csv.py` | Compares two CSV files (e.g., generated vs reference) row-by-row to highlight discrepancies. |
| `compare_reference.py` | Checks computed level values against `ReferenceDailyLevels.json` to ensure accuracy. |
| `analyze_levels.py` | Analyzes hit rates and statistical properties of levels over time. |
| `verify_ny_session_hits.py` | Specifically validates hit logic for the NY1 Session (08:00 - 12:00) including strict intersection rules. |
| `export_level_stats.py` | Exports calculated level statistics to JSON/CSV for external analysis. |

## debug/

Scripts in this folder are ad-hoc tools created to investigate specific bugs or test isolated components.

| Script | Purpose |
| :--- | :--- |
| `debug_frontend_logic.py` | Simulates the frontend `daily-levels.tsx` logic in Python to verify hit counting algorithms. |
| `debug_api.py` / `debug_api_response.py` | Tests API endpoints and prints raw JSON responses for inspection. |
| `debug_filters.py` | Tests the filtering logic (e.g., Days since High/Low, Session Status) in isolation. |
| `check_data.py` / `check_parquet_date.py` | Quick checks for data file integrity, timestamps, and missing values. |
| `test_*.py` | Various unit/integration tests for API performance, timezone handling, etc. |

## Usage

Most scripts can be run directly from the root directory:

```bash
python scripts/validation/generate_verification_csv.py
python scripts/debug/debug_api.py
```

Ensure your `PYTHONPATH` includes the root directory if imports fail:

```bash
$env:PYTHONPATH="C:\Users\vinay\tvDownloadOHLC"
python scripts/validation/verify_ny_session_hits.py
```
