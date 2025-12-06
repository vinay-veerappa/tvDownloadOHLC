# Chart Page UI Refinement

## Completed
- [x] Basic Navigation (Scroll, Zoom, Date Picker)
- [x] Fix: Force Auto-Scroll during Replay
- [x] Fix: Ref Delegation in ChartWrapper
- [x] Fix: Right sidebar layout "cut up" issue (Added flex-shrink-0)
- [x] **Feature**: Implement Icon-only mode for Right Sidebar (TradingView style)
- [x] **Fix**: Chart Resize/Clipping issue (Fix flex-item min-width)
        - [x] Integrate with Server Actions (`createTrade`, `closeTrade`)
        - [x] Visualizing Executions/Position on Chart
    - [x] **Phase 2.5: Journaling Controls (Top Bar)**
        - [x] Create `TradingContext` for shared state
        - [x] Move `useTradingEngine` logic to Provider
        - [x] Implement Account & Strategy Selectors in `TopToolbar`
        - [x] Display Session P&L in `TopToolbar`
        - [x] Connect `BuySellPanel` to Context
    - [x] **Phase 3: Advanced Order Management**
        - [x] Design & Build Advanced Order Panel (Limit/Stop Tabs)
        - [x] Add Limit/Stop Order Logic to Context
        - [x] Visualize Pending Orders on Chart
        - [x] Implement Bracket Orders (SL/TP)
        - [x] Chart Interaction (Drag & Drop)
    - [ ] **Phase 4: Journal Management (Backlog)**
        - [ ] Account Creation & Management UI (CRUD)
        - [ ] Full Trade History Table (Sort/Filter)
        - [ ] Trade Detail View (Screenshots, Notes)

## Bug Fixes & Refactoring (Complete)
- [x] **Data Integrity Fix**:
    - [x] Identified stale parquet files for ES1/NQ1 (ending 2024).
    - [x] Regenerated all aggregated timeframes from fresh 2025 source data.
- [x] **Chart Code Refactor**:
    - [x] Split monolithic `ChartContainer.tsx` into `useChartData`, `useChartTrading`, `useChartDrag`.
    - [x] Fixed cyclical dependency and syntax errors.
- [x] **Timeframe Synchronization Fix**:
    - [x] Implemented `getVisibleTimeRange` to preserve view center when switching timeframes.
    - [x] Fixed Replay Mode date drift by anchoring to Replay Head time.

## Backlog
- [ ] **Feature**: Advanced Fibonacci Settings (Style, Coordinates, Visibility, Levels)
    - [ ] Reference: `uploaded_image_1764994978604.png`
- [ ] Multiple chart layouts
- [ ] Drawing templates
