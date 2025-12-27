# 📚 Documentation Index

**Version:** 0.6.0
**Last Updated:** December 26, 2025

---

## 🏗️ Core Architecture
- **[System Architecture](architecture/ARCHITECTURE.md)**: Frontend (Next.js), Backend (FastAPI), and Database design.
- **[Developer Guide](setup/DEVELOPER_GUIDE.md)**: "Cookbook" for adding new Indicators and Drawing Tools.
- **[Indicator Standards](architecture/INDICATOR_DEVELOPMENT_STANDARDS.md)**: Performance & interaction patterns.
- **[Lessons Learned](reports/LESSONS_LEARNED.md)**: Common pitfalls (PowerShell, Git, Canvas coordinates).

## 🚀 Features & Usage
- **[User Guide](setup/USER_GUIDE.md)**: Manual for Charting, Trading Panel, Replay Mode, and Backtesting.
- **[Configuration](setup/CONFIGURATION.md)**: Setup guide for Schwab API, Secrets, and Scheduled Jobs.
- **[LLM Setup Guide](setup/LLM_SETUP.md)**: Instructions for setting up Local LLMs (Ollama).
- **[UX Guidelines](ui/UX_GUIDELINES.md)**: Design patterns for Modals, Settings, and Review.
- **[Roadmap](ROADMAP.md)**: Feature requirements and status.
- **[Journal Requirements](JournalRequirements/trading_journal_requirements.md)**: Trading Journal enhancements.

---

## 📊 Data Pipeline

Main documentation for data acquisition, processing, and storage.

- **[Data Pipeline Guide](data/DATA_PIPELINE.md)**: Master document - source locations, date ranges, quality issues, scheduled tasks.
- **[Data Sources](data/DATA_SOURCES.md)**: Format specs for TradingView, BacktestMarket, NinjaTrader.
- **[Derived Data](data/DERIVED_DATA.md)**: Precomputed files (profiler, HOD/LOD, VWAP) + Prisma database schema.
- **[Options Database](data/OPTIONS_DATABASE.md)**: Dolt DB tables, SQL queries, ER diagram.
- **[Data Coverage Report](data/DATA_COVERAGE_REPORT.md)**: Summary of available data ranges.
- **[Data Gaps Report](reports/DATA_GAPS_REPORT.md)**: Analysis of missing chunks in history.
- **[Data Anomaly Report](data/DATA_ANOMALY_REPORT.md)**: Price anomalies and verification.

---

## 📈 Trading Strategies

Strategy documentation and backtesting results.

- **[Backtest Standards](strategies/BACKTEST_STANDARDS.md)**: How to document and validate strategies.
- **[9:30 NQ Breakout Strategy](strategies/9_30_NQ_STRATEGY.md)**: Opening range breakout for NQ.
- **[9:30 NQ V2 Strategy](strategies/9_30_NQ_V2_STRATEGY.md)**: Enhanced version with filters.
- **[Initial Balance Break Strategies](strategies/initial_balance_break/)**: IB break analysis (16 docs).

---

## 🎯 Expected Moves Analysis

Research on expected move calculations and trading applications.

- **[Expected Moves README](expected_moves/README.md)**: Overview of EM methodology.
- **[Data Dictionary](expected_moves/DATA_DICTIONARY.md)**: EM data fields and calculations.
- **[Methodology Comparison](expected_moves/METHODOLOGY_COMPARISON.md)**: Straddle vs IV approaches.
- **[ES Comprehensive Analysis](expected_moves/ES_COMPREHENSIVE_ANALYSIS.md)**: ES-specific findings.
- **[Intraday Trading Playbook](expected_moves/INTRADAY_TRADING_PLAYBOOK.md)**: EM-based trading strategies.
- **[Overnight Analysis](expected_moves/OVERNIGHT_ANALYSIS.md)**: Overnight session statistics.
- **[Intraday S/R Analysis](expected_moves/INTRADAY_SR_ANALYSIS.md)**: Support/Resistance analysis.

---

## 📊 Profiler Feature

Documentation for the session profiler feature.

- **[Daily Profiler Requirements](profiler/daily_profiler_requirements.md)**: Feature specifications.
- **[Profiler Data Verification](profiler/profiler_data_verification.md)**: Data quality checks.
- **[Profiler Summary Stats](profiler/profiler_summary_stats.md)**: Statistical outputs.

---

## 📂 Other Sections

| Folder | Contents |
|:---|:---|
| `backtest/` | Backtesting system requirements |
| `features/` | Feature-specific documentation |
| `reference_data/` | Reference data files |
| `research/` | Research notes and experiments |
| `release_notes/` | Version release notes |
| `archive/` | Deprecated plans and legacy docs |
| `legacy/` | Legacy documentation |
