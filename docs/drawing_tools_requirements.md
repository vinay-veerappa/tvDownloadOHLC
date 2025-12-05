# Advanced Drawing Tools Requirements

## 🎯 Objective
Enhance the drawing tools to match professional charting platforms (like TradingView) with deep customization, text annotations, templates, and refined interaction models.

## 🛠 Common Features (All Tools)

### 1. Text Annotations (Enhanced)
Every drawing tool (TrendLine, Rectangle, etc.) should support an optional text label with rich formatting:
*   **Content:** Multi-line text entry.
*   **Visibility:** Toggle On/Off.
*   **Styling:**
    *   **Font Size:** Dropdown (10, 11, 12, 14, 16, 20, 24, 28, 32, 40).
    *   **Format:** Bold (B), Italic (I) toggles.
    *   **Color:** Default to drawing color or custom.
*   **Alignment:**
    *   **Vertical:** Top, Middle, Bottom (or Inside).
    *   **Horizontal:** Left, Center, Right.
    *   **Orientation:** Horizontal or aligned with drawing path.

### 2. Templates (Presets)
Users must be able to save and load configuration sets for drawings:
*   **Save As:** Save current settings (color, width, text options, specific flags) as a named template.
*   **Quick Load:** Dropdown in the properties panel (bottom-left) to apply a template.
*   **Storage:** Persisted to local storage (or database/user profile).
*   **Default:** "Save as Default" option for new drawings.

### 3. Visibility & Coordinates (Timeframe Awareness)
*   **Timeframe Visibility:** Detailed control to show/hide drawings on specific intervals:
    *   **Ticks / Seconds / Minutes / Hours / Days / Weeks / Months / Ranges.**
    *   **Range Sliders:** Define visibility range (e.g., "1 min to 2 hours").
*   **Precise Coordinates:** Input fields to manually edit Price and Time/Bar Index.
*   **Auto-Scaling (autoscaleInfo):** Ensure drawings affect chart scaling.

---

## 📐 Tool-Specific Requirements

### 1. Rectangle (Box)
*   **Borders & Fill:** Separate control for Border Color/Width and Fill Color/Opacity.
*   **Extensions:** Extend Left, Extend Right (infinite horizontal).
*   **Internal Lines (New Request):**
    *   **Midline (50%):** Toggle On/Off, Style (Color, Width, Dash).
    *   **Quarter Lines (25%, 75%):** Toggle On/Off, Style.
*   **Text Alignment:** Critical for "Order Blocks" or "Gaps".
    *   *Example:* "FVP" label centered inside, or "Supply" label on top-right.

### 2. Trend Line (Ray/Segment)
*   **Line Style:** Solid, Dashed, Dotted.
*   **Endings:** Arrow Head (Start), Arrow Head (End).
*   **Extensions:** Extend Left (Infinite), Extend Right (Infinite).
*   **Stats:** Show Angle (degrees), Show Distance (bars/time), Show Price Range (% and raw).
*   **Text:** Text should flow along the line or stay horizontal.

### 3. Fibonacci Retracement
*   **Levels:**
    *   Enable/Disable specific levels (0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, etc.).
    *   Custom Levels: User can add/remove levels (e.g., 0.705).
    *   Per-Level Styling: Color and Opacity for each level line/background.
*   **Trend Line:** Show/Hide the diagonal trend line connecting the anchors.
*   **Background:** Fill background between levels (with transparency).
*   **Labels:**
    *   Position: Left, Right, Center.
    *   Values: Price, Percent, or Both.
*   **Reverse:** Button to flip the direction (0-1 vs 1-0).

### 4. Vertical Line
*   **Label:** Show Date/Time at the top or bottom.
*   **Text:** Custom text annotation (e.g., "News Event").
*   **Style:** Full height (always), Fixed width (optional).

### 5. Horizontal Price Line
*   **Label:** Show Price on axis (already implemented).
*   **Text:** Custom text (e.g., "Daily Open").
*   **Style:** Solid, Dashed, Dotted.

### 6. Measuring Tool (Date & Price Range)
*   **Function:** Measure distance between two points.
*   **Visual:**
    *   **Box/Line:** Shaded area covering the time/price range.
    *   **Label:** Tooltip showing:
        *   Price Change (Absolute & Percentage).
        *   Time Change (Bars & Time duration).
*   **Interaction:** Click-Drag or Click-Click.
*   **Shortcut:** Shift + Click (Standard behavior).

---

## 📊 Standard Indicators (TradingView Core)
The following indicators are essential for a complete charting platform:

