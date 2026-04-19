# PineDrawing v3 Split Migration Map

This file tracks extraction progress from monolithic `PineDrawingLib.pine` to split v3 family libraries.

## Status

- `PineDrawingCore.pine`: created
- `PineDrawingHorizontalLevels.pine`: created
- `PineDrawingZones.pine`: created
- `PineDrawingTables.pine`: created
- `PineDrawingVerticalMarkers.pine`: created
- `PineDrawingMarkers.pine`: created
- `PineDrawingComposites.pine`: created
- `PineDrawingSpecialized.pine`: created

## Function allocation

### Core
- `PineDrawingState`, `LabelRegistry`
- `f_new_drawing_state`, `f_clear_all`
- `f_label_registry_*`
- `f_format_template`
- `f_merge_threshold_for_symbol`
- `f_line_style`, `f_display_size`, `f_text_size`, `f_table_pos`
- Primitive wrappers:
  - `f_draw_line`
  - `f_draw_or_box`
  - `f_draw_hist_band`
  - `f_draw_stat_label`
  - `f_draw_time_bar`
  - `f_draw_vline`
  - `f_draw_day_separator`

### HorizontalLevels
- `f_draw_stat_line`
- `f_draw_labeled_stat_line`

### Zones
- `f_draw_or_box` (semantic wrapper)
- `f_draw_hist_band` (semantic wrapper)
- `f_draw_time_bar` (semantic wrapper)

### Tables
- `f_table_pos` (semantic wrapper)
- `f_draw_header_cell`
- `f_draw_value_cell`
- `f_draw_metric_row`

### VerticalMarkers
- `f_draw_vline` (semantic wrapper)
- `f_draw_day_separator` (semantic wrapper)

### Markers
- `f_draw_text_marker`
- `f_enqueue_text_marker`

### Composites
- `f_draw_histogram_bucket`
- `f_draw_time_distribution_segment`
- `f_draw_distribution_stat_marker`

### Specialized
- `f_draw_scored_level`

## Migration phases

1. Keep indicators on monolithic `PineDrawingLib` until split libraries are published.
2. Publish `PineDrawingCore` first.
3. Publish extracted family libraries (`HorizontalLevels`, `Zones`, `Tables`, `VerticalMarkers`).
4. Switch indicator imports and map calls family by family.
5. Run parity validation checklist from `docs/indicators/DailyNYLevels/PHASE3_VALIDATION.md`.
