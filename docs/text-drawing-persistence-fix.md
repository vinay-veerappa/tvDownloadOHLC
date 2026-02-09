# Text Drawing Fixes

This document describes two related fixes for text drawing tools in the V2 drawing engine.

## Fix 1: Text Drawing Persistence

### Problem
Text drawings were disappearing during data loading and scrolling because coordinate calculations failed when new data was loaded. When the chart loads new data or the user scrolls, the time scale temporarily returns invalid coordinates (NaN, undefined, or out of bounds) for the drawing tools' anchor points, causing the text renderer to fail and the drawings to vanish.

### Root Cause Analysis

The issue was a **two-level problem**:

#### Level 1: Renderer Early Exit (generic-renderers.ts)
The `TextRenderer` class was exiting early in `draw()`, `hitTest()`, and `isOutOfScreen()` when current data points were missing, even though cached coordinates might be available.

#### Level 2: Pane View Logic (text.ts)
The `TextPaneViewV2._updateImpl()` method only called `setData()` and appended the renderer when `_points.length >= 1`. When point conversion failed during data loading, the renderer was never added to the composite, so it never drew - even though it had cached data.

### Solution

Implemented a **multi-layer fix** that ensures text drawings persist during temporary coordinate calculation failures:

#### 1. TextPaneViewV2._updateImpl() (text.ts)
- **Before**: Only called `setData()` and appended renderer when `_points.length >= 1`
- **After**: Always calls `setData()` and appends the renderer when either:
  - Current points are available (`_points.length >= 1`)
  - OR point conversion explicitly failed (`pointsValid === false`)
- Passes `undefined` for points when conversion fails, allowing the renderer to use its cache

#### 2. TextRenderer.draw() (generic-renderers.ts)
- **Before**: Returned early if `_data.points` was empty/undefined AND no `box` was defined
- **After**: Also allows drawing if `_lastGoodInternalData` exists (cached coordinates)

#### 3. TextRenderer.hitTest() (generic-renderers.ts)
- **Before**: Returned null if `_data.points` was empty/undefined AND no `box` was defined
- **After**: Also allows hit testing if `_lastGoodPolygonPoints` exists (cached polygon)
- Added null-safe property access for data destructuring

#### 4. TextRenderer.isOutOfScreen() (generic-renderers.ts)
- **Before**: Returned true (out of screen) if no current data points
- **After**: Also allows rendering if `_lastGoodInternalData` exists

---

## Fix 2: Inline Text Editing Save

### Problem
When editing text inline (double-click to edit, then click away to save), the text changes were being lost. The console showed:
```
[ChartContainer] handleInlineSave: Tool with ID xxx is NOT InlineEditable. Missing methods?
```

All InlineEditable methods (`setText`, `setEditing`, `getText`, etc.) were returning `false`.

### Root Cause

The issue was in `chart-container.tsx`:

1. The `handleSelectionChanged` callback receives **export data objects** (from `tool.getExportData()`) rather than actual tool instances
2. The export data was stored in `selectedDrawingRef.current`
3. When `handleInlineSave` was called, it first checked `selectedDrawingRef.current`
4. Since the export data object has the same `.id` property as the tool ID, the code thought it found the tool
5. But the export data is a **plain object** without the class methods (`setText`, `setEditing`, etc.)

### Solution

Modified `handleInlineSave` and `handleInlineCancel` in `chart-container.tsx` to **always** use `v2SandboxRef.current?.plugin.getLineTool(toolId)` to retrieve the actual tool instance, rather than relying on `selectedDrawingRef.current` which may contain export data.

#### Before:
```typescript
let tool = selectedDrawingRef.current;
const currentId = tool ? (typeof (tool as any).id === 'function' ? (tool as any).id() : (tool as any).id) : null;

if (!tool || currentId !== toolId) {
    tool = v2SandboxRef.current?.plugin.getLineTool(toolId) || null;
}
```

#### After:
```typescript
// CRITICAL FIX: Always use getLineTool() to get the actual tool instance.
// selectedDrawingRef.current may contain the EXPORT DATA (plain object from getExportData())
// rather than the actual tool instance that has the setText/setEditing methods.
const tool = v2SandboxRef.current?.plugin.getLineTool(toolId) || null;
```

---

## Testing Recommendations

### For Persistence Fix:
1. Create a text drawing on the chart
2. Load new data (e.g., change timeframe)
3. Scroll the chart rapidly
4. Verify the text drawing remains visible throughout
5. Verify drawing updates to correct position after data loads
6. Verify the text can still be clicked/selected during data loading

### For Inline Editing Fix:
1. Create a text drawing on the chart
2. Double-click on the text to enter editing mode
3. Modify the text content
4. Click outside the text area to save
5. Verify the text is updated and persisted
6. Reload the page and verify the text is still the updated value

---

## Related Files

- `web/lib/charts/v2/core/rendering/generic-renderers.ts` - TextRenderer implementation
- `web/lib/charts/v2/tools/text.ts` - Text tool and pane view
- `web/lib/charts/v2/core/views/line-tool-pane-view.ts` - Base pane view with point conversion
- `web/lib/charts/v2/core/model/base-line-tool.ts` - Base class for drawing tools
- `web/components/chart-container.tsx` - Chart container with inline editing handlers
- `web/lib/charts/v2/sandbox-manager.ts` - V2 sandbox manager with event handling

## Notes

- The persistence fix is defensive and doesn't change behavior during normal operation
- The inline editing fix ensures we always get the actual tool instance with methods
- Both fixes apply to all text-based drawing tools (Text, Note, Callout, etc.)
- Console warnings are intentionally verbose for debugging