### 1. Overlays (Main Pane)
*   **Moving Averages:** SMA, EMA, WMA, VWMA.
*   **Bollinger Bands:** Standard deviation bands around an MA.
*   **VWAP:** Volume Weighted Average Price (Intraday).
*   **Supertrend:** Trend-following indicator.
*   **Ichimoku Cloud:** Comprehensive trend/momentum indicator.

### 2. Oscillators (Separate Pane)
*   **RSI:** Relative Strength Index.
*   **MACD:** Moving Average Convergence Divergence (Histogram + Lines).
*   **Stochastic:** Stochastic Oscillator.
*   **ATR:** Average True Range (Volatility).
*   **Volume:** (Often an overlay at bottom, or separate pane).

---

## 🖱 Interaction Model

### Mouse Actions
*   **Click-Click Drawing:**
    *   *Click 1:* Set Start Point (Anchor 1).
    *   *Move:* Preview the drawing.
    *   *Click 2:* Set End Point (Anchor 2).
    *   *Why:* More precise than Click-Drag, preferred by professional traders.
*   **Drag to Move:**
    *   Clicking and dragging the *body* of a drawing moves the entire shape (maintaining relative geometry).
*   **Drag Anchors:**
    *   Clicking and dragging a specific *anchor point* (white dot) resizes/reshapes the drawing.
*   **Hover Effects:**
    *   Cursor changes to "Pointer" or "Move" when hovering over a selectable drawing.
    *   Drawing highlights (glow or thicker line) on hover.
*   **Double Click:**
    *   Opens the **Full Properties Modal** (for detailed editing like Templates, Coordinates).

### Keyboard Shortcuts
*   **Delete / Backspace:** Delete selected drawing.
*   **Ctrl + C / Ctrl + V:** Copy and Paste selected drawing.
*   **Ctrl + Z / Ctrl + Y:** Undo / Redo drawing actions.
*   **Esc:** Cancel current drawing action or Deselect.

---

## 🏗 Architecture & Design Implications

### 1. Enhanced `options` Structure
The current flat options object needs to be nested or more structured to handle complexity.
```javascript
// Example Rectangle Options
{
    style: {
        borderColor: '#FF0000',
        borderWidth: 2,
        fillColor: 'rgba(255, 0, 0, 0.1)',
        extendRight: false
    },
    levels: { // For Midline/Quarter lines
        midline: { enabled: true, color: '#FF0000', style: 'dashed' },
        quarter: { enabled: false }
    },
    text: {
        content: "Order Block",
        visible: true,
        color: '#FFFFFF',
        fontSize: 12,
        bold: true,
        alignment: { vertical: 'center', horizontal: 'center' }, // 'top', 'bottom', 'left', 'right'
        position: 'inside' // 'outside'
    }
}
```

### 2. Text Rendering Primitive
We need a reusable `TextPrimitive` or `LabelPrimitive` class that can be composed into other drawings.
*   Instead of rewriting text logic for every tool, create a `TextLabel` class that takes a coordinate (x, y) and options, and renders text on the canvas.
*   Plugins will instantiate this `TextLabel` as part of their `paneViews`.

### 3. Template Manager
A new `TemplateManager` class/module.
*   **Storage:** Save templates to `localStorage` (or backend DB later).
*   **Structure:** Map of `ToolType -> { TemplateName -> OptionsObject }`.
*   **UI:** The Properties Panel needs a "Templates" dropdown section.

