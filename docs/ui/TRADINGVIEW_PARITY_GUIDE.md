# TradingView Drawing Tools - UI/UX Parity Guide

This document provides a comprehensive comparison between our current drawing tools implementation and TradingView's UI/UX patterns, serving as the reference for achieving feature parity.

---

## Table of Contents

1. [Overview](#overview)
2. [TradingView's Core UI Patterns](#tradingviews-core-ui-patterns)
3. [Tool-by-Tool Comparison](#tool-by-tool-comparison)
4. [Universal Missing Features](#universal-missing-features)
5. [Design Specifications](#design-specifications)
6. [Implementation Roadmap](#implementation-roadmap)

---

## Overview

**Current Status:** 14 drawing tools implemented with basic functionality  
**Goal:** Match TradingView's professional UI/UX for all tools  
**Priority:** Universal components first, then per-tool customization

### Current Tools
- Trend Line
- Horizontal Line
- Vertical Line
- Ray
- Rectangle
- Fibonacci Retracement
- Text
- Measure
- Risk/Reward
- Expected Move Levels (custom)
- Session Highlighting (custom)
- Hourly Profiler (custom)
- VWAP (custom)
- Anchored Text

---

## TradingView's Core UI Patterns

### 1. Floating Toolbar

**Appears immediately after drawing completion**

```
┌─────────────────────────────────────────┐
│ [⚙️] [📋] [🔒] [🗑️] [👁️] [⭐]         │
└─────────────────────────────────────────┘
```

**Buttons:**
- ⚙️ **Settings** - Opens settings dialog
- 📋 **Clone** - Duplicates the drawing
- 🔒 **Lock** - Prevents accidental modification
- 🗑️ **Delete** - Removes the drawing
- 👁️ **Hide** - Toggles visibility
- ⭐ **Favorite** - Adds tool to favorites

**Behavior:**
- Positioned near the drawing's end point
- Follows the drawing when moved
- Auto-hides after 3 seconds of no interaction
- Reappears on hover

---

### 2. Settings Dialog (4-Tab System)

**Structure:**
```
┌─────────────────────────────────────────┐
│  [Tool Name] Settings           [x]     │
├─────────────────────────────────────────┤
│  [Style] [Coordinates] [Visibility] [Text] │
├─────────────────────────────────────────┤
│  [Tab Content]                          │
│                                         │
│  [Template ▼]  [OK]  [Cancel]          │
└─────────────────────────────────────────┘
```

**Tab 1: Style**
- Color picker with hex display
- Opacity slider (0-100%)
- Line thickness (1-4px)
- Line style (Solid/Dashed/Dotted)
- Tool-specific options (extend, fill, etc.)
- Stats display toggles

**Tab 2: Coordinates**
- Precise point editing
- Bar number
- Date/Time
- Price value
- Apply button

**Tab 3: Visibility**
- Timeframe checkboxes
- Show/hide on specific intervals
- Multi-timeframe support

**Tab 4: Text**
- Text input field
- Position selector
- Font size
- Color picker
- Alignment options

---

### 3. Keyboard Shortcuts

**Tool Selection:**
| Shortcut | Tool |
|:---------|:-----|
| `Alt + T` | Trend Line |
| `Alt + H` | Horizontal Line |
| `Alt + V` | Vertical Line |
| `Alt + F` | Fibonacci Retracement |
| `Alt + C` | Cross Line |
| `Alt + Shift + R` | Rectangle |

**Actions:**
| Shortcut | Action |
|:---------|:-------|
| `Esc` | Cancel active tool |
| `Del` | Delete selected |
| `Ctrl + Z` | Undo |
| `Ctrl + Y` | Redo |
| `Ctrl + C` | Copy selected |
| `Ctrl + V` | Paste |
| `Ctrl + D` | Clone selected |
| `Ctrl + Alt + H` | Hide all drawings |
| `Arrow Keys` | Move selected (1px) |
| `Shift + Arrow` | Move selected (10px) |

---

### 4. Template System

**Template Dropdown in Settings:**
```
┌──────────────────────────┐
│ Template:  [▼]           │
├──────────────────────────┤
│ • Default                │
│ • My Blue Trendline      │
│ • Support Level          │
│ • Resistance Level       │
│ ──────────────────────   │
│ ✚ Save as...             │
│ ⚙️ Manage Templates...   │
└──────────────────────────┘
```

**Features:**
- Save current settings as template
- Apply template to new drawings
- Set default template per tool
- Manage/delete templates

---

### 5. Magnet Mode

**UI Location:** Top toolbar

**States:**
- 🧲 **Off** - No snapping
- 🧲 **Weak** - Snap within 30% of bar range
- 🧲 **Strong** - Always snap to nearest OHLC

**Visual Feedback:**
- Green dot at snap point
- Tooltip shows value (e.g., "High: 4,250.50")
- Line "jumps" to OHLC point

**Keyboard:** Hold `Ctrl` to temporarily toggle

---

## Tool-by-Tool Comparison

### 1. Trend Line

**TradingView Features:**

**Style Tab:**
- Color + Opacity
- Thickness (1-4)
- Style (Solid/Dashed/Dotted)
- ☐ Extend Left
- ☑ Extend Right
- Show Stats:
  - ☑ Price Range
  - ☑ Bars Range
  - ☑ Date/Time Range
  - ☑ Distance
  - ☑ Angle

**Our Status:**
- ✅ Basic drawing
- ✅ Selection handles
- ✅ Magnet snapping (hidden)
- ❌ No settings dialog
- ❌ No extend options
- ❌ No stats display
- ❌ No keyboard shortcut

**Gap Priority:** CRITICAL

---

### 2. Horizontal Line

**TradingView Features:**

**Style Tab:**
- Color + Opacity
- Thickness (1-4)
- Style (Solid/Dashed/Dotted)
- ☑ Show Price
- ☑ Show Percent

**Additional:**
- 🔔 Create Alert button
- Price label on right axis

**Our Status:**
- ✅ Basic drawing
- ❌ No settings
- ❌ No price label
- ❌ No alert creation
- ❌ No keyboard shortcut

**Gap Priority:** HIGH

---

### 3. Vertical Line

**TradingView Features:**

**Style Tab:**
- Color + Opacity
- Thickness (1-4)
- Style (Solid/Dashed/Dotted)
- ☑ Show Date/Time

**Our Status:**
- ✅ Basic drawing
- ❌ No settings
- ❌ No date/time label
- ❌ No keyboard shortcut

**Gap Priority:** MEDIUM

---

### 4. Rectangle

**TradingView Features:**

**Style Tab:**
- Border: Color, Opacity, Thickness, Style
- Background: ☑ Filled, Color, Opacity
- ☐ Show Price Range
- ☐ Show Bars Range

**Interaction:**
- 8-point resize (4 corners + 4 edges)
- Maintain aspect ratio (Shift+Drag)

**Our Status:**
- ✅ Basic drawing
- ✅ Fill + border colors
- ❌ No separate opacity controls
- ❌ Only 2-point resize
- ❌ No stats display
- ❌ No keyboard shortcut

**Gap Priority:** HIGH

---

### 5. Fibonacci Retracement

**TradingView Features:**

**Style Tab:**
- Trend Line: Visible, Color, Thickness, Style
- Levels: Individual colors, Add custom levels
- Levels Line: Thickness, Style
- Extend Lines: None/Left/Right/Both
- Background: Filled, Color, Opacity
- Labels: Show, Prices, Levels, Position, Font Size

**Our Status:**
- ✅ Comprehensive settings (BEST!)
- ✅ All major features
- ❌ Can't add custom levels
- ❌ No reverse button
- ❌ No keyboard shortcut

**Gap Priority:** LOW (already close to parity)

---

### 6. Text Tool

**TradingView Features:**

**Style Tab:**
- Text input
- Font: Family, Size
- Style: Bold, Italic, Underline
- Color
- Background: Filled, Color, Opacity
- Border: Visible, Color, Thickness
- Alignment: Left/Center/Right
- Word Wrap: Enabled, Width

**Our Status:**
- ✅ Basic text placement
- ❌ No font options
- ❌ No styling (B/I/U)
- ❌ No background
- ❌ No border
- ❌ No alignment

**Gap Priority:** HIGH

---

### 7. Measure Tool

**TradingView Features:**

**Auto-Display Stats Box:**
```
┌─────────────────────┐
│ Δ Price: +24.75     │
│ Δ %:     +0.58%     │
│ Bars:    222        │
│ Time:    6h 30m     │
│ Distance: 1.2%      │
└─────────────────────┘
```

**Settings:**
- Line: Color, Thickness, Style
- Stats Box: Toggle individual stats, Background, Opacity

**Our Status:**
- ✅ Basic measure line
- ✅ Shows stats
- ❌ Can't customize stats
- ❌ No stats box background

**Gap Priority:** MEDIUM

---

### 8. Risk/Reward Tool

**TradingView Features:**

**Style Tab:**
- Entry Line: Color, Thickness, Style
- Stop Loss: Color, Thickness, Style
- Take Profit: Color, Thickness, Style
- Risk/Reward Ratio: Target (auto-calculate)
- ☑ Show R:R Label
- ☑ Show Price Labels
- ☑ Show Percent Labels
- Background: Profit Zone (Green), Loss Zone (Red), Opacity

**Our Status:**
- ✅ Entry, Stop, Target points
- ✅ Basic R:R calculation
- ❌ No per-line color customization
- ❌ No R:R display
- ❌ No background zones

**Gap Priority:** MEDIUM

---

## Universal Missing Features

### 1. Floating Toolbar
**Priority:** CRITICAL  
**Affects:** All 14 tools  
**Effort:** Medium (1-2 days)

### 2. Settings Dialog (4 tabs)
**Priority:** CRITICAL  
**Affects:** 13 tools (Fibonacci has it)  
**Effort:** High (3-4 days for base, 1 day per tool)

### 3. Keyboard Shortcuts
**Priority:** CRITICAL  
**Affects:** All tools  
**Effort:** Low (1 day)

### 4. Template System
**Priority:** HIGH  
**Affects:** All tools  
**Effort:** Medium (2 days)

### 5. Coordinates Tab
**Priority:** MEDIUM  
**Affects:** All tools with points  
**Effort:** Medium (2 days)

### 6. Visibility Tab
**Priority:** MEDIUM  
**Affects:** All tools  
**Effort:** Low (1 day)

### 7. Clone Function
**Priority:** MEDIUM  
**Affects:** All tools  
**Effort:** Low (1 day)

### 8. Lock Function
**Priority:** LOW  
**Affects:** All tools  
**Effort:** Low (0.5 day)

---

## Design Specifications

### Colors (TradingView Defaults)

```typescript
const TRADINGVIEW_COLORS = {
  // Primary
  blue: '#2962FF',
  
  // Fibonacci Levels
  fib_0: '#787B86',
  fib_236: '#F23645',
  fib_382: '#FFA726',
  fib_5: '#26A69A',
  fib_618: '#2962FF',
  fib_786: '#9C27B0',
  fib_1: '#787B86',
  
  // Risk/Reward
  profit: '#26A69A',
  loss: '#F23645',
  
  // UI
  background: '#131722',
  text: '#D1D4DC',
  border: '#2A2E39',
  
  // Selection
  selectionHandle: '#2962FF',
  selectionBorder: '#FFFFFF',
};
```

### Sizing & Spacing

```typescript
const TRADINGVIEW_SIZES = {
  // Floating Toolbar
  toolbarHeight: 32,
  toolbarIconSize: 20,
  toolbarGap: 4,
  toolbarPadding: 4,
  
  // Settings Dialog
  dialogWidth: 420,
  dialogPadding: 20,
  tabHeight: 36,
  inputHeight: 32,
  labelFontSize: 13,
  
  // Selection Handles
  handleRadius: 6,
  handleBorderWidth: 2,
  
  // Line Widths
  minLineWidth: 1,
  maxLineWidth: 4,
  defaultLineWidth: 2,
};
```

---

## Toolbar Design Patterns

### Button Representation
**Rule**: Toolbar buttons must NEVER fallback to displaying their property name (e.g., "Width", "Style") as text. They must always communicate via Icons or Visual Values.

**Implementation**:
1.  **Always Configured Icons**: Every button in `toolbar-configs.ts` (including `select` types) must have an `icon` property defined.
2.  **Icon-First Rendering**: The `SelectButton` component must always render the `icon` if present.
3.  **Visual Over Text**: If a value is selected (e.g., 2px), preferential treatment should be given to a visual representation (graphical line) over text ("2px"). Text labels are a fallback for specific values, but the generic property name (Tooltip) should never be the button's face content.
4.  **State Hydration**: The parent container (e.g., `ChartContainer`) MUST synchronize the `selectedDrawingOptions` state with the active drawing's potential values immediately upon selection. Passing an empty or default object will trigger the "text fallback" anti-pattern.

**Anti-Pattern to Avoid**:
- Relying on `tooltip` as the default `label` when `value` is undefined.
- Omitting `icon` for dropdown triggers.

### Text Entry Patterns
**Rule**: Text changes from any source (Inline Editor, Settings Dialog) must propagate to the central state immediately.

**Implementation**:
1.  **State Hydration**: When `InlineTextEditor` saves, it MUST update `selectedDrawingOptions` in `ChartContainer` if the edited drawing is currently selected.
2.  **Property Standardization**: All text-capable tools must use `textColor` (not `color`) for text styling to match the standardized `TextSettingsTab` interface.

### Standard Properties Reference

To prevent property mismatches, all Drawing Tools must strictly adhere to the following naming conventions. Do not use legacy or tool-specific variations (e.g., `labelColor`, `showLabels`).

| capabilities | Property Name | Type | Description |
| :--- | :--- | :--- | :--- |
| **Line** | `lineColor` | string | Main line color |
| | `lineWidth` | number | Line width in px |
| | `lineStyle` | number | 0=Solid, 1=Dotted, 2=Dashed |
| **Text** | `text` | string | The text content |
| | `textColor` | string | Color of the text (NOT `color`) |
| | `fontSize` | number | Size in px (default 14) |
| | `showLabel` | boolean | Toggle visibility (Singular!) |
| | `bold` | boolean | |
| | `italic` | boolean | |
| **Fill** | `fillColor` | string | Background fill color |
| | `fillOpacity` | number | 0-1 opacity multiplier |

> [!IMPORTANT]
> **Inheritance vs Composition**: While tools inherit from `DrawingBase`, standardized features like Text and Fill are composed via interfaces (`TextCapableOptions`, `FillableOptions`). Strict adherence to these property names allows the `FloatingToolbar` and `SettingsDialog` to be polymorphic and reusable.

### Drawing Systems Architecture

To ensure long-term maintainability and consistency, the drawing system follows a strict architecture involving inheritance for core behavior and composition for capabilities.

#### 1. Class Hierarchy

All drawing tools should inherit from a base class that handles common rendering lifecycle events (`attached`, `detached`, `updateAllViews`).

*   **`DrawingBase` (Abstract)**: The root class. Handles ID generation, selection state (`isSelected`, `setSelected`), serialization (`toJSON`), and common options management.
    *   **`TwoPointLineTool`**: Extends `DrawingBase`. Specialized for tools defined by a start and end point (e.g., `TrendLine`, `Ray`, `Arrow`). Handles common point updates and hit testing for lines.
        *   `TrendLine`
        *   `Ray`
        *   `Arrow`
    *   **`MultipointDrawing`** (Conceptual): For tools with >2 points (e.g., `Triangle`, `Path`).
    *   **`Standalone Primitive`**: Tools that implement `ISeriesPrimitive` directly without `DrawingBase` (e.g., `Rectangle`). *Note: Future refactors should aim to migrate these to `DrawingBase` for consistency.*

#### 2. Composition (Capabilities)

Features shared across disparate tools (like Text or Fills) are defined as **Interfaces** and composed into the tool's Options interface. They are NOT inherited.

*   **`TextCapableOptions`**:
    *   `text` (string)
    *   `textColor` (string) - **CRITICAL**: Do NOT use `color` or `labelColor`.
    *   `fontSize` (number)
    *   `showLabel` (boolean) - **CRITICAL**: Singular, not `showLabels`.
    *   `bold`, `italic` (boolean)
    *   `alignmentVertical`, `alignmentHorizontal`
*   **`FillableOptions`**:
    *   `fillColor` (string)
    *   `fillOpacity` (number)

**Example Usage**:
```typescript
interface MyToolOptions extends DrawingOptions, TextCapableOptions, FillableOptions {
    // Tool specific props
    lineWidth: number;
}
```

#### 3. Naming Conventions

*   **Classes**: PascalCase (e.g., `TrendLine`, `TextDrawing`).
*   **Files**: Kebab-case (e.g., `trend-line.ts`, `text-drawing.ts`).
*   **Properties**: camelCase.
    *   **Colors**: Suffix with `Color` (e.g., `lineColor`, `textColor`, `fillColor`). Avoid generic `color`.
    *   **Booleans**: Prefix with `show`, `enable`, or `is` (e.g., `showLabel`, `isLocked`).
    *   **Handlers**: Prefix with `on` (e.g., `onDrawingCreated`).

#### 4. Best Practices

1.  **State Hydration**: When a tool's options change (via Toolbar or Settings), the `ChartContainer`'s `selectedDrawingOptions` state MUST be updated immediately. This ensures the Toolbar reflects the new reality.
2.  **Renderer Separation**: logic should be split into a logical class (e.g., `TrendLine`) and a renderer class (e.g., `TrendLineRenderer`) that handles the raw Canvas 2D API. The logical class passes simple data structures (points, resolved options) to the renderer.
3.  **Hit Testing**: Implement `hitTest` in the logical class, not the renderer. Return standard hit objects (`cursorStyle`, `hitType`, `externalId`).

---

## Implementation Roadmap

### Phase 1: Universal Components (Week 1)
**Goal:** Build reusable components for all tools

**Tasks:**
1. FloatingToolbar component
2. DrawingSettingsDialog base component
3. Keyboard shortcuts system
4. Template storage system

**Deliverables:**
- `<FloatingToolbar>` - 6 buttons, auto-hide, positioning
- `<DrawingSettingsDialog>` - 4 tabs, template dropdown
- `KeyboardShortcutManager` - Global handler
- `TemplateStorage` - Save/load/manage

---

### Phase 2: Per-Tool Settings (Week 2)
**Goal:** Add settings dialogs to all tools

**Priority Order:**
1. Trend Line (most used)
2. Horizontal Line (most used)
3. Rectangle (high value)
4. Text (high gap)
5. Vertical Line
6. Ray
7. Measure
8. Risk/Reward

**Deliverables:**
- Settings tabs for each tool
- Stats display components
- Coordinate editors

---

### Phase 3: Advanced Features (Week 3)
**Goal:** Polish and advanced functionality

**Tasks:**
1. Multi-select + bulk edit
2. Undo/Redo system
3. Clone function (Ctrl+D)
4. Lock function
5. Alert creation (Horizontal Line)
6. Stats display (Trend Line, Measure)

**Deliverables:**
- Full keyboard shortcut support
- Professional interaction patterns
- TradingView parity achieved

---

## Success Criteria

1. ✅ All tools have floating toolbar
2. ✅ All tools have 4-tab settings dialog
3. ✅ All tools have keyboard shortcuts
4. ✅ Template system works for all tools
5. ✅ Magnet mode has visible UI
6. ✅ Stats display on relevant tools
7. ✅ Clone/Lock/Hide functions work
8. ✅ User feedback: "Feels like TradingView"

---

## References

- [TradingView Drawing Tools Documentation](https://www.tradingview.com/support/solutions/43000481029-drawings-and-annotations/)
- [TradingView Keyboard Shortcuts](https://www.tradingview.com/support/solutions/43000555216-keyboard-shortcuts/)
- Implementation Design: See `DRAWING_TOOLS_IMPLEMENTATION_DESIGN.md`

---

*Last Updated: 2025-12-19*
