# Plugin Refactoring Plan - Official API Compliance

## Official Lightweight Charts API Review

### ✅ What We're Doing Right

1. **Using Series Primitives** - All our drawing tools (TrendLine, Fibonacci, VertLine) correctly use the series primitives pattern
2. **Lifecycle Methods** - We implement `attached()` and `detached()` correctly
3. **Views Pattern** - We use PaneViews and TimeAxisViews as recommended
4. **attachPrimitive()** - We correctly attach primitives to series

### ❌ What Needs Improvement

1. **Inconsistent `applyOptions()` method** - Not part of official API, but needed for our use case
2. **Missing `updateAllViews()` in some plugins** - Official API recommends this method
3. **No standardized interface** - Each plugin implements things slightly differently
4. **Drawing creation logic in `drawings.js`** - Should be in plugin classes

## Official API Interface

According to the docs, a Series Primitive should implement:

```typescript
interface ISeriesPrimitive {
    // Required: Return views for rendering
    paneViews(): IPrimitivePaneView[];
    
    // Optional: Return time axis views
    timeAxisViews?(): ISeriesPrimitiveAxisView[];
    
    // Optional: Return price axis views  
    priceAxisViews?(): ISeriesPrimitiveAxisView[];
    
    // Lifecycle: Called when attached to series
    attached?(params: SeriesPrimitivePaneViewParams): void;
    
    // Lifecycle: Called when detached from series
    detached?(): void;
    
    // Update: Should update all views
    updateAllViews?(): void;
    
    // Autoscale: Extend price range if needed
    autoscaleInfo?(startTimePoint, endTimePoint): AutoscaleInfo | null;
}
```

## Recommended Standard Plugin Interface

Based on official API + our needs:

```javascript
class StandardDrawingPlugin {
    constructor(chart, series, p1, p2, options) {
        this._chart = chart;
        this._series = series;
        this._p1 = p1;
        this._p2 = p2;
        this._options = { ...this.defaultOptions(), ...options };
        this._requestUpdate = null;
        
        // Create views
        this._paneViews = [new DrawingPaneView(this, this._options)];
        this._timeAxisViews = [];  // if needed
    }
    
    // ===== OFFICIAL API METHODS =====
    
    // Required: Return pane views
    paneViews() {
        return this._paneViews;
    }
    
    // Optional: Return time axis views
    timeAxisViews() {
        return this._timeAxisViews;
    }
    
    // Lifecycle: Attached to series
    attached({ chart, series, requestUpdate }) {
        this._requestUpdate = requestUpdate;
        this.updateAllViews();
    }
    
    // Lifecycle: Detached from series
    detached() {
        this._requestUpdate = null;
    }
    
    // Update all views (RECOMMENDED by docs)
    updateAllViews() {
        this._paneViews.forEach(view => view.update());
        this._timeAxisViews.forEach(view => view.update());
    }
    
    // ===== CUSTOM METHODS FOR OUR USE CASE =====
    
    // Get current options (for properties panel)
    options() {
        return this._options;
    }
    
    // Apply new options (for properties panel)
    applyOptions(options) {
        this._options = { ...this._options, ...options };
        // Recreate views with new options
        this._paneViews = [new DrawingPaneView(this, this._options)];
        this.updateAllViews();
        if (this._requestUpdate) this._requestUpdate();
    }
    
    // Hit test for selection (custom)
    hitTest(point) {
        // Return true if point intersects this drawing
        return false;
    }
    
    // Default options
    defaultOptions() {
        return {
            color: '#2962FF',
            lineWidth: 2
        };
    }
}
```

## Refactoring Plan

### Phase 1: Standardize Existing Plugins ✅

**Goal:** Make all plugins follow the same interface

**Files to Update:**
- `trendline_plugin.js` - Add `options()` method
- `fibonacci_plugin.js` - Add `options()` and `applyOptions()` methods
- `vertical_line_plugin.js` - ✅ Already has all methods (done!)

**Changes:**

1. **TrendLine** - Add `options()` method:
```javascript
options() {
    return this._options;
}
```

