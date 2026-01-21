# Backtest System & NQ Strategy Requirements

## 1. Overview
This system provides a high-performance backtesting engine for the NQ 9:30 Reversal Strategy, tightly integrated with a Visual Charting interface and a Trade Journal for performance tracking.

## 2. NQ 9:30 Reversal Strategy
**Objective**: Capture mean reversion or trend continuation moves at the 9:30 AM NY market open.

### Parameters
- **Timeframe**: 1 minute (`1m`)
- **Entry Window**: 09:30 - 09:40 NY Time (Strict)
- **Filters**:
    - **Gap**: Strategy checks gap size (Open vs Prev Close).
    - **Reversal**: Fade logic or Follow logic (configurable).
- **Exit Conditions**:
    - **Hard Exit**: 15:55 NY Time (End of Day).
    - **Stop Loss**: 40 points (configurable).
    - **Take Profit**: 
        - **Mode**: 'R' (R-Multiple) or 'BPS' (Basis Points).
        - **Logic**: Dynamic calculation based on entry risk.

### Scalability Updates
- **Data Loading**: "Unlimited" data loading capability (2008-Present).
- **Optimization**: Parameter sweep script (`scripts/optimize-strategy.ts`) identified **3R Target / End of Day Exit** as the optimal configuration.

## 3. Backtest UI & Workflow
### Configuration Panel
- **Ticker**: Input (e.g., `NQ1!`).
- **Strategy Selector**: `SMA_CROSSOVER` or `NQ_1MIN`.
- **Advanced Params**:
    - `TP Mode`: Toggle between `R-Multiple` and `Basis Points`.
    - `Max Trades`: Limit execution count (0 = Unlimited).

### Interactive Results
- **Metrics**: Real-time display of Total Trades, Win Rate, Profit Factor, Total PnL.
- **Trade List**:
    - Chronological list of all executed trades.
    - **Click-to-Jump**: Clicking a trade instantly centers the Chart on that trade's entry time.

### Visual Validation (Chart)
- **Markers**: Buy/Sell arrows overlaid on the chart.
- **Navigation Controls**:
    - `[<]` Previous Trade
    - `[>]` Next Trade
    - Allows rapid visual verification of strategy execution.
- **Full Screen Chart**:
    - **"Open in Chart"**: Dedicated button to launch the `/chart` full-screen interface.
    - **Trade Transfer**: Automatically transfers backtest markers to the new view.

## 4. Journal Integration
**Goal**: bridge the gap between "Simulation" and "Journaling".

### Features
1.  **Metric Storage**:
    - `metadata` field added to Database schema to store arbitrary JSON metrics (e.g., Correlation data, VIX, Gap Size).
2.  **Export Action**:
    - **"Export to Journal"** button in UI.
    - Function:
        1. Creates a dedicated Journal Account (e.g., "Backtest Run 1").
        2. Bulk imports all backtest trades into this account.
        3. Allows using the full Journal Suite (Calendar, Monthly Reports) to analyze backtest performance.

## 5. Technical Implementation
- **Frontend**: Next.js 14, Shadcn UI.
- **Engine**: TypeScript-based `StrategyRunner` (Client/Server hybrid).
- **Database**: SQLite with Prisma ORM.
- **Charts**: Lightweight Charts (TradingView) with React wrapper.
