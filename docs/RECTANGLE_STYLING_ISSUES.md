# V2 Drawing Tools - Floating Toolbar & Settings Implementation

## Status: Active

## Completed Tasks

### Phase 1: Keyboard Shortcuts
- [x] Add Delete/Backspace keyboard support for deleting selected drawings
- [x] Add Escape key to deselect drawings
- [x] Fix stale closure issue by getting selected tool from V2 plugin directly

### Phase 2: Floating Toolbar Integration
- [x] Toolbar position calculation (initially floating, now pinning)
- [x] Tool type alias mapping (V2 PascalCase → existing kebab-case configs)
- [x] Implement pinned mode in FloatingToolbar
- [x] Pin toolbar to bottom of chart in ChartContainer
- [x] Implement React Portal for reliable toolbar rendering (bypass CSS constraints)
- [x] Fixed `DRAWING_TYPES` case-sensitivity mismatch causing selection clearing
- [x] Verify quick action buttons work (color, width, style)
- [x] Verify Settings button opens dialog
- [x] Fix redundant deselection in InteractionManager during panning
- [x] Fix legacy click handler in ChartContainer interfering with V2 selection


### Phase 3: Settings Dialog Integration
- [x] Ensure DrawingSettingsDialog works with V2 tools
- [x] Connect style tab options to V2 tool applyOptions
- [x] Test template save/load
- [x] Add coordinates tab for V2 tools
- [x] Add text tab for text-capable tools

### Phase 4: Per-Tool Settings Tabs (V2 Drawing Tools Integration)
- [x] Create `v2-option-adapter.ts` for bidirectional mapping
- [x] Integrate adapter into `ChartContainer.tsx` (openProperties/handlePropertiesSave)
- [x] Standardize `onApply` interfaces for all core tools
- [x] Enable Style, Text, and Coordinates tabs for all integrated V2 tools
- [x] Fix `[object Object]` bug in Text tab (Fixed: Added defensive handling in `TextSettingsTab` and strict sanitization in adapter)
- [x] Fix missing TrendLine style checkboxes (Fixed: Usage of normalized tool types in `ChartContainer` ensured correct dialog opening)
- [x] Verify horizontal/vertical line coordinate editing
- [x] **Debugging Phase 5**: Fix Rectangle Background Color Not Applying
  - [x] Investigate `RectangleRenderer` (found it ignores `opacity`)
  - [x] Update `RectangleRenderer` to support opacity (Implemented `applyOpacity` helper)
  - [x] Fix Color Input Crash: Added `toHex` sanitizer in `V2OptionAdapter`
  - [x] Fix Initial Opacity: Implemented `getOpacity` in Adapter to parse defaults
  - [x] **Robustness**: Updated `applyOpacity` to strictly enforce opacity override on all color formats.
  - [x] **Fix State Reset**: Patched `RectangleSettings.tsx` to prevent option reset on re-render.
- [x] Fix Rectangle Text Visibility on Chart (Fixed: Integrated `TextRenderer` into `RectangleV2`)
- [x] Fix `TextRenderer` Runtime Crashes (Fixed: Added defensive checks for undefined text AND font family in `generic-renderers.ts`)
- [x] **Debugging Phase 6**: Fix Runtime Crash in TextRenderer
    - [x] Analyze stack trace (identified `ensureDefined` on `alignment`)
    - [x] Apply defensive fix for `alignment` access
- [x] **Debugging Phase 7**: Fix Text Persistence and Synchronization
    - [x] Fix Text Visibility: Updated `RectangleRenderer` to use correct point data (Points instead of Box) for TextRenderer.
    - [x] Fix Text Alignment: Inverted vertical alignment logic in `TextRenderer` to ensure text renders *inside* the box.
    - [x] Fix "Reverting" Issue: Implemented merge logic in `ChartContainer.handlePropertiesSave` to preserve existing options during partial updates.
    - [x] Fix Dialog Sync (Phase 1): Updated `RectangleSettings` to react to external `options` prop changes.
    - [x] Fix Dialog Sync (Phase 2): Fixed `ChartContainer.useEffect` to adapt nested V2 options from property access.
    - [x] Fix Dialog Sync (Phase 3): Fixed `ChartContainer.openProperties` to adapt nested V2 options unconditionally.
    - [x] Fix Usage of `fillColor` vs `background.color`: Updated `V2OptionAdapter` to handle both.
    - [x] Fix Circular Reference Fix: Patched `V2OptionAdapter` to handle `text` object vs string safely.

