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
*   **Storage:** SQLite (Development) / PostgreSQL (Production)
*   **ORM:** Prisma
*   **Entities:**
    *   **Trades:** Individual trade records (entry, exit, pnl).
    *   **Journal:** Daily journal entries, notes, tags.
    *   **Backtest Results:** Configuration and results of backtest runs.
*   **Reasoning:**
    *   **Relational:** User data is highly relational (Trades belong to Strategies, etc.).
    *   **Ecosystem:** Prisma provides excellent type safety and migration tools.

## Future Considerations
*   **DuckDB Integration:** Replace Python scripts with DuckDB for faster in-process querying of Parquet files.
*   **TimescaleDB Migration:** If the dataset grows too large for file-based management, we may migrate OHLC data to TimescaleDB.

## Decision Log
*   **2025-12-04:** Decided to stick with Parquet for OHLC data to expedite Backtesting implementation. Database will be used for user data only.
