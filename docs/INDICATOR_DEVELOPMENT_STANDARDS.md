# Standard Indicator Development Guide

This guide outlines the **mandatory standards** for developing high-performance indicators and drawing tools this project. Adhering to these standards ensures consistent behavior, 60fps rendering performance, and proper interaction (modals, selection).

---

## 1. Performance & Data Architecture

### ✅ DO: Use Time-Range API
When fetching data from the backend, **never** fetch the entire history blindly. Always support time-range filtering to align with the chart's lazy-loading strategy.

**Pattern:**
```typescript
interface FetchOptions {
    ticker: string;
    startTs?: number; // Unix Seconds
    endTs?: number;   // Unix Seconds
}

async function fetchData(opts: FetchOptions) {
    // API should support start_ts and end_ts
    const url = `/api/data/${opts.ticker}?start_ts=${opts.startTs}&end_ts=${opts.endTs}`;
    const res = await fetch(url);
    // ...
}
```

### ✅ DO: Pre-Compute Logic Outside Render Loop
The `draw()` method runs every frame (60fps). **Never** perform heavy calculations (like parsing dates, converting hex to RGBA, or iterating irrelevant data) inside `draw()`.

**Pattern:**
```typescript
class MyIndicator {
    // Pre-compute colors/formats in setters or update()
    updateOptions(newOptions) {
        this._lineColorRgba = hexToRgba(newOptions.color); // Do this ONCE
    }
}

class Renderer {
    draw(target) {
        // Just use the pre-computed value
        ctx.strokeStyle = this._lineColorRgba; 
    }
}
```

### ✅ DO: Optimize Data Iteration
Do not iterate your entire dataset inside `draw()`. Use the visible range provided by the chart or binary search to find the start index.

---

## 2. Interaction Standards (Double-Click & Modals)

To support Double-Click-To-Edit and Context Menus, every indicator **MUST** implement the following:

### 1. The `_type` Getter
This property routes the double-click event to the correct settings modal in `ChartContainer.tsx`.

```typescript
export class MyIndicator implements ISeriesPrimitive<Time> {
    // ...
    public get _type(): string {
        return 'my-indicator-id'; // MUST match the ID used in ChartContainer routing
    }
}
```

### 2. The `hitTest` Method
This method allows the `ChartContainer` to detect clicks on your indicator, even if it's not a standard drawing.

**Signature:**
```typescript
hitTest(x: number, y: number): { 
    hit: boolean, 
    externalId: string, 
    zOrder: string, 
    drawing?: any 
} | null
```

**Implementation Pattern:**
1. Convert `x` to `time` using `chart.timeScale().coordinateToTime(x)`.
2. Check if your indicator has data at this time.
3. If yes, return the hit object. Use `externalId` equal to your `_type`.

```typescript
hitTest(x: number, y: number) {
    const time = this._chart.timeScale().coordinateToTime(x);
    // Check if 'time' corresponds to a valid data point
    if (this.hasDataAt(time)) {
        return { 
            hit: true, 
            externalId: 'my-indicator-id', 
            zOrder: 'top', 
            drawing: this // Reference to self
        };
    }
    return null;
}
```

---

## 3. Lifecycle & Cleanup

### ✅ DO: Implement Destroy
Indicators are frequently added/removed. You MUST clean up listeners, intervals, and references.

```typescript
public destroy() {
    if (this._abortController) {
        this._abortController.abort(); // Cancel pending fetches
    }
    // Remove event listeners if any
}
```

### ✅ DO: Handle Detach
When `detached()` is called, ensure no pending updates try to run.

---

## 4. Checklist for New Indicators

- [ ] **Data**: Fetches only required range or handles pagination?
- [ ] **Rendering**: `draw()` loop is clean of heavy math?
- [ ] **Type**: `get _type()` returns a unique string ID?
- [ ] **Interaction**: `hitTest()` is implemented and accurate?
- [ ] **Cleanup**: `destroy()` cancels network requests?
- [ ] **Integration**: Added to `ChartContainer`'s `dblClickHandler` logic (if standard indicator) or handled generic via `_type`?

