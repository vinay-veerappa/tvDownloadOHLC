# Data Documentation Index

> **⚠️ CRITICAL: Read Before Making Data Changes**
> 
> This document serves as the master index for all data-related documentation.
> **Always consult these documents before modifying data pipelines, merge scripts, or storage formats.**

---

## Core Documents

### 1. [DATA_STRATEGY.md](data/DATA_STRATEGY.md)
**Purpose:** High-level architecture decisions for data storage.

**Key Points:**
- Parquet for OHLC, SQLite/PostgreSQL for user data
- **Timezone Standard**: Store as UTC (Naive), Display as NY

---

### 2. [DATA_PIPELINE.md](data/DATA_PIPELINE.md)
**Purpose:** Detailed procedures for data ingestion and processing.

**Key Points:**
- **Timezone Strategy** (Section 1.1): Critical rules for UTC storage
- **Scripts Reference** (Section 3): Master list of all data scripts
- **SOP** (Section 4): Step-by-step for NinjaTrader imports

---

### 3. [ARCHITECTURE.md](architecture/ARCHITECTURE.md)
**Purpose:** System architecture including frontend data consumption.

**Key Points:**
- **Section 2.5 - Data Timezone Contract**: How frontend expects data
- **Hybrid Output**: `_time` (NY strings) + `_ts` (Unix timestamps)

---

## Quick Reference

### Timezone Rules (DO NOT VIOLATE)

| Layer | Format | Example |
|-------|--------|---------|
| **Storage (Parquet)** | Naive UTC | `2025-12-25 14:30:00` (no TZ info) |
| **Derived (JSON)** | Hybrid | `hod_time: "09:30"` + `hod_ts: 1735125000` |
| **Display (App)** | America/New_York | `09:30 AM EST` |

### Common Commands

```powershell
# Fresh Import from NinjaTrader CSV (Complete replacement - use for clean slate)
python scripts/fresh_ticker_import.py ES1 "data/NinjaTrader/24Dec2025/ES Thursday 857.csv"

# Incremental Import (Merges with existing data)
python scripts/data_processing/import_ninjatrader.py "path/to/file.csv" ES1 1m

# Regenerate ALL derived data after import (MANDATORY)
python scripts/derived/regenerate_derived.py ES1

# Check data continuity/gaps
python scripts/validation/check_data_continuity.py ES1
```

---

## Related Documents

- [DATA_ANOMALY_REPORT.md](reports/DATA_ANOMALY_REPORT.md) - **Documented anomaly dates for verification**
- [DATA_COVERAGE_REPORT.md](reports/DATA_COVERAGE_REPORT.md) - Current data availability
- [DATA_GAPS_REPORT.md](reports/DATA_GAPS_REPORT.md) - Known gaps in history
- [DATA_SOURCES.md](data/DATA_SOURCES.md) - Vendor information

---

## Changelog

| Date | Change |
|------|--------|
| 2025-12-25 | Added Timezone Strategy sections to all docs. Standardized to "Store UTC, Consume NY, Hybrid Output". |
| 2025-12-25 | Created this master index document. |
