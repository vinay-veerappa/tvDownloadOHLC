---
name: Weekly Outlook
description: Analyzes Weekly Candle structure, Day-of-Week macro cycles (Monday/Tuesday low/high formation vs. Thursday/Friday expansion), weekly reference levels (W-Open, W-High, W-Low, W-Mid, PWH, PWL, PWC), and multi-expiry Expected Move matrices up to next Friday.
applyTo: "scripts/wargaming/weekly_outlook_engine.py,scripts/wargaming/**"
---

# 🗓️ Weekly Outlook & Candle Structure Skill

## Overview
Models higher timeframe weekly candle dynamics and macroeconomic day-of-week structural cycles:
1. **Day-of-Week Cycle**: Statistically, 80%+ of weekly highs/lows are established on Monday or Tuesday. Thursdays and Fridays historically expand to print the opposite extreme of the weekly candle.
2. **Weekly Candle Progression**: Real-time tracking of Weekly Open, High, Low, 50% Midpoint, and Prior Week High/Low/Mid/Close.
3. **Multi-Expiry Expected Moves (EM)**: Multi-horizon implied volatility bands from 0DTE (today) through next Friday's expiration.

## Execution
Run the standalone engine:
```bash
python scripts/wargaming/weekly_outlook_engine.py --ticker NQ1
```
