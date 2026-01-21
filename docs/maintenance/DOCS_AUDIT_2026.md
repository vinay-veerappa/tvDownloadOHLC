# Documentation Audit (2026-01-21)

This report details the reorganization of the system documentation to improve discoverability and maintainability.

## 1. Directory Structure Changes

The documentation has been consolidated into this high-level structure:

| Path | Purpose | Key Files |
|------|---------|-----------|
| `docs/architecture/` | System Technical Design | `ARCHITECTURE.md`, `API_REFERENCE.md`, `LIVE_TRADING_SYSTEM.md` |
| `docs/features/` | Feature Specifications | `journal/`, `backtest/`, `profiler/`, `drawing/` |
| `docs/ui/charting/` | Chart Engine & Components | `DRAWING_TOOLS_ARCHITECTURE.md`, `COMPONENT_LIBRARY.md` |
| `docs/data/` | Data Pipeline | `README.md` (Index), `DATA_STRATEGY.md` |
| `docs/strategies/` | Trading Logic | `KNOWLEDGE_BASE.md`, Specific Strategies |
| `docs/archive/` | Legacy/Superseded | `IMPLEMENTATION_LOG.md`, Old Plans |

## 2. File Moves & Renames

### Archived (Stale or Legacy)
- `task.md` (Root) → `docs/archive/IMPLEMENTATION_LOG.md` (Historical log vs active task)
- `implementation_plan.md` → `docs/archive/IMPLEMENTATION_PLAN_LEGACY.md`
- `walkthrough.md` → `docs/archive/WALKTHROUGH_LEGACY.md`

### Consolidations
- `JOURNAL*.md` → `docs/features/journal/` (Grouped all Journal docs)
- `backtest_system_requirements.md` → `docs/features/backtest/REQUIREMENTS.md`
- `DATA_INDEX.md` → `docs/data/README.md` (Central entry point for Data)
- `SCRIPTS.md` → `docs/SCRIPTS_CATALOG.md` (Clearer name)

### Cleaned Up
- `DRAWING_TOOLS.md` → `docs/features/drawing/USER_GUIDE.md`
- `ProfilerFeatures.md` → `docs/features/profiler/USER_GUIDE.md`
- `PERFORMANCE.md` → `docs/architecture/SYSTEM_PERFORMANCE.md`

## 3. Recommended Maintenance

1.  **Use the `Documentation Architect` Skill**: When modifying code, update the corresponding file in `docs/features/` or `docs/architecture/`.
2.  **Keep `ROADMAP.md` Active**: Use it for high-level product goals.
3.  **Use `strategies/` for Logic**: Keep pure trading logic separate from UI implementation docs.
