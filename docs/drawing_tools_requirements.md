# Advanced Drawing Tools Requirements

## 🎯 Objective
Enhance the drawing tools to match professional charting platforms (like TradingView) with deep customization, text annotations, templates, and refined interaction models.

## 🛠 Common Features (All Tools)

### 1. Text Annotations
Every drawing tool (TrendLine, Rectangle, etc.) should support an optional text label.
*   **Content:** Multi-line text entry.
*   **Visibility:** Toggle On/Off.
*   **Positioning:**
    *   *Relative:* Inside/Outside, Top/Bottom/Center, Left/Right/Center.
    *   *Orientation:* Horizontal or Aligned with the drawing (e.g., along the trendline).
*   **Styling:** Font size (10px, 12px, 14px, etc.), Bold/Italic, Color (default to drawing color or custom).

### 2. Templates (Presets)
Users must be able to save and load configuration sets.
*   **Save As:** Save current settings (color, width, text options, specific flags) as a named template (e.g., "Bullish Order Block", "Stop Loss Line").
*   **Quick Load:** Dropdown in the properties panel to apply a template.
*   **Default:** Option to "Save as Default" for new drawings of that type.
*   **Hotkeys:** (Optional) Bind templates to hotkeys (e.g., Alt+1 for Template 1).

### 3. Visibility & Coordinates
*   **Timeframe Visibility:** Option to show/hide drawings on specific timeframes (e.g., "Show on 1H only").
*   **Precise Coordinates:** Input fields to manually edit Price and Time/Bar Index for anchor points.
*   **Auto-Scaling (autoscaleInfo):**
    *   Drawings must implement `autoscaleInfo` to ensure they are included in the chart's vertical auto-scaling calculation.
    *   Critical for tools that extend beyond the current price range (e.g., Fibonacci extensions, long TrendLines).

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

---

## 📝 Next Steps Plan

1.  **Mockup:** Design the new "Quick Toolbar" vs "Full Settings Modal".
2.  **Architecture:** Implement the `TextLabel` primitive.
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
|  |  Border:  [ Color Picker ]   [ 2px ]   [ Solid v ]      |  |
|  |  Fill:    [ Color Picker ]   [ 20% Opacity ]            |  |
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
