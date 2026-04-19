Daily NY Levels local library workspace (v3 split draft).

Purpose:
- Keep the current runtime-safe monolithic path (`PineDrawingLib.pine`) intact.
- Stage incremental extraction into split libraries before TradingView publication.

Current files:
- `PineDrawingLib.pine`: active monolithic implementation used by current scripts.
- `PineDrawingCore.pine`: extracted core layer draft (state, lifecycle, label registry, primitives).
- `PineDrawingHorizontalLevels.pine`: first family draft for horizontal/stat line semantics.
- `PineDrawingZones.pine`: zone family draft (OR boxes, histogram bands, time bars).
- `PineDrawingTables.pine`: table family draft (position tokens and reusable cell render helpers).
- `PineDrawingVerticalMarkers.pine`: vertical marker family draft (vlines and day separators).
- `PineDrawingMarkers.pine`: marker family draft (text markers and registry-backed marker enqueue).
- `PineDrawingComposites.pine`: composite family draft (histogram/time-distribution composite helpers).
- `PineDrawingSpecialized.pine`: specialized family draft (indicator-contributed experimental renderers).
- `RangeSessionLib.pine`: session/range runtime contract.
- `StatsLib.pine`: stats and percentile helpers.
- `SPLIT_MIGRATION_MAP.md`: extraction inventory and phased migration checklist.
- `ANALYTICS_IMPORT_MIGRATION_CHECKLIST.md`: concrete symbol-by-symbol import switch plan for `DailyNYLevelsAnalytics.pine`.

Notes:
- `PineDrawingHorizontalLevels.pine` imports `vveerappa/PineDrawingCore/1` as the intended published dependency.
- Local Pine sources cannot import sibling files directly; publish order must be Core first, then families.

Suggested publication sequence:
1. Publish `PineDrawingCore`.
2. Publish `PineDrawingHorizontalLevels`.
3. Publish `PineDrawingZones`.
4. Publish `PineDrawingTables`.
5. Migrate indicator imports from monolithic `PineDrawingLib` to split family libraries.

Reference design docs:
- `docs/indicators/DailyNYLevels/LIBRARY_ARCHITECTURE.md`
- `docs/indicators/DailyNYLevels/PHASE3_VALIDATION.md`
