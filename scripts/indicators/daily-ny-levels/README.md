# Daily NY Levels V5 — Scripts

This folder contains the Pine Script and NinjaScript implementations of the Daily NY Levels indicator suite.

## Structure

```
daily-ny-levels/
├── DailyNYLevelsV5.pine              # Phase 1: Core indicator
├── DailyNYLevelsAnalytics.pine       # Phase 2: MFE/MAE analytics
├── lib/
│   ├── RangeSessionLib.pine          # Phase 1: Session/range UDTs & resolver
│   ├── PineDrawingLib.pine           # Phase 1: Pine-only drawing helpers
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

## TradingView Publication Workflow

Libraries must be published **in dependency order** before `DailyNYLevelsV5` can be used on TradingView (imported library IDs must resolve):

1. `RangeSessionLib` — no dependencies
2. `PineDrawingLib` — no dependencies
3. `StatsLib` — no dependencies
4. `DailyNYLevelsV5` — depends on all three above

After publishing all libraries, open `DailyNYLevelsV5.pine` in the TradingView editor and verify the import block resolves. Then add to a 1m/5m/15m/60m chart and confirm: OR box renders, stat lines appear, histogram visible when `i_show_histogram = true`.
