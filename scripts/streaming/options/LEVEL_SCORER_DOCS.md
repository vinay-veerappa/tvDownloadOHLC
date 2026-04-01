# Three-Filter Architecture: Institutional Level Scorer

This module implements a three-tier filtering system to separate dealer-positioning noise from true institutional gravity.

## 🧱 Filter 1: Mechanical Flow (The "Brakes")
Calculates `hedge_contracts_per_dollar` to identify strikes where dealer gamma hedging will physically slow down price movement. 
- **Mechanical Walls**: Strikes where hedging intensity is in the top 5% of the total book.

## ⚓ Filter 2: Structural Anchors (Institutional Gravity)
Identifies major institutional positioning based on Open Interest and volatility surface characteristics.
- **Matched Programs**: Detects patterns like "Systemic Buyback", "Hedge Fund Floor", or "Pension Collar".
- **Roll Windows**: Flags expiration dates that are approaching a quarterly roll.

## 📈 Filter 3: Inflection Geometry
Extracts key mathematical points from the GEX profile to define the day's likely range.
- **Gamma Cliff**: Large drops in positioning that suggest "air pockets".
- **Vanna Pivot**: Points where changes in implied volatility trigger dealer re-hedging.

## Integration Points
1. **Intraday Pipeline** (`run_options_levels.py`): Scores each ticker in every update cycle.
2. **Weekend/Macro Pipeline** (`macro_pipeline.py`): Adds institutional briefing and scorecard to HTF analysis.
3. **Discord Notification**: New "THREE-FILTER ANALYSIS" section in detailed alerts.
4. **Macro Charting**: New visual overlays for anchors and mechanical walls.
5. **Data Export**: Scored analysis is persisted in `daily_levels.json` for frontend consumption.
