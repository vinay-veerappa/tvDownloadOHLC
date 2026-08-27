# Data Documentation Index

> **⚠️ CRITICAL: Read Before Making Data Changes**
>
> This directory (`docs/data/`) contains the authoritative documentation for the platform's data layer.
> **All data operations must adhere to the standards defined in the Core Documents.**

---

## 📚 Core Documents (`core/`)

Fundamental architecture and strategy decisions.

- **[STRATEGY.md](core/STRATEGY.md)**: High-level storage strategy (Parquet + SQLite) and Timezone standards (UTC storage, NY display).
- **[SCHEMA.md](core/SCHEMA.md)**: Database schema for User and Derived Market data (Prisma/SQLite).
- **[LIVE_ARCHITECTURE.md](core/LIVE_ARCHITECTURE.md)**: Architecture for real-time data streaming (Hot/Cold storage).
- **[OPTIONS.md](core/OPTIONS.md)**: Documentation for the Dolt-based Options database.
- **[DERIVED.md](core/DERIVED.md)**: detailed catalog of all precomputed JSON/Parquet files (Profiler, HOD/LOD, etc.).

---

## 🛠️ Data Pipeline (`pipeline/`)

Standard Operating Procedures (SOPs) and technical details for data ingestion.

- **[OVERVIEW.md](pipeline/OVERVIEW.md)**: **Start Here**. The Master Pipeline document. Describes the end-to-end flow, script reference, and key processes.
- **[SOURCES.md](pipeline/SOURCES.md)**: Detailed specifications for supported data sources (TradingView, NinjaTrader, BacktestMarket) and their formats.
- **[VOLATILITY_INDICES.md](pipeline/VOLATILITY_INDICES.md)**: CBOE volatility index (VIX family) data sources — Cboe CDN flat CSVs, source matrix, puller scripts.
- **[INSTRUCTIONS.md](pipeline/INSTRUCTIONS.md)**: Specific processing instructions for edge cases.
- **[INTEGRITY.md](pipeline/INTEGRITY.md)**: Guidelines for maintaining data integrity.

---

## 📊 Reports (`reports/`)

Automated reports on data quality and coverage.

- **[COVERAGE.md](reports/COVERAGE.md)**: Current inventory of available data for all tickers/timeframes.
- **[ANOMALIES.md](reports/ANOMALIES.md)**: Log of known price anomalies and data gaps.

---

## 📦 Legacy (`legacy/`)

- **[DATA_INVENTORY_ARCHIVED.md](legacy/DATA_INVENTORY_ARCHIVED.md)**: Archived inventory snapshot. Use `reports/COVERAGE.md` for current data.

---

## Quick Reference: Timezone Rules

| Layer | Format | Example |
|-------|--------|---------|
| **Storage (Parquet)** | Naive UTC | `2025-12-25 14:30:00` (no TZ info) |
| **Derived (JSON)** | Hybrid | `hod_time: "09:30"` + `hod_ts: 1735125000` |
| **Display (App)** | America/New_York | `09:30 AM EST` |
