# Daily NY Levels — Standardized PineDrawing Framework

This directory contains the production-grade implementation of the **Daily NY Levels** indicator and the associated **PineDrawing** library family. The system follows a unified visual system with theme-aware color resolution and display profiles.

## Project Structure

```
daily-ny-levels/
├── DailyNYLevels.pine               # Main Production Indicator (Finalized)
├── DailyNYLevelsAnalytics.pine      # Analytics & Statistical Verifier
├── lib/
│   ├── PineDrawingCore.pine         # Core: Style resolver & drawing primitives
│   ├── PineDrawingHorizontalLevels.pine # Levels: Statistical & session lines
│   ├── PineDrawingZones.pine        # Zones: FVGs, Order Blocks, Session Ranges
│   ├── PineDrawingMarkers.pine      # Markers: Judas, Sweeps, Trade markers
│   ├── PineDrawingTables.pine       # Tables: Bias Dashboards & Distribution tables
│   ├── RangeSessionLib.pine         # Session/range UDTs & resolver logic
│   └── StatsLib.pine                # Statistical utilities (MFE/MAE)
└── ninja/
    └── (NinjaScript implementations following same architecture)
```

## Visual System Integration

All components are derived from the [Visual System Specification](file:///c:/Users/vinay/tvDownloadOHLC/docs/indicators/DailyNYLevels/VISUAL_SYSTEM.md):

- **Themes**: Supports `Dark`, `Light`, and `Custom` color resolutions automatically.
- **Profiles**: Supports `Compact`, `Normal`, and `Large` display scaling for different resolutions.
- **Tiers**: Systematic rendering via **Primary (P)**, **Secondary (S)**, and **Context (C)** levels.

## TradingView Publication Workflow

To ensure all imports resolve correctly, publish the libraries in the following dependency order:

1. **`PineDrawingCore`** (No dependencies)
2. **`RangeSessionLib`**, **`StatsLib`** (No dependencies)
3. **`PineDrawingHorizontalLevels`**, **`PineDrawingZones`**, **`PineDrawingMarkers`**, **`PineDrawingTables`** (Depend on `Core`)
4. **`DailyNYLevels`** (Depends on the entire family)

## Testing & Verification

1. Load `DailyNYLevels.pine` in the TradingView Pine Editor.
2. Verify all labels render correctly on the right edge using the `LabelRegistry`.
3. Toggle the **Display Profile** in inputs to verify size scaling.
4. Switch between **Dark** and **Light** themes to verify color contrast stability.
