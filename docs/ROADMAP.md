# Project Roadmap

**Version:** 1.0.0 (AI-Native Command Center)
**Last Updated:** March 25, 2026

This document consolidates all planned features, requirements, and known technical debt for the **tvDownloadOHLC** platform.

---

## 🚀 1. Drawing Tools (Advanced)

**Objective**: Reach parity with professional platforms (TradingView) regarding shape types, customization, and interaction.

### Core Architecture
- [ ] **Text Primitives**: Implement a reusable `TextLabel` class for all drawings.
- [ ] **Template Manager**: Save/Load styling presets (e.g., "Bullish Order Block" styling for Rectangles).
- [ ] **Serialization**: Standardize `toJSON()`/`fromJSON()` for all tools to support saving to DB.
- [ ] **Properties Modal**: Upgrade from simple inputs to a tabbed modal (Style, Text, Coordinates, Visibility).

### Tool-Specific Requirements
- [ ] **Rectangle**:
    - [ ] Midline (50%) and Quarter lines (25%/75%) toggles.
    - [ ] Extension (Extend Left/Right).
    - [ ] Integrated Text Labels (Center/Corner alignment).
- [ ] **Trend Line**:
    - [ ] Arrow heads (Start/End).
    - [ ] Angle & Distance stats.
- [ ] **Fibonacci Retracement**:
    - [ ] Custom levels with per-level opacity/color.
    - [ ] "Trend Line" connector toggle.
- [ ] **Toolbox**:
    - [ ] Quick Toolbar (floating near selection) for fast color/delete actions.

### Interaction
- [ ] **Draft Mode**: "Click-Click" drawing (Rubberbanding) vs "Click-Drag".
- [ ] **Magnet Mode**: Refine "Weak" vs "Strong" snapping to High/Low/Open/Close.

---

## 📈 2. Indicators & Charting

**Objective**: Comprehensive technical analysis capability.

### Management
- [ ] **Indicators Modal**: Searchable library of built-in indicators.
- [ ] **Legend**: Interactive list on chart (Show/Hide, Settings, Remove).
- [ ] **Persistence**: Save active indicator set to local storage/DB.

### Rendering
- [ ] **Oscillators**: Support multi-pane layout (stacked scales) for RSI, MACD, etc.
- [ ] **Customization**: Line width, color, and input parameters (e.g., SMA Period).

### Custom Indicators
- [x] **Hourly Profiler**: (Completed v0.4.0)
    - [x] Alternating Quarters.
    - [x] 3H Profiler Bounds.
    - [x] Theme Integration.
- [ ] **Volume Profile**: Fix existing implementation (requires valid Volume data).

---

## 💵 3. Trading Engine & Journal

**Objective**: High-fidelity simulation and performance tracking.

### Execution
- [x] **Basic Order Entry**: Buy/Sell Market.
- [x] **Position Management**: SL/TP lines on chart.
- [ ] **Limit Orders**: Place via Context Menu on chart.
- [ ] **Visual Dragging**: Drag active orders/SL/TP lines to modify price.

### Journaling
- [x] **Trade History**: Database storage of closed trades.
- [x] **Metrics**: MAE/MFE tracking.
- [ ] **Context Tags**: Tagging trades (e.g., "News", "Revenge Trading").
- [ ] **Screenshots**: Auto-capture chart on Entry/Exit.
- [ ] **Analytics**: P&L Curve, Win Rate Dashboard.

### Automated Backtesting (`/backtest`)
- [x] **Strategy Runner**: Server-side execution of logic (SMA Crossover).
- [x] **Results UI**: Metrics, Chart Markers, and Trade List.
- [ ] **Strategy Editor**: UI to define custom logic.

---

## 🏗 4. Architecture & Platform

- [x] **Frontend**: Next.js 16 + Shadcn/UI (Stable).
- [x] **Backend**: FastAPI + Polars/Parquet (Stable).
- [x] **Data Pipeline**: Selenium Downloader (Stable).
- [ ] **Multi-Chart**: Grid layout (2x2) for multi-timeframe analysis.
- [ ] **Global Timezone**: Unified timezone setting (e.g., "America/New_York") affecting all tools/scales.

---

## 🧪 5. Known Issues / Tech Debt

- [x] **Date Parsing**: Ensure consistent handling of "YYYY-MM-DD" vs Unix Timestamps across Python/JS.
- [ ] **Data Gaps**: `DATA_GAPS_REPORT.md` highlights missing chunks in historical data.
- [x] **Purge historical parquet from git history** — ✅ **done, and verified by measurement
  2026-08-13.** The 2026-08-07 cleanup only covered the then-unpushed range, leaving 50
  parquet objects (0.28 GB, two of them 96.8 MB copies of `data/NQ1_1m.parquet`) in the
  older *published* history. A later full-history rewrite cleared them.

  How it was checked, so the next person does not have to trust this line:

  ```bash
  git fetch --all --prune
  git rev-list --objects --remotes | grep -ciE '\.parquet$'   # 0
  git rev-list --objects --all     | grep -ciE '\.parquet$'   # 0  (local refs too)
  ```

  Largest blob remaining in published history is **39.2 MB** (`web/public/duckdb/duckdb-mvp.wasm`),
  then two 34 MB `results/RESEARCH/` files and a run of 14–20 MB `.pkl`/`.npz` report
  artifacts — all well under GitHub's 100 MB hard limit. Published history totals 11,959
  blobs / 2.14 GB uncompressed.

  ⚠️ **Two things that look like failure and are not:** the GitHub API still reports
  `size: 423 MB`, because that counts objects made unreachable by the rewrite until
  GitHub's own GC runs; and this clone's `.git` is still 1.5 GB (`size-pack` 1021 MiB) for
  the same reason locally. `git gc --prune=now` reclaims the local half — but it also
  destroys the only remaining copy of the pre-rewrite objects, so leave it a while. There
  is also a stray `.git/objects/pack/tmp_pack_*` (0 bytes) that makes git print
  `warning: garbage found`; harmless, and `git gc` removes it.

  Still true, and unrelated to the parquet: **both rewrites orphaned commit SHAs that the
  RiskGuard docs cite.** That is recorded in the handover's §0.0 rather than here.
- **Pre-commit hook — install per clone**: `git config core.hooksPath .githooks`. Not a task
  that can ever be ticked, because `core.hooksPath` is *local config*: a fresh clone has the
  hook disabled and nothing says so. Installed as of 2026-08-13 in this repo and in both NT8
  addon repos, which carry their own copy blocking build output rather than parquet.

## ✅ Completed (Recent)
- [x] **Scheduled Expected Move**: Database persistence with Read-First strategy + 09:30/16:15 Cron Job.
- [x] **Watchlist Management**: Multi-list support (Tech, Indexes, Futures) with Import/Seed.
- [x] **Dashboard**: "Context" page promoted to Home with Quick Links.
- [x] **Sidebar**: Reorganized into "Main" and "Tools".
- [x] **Futures Data**: Fixed `/ES` and `/NQ` data fetching using Proxy sources and Schwab API.
