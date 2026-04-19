# DailyNYLevelsAnalytics Import Migration Checklist

Target file: `scripts/indicators/daily-ny-levels/DailyNYLevelsAnalytics.pine`

Current import:
- `import vveerappa/PineDrawingLib/4 as PDL`

Target split imports (after publication):
- `import vveerappa/PineDrawingCore/<ver> as PDC`
- `import vveerappa/PineDrawingHorizontalLevels/<ver> as PDLH`
- `import vveerappa/PineDrawingZones/<ver> as PDLZ`
- `import vveerappa/PineDrawingTables/<ver> as PDLT`
- `import vveerappa/PineDrawingVerticalMarkers/<ver> as PDLV`

## Used symbols and destination

- `PDL.PineDrawingState` -> `PDC.PineDrawingState`
- `PDL.LabelRegistry` -> `PDC.LabelRegistry`
- `PDL.f_new_drawing_state` -> `PDC.f_new_drawing_state`
- `PDL.f_clear_all` -> `PDC.f_clear_all`
- `PDL.f_label_registry_begin` -> `PDC.f_label_registry_begin`
- `PDL.f_label_registry_push_ex` -> `PDC.f_label_registry_push_ex`
- `PDL.f_label_registry_flush` -> `PDC.f_label_registry_flush`
- `PDL.f_merge_threshold_for_symbol` -> `PDC.f_merge_threshold_for_symbol`
- `PDL.f_draw_stat_line` -> `PDLH.f_draw_stat_line`
- `PDL.f_draw_or_box` -> `PDLZ.f_draw_or_box`
- `PDL.f_draw_hist_band` -> `PDLZ.f_draw_hist_band`
- `PDL.f_draw_time_bar` -> `PDLZ.f_draw_time_bar`
- `PDL.f_draw_vline` -> `PDLV.f_draw_vline`
- `PDL.f_draw_stat_label` -> `PDC.f_draw_stat_label`
- `PDL.f_table_pos` -> `PDLT.f_table_pos`

## Cutover sequence

1. Publish `PineDrawingCore` and family libraries.
2. Add split imports alongside monolithic import in a temporary branch.
3. Replace symbol references in grouped commits:
   - Types/lifecycle first (`PineDrawingState`, `LabelRegistry`, registry methods)
   - Zones/levels next
   - Table position and vertical markers last
4. Remove monolithic import once all references are migrated.
5. Re-run visual parity checks from `docs/indicators/DailyNYLevels/PHASE3_VALIDATION.md`.