### Phase 8: Fixing Rectangle Specific Rendering
- [x] Fix Text Alignment: Investigate why text alignment changes are not applying visually.
- [x] Fix Midline/Quarter Lines: Investigate missing rendering logic for `showMidline` and `showQuarterLines`.
- [x] Verify `RectangleRenderer` implementation for these features.

### Phase 9: Enhanced Rectangle Styling (User Request)
- [x] Implement Separate Line Options for Midline (Color, Width, Style).
- [x] Implement Separate Line Options for Quarter Lines (Color, Width, Style).
- [x] Update `types.ts`, `RectangleSettings`, `RectangleRenderer`, and Adapters.
- [x] Create Architecture Documentation: `DESIGN_DRAWING_TOOLS_V2.md`.

### Phase 10: Bug Fixes & Refinements
- [x] Fix Object Tree Settings Button: Debug `onEditDrawing` callback in `ChartContainer`.
    - [x] V2 Tool Lookup: Implemented lookup via `v2SandboxRef` in `handleEditDrawing`.
- [x] Fix Text Alignment Re-render: Fixed by deep copying text options in `RectanglePaneViewV2` to force cache invalidation.
- [x] Fix Style Independence: Updated `RectangleSettings.tsx` to save fallback colors explicitly when changing styles.

- [x] Refactor RectangleSettings to separate View and Dialog for reuse
- [x] Integrate RectangleSettingsView into PropertiesModal to fix style sync issues
- [ ] Final verification and documentation


### Phase 11: Unify Settings Dialogs
- [x] Unify Settings Dialogs
    - [x] Ensure Object Tree "Edit" opens the same V2 dialog as Toolbar
        - Updated `ChartContainer.tsx` to explicitly route 'rectangle' edits to `RectangleSettingsDialog`.
        - Verified `openProperties` also handles 'rectangle'.
    - [x] Fix accessible title warning in `RectangleSettingsDialog`

## Files Modified
- `web/components/chart-container.tsx` - Keyboard handler, toolbar position
- `web/lib/toolbar-configs.ts` - V2 tool type aliases
- `web/lib/charts/v2/core/core-plugin.ts` - Added getSelectedTool()
- `web/lib/charts/v2/core/interaction/interaction-manager.ts` - Added getSelectedTool()
- `web/lib/charts/v2/sandbox-manager.ts` - Fixed tool.id() call
- `web/lib/charts/v2/utils/v2-option-adapter.ts` - Added text sanitization
- `web/components/drawing-settings/TextSettingsTab.tsx` - Added defensive text rendering

## Known Issues (To Be Fixed Later)

### Rectangle Midline/Quarter Line Styling Not Persisting

**Status**: Parked

**Symptoms**:
1. Midline and Quarter Line style options (color, width, style) do not persist correctly when changed in the dialog
2. When reopening the dialog, values reset to defaults (blue, solid)
3. Style changes (Solid/Dashed/Dotted) are particularly prone to resetting
4. Dialog may not close when Save button is pressed

**Root Cause Analysis**:
- The `selectedDrawingOptions` state in `ChartContainer.tsx` is updated multiple times during dialog open, causing stale values
- React re-renders cause the dialog's `options` prop to change, triggering the useEffect multiple times
- Even with the `initializedRef` guard, the FIRST render may receive options without the midline/quarter values
- The fallback logic (`midlineStyle ?? borderStyle`) causes incorrect defaults when values are undefined

**Attempted Fixes** (partial progress, not fully resolved):
1. Added fallback values for midline/quarter properties in ChartContainer dialog options
2. Changed RectangleSettingsDialog useEffect to only initialize once per open session (using ref)
3. Fixed onChange handlers to only update properties that actually changed
4. Added `type="button"` to Save/Cancel buttons
5. Nested midline/quarterLine options under `rectangle` in V2OptionAdapter

**Files Involved**:
- `web/components/chart-container.tsx` - Dialog props and state management
- `web/components/drawing-settings/RectangleSettings.tsx` - Dialog component
- `web/lib/charts/v2/utils/v2-option-adapter.ts` - Option conversion
- `web/lib/charts/v2/tools/rectangle.ts` - Tool implementation

**Next Steps for Future Session**:
1. Add comprehensive logging to trace exact values at each step of the flow
2. Consider using `useMemo` to stabilize the options object passed to dialog
3. Investigate if there's a race condition between `setSelectedDrawingOptions` and dialog render
4. Consider separating the dialog state from selection state to prevent interference
5. May need to refactor how options flow from tool → adapter → state → dialog
