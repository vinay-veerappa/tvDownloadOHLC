# Drawing Tools Reference

This document describes the drawing tools available in the chart application.

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

### Shapes
| Tool | Icon | Description |
|------|------|-------------|
| Rectangle | `Square` | 2-point rectangle with optional text |

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

### Trading
| Tool | Icon | Description |
|------|------|-------------|
| Risk/Reward | `ArrowRight` (rotated) | Long position with stop/target |

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

---

## Magnet Mode

Magnet mode allows drawing tools to snap to OHLC values:

- **Off**: No snapping
- **Weak**: Snaps within 15px threshold
- **Strong**: Always snaps to nearest OHLC level

Affected tools: Trend Line, Ray, Fibonacci, Price Label

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
