# Developer Guide & Cookbook

**Version:** 0.4.0
**Last Updated:** December 09, 2025

This guide provides step-by-step "Recipes" for extending the platform. Follow these patterns to ensure consistency and prevent regression.

---

## 🧪 Recipe 1: Adding a New Indicator

Indicators in this project use the **Lightweight Charts Primitive** architecture, not just simple line series. This allows for custom rendering (boxes, text, shapes).

### Step 1: Define the Options Interface
Create a file in `web/lib/charts/indicators/<name>.ts`. Start by defining what can be customized.
```typescript
export interface MyIndicatorOptions {
    color: string;
    opacity: number;
    showLabel: boolean;
}

export const DEFAULT_MY_INDICATOR_OPTIONS: MyIndicatorOptions = {
    color: '#00FF00',
    opacity: 0.5,
    showLabel: true
};
```

### Step 2: Create the Renderer
volume-profile-calc.tsThe renderer is responsible for the actual Canvas API calls. It is recreated purely for drawing frames.
```typescript
class MyIndicatorRenderer {
    constructor(private main: MyIndicator) {}

    draw(target: any) {
        target.useBitmapCoordinateSpace((scope: any) => {
            const ctx = scope.context;
            // logic to draw using ctx
            // Use scope.horizontalPixelRatio for X-axis scaling
            // Use scope.verticalPixelRatio for Y-axis scaling
        });
    }
}
```

### Step 3: Create the Primitive Class
The Primitive manages state, data fetching, and the lifecycle.
```typescript
export class MyIndicator implements ISeriesPrimitive<Time> {
    _options: MyIndicatorOptions;
    // ... setup properties

    constructor(chart, series, options) {
        this._options = { ...DEFAULT_MY_INDICATOR_OPTIONS, ...options };
        // Fetch data here if needed
    }

    paneViews() {
        // Return the renderer
        return [{
            renderer: () => new MyIndicatorRenderer(this)
        }];
    }
}
```

### Step 4: Integration & Registration
1.  **Instantiate**: Add to `web/components/chart-container.tsx`. Import your class, add a `ref`, and handle the `useEffect` lifecycle to `attachPrimitive` and `updateOptions`.
2.  **Indicators Menu**: Add your indicator to the list in `web/components/indicators-dialog.tsx`.
3.  **Right Sidebar**: Update `web/components/chart-wrapper.tsx` to handle the label and "edit" click actions.
4.  **Settings Modal**:
    *   Create `web/components/settings/<name>-settings-view.tsx`.
    *   Add your settings view to `web/components/properties-modal.tsx` and handle the state injection.

---

## ✏️ Recipe 2: Adding a New Drawing Tool

Drawings are more complex because they require user interaction (Mouse clicks).

### Architecture
1.  **Renderer**: Draws the shape on canvas.
2.  **Primitive**: Holds the state (Points `p1, p2`), handles `hitTest` (for selection/hover).
3.  **Tool**: Listens to Chart events (`click`, `crosshairMove`) and creates/updates the Primitive.

### Step 1: The Primitive (State & HitTest)
Create `web/lib/charts/plugins/<tool-name>.ts`.
```typescript
export class MyDrawing implements ISeriesPrimitive {
    // ... holds p1, p2
    
    hitTest(x, y) {
        // Return an object if the mouse (x,y) is near the drawing
        // Used for hover effects and selection
        if (isNear) return { cursorStyle: 'move', zOrder: 'top' };
        return null;
    }
}
```

### Step 2: The Tool (Interaction)
The Tool acts as the controller.
```typescript
export class MyDrawingTool {
    startDrawing() {
        this._chart.subscribeClick(this._onClick);
        this._chart.subscribeCrosshairMove(this._onMove);
    }

    _onClick(param) {
        // 1st Click: Create instance of MyDrawing and attachPrimitive
        // 2nd Click: Finalize drawing, unsubscribe events
    }
}
```

### Step 3: Registration
1.  Add the tool to `web/components/chart/drawing-toolbar.tsx` (The UI button).
2.  Handle the selection logic to instantiate `MyDrawingTool` and call `startDrawing()`.

---

## 🚫 Common Pitfalls (Read Before Committing)

### 1. PowerShell & CLI
*   **The `&&` Operator**: Standard PowerShell (v5.1 default on Win10/11) does **NOT** support `&&`. Use `;` or install PowerShell 7 (`pwsh`).
    *   *Bad:* `git add . && git commit` (Fails on vanilla Windows)
    *   *Good:* `git add .; git commit`
*   **Quoting Arguments**: PowerShell parses `!` as a special operator (history expansion) sometimes.
    *   *Bad:* `--ticker ES1!`
    *   *Good:* `--ticker "ES1!"` (Always quote strings with special chars).

### 2. Git Workflow
*   **Empty Commits**: Don't commit if `git status` says "working tree clean". Check status first.
*   **Tags**: Tags are not pushed by `git push`.
    *   *Correct:* `git push origin <tagname>` or `git push --tags`.
*   **Upstream**: New branches need upstream set explicitly.
    *   *Correct:* `git push -u origin <branchname>`.

### 3. Lightweight Charts
*   **Coordinate Scaling**: `target.useBitmapCoordinateSpace` gives you a **scaled** context.
    *   Coordinates from `timeScale.timeToCoordinate` are **Logical (CSS pixels)**.
    *   You **MUST** multiply them by `scope.horizontalPixelRatio` before drawing on the canvas.
    *   *Failing to do this results in blurry lines or misaligned shapes.*
*   **Null Checks**: Always check if `timeToCoordinate` or `priceToCoordinate` returns `null` (off-screen) before using usage.