### 4. Properties Panel Upgrade
The current simple bottom-left panel is insufficient for this level of detail.
*   **Tabbed Modal:** We likely need a floating modal window (like TradingView's settings dialog) with tabs: "Style", "Text", "Coordinates", "Visibility".
*   **Quick Toolbar:** Keep the small floating toolbar for common actions (Color, Thickness, Delete, Settings Icon). Clicking "Settings Icon" opens the full modal.

### 5. Multi-Pane Support (Stacked Scales)
To support indicators like RSI/MACD in separate panels below the main price:
*   **Architecture:** Use `lightweight-charts` multiple price scales feature with `scaleMargins` to stack them vertically within a single chart instance.
*   **Drawing Dependency:**
    *   **Attachment:** Each drawing must be attached to a specific `priceScaleId` (e.g., "right" for Price, "pane1" for RSI).
    *   **Drag/Drop:** Users should be able to move drawings between panes (if applicable) or the drawing should be strictly bound to the pane it was created on.
    *   **Global Tools:** Vertical Lines should optionally span *all* panes (global time marker).
    *   **Coordinates:** Y-coordinates are scale-dependent. X-coordinates (Time) are shared.

---

## 📝 Next Steps Plan

1.  **Mockup:** Design the new "Quick Toolbar" vs "Full Settings Modal".
2.  **Architecture:** Implement the `TextLabel` primitive.
### 6. Trade Execution & Visualization (Chart Trading)
*   **Visual Orders:**
    *   **Drag-and-Drop:** Users can drag limit/stop orders directly on the chart.
    *   **Modification:** Dragging an active order line modifies its price.
    *   **Cancellation:** "X" button on the order line to cancel.
*   **Position Management:**
    *   **Position Line:** Shows Entry Price, Quantity, and current PnL (floating).
    *   **SL/TP Brackets:** Draggable Stop Loss and Take Profit lines attached to the position.
*   **Dependency:**
    *   **Order Management System (OMS):** Requires a backend to handle order logic.
    *   **Real-time Data:** PnL calculations need live ticks.

### 7. Core Dependencies & Utilities
*   **Magnet Mode:**
    *   **Function:** Cursor snaps to OHLC values (High/Low/Close/Open) when drawing.
    *   **Dependency:** Critical for precise drawing (Trendlines, Fibs).
    *   **Toggle:** Weak Magnet, Strong Magnet, Off.
*   **Timezone Management:**
    *   **Global Setting:** Chart and all time-based tools (Vertical Lines, Sessions) must respect the selected timezone (e.g., "America/New_York").
    *   **Dependency:** Essential for "Session Highlighting" and correct "Daily Open" lines.
*   **Crosshair Sync:**
    *   **Multi-Pane:** Crosshair must move in sync across all stacked panes (Price, RSI, MACD).
    *   **Multi-Chart:** (Future) Sync crosshair across multiple chart widgets in a grid.

### 8. User's Favorite Tools (Priority List)
Derived from the provided screenshot (TradingView Toolbar):

1.  **Trend Line:** Basic line with 2 anchors.
2.  **Fibonacci Retracement:** Standard retracement levels.
3.  **Trend-Based Fib Extension:** 3-point tool for projections.
4.  **Fixed Range Volume Profile (FRVP):** [DEFERRED] Volume distribution over a specific time range.
5.  **Long Position:** Risk/Reward tool for buying.
6.  **Short Position:** Risk/Reward tool for selling.
7.  **Date & Price Range:** Measurement tool.
8.  **Brush:** Freehand drawing.
9.  **Highlighter:** Transparent freehand drawing.
10. **Rectangle:** Box shape.
11. **Text:** Simple text label.
12. **Callout:** Text bubble with an arrow.
13. **Arrow:** Single directional arrow.
14. **Ray:** Line extending infinitely in one direction.
15. **Extended Line:** Line extending infinitely in both directions.
16. **Parallel Channel:** Two parallel lines forming a channel.

---

## 🎨 UI Mockups

### 1. Quick Toolbar (Floating)
Appears near the drawing when selected. Minimalist.
```text
+--------------------------------------------------+
|  [ Color ]  [ 2px ]  [ Line Style ]  [ Settings ]  [ Trash ]  |
+--------------------------------------------------+
```

### 2. Full Properties Modal (Settings)
Opens when clicking "Settings" or Double-Clicking.

```text
+---------------------------------------------------------------+
|  Settings: Rectangle                                     [X]  |
+---------------------------------------------------------------+
|  [ Style ]   [ Text ]   [ Coordinates ]   [ Visibility ]      |
|                                                               |
|  + Style --------------------------------------------------+  |
|  |  Border:  [ Color Picker (w/ Alpha) ]  [ 2px ]          |  |
|  |  Fill:    [ Color Picker (w/ Alpha) ]                   |  |
|  |                                                         |  |
|  |  [x] Extend Left    [ ] Extend Right                    |  |
|  |                                                         |  |
|  |  Internal Lines:                                        |  |
|  |  [x] Midline (50%)   [ Color ] [ Dash ]                 |  |
|  |  [ ] Quarter Lines   [ Color ] [ Dot  ]                 |  |
|  +---------------------------------------------------------+  |
|                                                               |
|  Template: [ Save As... ]  [ Load Template v ]                |
|                                                               |
|                  [ Cancel ]       [ OK ]                      |
+---------------------------------------------------------------+
```

### 3. Text Tab (in Modal)

```text
+---------------------------------------------------------------+
|  [ Style ]   [ Text ]   [ Coordinates ]   [ Visibility ]      |
|                                                               |
|  [x] Show Text                                                |
|                                                               |
|  Content:                                                     |
|  +---------------------------------------------------------+  |
|  | Order Block (Daily)                                     |  |
|  +---------------------------------------------------------+  |
|                                                               |
|  Color: [ White ]   Size: [ 12px ]   [ B ] [ I ]              |
|                                                               |
|  Position:                                                    |
|  [ Inside v ]  [ Top v ]  [ Right v ]                         |
|                                                               |
+---------------------------------------------------------------+
```
