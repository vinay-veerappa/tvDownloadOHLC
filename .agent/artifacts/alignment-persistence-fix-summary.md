# Text Alignment Persistence Fix - Summary

## Problem
Text alignment settings (horizontal: left/center/right, vertical: top/middle/bottom) were not persisting correctly across all drawing tools. When users changed alignment in the settings dialog, the changes would either:
1. Not save at all (reverting to defaults)
2. Save but not display correctly when reopening the dialog
3. Not work at all for tools using the generic PropertiesModal

## Root Cause
The issue was caused by **multiple incompatible alignment formats** flowing through the system, with bugs in the translation layer between them:

### Three Alignment Formats
1. **Flat format** (`alignmentHorizontal`, `alignmentVertical`) - Used by dedicated settings dialogs (RaySettings, TrendLineSettings, etc.)
2. **Nested object format** (`alignment.horizontal`, `alignment.vertical`) - Previously used by PropertiesModal (generic dialog)
3. **V2 Engine format** (`text.box.alignment.horizontal`, `text.box.alignment.vertical`) - Internal storage in drawing tools

### The V2OptionAdapter Bridge
The `V2OptionAdapter` translates between:
- **Flat format** (React UI dialogs) ↔ **V2 Engine format** (tool storage)

It had 4 critical bugs that prevented alignment from round-tripping correctly.

## Fixes Applied

### Fix 1: `toV1FlatOptions` - Reading alignment from tools
**File:** `web/lib/charts/v2/utils/v2-option-adapter.ts` (lines 112-122)

**Problem:** Only read from `text.box.alignment`, ignoring the legacy `text.alignment` property. If `box.alignment` wasn't set, alignment appeared as `undefined` in dialogs.

**Solution:** 
- Added fallback to read `text.alignment` when `box.alignment` is missing
- Map renderer's vertical `'middle'` to UI's `'center'` (the UI uses 'center' for the middle option)

```typescript
// Read alignment - prefer box.alignment, fall back to legacy text.alignment
if (v2Options.text.box?.alignment) {
    flat.alignmentHorizontal = v2Options.text.box.alignment.horizontal;
    // Map renderer's 'middle' to UI's 'center' for vertical alignment
    const rawVert = v2Options.text.box.alignment.vertical;
    flat.alignmentVertical = rawVert === 'middle' ? 'center' : rawVert;
}
// Fallback: if box alignment didn't provide horizontal, check legacy text.alignment
if (!flat.alignmentHorizontal && v2Options.text.alignment) {
    flat.alignmentHorizontal = v2Options.text.alignment;
}
```

### Fix 2: `toV2NestedOptions` - Writing alignment to tools
**File:** `web/lib/charts/v2/utils/v2-option-adapter.ts` (lines 262-277)

**Problem:** Used truthy checks (`||`) instead of `!== undefined` checks, which would fail for falsy values.

**Solution:**
- Changed to `!== undefined` checks
- Map UI's vertical `'center'` back to renderer's `'middle'`
- Sync both `text.box.alignment.horizontal` and legacy `text.alignment` property

```typescript
if (v1Options.alignmentVertical !== undefined || v1Options.alignmentHorizontal !== undefined) {
    const align = ensure(v2, 'text.box.alignment');
    if (v1Options.alignmentVertical !== undefined) {
        // Map UI's 'center' back to renderer's 'middle' for vertical alignment
        align.vertical = v1Options.alignmentVertical === 'center' ? 'middle' : v1Options.alignmentVertical;
    }
    if (v1Options.alignmentHorizontal !== undefined) {
        align.horizontal = v1Options.alignmentHorizontal;
    }

    // CRITICAL SYNC: Ensure text.alignment (internal) matches text.box.alignment.horizontal
    if (v1Options.alignmentHorizontal !== undefined) {
        text.alignment = v1Options.alignmentHorizontal;
    }
}
```

### Fix 3: Guard condition for text mapping
**File:** `web/lib/charts/v2/utils/v2-option-adapter.ts` (line 214)

**Problem:** The guard condition that controls whether the text mapping block runs didn't include alignment properties. If a user only changed alignment (without touching text, font, etc.), the entire text block was skipped.

**Solution:** Added alignment properties to the guard condition.

```typescript
if (v1Options.text !== undefined || v1Options.fontSize || v1Options.textColor || 
    v1Options.fontFamily || v1Options.backgroundVisible !== undefined || 
    v1Options.alignmentVertical !== undefined || v1Options.alignmentHorizontal !== undefined) {
```

### Fix 4: Ray dialog default spread
**File:** `web/components/chart-container.tsx` (lines 2304-2316)

**Problem:** `...DEFAULT_RAY_OPTIONS` was spread first, setting default alignment. When `selectedDrawingOptions?.alignmentHorizontal` was `undefined` (due to Bug 1), the default persisted instead of the real tool value.

**Solution:** Removed the default spread and used explicit fallbacks.

