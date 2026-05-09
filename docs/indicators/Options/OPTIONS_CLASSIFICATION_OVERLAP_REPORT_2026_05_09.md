# Options Level Classification Overlap Report

Generated: 2026-05-09 10:47:30

## Interpretation

- Daily levels = trading-day actionable levels
- Macro levels = higher-timeframe structure and extension targets
- Scored levels = the ranked key-price layer that selects the strongest walls, anchors, and pivots

## Classification Buckets

- tactical: 0DTE, local nodes, DEX, whale-style short-horizon levels
- key_structural: absolute walls, zero gamma, hedge wall, max pain, pin strike
- macro_extension: EM, gamma flip/cliff, vanna/charm, liquidity vacuum, and related extension levels
- wall / anchor / pivot: scored-level filter families

## Class Overlap Matrix

| Class | Daily | Macro | Scored Daily | Scored Macro | Daily∩Macro | All Three |
|---|---:|---:|---:|---:|---:|---:|
| anchor | 0 | 0 | 42 | 0 | 0 | 0 |
| key_structural | 131 | 129 | 0 | 0 | 71 | 31 |
| macro_extension | 261 | 257 | 0 | 0 | 199 | 31 |
| other | 266 | 497 | 0 | 0 | 251 | 20 |
| pivot | 0 | 0 | 9 | 0 | 0 | 0 |
| tactical | 63 | 69 | 0 | 0 | 59 | 33 |
| wall | 0 | 0 | 14 | 25 | 0 | 0 |

## What The Overlap Means

- High daily∩macro overlap is normal for key structural levels; it means the same strike matters both intraday and at the higher timeframe.
- Scored overlap should be smaller; it should mainly capture the few levels that dominate price acceptance/rejection.
- Tactical overlap should be the easiest place to cut clutter, because these levels are the most redundant around spot.

## First-Pass Optimization Logic

1. Keep all key_structural levels as must-keep.
2. Keep only the nearest and strongest tactical levels in daily.
3. In macro, keep extension targets that are meaningfully outside the daily tactical band.
4. In scored, keep only the top-ranked key-price levels per type and suppress context from chart output.

## Examples Of Three-Way Shared Strikes

- key_structural: AAPL:280.00, AAPL:300.00, AMZN:272.50, AMZN:275.00, AMZN:280.00, AVGO:420.00, AVGO:450.00, DIA:490.00, DIA:500.00, GOOGL:390.00
- macro_extension: AAPL:280.00, AAPL:300.00, AMZN:272.50, AMZN:275.00, AMZN:280.00, AVGO:420.00, AVGO:450.00, DIA:490.00, DIA:500.00, GOOGL:390.00
- other: AAPL:300.00, AMZN:275.00, AMZN:280.00, DIA:500.00, GOOGL:400.00, GOOGL:405.00, GOOGL:410.00, IWM:270.00, IWM:275.00, IWM:280.00
- tactical: AAPL:280.00, AAPL:300.00, AMZN:272.50, AMZN:275.00, AMZN:280.00, AVGO:420.00, AVGO:450.00, DIA:490.00, DIA:500.00, GOOGL:390.00

## Next Step

Use this classification report, not raw exact-price overlap alone, as the basis for reducing clutter without losing important levels.
