"""
Edgeful Platform Shared Infrastructure Layer (Phase 1)

Provides foundational data loading, context computation, and filtering utilities
for all modules in the Market Analytics Platform.

Modules:
  - data_loader: Unified parquet + live data loading with caching
  - session_tagger: Trading date and session classification
  - context: DailyContext computation and cache
  - trade_simulator: Generic strategy entry/exit and MFE/MAE simulation
  - filters: Universal filter dimensions and subreport logic
"""
