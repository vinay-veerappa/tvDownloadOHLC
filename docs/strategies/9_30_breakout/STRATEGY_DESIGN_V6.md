# ORB Strategy V6 (NinjaScript) - Design & Implementation Guide

## 1. Architectural Overview: Dual-Loop System
The strategy employs a sophisticated **Dual-Loop Architecture** to achieve high precision (Seconds) for range definition while ensuring robust execution (Minute/Timeframe) for entries.

### Loop 1: Range Capture (1-Second Series)
*   **Source**: `BarsInProgress == 1` (1-Second Data Series)
*   **Purpose**: Tracks High/Low of the Opening Range (e.g., 9:30:00 to 9:31:00 EST) with granular precision.
*   **Benefit**: Ensures the ORB High/Low is identical regardless of the chart timestamp (5-minute vs 1-minute chart).

### Loop 2: Execution Engine (Primary Series)
*   **Source**: `BarsInProgress == 0` (Primary Chart Timeframe)
*   **Trigger**: Runs on **Bar Close** (`Calculate = OnBarClose`).
*   **Purpose**: Validates breakouts and executes entries.
*   **Benefit**: Eliminates "Early Entry" or "Wick entry" issues. The strategy strictly waits for the Primary Candle to close before confirming a signal.

---

## 2. Entry Logic Flow

To prevent conflicting signals, the Logic is strictly prioritized:

### Priority 1: Immediate Breakout (`BreakoutClose`)
**IF** `EntryMode == BreakoutClose`:
1.  Check `CrossAbove(Close, rHigh)` on Primary Candle Close.
2.  **IF True**:
    *   **ENTER IMMEDIATELY** (Market Order).
    *   Set `breakoutBarPrimary` (for Color).
    *   **STOP** (Do not check Pullback Logic).

### Priority 2: Pullback Arming (`Pullback/Retest`)
**IF** `EntryMode != BreakoutClose` (i.e., Retest/Shallow/Deep):
1.  Check **Breakout Condition** (Breakout Candle must Close outside Range).
2.  **IF True**:
    *   **ARM** the setup (`longPending = true`).
    *   Wait for subsequent bars.
3.  **ON FUTURE BARS**:
    *   **Entry**: If Price Touches Level AND Closes Validly -> ENTER.
    *   **Timeout**: If `PBTimeoutBars` reached -> Fallback Entry (Market).
    *   **Cancel**: If Price reverses (Crosses Logic Line) -> CANCEL.

---

## 3. Debug Suite (Diagnostic Output)

The strategy includes a robust debug suite to diagnose "No Trade" scenarios via the Output Window.

### State Logs
*   `BLOCKED [Time]: Filtered=... Closed=... Won=...`
    *   Explains *why* the strategy is sitting out (e.g., Daily Profit Target hit, Filter active).
*   `ACTIVE [Time]: Close=... rHigh=... rLow=...`
    *   Confirm strategy is watching price levels.

### Signal Logs
*   `BREAKOUT SIGNAL [Time]: Long=... Short=...`
    *   Fires immediately when the logic detects a crossing candle.

### Entry Logs
*   `ENTRY: Breakout Buy @ [Price]` -> Confirm Order Submission.
*   `PB ENTRY: Long Confirmed` -> Touch Entry.
*   `PB CANCEL: Deep PB` -> Cancelled due to invalid price action.

---

## 4. Key Variables & State

| Variable | Scope | Purpose |
|----------|-------|---------|
| `rHigh / rLow` | Global | The High/Low of the Opening Range (defined in BiP 1). |
| `rDefined` | Global | True if time window has passed and range is set. |
| `breakoutBarPrimary` | Visualization | Valid candle index of the *Primary* breakout bar (for Cyan coloring). |
| `longPending` | Logic | True if we are waiting for a Pullback entry. |

---

## 5. Visuals Sync

The strategy and indicator share an identical visual language to ensure "What You See Is What You Get".

### Geometry
*   **ORB Range Box**: Transparent shaded region spanning from 9:30 AM to End of Session (16:00).
    *   **Blue (20% Opacity)**: Standard Range.
    *   **Orange (20% Opacity)**: "Sweet Spot" (VVIX 98-115).
    *   **Red (20% Opacity)**: "Too Big" (Range > MaxRangePct).
*   **Range Lines**:
    *   **High (Blue)** / **Low (Red)**: Solid 2px lines.
    *   **Mid (Gold)**: Dashed 1px line.
    *   **Buffer Lines (0.10%)**: Gray Dot-Dashed lines extending 0.10% beyond High/Low.

### Candles
*   **Yellow Bar**: The defined ORB Candle (9:30 or 9:31 timestamp).
*   **Cyan Bar**: The Breakout Trigger Candle (Primary).

### Signals
*   **Triangles**:
    *   **Green/Red**: Confirmed Entry (Breakout or Pullback).
    *   **Dim Gray**: "Armed" state (waiting for Pullback).
*   **Text**:
    *   `PB BUY` / `PB SELL`: Confirmed Pullback Entry.
    *   `⚡`: Timeout "Fallback" Entry.
*   **Risk Lines**:
    *   **Dashed Red**: Active Stop Loss level (while in trade).
    *   **Dashed Green**: Active Take Profit level (while in trade).
