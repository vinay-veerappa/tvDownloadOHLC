# PineDrawing v3 Split Library — Pre-Publication Validation Checklist

## Purpose

This checklist documents all validation steps to be completed before publishing the split libraries to TradingView. Each library is published sequentially, and the indicator cutover begins only after Core and first-tier families are live.

---

## Library Publication Order

**Publication Sequence** (publish in this order):
1. ✅ **PineDrawingCore/1** (foundation, no dependencies)
2. ✅ **PineDrawingHorizontalLevels/1** (depends on Core)
3. ✅ **PineDrawingZones/1** (depends on Core)
4. ✅ **PineDrawingTables/1** (depends on Core)
5. ✅ **PineDrawingVerticalMarkers/1** (depends on Core)
6. ✅ **PineDrawingMarkers/1** (depends on Core)
7. ✅ **PineDrawingComposites/1** (depends on Core, Zones, VerticalMarkers)
8. ✅ **PineDrawingSpecialized/1** (depends on Core)

---

## Pre-Publication Phase: Local Validation

### ✅ Code Quality Checks

- [ ] **Syntax Validation**
  - [ ] PineDrawingCore.pine compiles without syntax errors
  - [ ] PineDrawingHorizontalLevels.pine compiles without syntax errors
  - [ ] PineDrawingZones.pine compiles without syntax errors
  - [ ] PineDrawingTables.pine compiles without syntax errors
  - [ ] PineDrawingVerticalMarkers.pine compiles without syntax errors
  - [ ] PineDrawingMarkers.pine compiles without syntax errors
  - [ ] PineDrawingComposites.pine compiles without syntax errors
  - [ ] PineDrawingSpecialized.pine compiles without syntax errors
  - **Command:** Use Pine editor syntax check or compile indicator that imports each library

- [ ] **Export Function Coverage**
  - [ ] All 27 exported items verified from monolithic source
  - [ ] Exported types: `PineDrawingState`, `LabelRegistry` ✓ in Core
  - [ ] Lifecycle functions: `f_new_drawing_state`, `f_new_label_registry`, `f_label_registry_begin`, etc. ✓ in Core
  - [ ] Label registry functions: `f_label_registry_clear`, `f_label_registry_push`, `f_label_registry_push_ex`, etc. ✓ in Core
  - [ ] Format helpers: `f_format_template`, `f_merge_threshold_for_symbol` ✓ in Core
  - [ ] Style resolvers: `f_resolve_color`, `f_display_profile_label_size`, `f_display_profile_table_size`, `f_display_profile_width`, `f_display_profile_transparency`, `f_line_style`, `f_display_size`, `f_text_size`, `f_table_pos` ✓ in Core
  - [ ] Primitive wrappers: `f_draw_line`, `f_draw_or_box`, `f_draw_hist_band`, `f_draw_stat_label`, `f_draw_time_bar`, `f_draw_vline`, `f_draw_day_separator` ✓ in Core
  - [ ] Registry drawing: `f_label_registry_draw`, `f_label_registry_flush`, `f_label_registry_draw_merged` ✓ in Core
  - [ ] Family-specific semantic wrappers ✓ in respective families
  - **Document:** See SPLIT_MIGRATION_MAP.md

- [ ] **Import Path Correctness**
  - [ ] All family libraries import from `vveerappa/PineDrawingCore/1` (not local workspace paths)
  - [ ] Composites imports Core, Zones, VerticalMarkers (no circular dependencies)
  - [ ] No undefined symbol references in any family library
  - [ ] All public APIs referenced in monolithic indicator are present in split families
  - **Check:** Search for `vveerappa/` import statements in each file

