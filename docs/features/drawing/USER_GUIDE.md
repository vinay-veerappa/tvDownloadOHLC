# Drawing Tools User Guide

This document describes the drawing tools available in the chart application.

> **For Developers:** See [../../architecture/DRAWING_TOOLS_ARCHITECTURE.md](../../architecture/DRAWING_TOOLS_ARCHITECTURE.md) for technical architecture details.

## Tool Categories

### Selection
| Tool | Icon | Shortcut | Description |
|------|------|----------|-------------|
| Cursor | `MousePointer2` | - | Select and manipulate drawings |

### Lines
| Tool | Icon | Description |
|------|------|-------------|
| Trend Line | `TrendingUp` | 2-point diagonal line |
| Ray | `ArrowRight` | Line extending infinitely in one direction |
| Horizontal Line | `Minus` | Price level line |
| Vertical Line | `SeparatorVertical` | Time marker line |
| Horizontal Ray | `ArrowRight` (horizontal) | Horizontal line extending infinitely |
| Extended Line | `TrendingUp` (extended) | Line extending infinitely in both directions |
| Cross Line | `Plus` | Vertical and horizontal crosshair |

### Shapes
| Tool | Icon | Description |
|------|------|-------------|
| Rectangle | `Square` | 2-point rectangle with optional text |
| Circle | `Circle` | 2-point circle |
| Arrow | `ArrowRight` | Directional arrow |
| Triangle | `Triangle` | 3-point triangle |

### Fibonacci
| Tool | Icon | Description |
|------|------|-------------|
| Fibonacci Retracement | `Tally5` | Key retracement levels (23.6%, 38.2%, etc.) |

### Measurements
| Tool | Icon | Description |
|------|------|-------------|
| Measure | `Ruler` | Diagonal measurement with price/percent stats |
| Price Range | `MoveVertical` | Vertical price measurement |
| Date Range | `CalendarRange` | Horizontal time measurement |

### Annotations
| Tool | Icon | Description |
|------|------|-------------|
| Text | `Type` | Freeform text label |
| Price Label | `BadgeDollarSign` | 2-point price annotation with connector |
| Callout | `MessageSquare` | Text with callout arrow |

### Trading
| Tool | Icon | Description |
|------|------|-------------|
| Risk/Reward | `ArrowRight` (rotated) | Long position with stop/target |

---

## Text Annotations

Most drawing tools support text annotations with full formatting options:

### Text Formatting
- **Color**: Choose any color for text
- **Size**: Font sizes from 8px to 48px
- **Style**: Bold and italic options
- **Background**: Optional colored background with opacity control
- **Border**: Optional border with customizable width and color

### Text Alignment

Text can be aligned both horizontally and vertically:

**Horizontal Alignment:**
- **Left**: Text aligns to the left edge
- **Center**: Text centers horizontally (default)
- **Right**: Text aligns to the right edge

**Vertical Alignment:**
- **Top**: Text aligns to the top edge
- **Middle**: Text centers vertically (default)
- **Bottom**: Text aligns to the bottom edge

> **Note:** Alignment settings persist when you save and reopen tool settings. The "Middle" vertical option is internally stored as "middle" but displays as "Middle" or "Center" in the UI.

### Adding Text to Line Tools

1. Draw your line tool (Ray, Trend Line, Horizontal Line, etc.)
2. Double-click the tool to open settings
3. Go to the **Text** tab
4. Enter your text in the text area
5. Adjust formatting (color, size, bold, italic)
6. Set alignment (horizontal and vertical)
7. Optionally enable background and/or border
8. Click **OK** to apply

---

## Measurement Tools Behavior

All measurement tools (Measure, Price Range, Date Range) share consistent behavior:

1. **2-Point Click System**: Click to set first corner, drag, click to set opposite corner
2. **Rectangular Bounds**: Shaded fill limited to the rectangle formed by the two points
3. **Boundary Lines**: Lines extend to rectangle edges
4. **Center Connector**: Arrow or line indicating direction
5. **Stats Label**: Relevant statistics displayed
6. **Resize Handles**: Handles at corners for resizing

### Price Range
- Shows: Price difference, percentage change
- Format: `103.25 (0.41%)`
- Visual: Horizontal lines at top/bottom, vertical connector with arrows

### Date Range  
- Shows: Bar count, time duration
- Format: `65 bars, 1h 5m`
- Visual: Vertical lines at left/right, horizontal connector with arrow

### Measure
- Shows: Price change, percentage, direction indicator
- Format: `▲ +25.50 (+0.15%)`
- Visual: Diagonal line with dashed guides, bounded fill

---

## Price Label Tool

The Price Label (Price Note) tool is a 2-point annotation tool:

1. **First Click**: Set anchor point on OHLC bar
   - Uses magnet mode if enabled (snaps to O/H/L/C)
2. **Second Click**: Position the label
3. **Connector Line**: Visual line between anchor and label
4. **Display**: Shows price value at anchor point

### Options
- Line color
- Text color
- Background color
- Font size
- Border visibility
- Text alignment (horizontal and vertical)

---

## Magnet Mode

Magnet mode allows drawing tools to snap to OHLC values:

- **Off**: No snapping
- **Weak**: Snaps within 15px threshold
- **Strong**: Always snaps to nearest OHLC level

Affected tools: Trend Line, Ray, Fibonacci, Price Label

---

## Settings Dialogs

### Dedicated Settings Dialogs
These tools have specialized 4-tab settings dialogs (Style, Text, Coordinates, Visibility):
- Ray
- Trend Line
- Horizontal Line
- Vertical Line
- Rectangle
- Text

### Generic Properties Dialog
All other tools use a generic 3-tab dialog (Style, Text, Coordinates) with the same text formatting and alignment options.

---

## Templates

All drawing tools support templates for saving and loading preset configurations:

1. Configure a tool with your preferred settings
2. Open the tool's settings dialog
3. Click **Save as Template**
4. Enter a template name
5. Click **Save**

To load a template:
1. Open any tool's settings dialog
2. Select a template from the dropdown
3. Settings are applied immediately

To set default settings:
1. Configure a tool with your preferred settings
2. Open the tool's settings dialog
3. Click **Set as Default**
4. All new tools of this type will use these settings

---

## Toolbar Icons (Lucide React)

| Tool | Lucide Icon Name |
|------|------------------|
| Cursor | `MousePointer2` |
| Trend Line | `TrendingUp` |
| Ray | `ArrowRight` |
| Horizontal Line | `Minus` |
| Vertical Line | `SeparatorVertical` |
| Text | `Type` |
| Measure | `Ruler` |
| Price Label | `BadgeDollarSign` |
| Price Range | `MoveVertical` |
| Date Range | `CalendarRange` |
| Fibonacci | `Tally5` |
| Rectangle | `Square` |
| Risk/Reward | `ArrowRight` (rotated -45deg) |
| Circle | `Circle` |
| Arrow | `ArrowRight` |
| Triangle | `Triangle` |
| Callout | `MessageSquare` |
| Cross Line | `Plus` |

---

## Related Documentation

- [Technical Architecture](../../architecture/DRAWING_TOOLS_ARCHITECTURE.md) - Detailed architecture and implementation guide
- [TradingView Parity](../../ui/charting/TRADINGVIEW_PARITY.md) - Feature comparison & keyboard shortcuts