```typescript
options={{
    color: selectedDrawingOptions?.lineColor || selectedDrawingOptions?.color || DEFAULT_RAY_OPTIONS.color,
    width: selectedDrawingOptions?.lineWidth || selectedDrawingOptions?.width || DEFAULT_RAY_OPTIONS.width,
    style: selectedDrawingOptions?.lineStyle ?? selectedDrawingOptions?.style ?? DEFAULT_RAY_OPTIONS.style,
    opacity: selectedDrawingOptions?.opacity ?? DEFAULT_RAY_OPTIONS.opacity,
    text: selectedDrawingOptions?.text,
    textColor: selectedDrawingOptions?.textColor,
    fontSize: selectedDrawingOptions?.fontSize,
    bold: selectedDrawingOptions?.bold,
    italic: selectedDrawingOptions?.italic,
    alignmentVertical: selectedDrawingOptions?.alignmentVertical,
    alignmentHorizontal: selectedDrawingOptions?.alignmentHorizontal,
}}
```

### Fix 5: PropertiesModal alignment format
**File:** `web/components/properties-modal.tsx` (lines 681-705)

**Problem:** The generic PropertiesModal used a third alignment format (`options.alignment.horizontal/vertical`) that was never translated by the adapter. This broke alignment for all tools using the generic modal (horizontal-ray, arrow, extended-line, cross-line, circle, etc.).

**Solution:** Changed to use the flat format (`alignmentHorizontal`, `alignmentVertical`) that the adapter correctly handles.

```typescript
// Before (broken):
onClick={() => handleChange('alignment', { ...options.alignment, horizontal: 'left' })}
variant={options.alignment?.horizontal === 'left' ? "secondary" : "ghost"}

// After (working):
onClick={() => handleChange('alignmentHorizontal', 'left')}
variant={options.alignmentHorizontal === 'left' ? "secondary" : "ghost"}
```

## Impact

### Tools with Dedicated Settings Dialogs (Now Fixed)
- Ray
- Trend Line
- Horizontal Line
- Vertical Line
- Rectangle
- Text

### Tools Using Generic PropertiesModal (Now Fixed)
- Horizontal Ray ✅ (was completely broken)
- Extended Line ✅
- Arrow ✅
- Cross Line ✅
- Circle ✅
- Price Label ✅
- Callout ✅
- Triangle ✅
- Parallel Channel ✅
- Brush ✅
- Path ✅
- Highlighter ✅
- And any other tools using the generic modal

## Vertical Alignment: 'middle' vs 'center'

The UI uses `'center'` for the middle vertical alignment option (to match horizontal alignment naming), but the renderer internally uses `'middle'`. The adapter now correctly maps between these:

- **UI → Renderer:** `'center'` → `'middle'`
- **Renderer → UI:** `'middle'` → `'center'`
- **Other values:** `'top'` and `'bottom'` pass through unchanged

## Testing Checklist

To verify the fixes work:

1. **Ray tool:**
   - Draw a ray with text
   - Open settings, change alignment to "Right" + "Top"
   - Click OK
   - Reopen settings → Should show "Right" + "Top" (not defaults)
   - Text should render in the correct position

2. **Horizontal Ray tool (generic modal):**
   - Draw a horizontal ray
   - Open settings → Text tab
   - Add text, change alignment to "Left" + "Bottom"
   - Click OK
   - Reopen settings → Should show "Left" + "Bottom"
   - Text should render in the correct position

3. **Middle alignment:**
   - For any tool, set vertical alignment to "Middle"
   - Save and reopen → Should show "Middle" (not "Top" or "Bottom")
   - Text should render vertically centered

4. **Alignment-only changes:**
   - Draw a tool with default text
   - Open settings, ONLY change alignment (don't touch text, color, font, etc.)
   - Save and reopen → Alignment should persist

## Architecture Notes

### All Tools Are V2
There are no "V1 tools" left in the codebase. All tools extend `BaseLineTool` and are registered in `sandbox-manager.ts`. The "V1/V2" naming refers to **option formats**, not tool architectures:

- **V2 Nested format** = Internal tool storage (`text.box.alignment.horizontal`)
- **V1 Flat format** = React UI dialogs (`alignmentHorizontal`)

The `V2OptionAdapter` is the bridge between these formats. The naming could be improved (e.g., `OptionFormatAdapter` with `toFlatFormat` / `toNestedFormat`), but this is a cosmetic change.

### Why Multiple Alignment Properties?

The renderer reads alignment from multiple sources for backwards compatibility:

```typescript
// Horizontal alignment with fallback chain
const hAlign = (data.text?.box?.alignment?.horizontal || data.text?.alignment || 'center').toLowerCase();

// Vertical alignment with fallback
const vAlign = (data.text?.box?.alignment?.vertical || 'middle').toLowerCase();
```

The adapter now ensures both paths are set when alignment changes, so the renderer always finds the correct value regardless of which property it checks first.

## Future Improvements

1. **Rename V2OptionAdapter** to something clearer like `OptionFormatAdapter`
2. **Consolidate alignment properties** in the V2 engine to use only `text.box.alignment.*` (remove legacy `text.alignment`)
3. **Create dedicated settings dialogs** for remaining tools instead of using the generic PropertiesModal (better UX, tool-specific options)
4. **Investigate floating toolbar** not appearing for some tools (separate issue from alignment)
