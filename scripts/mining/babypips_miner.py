"""BabyPips Mechanical Strategy Harvester.

Extracts and adapts famous mechanical rulebooks from BabyPips:
- The Cowabunga System (Multi-timeframe EMA + MACD + RSI)
- HLHB Trend-Catcher System (EMA + RSI + ADX filter)
- London Daybreak Strategy (Asian Range Breakout into London Open)
- Amazing Crossover System (5/10 EMA crossover with stop/target rules)
- Asian Session Range Fade (Overnight mean reversion)

Translates forex-style pips into universal basis points (bps) and ATR brackets
suitable for index futures (NQ1/ES1).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from scripts.mining.config import DATA_DIR

log = logging.getLogger(__name__)

BABYPIPS_MECHANICAL_SYSTEMS: List[Dict[str, Any]] = [
    {
        "id": "babypips_cowabunga",
        "title": "The Cowabunga System (Mechanical Trend Pullback)",
        "source": "babypips",
        "archetype": "ema_pullback",
        "url": "https://www.babypips.com/learn/forex/the-cowabunga-system",
        "timeframe": "15m main, 4h trend bias",
        "indicators": [
            {"name": "ema_5", "period": 5},
            {"name": "ema_10", "period": 10},
            {"name": "rsi", "period": 9},
            {"name": "stochastic", "k": 14, "d": 3, "slowing": 3},
            {"name": "macd", "fast": 12, "slow": 26, "signal": 9},
        ],
        "rules": (
            "HTF (4H) Filter: EMA 5 > EMA 10 = Long Only, EMA 5 < EMA 10 = Short Only. "
            "Entry Trigger (15m): EMA 5 crosses EMA 10 in direction of 4H trend, "
            "RSI > 50 (long) or < 50 (short), Stochastic heading up (long) or down (short), "
            "MACD histogram flips from negative to positive on or within 1 candle of crossover. "
            "Stop Loss: Recent swing low/high or 1.5x ATR(14). "
            "Target: 1:1 risk-reward partial scale-out + trailing stop on opposite EMA cross."
        ),
        "futures_adaptation": (
            "Adapt 4H trend to Daily EMA(20) / Overnight P12 Mid. "
            "Use 5m entry timeframe. Cover Queen at +10 bps, trail runner on 5/10 EMA cross."
        ),
    },
    {
        "id": "babypips_hlhb_trend_catcher",
        "title": "HLHB Trend-Catcher System (Trend-Filter Momentum)",
        "source": "babypips",
        "archetype": "ema_pullback",
        "url": "https://www.babypips.com/trading/systems/hlhb-trend-catcher",
        "timeframe": "1h main",
        "indicators": [
            {"name": "ema_5", "period": 5},
            {"name": "ema_10", "period": 10},
            {"name": "rsi", "period": 10},
            {"name": "adx", "period": 14},
        ],
        "rules": (
            "Entry Long: EMA 5 crosses above EMA 10, RSI > 50, ADX > 25 (confirming trending regime). "
            "Entry Short: EMA 5 crosses below EMA 10, RSI < 50, ADX > 25. "
            "Stop Loss: 50 pips (approx 20 bps on NQ), trailing stop moved to breakeven at +25 pips. "
            "Exit: Opposite EMA crossover or ADX dropping below 20."
        ),
        "futures_adaptation": (
            "Use on 5m NQ with 200 EMA session filter. ADX > 25 ensures high-velocity trend. "
            "Stop: 15 bps ceiling. Target 1: +10 bps (Cover the Queen). Target 2: +30 bps."
        ),
    },
    {
        "id": "babypips_london_daybreak",
        "title": "London Daybreak Breakout Strategy",
        "source": "babypips",
        "archetype": "opening_range",
        "url": "https://www.babypips.com/trading/systems/london-daybreak",
        "timeframe": "15m / 5m",
        "indicators": [
            {"name": "asian_range", "window": "00:00-07:00 GMT"},
        ],
        "rules": (
            "Identify the High and Low of the Asian session consolidation box (00:00 - 07:00 GMT). "
            "At London Open (07:00 GMT / 02:00-03:00 ET), place buy stop above Asian High and sell stop below Asian Low. "
            "Filter: If Asian Range is > 50 pips (already expanded), cancel orders (chop avoidance). "
            "Stop Loss: Middle of the Asian range or opposite boundary. "
            "Target: 1:1 or 1:2 expansion of Asian Range."
        ),
        "futures_adaptation": (
            "Direct 1-to-1 equivalent to NQ London Killzone Breakout (02:00-05:00 ET). "
            "Define Asian range (18:00–02:00 ET). If Asian range is compressed (IB quintile 1-2), "
            "trade the London expansion break."
        ),
    },
    {
        "id": "thestrat_212_continuation",
        "title": "TheStrat 2-1-2 Continuation & Reversal System",
        "source": "the_strat",
        "archetype": "the_strat",
        "url": "https://www.youtube.com/results?search_query=thestrat+rob+smith+212",
        "timeframe": "15m trigger, 1H / Daily Full Timeframe Continuity (FTFC)",
        "indicators": [
            {"name": "bar_classification", "types": ["1_inside", "2u_up", "2d_down", "3_outside"]},
            {"name": "ftfc", "continuity": ["daily", "hourly", "15m"]},
        ],
        "rules": (
            "Rule 1: Filter by FTFC (Full Timeframe Continuity) - trade only in direction of the 1H/Daily candle. "
            "Setup 2-1-2 Bullish Continuation: Bar 1 is 2U (directional up), Bar 2 is 1 (inside bar consolidation), "
            "Bar 3 triggers entry on crossing above the high of Bar 2 (1-bar). "
            "Setup 3-1-2 Reversal: Bar 1 is 3 (outside bar expansion), Bar 2 is 1 (inside bar), "
            "Bar 3 triggers entry on breakout of the inside bar in the direction of FTFC. "
            "Stop Loss: Placed at the opposite side of the 1 (inside bar) or 10 bps ceiling. "
            "Target 1: +10 bps Cover The Queen (50% scale-out, stop to breakeven). "
            "Target 2: Prior swing high / Broadening Formation magnitude."
        ),
        "futures_adaptation": (
            "Enforce strict 09:30-11:30 NY AM session window. 1 tick slippage, "
            "stop loss at low of inside bar, Cover The Queen +10 bps lock."
        ),
    },
]


def harvest_babypips(
    archetype: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Export standardized BabyPips mechanical systems converted for index futures."""
    out_dir = DATA_DIR / "babypips"
    out_dir.mkdir(parents=True, exist_ok=True)

    harvested = []
    for item in BABYPIPS_MECHANICAL_SYSTEMS:
        if archetype and archetype != "all" and item["archetype"] != archetype:
            continue

        item_id = item["id"]
        out_file = out_dir / f"{item_id}.json"
        out_file.write_text(json.dumps(item, indent=2), encoding="utf-8")
        harvested.append(item)
        log.info(f"[BabyPips Miner] Exported mechanical rulebook: {item['title']}")

    return harvested
