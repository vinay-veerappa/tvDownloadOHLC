# Daily NY Levels V5 — Scripts

This folder contains the Pine Script and NinjaScript implementations of the Daily NY Levels indicator suite.

## Structure

```
daily-ny-levels/
├── DailyNYLevelsV5.pine              # Phase 1: Core indicator
├── DailyNYLevelsAnalytics.pine       # Phase 2: MFE/MAE analytics
├── lib/
│   ├── RangeSessionLib.pine          # Phase 1: Session/range UDTs & resolver
│   ├── DrawingLib.pine               # Phase 1: Drawing helpers
│   └── StatsLib.pine                 # Phase 1: Statistical utilities
└── ninja/
    ├── DailyNYLevels.cs              # Phase 3: NinjaScript indicator
    ├── DailyNYLevelsStrategy.cs      # Phase 4: NinjaScript strategy
    └── Lib/
        ├── RangeEngine.cs            # Phase 3: Range/session engine
        └── ExcursionEngine.cs        # Phase 3: MFE/MAE engine
```

## Docs

Design documents live in `docs/indicators/DailyNYLevels/`.
