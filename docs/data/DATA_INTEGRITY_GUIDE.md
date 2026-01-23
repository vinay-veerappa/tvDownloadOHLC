# Data Integrity & Streaming Guide

This guide explains how the system maintains data accuracy between the live streaming charts and authoritative historical data.

## 📡 Live Streaming (stream_chart.py)

The `stream_chart.py` script provides real-time data for the web charts. It uses the Schwab API to "bridge" gaps when it restarts.

### 🛡️ Corruption Prevention
To prevent corrupted data (e.g., wrong contract rollovers from the API) from entering the system, the streamer implements:

1.  **First-Occurrence Preservation**: The `deduplicate_candles` function is designed to preserve the *first* data entry for any given timestamp. Once a candle is stored in `data/live/live_storage_{symbol}.parquet` and verified as correct, it cannot be overwritten by subsequent API fetches.
2.  **Bootstrap Validation**: Every time the streamer starts, it fetches 30 days of "bootstrap" data. This data is compared against your authoritative historical Parquet files (e.g., `ES1_1m.parquet`).
3.  **Conflict Rejection**: If the API returns data that differs significantly (>1%) from the historical record, those specific candles are rejected and not merged.

## 📉 Conflict Reporting

Discrepancies between the live API and historical data are logged for investigation.

### Conflict Logs
-   **Location**: `data/live/bootstrap_conflicts_{symbol}.json`
-   **Content**: Contains timestamps, historical prices, and the conflicting prices returned by the API.

### Automated Briefing
The system sends a daily briefing to Discord summarizing these conflicts.

-   **Discord Channel**: `Data Gap reports`
-   **Script**: `scripts/maintenance/generate_conflict_report.py`
-   **Workflow**: Integrated as **Step 4** in `scripts/trader/run_daily_prep.py`.

## 🛠️ Manual Data Repair

If you encounter persistent displacement on charts:

1.  Stop the `stream_chart.py` process.
2.  Verify the historical Parquet files are correct.
3.  The streamer will automatically skip bad data on restart, but you may need to clear the `live_storage` file if corrupted data was already saved before the robust fix was implemented.
