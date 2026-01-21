---
name: Data Pipeline Doctor
description: Diagnoses data gaps, timestamp inconsistencies, and integrity issues in Parquet and JSON files.
---

# Data Pipeline Doctor

## Purpose
Ensures the reliability of the "Live Trading System". Detects silence (gaps) and noise (corruption) in the data feed.

## Workflow

### 1. Gap Analysis
- **Input**: Parquet file (Historical) or JSON file (Live).
- **Logic**:
    - Iterate through timestamps.
    - Check delta: `current_time - prev_time`.
    - If `delta > expected_interval` (e.g., 60s for 1m bars):
        - Flag as **GAP**.
        - Ignore if outside RTH (Regular Trading Hours) unless it's a 24/5 ticker.
- **Action**: Report gap start/end and duration.

### 2. Integrity Check
- **Monotonicity**: Ensure `T(n) > T(n-1)`.
- **Structure**: Ensure all fields (`open`, `high`, `low`, `close`, `volume`) are present and numeric.
- **Zero Values**: Flag candles with `price=0` or `volume=0` (if suspicious).

### 3. Fix Recommendation
- Suggest using `scripts/maintenance/force_gap_fill.py` if a specific range is missing.
- Suggest deleting corrupted rows if data is invalid.
