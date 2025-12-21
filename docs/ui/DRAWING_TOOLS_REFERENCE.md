# Drawing Tools Reference

This is the consolidated reference for implementing and extending drawing tools in the charting application.

## Overview

All drawing tools are implemented as **Lightweight Charts Plugins** (`ISeriesPrimitive`). Each tool consists of:

1. **Primitive Class** - Main class implementing `ISeriesPrimitive`, holds state and options
2. **Pane View** - Bridge between Primitive and Renderer
3. **Renderer** - Canvas API drawing calls

---

## Available Tools

| Tool | Icon | Type | Points | File |
|------|------|------|--------|------|
| Trend Line | `TrendingUp` | Line | 2 | `trend-line.ts` |
| Ray | `ArrowRight` | Line | 2 | `ray.ts` |
| Horizontal Line | `Minus` | Line | 1 | `horizontal-line.ts` |
| Vertical Line | `SeparatorVertical` | Line | 1 | `vertical-line.ts` |
| Rectangle | `Square` | Shape | 2 | `rectangle.ts` |
| Fibonacci | `Tally5` | Levels | 2 | `fibonacci.ts` |
| Text | `Type` | Annotation | 1 | `text-drawing.ts` |
| Price Label | `BadgeDollarSign` | Annotation | 2 | `price-label.ts` |
| Measure | `Ruler` | Measurement | 2 | `measuring-tool.ts` |
| Price Range | `MoveVertical` | Measurement | 2 | `price-range.ts` |
| Date Range | `CalendarRange` | Measurement | 2 | `date-range.ts` |
| Risk/Reward | `ArrowRight` | Trading | 3 | `risk-reward.ts` |

---

## Architecture

### Class Hierarchy

```
ISeriesPrimitive (Lightweight Charts)
    └── DrawingBase (Abstract)
            ├── TwoPointDrawing
            │       ├── TrendLine
            │       ├── Ray
            │       ├── Fibonacci
            │       └── Rectangle
            └── SinglePointDrawing
                    ├── HorizontalLine
                    ├── VerticalLine
                    └── TextDrawing
```

### Standard Options Interface

Every tool accepts an options object with these common properties:

```typescript
interface DrawingOptions {
    // Line properties
    lineColor: string;      // NOT "color"
    lineWidth: number;
    lineStyle: number;      // 0=Solid, 1=Dotted, 2=Dashed
    
    // Text properties (if applicable)
    text?: string;
    textColor: string;      // NOT "color" or "labelColor"
    fontSize: number;
    showLabel: boolean;     // Singular, NOT "showLabels"
    bold?: boolean;
    italic?: boolean;
    
    // Fill properties (if applicable)
    fillColor?: string;
    fillOpacity?: number;
    showFill?: boolean;
    
    // Background (for text)
    backgroundColor?: string;
    showBackground?: boolean;
    backgroundOpacity?: number;
}
```

> **Critical**: Use `textColor` not `color`, `showLabel` not `showLabels`, `lineColor` not `color`.

---

## Implementation Patterns

### 1. Options Management

**Always reference live options from source:**

```typescript
// ❌ BAD - stale options
constructor(source, options) {
    this._options = options; // Captures initial snapshot
}

// ✅ GOOD - live options
renderer() {
    return new Renderer(this._source._options); // Always current
}
```

### 2. Coordinate Scaling

Scale all coordinates by pixel ratio:

```typescript
draw(target: any) {
    target.useBitmapCoordinateSpace((scope) => {
        const ctx = scope.context;
        const hPR = scope.horizontalPixelRatio;
        const vPR = scope.verticalPixelRatio;
        
        const x = Math.round(this._x * hPR);
        const y = Math.round(this._y * vPR);
        ctx.lineWidth = Math.max(1, this._options.lineWidth * hPR);
    });
}
```

### 3. Hit Testing

Return standardized hit objects:

```typescript
hitTest(x: number, y: number) {
    // Check handles first
    if (distToP1 <= HANDLE_RADIUS) {
        return {
            cursorStyle: 'nwse-resize',
            externalId: this._id,
            zOrder: 'top',
            hitType: 'p1'
        };
    }
    
    // Check body
    if (distToLine < THRESHOLD) {
        return {
            cursorStyle: 'move',
            externalId: this._id,
            zOrder: 'top',
            hitType: 'body'
        };
    }
    
    return null;
}
```

### 4. Serialization

Implement `serialize()` for persistence:

```typescript
serialize() {
    return {
        id: this._id,
        type: this._type,
        p1: this._p1,
        p2: this._p2,
        options: this._options,
        createdAt: Date.now()
    };
}
```

---

## Measurement Tools Pattern

All measurement tools (Measure, Price Range, Date Range) share:

1. **2-point corner system** - Opposite corners define rectangle
2. **Bounded shading** - Fill limited to rectangle area
3. **Edge lines** - Extend to rectangle boundaries only
4. **Stats label** - Positioned at center or edge
5. **Corner handles** - Resize from any corner

---

## Toolbar Integration

Tools integrate with the floating toolbar via `toolbar-configs.ts`:

```typescript
'tool-name': {
    quickActions: ['lineColor', 'lineWidth', 'lineStyle'],
    commonButtons: ['delete', 'duplicate', 'lock']
}
```

---

## Checklist for New Tools

- [ ] Implements `ISeriesPrimitive`
- [ ] Uses standard property names (`lineColor`, `textColor`, etc.)
- [ ] Scales coordinates by pixel ratio
- [ ] Implements `hitTest()` returning standard objects
- [ ] Implements `serialize()` for persistence
- [ ] Added to `use-drawing-manager.ts` for restoration
- [ ] Added to `toolbar-configs.ts` for toolbar
- [ ] Added to `left-toolbar.tsx` with icon

---

## Related Documentation

- [TradingView Parity](./TRADINGVIEW_PARITY.md) - Feature comparison & keyboard shortcuts
- [Performance Guide](./Lightweight_Charts_Performance_Guide.md) - Optimization patterns
- [UX Guidelines](./UX_GUIDELINES.md) - Layout & spacing standards
