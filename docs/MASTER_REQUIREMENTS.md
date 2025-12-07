# Master Requirements Log

This document consolidates all pending requirements for the Trading Platform, superseding previous roadmap documents.

## 1. Plugin System (Chart Extensibility)
*Source: `docs/PLUGIN_SYSTEM.md`*

The plugin system allows dynamic loading of visual tools and indicators.
- [ ] **Indicators Modal**: Replace the simple dropdown with a searchable modal dialog to browse/add plugins.
- [ ] **Active Plugin Management (Legend)**:
    - [ ] Show list of active indicators/plugins on the chart.
    - [ ] Allow toggling visibility (Eye icon).
    - [ ] Allow removal (X icon).
    - [ ] Allow configuration (Settings icon).
- [ ] **Drawing Tools**:
    - [ ] Select individual drawings.
    - [ ] Delete specific drawings (vs "Clear All").
    - [ ] Edit drawing properties (color, line width) after placement.
- [ ] **Specific Plugin Fixes**:
    - [ ] `volume-profile.js`: Fix data initialization (requires `vol` data).
    - [ ] `session-highlighting.js`: Add UI for configuring session times.

## 2. Indicators (Calculation & Rendering)
*Source: `docs/INDICATORS.md`*

Client-side calculation and rendering of technical indicators.
- [ ] **Oscillators (Separate Panes)**:
    - [ ] Implement multi-pane chart layout (Price Pane vs Indicator Panes).
    - [ ] Support RSI, MACD, Stochastics in separate panes.
- [ ] **Customization**:
    - [ ] Color pickers for indicator lines.
    - [ ] Line style (solid, dashed) and width.
    - [ ] Input parameters (e.g., SMA period, StDev).
- [ ] **Persistence**:
    - [ ] Save active indicators and their settings to local storage/DB.
    - [ ] Restore indicators on page reload.
- [ ] **Templates**:
    - [ ] Save "Indicator Sets" (e.g., "Trend Setup", "Oscillator Setup").

## 3. Trading Journal & Simulation
*Source: `docs/trading_journal_requirements.md`*

A comprehensive system to simulate trading and log results.

### A. Trade Execution (Simulated)
- [ ] **Advanced Order Types**:
    - [ ] Stop Loss & Take Profit (Bracket Orders).
    - [ ] Limit Orders (placing on chart via context menu).
- [ ] **Visual Management**:
    - [ ] Draggable Order Lines (Entry, SL, TP) modification.
    - [ ] "Close Position" button on the chart line.
    - [ ] "Reverse Position" button.

### B. Journal Context
- [x] **Context Bar**:
    - [x] Account Selector (Implemented in Context/UI).
    - [x] Strategy Selector (Implemented in Context/UI).
    - [ ] Session Tags (e.g., "News Day", "Choppy").
- [ ] **Trade Entry Details**:
    - [ ] Pop-up modal on entry (optional) to add notes/tags.
    - [ ] Capture user emotion/mental state.

### C. Analysis & History
- [x] **Journal Tab**:
    - [x] List view of all historical trades (`journal-panel.tsx`).
    - [ ] Detail view (Drill-down) for a specific trade.
- [ ] **Automated Screenshots**:
    - [ ] Capture chart state on Entry.
    - [ ] Capture chart state on Exit.
    - [ ] Store and display in Trade Detail view.
- [ ] **Performance Dashboard**:
    - [ ] P&L Curve.
    - [ ] Win Rate, Profit Factor, Max Drawdown stats.

## 4. Platform Architecture
- [ ] **Multi-Chart Layout**: Support 2x2 or split-screen chart views.
- [ ] **Data Management**:
    - [ ] Session High/Low highlighting (server-side generation).
    - [ ] Manual "Reload Data" button.
- [x] **Database Setup**: Prisma Schema (Trades, Strategies, Accounts) is complete.
- [x] **State Management**: React Context (`trading-context.tsx`) implements store logic.
