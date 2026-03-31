# 📚 Documentation Index

**Version:** 1.1.0 (Performance Optimized)
**Last Updated:** March 31, 2026

---

## ⚡ Performance Framework (ADR-008)
- **[Vectorized Engine](architecture/ADR.md#adr-008-vectorized-backtesting)**: O(1) broadcasted matrix search for SL/TP (10-20x speedup).
- **[Derived Feature Store](data/core/DERIVED.md#212-stationary-feature-store-adr-008)**: "Calculate Once, Persist Everywhere" Parquet caching logic.
- **[Parallel Optimization](research/OPTIMIZATION_GUIDE.md)**: Multi-core Optuna with Median Pruning.

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
- **[Platform Standards](file:///C:/Users/vinay/.gemini/antigravity/brain/6e495637-f9f3-4976-b053-eff0060d9d9a/platform_standards.md)**: Rules for code and documentation placement.
- **[Journal Requirements](JournalRequirements/trading_journal_requirements.md)**: Trading Journal enhancements.

## 🤖 AI-Native Integration (MCP)
- **[Data Bridge Server](file:///c:/Users/vinay/tvDownloadOHLC/mcp/data_server.py)**: The central tool hub for AI assistants.
- **[Structural Truth](mcp_brainstorming/structural_truth.md)**: The repo-wide knowledge graph (36k nodes).
- **[Second Brain](file:///c:/Users/vinay/tvDownloadOHLC/mcp/memory.db)**: Persistent semantic memory for strategies and ADRs.
- **[Trading Second Brain](SecondBrain_Trading.md)**: Unified rules and statistics for ALN, NQStats (RTH/6AM), and ICT concepts.


---

## 📊 Data Pipeline

Main documentation for data acquisition, processing, and storage.

- **[Data Pipeline Guide](data/DATA_PIPELINE.md)**: Master document - source locations, date ranges, quality issues, scheduled tasks.
- **[Data Sources](data/DATA_SOURCES.md)**: Format specs for TradingView, BacktestMarket, NinjaTrader.
- **[Derived Data](data/DERIVED_DATA.md)**: Precomputed files (profiler, HOD/LOD, VWAP) + Prisma database schema.
- **[Options Database](data/OPTIONS_DATABASE.md)**: Dolt DB tables, SQL queries, ER diagram.
- **[Dealer Levels Pipeline](indicators/Options/README.md)**: Schwab options GEX pipeline for SPX/NDX translated to ES/NQ.
- **[Dealer Levels Requirements](indicators/Options/REQUIREMENTS.md)**: Functional + non-functional requirements for advanced level generation.
- **[Dealer Levels Technical Design](indicators/Options/DESIGN.md)**: Module architecture, fallback flow, and output schema details.
- **[Data Coverage Report](data/DATA_COVERAGE_REPORT.md)**: Summary of available data ranges.
- **[Data Gaps Report](reports/DATA_GAPS_REPORT.md)**: Analysis of missing chunks in history.
- **[Data Anomaly Report](data/DATA_ANOMALY_REPORT.md)**: Price anomalies and verification.

---

## 📈 Trading Strategies

Strategy documentation organized by strategy type.

### Standards
- **[Backtest Standards](strategies/BACKTEST_STANDARDS.md)**: How to document and validate strategies.

### 9:30 Opening Range Breakout (`strategies/9_30_breakout/`)
- **[9:30 NQ Strategy](strategies/9_30_breakout/9_30_NQ_STRATEGY.md)**: Original opening range breakout for NQ.
- **[9:30 NQ V2 Strategy](strategies/9_30_breakout/9_30_NQ_V2_STRATEGY.md)**: Enhanced version with filters.
- **[NQ 9:30 Backtest](strategies/9_30_breakout/nq_930_breakout.md)**: Backtest results and analysis.

### Initial Balance Break (`strategies/initial_balance_break/`)
- **[IB Break Strategies](strategies/initial_balance_break/)**: IB break analysis (16 docs).

### Expected Moves (`strategies/expected_moves/`)

Research on expected move calculations and trading applications.

- **[Expected Moves README](strategies/expected_moves/README.md)**: Overview of EM methodology.
- **[Data Dictionary](strategies/expected_moves/DATA_DICTIONARY.md)**: EM data fields and calculations.
- **[Methodology Comparison](strategies/expected_moves/METHODOLOGY_COMPARISON.md)**: Straddle vs IV approaches.
- **[ES Comprehensive Analysis](strategies/expected_moves/ES_COMPREHENSIVE_ANALYSIS.md)**: ES-specific findings.
- **[Intraday Trading Playbook](strategies/expected_moves/INTRADAY_TRADING_PLAYBOOK.md)**: EM-based trading strategies.
- **[Overnight Analysis](strategies/expected_moves/OVERNIGHT_ANALYSIS.md)**: Overnight session statistics.

---

## 📊 Profiler Feature

Documentation for the session profiler feature.

- **[Daily Profiler Requirements](profiler/daily_profiler_requirements.md)**: Feature specifications.
- **[Profiler Data Verification](profiler/profiler_data_verification.md)**: Data quality checks.
- **[Profiler Summary Stats](profiler/profiler_summary_stats.md)**: Statistical outputs.
- **[Profiler Summary Stats](profiler/profiler_summary_stats.md)**: Statistical outputs.

---

## 📂 Other Sections

| Folder | Contents |
|:---|:---|
| `features/` | Feature-specific documentation |
| `reference_data/` | Reference data files |
| `research/` | Research notes and experiments |
| `release_notes/` | Version release notes |
| `archive/` | Deprecated plans and legacy docs |
| `legacy/` | Legacy documentation |
