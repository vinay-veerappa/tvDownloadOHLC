# Drawing Tool Implementation Guide

This guide outlines the standard architecture, patterns, and requirements for implementing drawing tools in this project. All new drawing tools must adhere to these standards to ensure consistency, proper rendering, and full feature support (styling, text, selection).

## 1. Architecture Overview

Each drawing tool is a **Lightweight Charts Plugin** (`ISeriesPrimitive`). It consists of three main components:

1.  **The Primitive (`ToolName`)**: The main class implementing `ISeriesPrimitive`. It holds the state (points, logic, options, text label) and manages lifecycle.
2.  **The Pane View (`ToolNamePaneView`)**: A bridge between the Primitive and the Renderer. It prepares data for rendering.
3.  **The Renderer (`ToolNameRenderer`)**: A lightweight class responsible for the actual Canvas API drawing calls.

---

## 2. Standard Options Interface

All tools must accept an options object that extends the basic styling properties.

**Critical Rule:** The Renderer must **ALWAYS** use the live options object from the source primitive, not a copy stored at construction time.

### Common Properties
Every tool's options interface should include:
```typescript
interface ToolOptions {
    color: string;
    width: number;
    lineStyle: number; // 0=Solid, 1=Dotted, 2=Dashed, etc.
    text?: string;     // Annotation text
    textColor?: string;
    showLabel?: boolean;
    // ... tool specific options
}
```

### ⚠️ Common Pitfall: Stale Options
**Do NOT** do this in your Pane View:
```typescript
// BAD
constructor(source, options) {
    this._options = options; // Stores a reference to the INITIAL options object
}
renderer() {
    return new Renderer(..., this._options); // Renderer sees old options even after updates!
}
```

**DO** this instead:
```typescript
// GOOD
renderer() {
    return new Renderer(..., this._source._options); // Always reads the current options from the source
}
```

---

## 3. Rendering Logic

Renderers must implement the `draw(target)` method and use the `useBitmapCoordinateSpace` scope.

### Coordinate Space & Pixel Ratio
Always scale coordinates and sizes by `horizontalPixelRatio` (`hPR`) and `verticalPixelRatio` (`vPR`).

```typescript
draw(target: any) {
    target.useBitmapCoordinateSpace((scope: any) => {
        const ctx = scope.context;
        const hPR = scope.horizontalPixelRatio;
        const vPR = scope.verticalPixelRatio;

        // Scale coordinates
        const x = Math.round(this._x * hPR);
        const y = Math.round(this._y * vPR);
        
        // Scale stroke width
        ctx.lineWidth = Math.max(1, this._options.width * hPR);
    });
}
```

### Line Styling Support
Use the global `getLineDash` utility to support standard line styles.

```typescript
import { getLineDash } from "../chart-utils";

// Inside draw()
ctx.setLineDash(getLineDash(this._options.lineStyle || 0).map(d => d * hPR));
ctx.stroke();
ctx.setLineDash([]); // Reset immediately after
```

---

## 4. Text Label Integration

Don't implement text drawing manually. Use the standard `TextLabel` primitive.

1.  **Import**: `import { TextLabel } from "./text-label";`
2.  **Instantiate**: Create `this._textLabel` in your tool's constructor.
3.  **Update**: Call `this._textLabel.update(x, y, options)` in your `applyOptions` and update logic.
4.  **Draw**: Pass the `_textLabel` to your renderer and call `textLabel.draw()` inside the render loop.

```typescript
// In Tool.applyOptions
if (options.text) {
   this._textLabel.update(0, 0, {
       text: options.text,
       borderStyle: options.lineStyle, // Sync line style if needed
       // ...
   });
}
```

## 5. Selection & hitTest

While the standard `hitTest` logic is often handled by the `useDrawingManager` hook, your tool logic (or renderer) often needs to know if it is selected to draw handles.

*   **State**: Maintain `_selected: boolean` in the Primitive.
*   **Visual Feedback**: If `_selected` is true, draw handles (circles/squares) on anchor points in the Renderer.

## 6. Checklist for New Tools
1.  [ ] Does it implement `ISeriesPrimitive`?
2.  [ ] Does it accept and use `lineStyle`?
3.  [ ] does it use `hPR`/`vPR` for all drawing?
4.  [ ] Does it support `TextLabel`?
5.  [ ] Does the Pane View reference `source._options` directly?
6.  [ ] Are optional properties handled (e.g. `|| 0`)?
