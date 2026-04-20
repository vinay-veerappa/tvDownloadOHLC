# Trading Chart UI / UX System

A coherent visual design system for Pine Script v6 and NinjaScript chart indicators and strategies. Covers palette, typography, geometry, templates, library architecture, and per-indicator profiles.

**Not covered:** Next.js dashboard and web surfaces (different paradigm, separate design).

---

## Quick start

New to this repo? Read in order:

1. **[`HANDOFF.md`](HANDOFF.md)** — IDE entry point. 5-minute orientation.
2. **[`VISUAL_SYSTEM.md`](VISUAL_SYSTEM.md)** — the base visual layer.
3. **[`VISUAL_TEMPLATES.md`](VISUAL_TEMPLATES.md)** — the template catalog.
4. **[`LIBRARY_ARCHITECTURE.md`](LIBRARY_ARCHITECTURE.md)** — how libraries are structured.
5. **[`INDICATORS/README.md`](INDICATORS/README.md)** — how to write an indicator profile.

---

## Folder map

```
ui-system/
├── README.md                   ← you are here
├── HANDOFF.md                  ← IDE entry point, 5-min orientation
├── VISUAL_SYSTEM.md            ← palette, typography, geometry, theme,
│                                  display profile, state modifiers,
│                                  render pipeline, lifecycle, library splits
├── VISUAL_TEMPLATES.md         ← THE CATALOG — every canonical template
│                                  (longest doc; consulted most often)
├── LIBRARY_ARCHITECTURE.md     ← physical library structure, tier split,
│                                  Pine vs NT8 mapping, migration plan
├── INDICATORS/
│   ├── README.md               ← workflow + profile template
│   ├── daily_ny_levels.md      ← reference profile (migration target)
│   └── {others TBD}
└── STRATEGIES/
    └── {TBD — NT8 strategies when work begins}
```

---

## What this system does

**Problem:** chart indicators tend to drift visually. Every indicator invents its own colors, its own labels, its own table layouts, its own ways of handling dark vs. light themes, its own approaches to label collision, and its own render-cycle discipline. The result: five indicators on the same chart all say something different about a London session high.

**Approach:** strict centralization of visual decisions.

- **Palette** is defined once, contrast-validated against both dark and light charts, and resolved by the library based on a theme input.
- **Sizes, widths, transparencies** are defined once, scaled by a single chart-wide display profile input (Tiny/Small/Normal/Large/Huge).
- **Templates** are canonical, pre-styled presets. Every visual concept an indicator wants to render — session levels, expected moves, FVGs, walls, projected candles, distribution tables — binds to a named template in the catalog.
- **Indicators** describe what they draw using template bindings; they never invoke drawing APIs directly.
- **Libraries** own all the rendering logic, split into family libraries to respect Pine's line-count limit.

The result: Asia session highs look the same across every indicator. Invalidation lines look the same. Tables render consistently. The user changes their display profile from Normal to Large, and every indicator on the chart adjusts.

---

## Status (as of 2026-04-19)

- Design documents: **complete**
- Daily NY Levels implementation: **Unified Architecture Complete** (Phase 1 & 2 logic merged; shared library rendering fully implemented)
- Active Pine library path: **`PineDrawingLib/5` + `RangeSessionLib/6` + `StatsLib/3`**
- Core/family split libraries: **published** (`PineDrawingCore/1`, `PineDrawingComposites/1`, family modules)
- NT8 implementation: **design target only**, no code yet
- Hit-tracking infrastructure: **out of scope** for this system, separate future module

See [`HANDOFF.md §3`](HANDOFF.md) for up-to-date status.

---

## Contributing

When you want to:

- **Use an existing template in an indicator** → see `VISUAL_TEMPLATES.md` for the catalog, `INDICATORS/README.md` for the workflow
- **Add a new template** → see `VISUAL_TEMPLATES.md §11` for the governance process
- **Migrate an existing indicator** → see `LIBRARY_ARCHITECTURE.md §8` for the Daily NY Levels reference migration
- **Start NT8 work** → see `LIBRARY_ARCHITECTURE.md §5` (caveats and known limitations) and `HANDOFF.md §3.3`
- **Update a locked architectural decision** → see `HANDOFF.md §4` for the list; these decisions should not be re-opened lightly

---

## Revision history

| Version | Date | Changes |
|---------|------|---------|
| 1.3 | 2026-04-20 | Unified Architecture: Consolidated historical phase design documents into archive/history/ and updated primary specs to reflect 'Unified Rendering Flow'. |
| 1.2 | 2026-04-19 | Updated status to current published library versions and marked split libraries as published. |
| 1.1 | 2026-04-18 | Refreshed project status to reflect implemented Daily NY Levels phases and remaining parity + v3 split-library milestones. |
| 1.0 | 2026-04-18 | Initial document set. Complete design coverage for the visual system, template catalog, library architecture, and per-indicator profiling workflow. |
