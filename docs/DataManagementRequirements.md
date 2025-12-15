# Data Management Module Requirements

## 1. Overview
The Data Management Module is a centralized interface designed to maintain the integrity, currency, and coverage of the trading data used by the system (Charts, Backtests, Profiler). It aims to replace ad-hoc scripts with a unified, safe, and transparent workflow.

## 2. Key Objectives
1.  **Centralization**: All data operations (import, update, verify) must be accessible from a single dashboard.
2.  **Visibility**: Users must clearly see the state of their data (Date ranges, missing gaps, last updated).
3.  **Safety**: **Zero Data Loss**. Existing data must never be corrupted. Backups must be automatic.
4.  **Automation**: Simple "One-Click" updates for disparate sources (Yahoo Finance, TradingView exports).

## 3. Functional Requirements

### 3.1. Data Status Dashboard
- **File Inventory**:
    - **Core Data**: Parquet files (`ES1_1m.parquet`, `NQ1_5m.parquet`, etc.).
    - **Derived Assets**: Profiler and Backtest JSONs (`*_profiler.json`, `*_level_stats.json`, `*_hod_lod.json`).
- **Metadata Display**:
    - Start Date / End Date.
    - Total Rows / Size.
    - Last Modified Timestamp (Critical for checking if Derived Assets are stale vs Core Data).
- **Health Check**: Identify gaps or stale data (e.g., "Profiler data is older than Parquet data").

### 3.2. Data Updating (Intraday)
- **Source**: Yahoo Finance (`yfinance`).
- **Scope**: Recent history (Last 7 days at 1m resolution).
- **Mechanism**:
    - Fetch recent data.
    - Load existing master Parquet.
    - Merge new data (deduplicate).
    - **Backup** existing file.
    - Write new file atomically.

### 3.3. Data Import (Historical)
- **Source**: User's `Downloads` folder or specific upload.
- **Format**: CSV exports (TradingView, NinjaTrader, etc.).
- **Workflow**:
    - Select source file.
    - Specify Target Ticker/Timeframe (or auto-detect).
    - Validate CSV schema.
    - Merge into Master.

## 4. Safety & Integrity Strategy

### 4.1. Backup Protocol
> **CRITICAL**: No write operation shall proceed without a verifiable backup.

- **Pre-Write Backup**: Before modifying `X.parquet`, copy it to `X.parquet.bak` (or `backups/X_YYYYMMDD.parquet`).
- **Atomic Writes**: Write new data to `X.parquet.tmp`, verify success, then rename to `X.parquet`.

### 4.2. Testing Strategy
A robust testing suite will be implemented before features go live:
1.  **Dry-Run Mode**: Scripts will have a flag to simulate operations and print what *would* happen (rows added, file size change) without writing to disk.
2.  **Integrity Checks**:
    - **Schema Validation**: Ensure columns match exactly.
    - **Date Monotonicity**: Ensure timestamps are strictly increasing.
    - **Duplicate Check**: Verify no duplicate timestamps exist after merge.

## 5. Implementation Roadmap
1.  **Documentation & UI Skeleton**: visualize the dashboard without connecting dangerous logic.
2.  **Read-Only Status**: Implement the backend to *read* and *report* status (safe).
3.  **Backup System**: Implement and test the backup/restore utility.
4.  **Update Logic**: Implement `yfinance` updater with strict backup protocols.
5.  **Import Logic**: Implement CSV parser and merger.
