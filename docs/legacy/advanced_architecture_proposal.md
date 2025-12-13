# Advanced Architecture Proposal

## 🎯 Objective
To support advanced features (Text, Templates, Nested Options) with minimal rework, we need to upgrade our architecture from "Simple Plugins" to a "Robust Drawing System".

## 1. Serialization (Save/Load) 💾
**Current State:** We rely on `options` for state.
**Problem:** Complex state (like "which Fibonacci levels are enabled") might not map 1:1 to visual options. We also need to save/load from JSON.
**Proposal:** Standardize `toJSON()` and `fromJSON()`.

```javascript
class StandardPlugin {
    // ...
    toJSON() {
        return {
            type: 'Rectangle',
            points: [this._p1, this._p2],
            options: this._options, // Nested structure
            text: this._textConfig // Separate text state
        };
    }

    static fromJSON(chart, series, json) {
        return new Rectangle(chart, series, json.points[0], json.points[1], json.options);
    }
}
```

## 2. Composition over Inheritance (The "Text" Problem) 🧩
**Current State:** Each tool implements its own rendering.
**Problem:** We need Text on *every* tool. Duplicating text rendering logic in `Rectangle`, `TrendLine`, etc., is bad.
**Proposal:** Create reusable **Sub-Primitives**.

*   **`TextLabelPrimitive`**: A class that handles measuring and drawing text.
*   **Usage:** The `Rectangle` class *owns* an instance of `TextLabelPrimitive`.
*   **Rendering:** Inside `RectanglePaneView`, we delegate to `this._textLabel.draw(ctx)`.

```javascript
class Rectangle {
    constructor(...) {
        this._textLabel = new TextLabelPrimitive(options.text);
    }
    
    updateAllViews() {
        // Update text position based on Rectangle coordinates
        this._textLabel.updatePosition(this._getCenter());
    }
}
```

## 3. UI Decoupling (Schema-Based UI) 🎛️
**Current State:** `drawings.js` hardcodes inputs: `if (rect) showColorInput()`.
**Problem:** Adding "Midline", "Quarter Lines", "Text Alignment" requires massive updates to `drawings.js`.
**Proposal:** Plugins should **declare** their properties.

```javascript
// In Rectangle.js
getPropertiesSchema() {
    return [
        { group: 'Style', type: 'color', key: 'borderColor', label: 'Border' },
        { group: 'Style', type: 'number', key: 'borderWidth', label: 'Width' },
        { group: 'Text', type: 'text', key: 'textContent', label: 'Label' },
        { group: 'Text', type: 'select', key: 'textAlign', options: ['center', 'left'] }
    ];
}
```
*   **Benefit:** The Properties Panel becomes a generic "Schema Renderer". It loops through the schema and generates tabs/inputs automatically. Adding a new feature to Rectangle doesn't require touching `drawings.js`.

## 4. State Management (The "Draft" Problem) 📝
**Current State:** Tools create "live" drawings immediately.
**Problem:** "Preview" drawings pollute the series until finalized.
**Proposal:** Explicit **Draft Mode**.
*   The `Tool` holds a `DraftDrawing` (not attached to series, or attached to a temporary "Overlay" series).
*   Only on "Mouse Up" (finalize) is it converted to a real `Drawing` and added to the main list.

## 🚀 Recommendation
Before implementing features, we should:
1.  **Refactor Properties Panel:** Make it dynamic/schema-driven. This is the biggest time-saver.
2.  **Create `TextLabelPrimitive`:** Build the shared text logic once.
3.  **Implement `toJSON`:** Essential for the "Templates" feature.
