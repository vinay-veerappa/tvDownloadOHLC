# Application Roadmap: Backtesting & Journaling Platform

## 🎯 Vision
Transform the current "Chart Viewer" into a professional-grade "Backtesting & Journaling Platform" (similar to TradingView's Replay Mode + Notion-style Journaling).

## 🏗 Architectural Pillars

### 1. The Replay Engine (Time Travel) ⏪
**Current:** `data_loader.js` loads all data at once.
**Requirement:** Ability to "hide" future data and reveal it bar-by-bar.
**Architecture:**
*   **`ReplayManager` Class:**
    *   Holds the *full* dataset in memory (hidden).
    *   Manages a `cursor` (current replay time).
    *   On "Next Bar", pushes data from *Hidden* -> *Visible* series.
    *   **Tick Simulation:** Optional advanced feature to simulate intra-bar movement (OHLC -> 4 ticks) for realistic order fills.

### 2. Order Management System (OMS) 🛒
**Current:** No concept of trades or positions.
**Requirement:** Place Buy/Sell orders, Stop Loss, Take Profit, and track PnL.
**Architecture:**
*   **`OrderEngine` Class:**
    *   Tracks `AccountBalance`, `OpenPositions`, `WorkingOrders`.
    *   **Matching Engine:** On every new "tick" or "bar" (from Replay Engine), check if Price hits SL/TP or Limit Orders.
    *   **Events:** Dispatches `OrderFilled`, `StopHit` events.
*   **Visuals:** `OrderLinePrimitive` (draggable lines for Entry/SL/TP) on the chart.

### 3. Journaling & Persistence 📔
**Current:** Read-only Parquet files.
**Requirement:** Save trades, notes, and screenshots.
**Architecture:**
*   **Backend (Python/FastAPI):**
    *   Need a database (SQLite is perfect for local app) to store:
        *   `Journals` (Text, Tags, Date)
        *   `Trades` (Entry, Exit, PnL, ScreenshotPath)
        *   `Drawings` (Serialized JSON)
*   **Snapshot Service:**
    *   Frontend: `chart.takeScreenshot()` -> Blob.
    *   Backend: Save Blob to `user_data/snapshots/`.

### 4. UI Framework Scalability 🧩
**Current:** Vanilla JS + HTML.
**Risk:** As UI complexity grows (Order Forms, Journal Lists, Replay Controls), vanilla DOM manipulation becomes "spaghetti code".
**Recommendation:**
*   **Component-Based Architecture:** Even with Vanilla JS, we should strictly modularize UI components (e.g., `ReplayControls.js`, `TradePanel.js`).
*   **State Store:** A global `Store` (like Redux, but simpler) to manage app state (`isReplayActive`, `currentTicker`, `accountBalance`). Components subscribe to state changes.

---

## 🗺️ Implementation Stages

### Stage 1: The Foundation (Current Focus)
*   **Advanced Drawing Tools:** (Text, Templates) - *Prerequisite for annotating journals.*
*   **Architecture Refactor:** (Schema UI, Serialization) - *Prerequisite for saving work.*

### Stage 2: The Replay Engine
*   Implement `ReplayManager`.
*   UI: Play/Pause, Speed, Step Forward buttons.
*   Logic: Slicing data arrays.

### Stage 3: Order Entry (Paper Trading)
*   Implement `OrderEngine`.
*   UI: Buy/Sell buttons, Position lines on chart.
*   Logic: Simple fill simulation (High/Low checks).

### Stage 4: Journaling
*   Backend: SQLite setup.
*   UI: "Save Trade" modal, Screenshot capture.
*   Dashboard: List of past trades with stats.

## 💡 Key Decision Point
**Do we stick with Vanilla JS?**
For a complex "Trading Terminal" UI, a framework like **React** or **Vue** is usually recommended. However, since we have a working Vanilla base:
*   **Option A (Stick to Vanilla):** Use Web Components or strict Class-based UI modules. Good for performance, harder to maintain complex UI.
*   **Option B (Migrate to Framework):** High effort now, easier maintenance later.
*   **Recommendation:** Stick to **Vanilla JS** for now but be *very strict* about modularity (Stage 1 & 2). If UI becomes unmanageable in Stage 3, consider a framework for the *UI overlay* (keeping the Chart logic separate).
