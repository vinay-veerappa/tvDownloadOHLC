# Data Storage Strategy

## Overview
This document outlines the data storage strategy for the Trading Platform. We have chosen a **Hybrid Approach** to balance performance, simplicity, and scalability.

## Hybrid Architecture

### 1. Market Data (OHLCV)
*   **Storage:** Parquet Files (`.parquet`)
*   **Location:** `data/` directory
*   **Reasoning:**
    *   **Performance:** Parquet is highly efficient for reading large historical datasets (columnar storage).
    *   **Simplicity:** No need to manage a dedicated time-series database server (like TimescaleDB) initially.
    *   **Cost:** Free and file-based.
*   **Access:** Currently via Python scripts (`read_parquet.py`). Future optimization may involve `DuckDB` or native Node.js parquet readers.

### 2. User Data (Transactional)
    *   **User Data:** Trades, Journal, Settings, Tags.
    *   **Cached Market Data:** Economic Events, News, Expected Moves, Historical Volatility.
*   **ORM:** Prisma
*   **Reasoning:**
    *   **Relational:** Complex relationships between trades, tags, and events.
    *   **Caching:** SQLite serves as a fast, queryable cache for low-frequency market data (daily EM, calendar), avoiding repetitive API calls.
    *   **Type Safety:** Prisma provides end-to-end type safety for the web app.

### 3. Live Data Architecture (Hot/Cold Storage)
To support real-time charting without file locking issues:

*   **Hot Layer (Latency < 200ms):**
    *   **File:** `live_chart.json`
    *   **Format:** JSON (Array of recent candles + current tick)
    *   **Access:** Polled by frontend every 200ms.
    *   **Persistence:** Ephemeral (overwritten on restart).

*   **Cold Layer (Historical):**
    *   **File:** `[TICKER]_1m.parquet`
    *   **Format:** Parquet (Columnar)
    *   **Access:** Read on initial load / scroll back.
    *   **Persistence:** Permanent. `stream_chart.py` appends confirmed 1m bars here.

## Future Considerations
*   **DuckDB Integration:** Replace Python scripts with DuckDB for faster in-process querying of Parquet files.
*   **TimescaleDB Migration:** If the dataset grows too large for file-based management, we may migrate OHLC data to TimescaleDB.

## 3. Timezone Standards
*   **Storage (Source of Truth):** UTC (Naive). All Parquet files must be timezone-naive, implicitly representing UTC.
*   **Application (View Layer):** America/New_York (EST/EDT). All data is converted to NY time upon loading for analysis/display.
*   **Rationale:** UTC storage ensures mathematical continuity and prevents ambiguity (DST shifts). NY display ensures alignment with market hours (09:30 Open).

## Decision Log
*   **2025-12-04:** Decided to stick with Parquet for OHLC data to expedite Backtesting implementation. Database will be used for user data only.