- [ ] **Documentation Completeness**
  - [ ] Library header comment with v1.0 version and purpose in all 8 libraries
  - [ ] Doc comments (/// blocks) on all exported functions
  - [ ] Doc comments on both exported types (`PineDrawingState`, `LabelRegistry`)
  - [ ] Parameter descriptions and return value documentation for all exports
  - [ ] Dependency section in headers (e.g., "Depends on: PineDrawingCore/1")
  - **Check:** Run through README.md file to reference doc comment format

- [ ] **Line Count Verification**
  - [ ] PineDrawingCore.pine: ~750 lines (includes all primitives + registry logic + helpers)
  - [ ] PineDrawingHorizontalLevels.pine: ~30 lines (semantic wrappers)
  - [ ] PineDrawingZones.pine: ~40 lines (semantic wrappers)
  - [ ] PineDrawingTables.pine: ~35 lines (cell helpers)
  - [ ] PineDrawingVerticalMarkers.pine: ~25 lines (vline/separator wrappers)
  - [ ] PineDrawingMarkers.pine: ~30 lines (text marker wrappers)
  - [ ] PineDrawingComposites.pine: ~40 lines (composite helpers)
  - [ ] PineDrawingSpecialized.pine: ~25 lines (placeholder template)
  - **Total:** ~900 lines split vs. ~500 in monolithic (overhead acceptable)
  - **Check:** `wc -l *.pine` in lib directory

- [ ] **No Private Function Collisions**
  - [ ] Private helper functions prefixed consistently (e.g., `f_clear_boxes`, `f_registry_overlap`, etc.)
  - [ ] No exported private functions
  - [ ] No duplicate function names across families
  - **Check:** Grep for `export f_` and `f_` to verify naming

- [ ] **Type Definition Consistency**
  - [ ] `PineDrawingState` type fields match across all usages (boxes, lines, labels)
  - [ ] `LabelRegistry` type fields all match (11 arrays with consistent names)
  - [ ] No type redefinition in family libraries
  - **Check:** Compare type definitions in Core vs. monolithic source

---

## Publication Phase: TradingView Community Library

### ✅ Account & Permissions

- [ ] TradingView account with library publication rights verified
- [ ] Author name set correctly (vveerappa)
- [ ] Profile picture/bio updated (optional)

### ✅ Publication Steps (Sequential)

#### Step 1: Publish PineDrawingCore/1

- [ ] Open Pine editor with PineDrawingCore.pine
- [ ] Click "Publish Library" button
- [ ] Set:
  - [ ] Library name: `PineDrawingCore`
  - [ ] Version: `1` (first release)
  - [ ] Category: "Drawing" or "Utility"
  - [ ] Description: "Core drawing state, types, label registry, and primitive wrappers for PineDrawing family libraries"
  - [ ] Visibility: Public
  - [ ] Release notes: "Initial v3 split-library release. Foundation layer with types, lifecycle, label registry, and drawing primitives."
- [ ] Accept TradingView terms
- [ ] Publish
- [ ] **Verify:** Check that `vveerappa/PineDrawingCore/1` is now accessible in the community library

#### Steps 2-6: Publish Family Libraries

Repeat for each library (HorizontalLevels, Zones, Tables, VerticalMarkers, Markers, Composites, Specialized):

- [ ] Open Pine editor with the library file
- [ ] Verify import paths now resolve (all should import `vveerappa/PineDrawingCore/1` successfully)
- [ ] Click "Publish Library" button
- [ ] Set:
  - [ ] Library name: Match filename (e.g., "PineDrawingZones")
  - [ ] Version: `1`
  - [ ] Category: "Drawing" or "Utility"
  - [ ] Description: [Semantic purpose from header comment]
  - [ ] Visibility: Public
  - [ ] Release notes: "Initial v3 split-library release. Semantic renderers for [domain]."
- [ ] Publish
- [ ] **Verify:** Check that library is accessible in the community library

---

## Post-Publication Phase: Indicator Cutover

### ✅ Cutover Validation

- [ ] All 8 split libraries successfully published to TradingView
- [ ] All libraries import correctly from published paths (no local references)
- [ ] Create a cutover branch in git: `refactor/indicator-split-imports`
- [ ] Use ANALYTICS_IMPORT_MIGRATION_CHECKLIST.md to execute import cutover in DailyNYLevelsAnalytics.pine
  - [ ] Phase 1: Replace types and lifecycle imports
  - [ ] Phase 2: Replace drawing function imports
  - [ ] Phase 3: Replace table/marker function imports
  - [ ] Phase 4: Remove monolithic import statement
  - [ ] Phase 5: Test all function calls resolve correctly
- [ ] Compile DailyNYLevelsAnalytics.pine with new split imports
- [ ] **Verify:** No unresolved symbol errors

### ✅ Functional Parity Testing

After cutover, run the full parity validation from PHASE3_VALIDATION.md:

- [ ] **Label Registry Behavior**
  - [ ] Merge strategy ("merge") combines overlapping labels correctly
  - [ ] Stagger strategy offsets labels correctly
  - [ ] Hide strategy suppresses overlapping labels correctly
  - [ ] Off strategy always renders labels
  - [ ] Priority-based rendering works (higher priority first)

- [ ] **Drawing Primitives**
  - [ ] Horizontal lines render with correct styles (Solid, Dashed, Dotted)
  - [ ] Opening-range boxes have correct colors and transparency
  - [ ] Histogram bands render with correct transparency
  - [ ] Time bars render with correct dimensions
  - [ ] Vertical lines render correctly
  - [ ] Day separators extend full vertical range

- [ ] **Visual Parity**
  - [ ] Daily NY levels chart looks identical before and after cutover
  - [ ] Label positioning matches original behavior
  - [ ] Color schemes are unchanged
  - [ ] Right-edge label anchors are correct
  - [ ] No unexpected label merging or suppression

- [ ] **Performance**
  - [ ] Indicator loads in < 3 seconds
  - [ ] No timeout errors during compilation
  - [ ] Memory usage comparable to monolithic version

---

## Sign-Off Checklist

- [ ] All 8 libraries compile successfully locally
- [ ] All 27 exported functions verified in correct families
- [ ] All documentation comments added
- [ ] All libraries published to TradingView community library
- [ ] Import cutover completed in DailyNYLevelsAnalytics.pine
- [ ] Parity validation checklist passed
- [ ] Final commit created: `refactor: cutover to split PineDrawing libraries`
- [ ] Git tag created: `v3-split-libraries-published`
- [ ] Documentation updated with publication status

---

## Rollback Plan (if needed)

If any library publication fails or post-publication issues arise:

1. Revert the indicator to monolithic `vveerappa/PineDrawingLib/5` import
2. Unpublish problematic libraries from TradingView (via library settings)
3. Fix issues locally and re-publish
4. Document root cause in this checklist

---

## Appendix: Reference Documents

- [SPLIT_MIGRATION_MAP.md](SPLIT_MIGRATION_MAP.md) — Function allocation by family
- [ANALYTICS_IMPORT_MIGRATION_CHECKLIST.md](ANALYTICS_IMPORT_MIGRATION_CHECKLIST.md) — Concrete symbol remapping plan
- [lib/README.md](README.md) — Split library inventory
- [docs/indicators/DailyNYLevels/LIBRARY_ARCHITECTURE.md](../../docs/indicators/DailyNYLevels/LIBRARY_ARCHITECTURE.md) — Architecture docs
- [docs/indicators/DailyNYLevels/PHASE3_VALIDATION.md](../../docs/indicators/DailyNYLevels/PHASE3_VALIDATION.md) — Parity validation checklist