2. **Fibonacci** - Add both methods:
```javascript
options() {
    return this._options;
}

applyOptions(options) {
    this._options = { ...this._options, ...options };
    this._paneViews = [new FibonacciPaneView(this, this._options)];
    this.updateAllViews();
    if (this._requestUpdate) this._requestUpdate();
}
```

### Phase 2: Add Hit Testing to Plugins

**Goal:** Move hit testing logic from `drawings.js` into plugins

Add `hitTest(point)` method to each plugin:

```javascript
// In TrendLine
hitTest(point) {
    const timeScale = this._chart.timeScale();
    const series = this._series;
    
    const x1 = timeScale.timeToCoordinate(this._p1.time);
    const y1 = series.priceToCoordinate(this._p1.price);
    const x2 = timeScale.timeToCoordinate(this._p2.time);
    const y2 = series.priceToCoordinate(this._p2.price);
    
    if (x1 === null || y1 === null || x2 === null || y2 === null) return false;
    
    const dist = this._distanceToSegment(point.x, point.y, x1, y1, x2, y2);
    return dist < 10;
}
```

### Phase 3: Create Tool Classes

**Goal:** Separate drawing creation logic from plugins

Create tool classes that handle the drawing process:

```javascript
// tools/TrendLineTool.js
export class TrendLineTool {
    constructor(chart, series) {
        this._chart = chart;
        this._series = series;
        this._startPoint = null;
        this._activeDrawing = null;
    }
    
    handleClick(param) {
        if (!this._startPoint) {
            this._startPoint = { time: param.time, price: param.price };
            this._activeDrawing = new TrendLine(
                this._chart, 
                this._series, 
                this._startPoint, 
                this._startPoint,
                { lineColor: '#D500F9', lineWidth: 2 }
            );
            this._series.attachPrimitive(this._activeDrawing);
            return { drawing: this._activeDrawing, complete: false };
        } else {
            this._activeDrawing._p2 = { time: param.time, price: param.price };
            this._activeDrawing.updateAllViews();
            const drawing = this._activeDrawing;
            this._reset();
            return { drawing, complete: true };
        }
    }
    
    handleMouseMove(param) {
        if (this._activeDrawing && this._startPoint) {
            this._activeDrawing._p2 = { time: param.time, price: param.price };
            this._activeDrawing.updateAllViews();
        }
    }
    
    _reset() {
        this._startPoint = null;
        this._activeDrawing = null;
    }
}
```

### Phase 4: Simplify drawings.js

**Goal:** Make `drawings.js` a coordinator, not implementer

```javascript
// drawings.js becomes much simpler
import { TrendLineTool } from './tools/TrendLineTool.js';
import { FibonacciTool } from './tools/FibonacciTool.js';
// ... etc

const tools = {
    ray: new TrendLineTool(chart, series),
    fib: new FibonacciTool(chart, series),
    // ... etc
};

function handleDrawingClick(param) {
    const tool = tools[state.currentTool];
    if (!tool) return;
    
    const result = tool.handleClick(param);
    if (result.complete) {
        state.drawings.push(result.drawing);
        setTool(null);
    }
}
```

## Implementation Order

1. ✅ **Phase 1** - Standardize Existing Plugins (COMPLETE)
2. ✅ **Phase 2** - Add Hit Testing to Plugins (COMPLETE)
3. ✅ **Phase 3** - Create Tool Classes (COMPLETE)
4. ✅ **Phase 4** - Refactor drawings.js (COMPLETE - Merged with Phase 3)

## Status Update (2025-12-04)

**All architectural refactoring is complete.**
- All plugins (TrendLine, Fibonacci, VertLine, Rectangle) implement the standard interface (`options`, `applyOptions`, `hitTest`).
- Drawing creation logic is encapsulated in Tool classes (`TrendLineTool`, `FibonacciTool`, `VertLineTool`, `RectangleDrawingTool`).
- `drawings.js` has been simplified to act as a coordinator.
- Obsolete duplicate files have been removed.

## Next Steps

1. **Ticker-Specific Drawings** - Implement storage to save/load drawings per ticker.

