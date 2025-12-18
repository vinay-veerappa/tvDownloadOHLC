# Project Roadmap

**Version:** 0.5.0
**Last Updated:** December 18, 2025

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

## ✅ Completed (Recent)
- [x] **Scheduled Expected Move**: Database persistence with Read-First strategy + 09:30/16:15 Cron Job.
- [x] **Watchlist Management**: Multi-list support (Tech, Indexes, Futures) with Import/Seed.
- [x] **Dashboard**: "Context" page promoted to Home with Quick Links.
- [x] **Sidebar**: Reorganized into "Main" and "Tools".
- [x] **Futures Data**: Fixed `/ES` and `/NQ` data fetching using Proxy sources and Schwab API.
