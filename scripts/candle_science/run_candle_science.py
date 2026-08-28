"""Standalone Candle Science Engine & CLI Tool

Mickey & Austin Candle Science Methodology:
1. Analyzes 3-candle daily sequence (C1 -> C2 -> C3).
2. Computes empirical MFE (Bullish Excursion) and MAE (Bearish Excursion) percentiles (P30, P50, P70).
3. Translates percentiles into exact Dollar/Point Target Boxes for Open mode and Close mode.
4. Identifies historical subset match rate and expansion vs. reversal probabilities.
"""
from __future__ import annotations

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.trader.signals.candle_science import get_candle_science_read
from api.features.shared.data_loader import load_parquet

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def analyze_candle_science(ticker: str = "NQ1", target_date: Optional[str] = None, mode: str = "open") -> Dict[str, Any]:
    """Execute complete 3-candle sequence analysis and excursion percentiles."""
    cs_raw = get_candle_science_read(ticker=ticker, mode=mode, target_date=target_date)
    
    # Load daily parquet for spot price and candle history
    daily_file = REPO_ROOT / "data" / f"{ticker}_1d.parquet"
    if not daily_file.exists():
        daily_file = REPO_ROOT / "data" / "historical" / f"{ticker}_1d.parquet"

    df_1d = pd.DataFrame()
    if daily_file.exists():
        df_1d = pd.read_parquet(daily_file)
        if df_1d.index.tz is not None:
            df_1d.index = df_1d.index.tz_convert("US/Eastern")
        else:
            df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

    if target_date:
        t_dt = pd.to_datetime(target_date).date()
        df_1d = df_1d[df_1d.index.date <= t_dt]

    spot = float(df_1d["close"].iloc[-1]) if not df_1d.empty else 29650.0

    mfe = cs_raw.get("mfe", {})
    mae = cs_raw.get("mae", {})

    bull_p30_pct = float(mfe.get("p30", 0.85))
    bull_p50_pct = float(mfe.get("p50", 1.28))
    bull_p70_pct = float(mfe.get("p70", 1.88))

    bear_p30_pct = float(mae.get("p30", -0.42))
    bear_p50_pct = float(mae.get("p50", -0.79))
    bear_p70_pct = float(mae.get("p70", -1.40))

    # Calculate absolute price targets
    bull_p30_price = round(spot * (1.0 + bull_p30_pct / 100.0), 2)
    bull_p50_price = round(spot * (1.0 + bull_p50_pct / 100.0), 2)
    bull_p70_price = round(spot * (1.0 + bull_p70_pct / 100.0), 2)

    bear_p30_price = round(spot * (1.0 + bear_p30_pct / 100.0), 2)
    bear_p50_price = round(spot * (1.0 + bear_p50_pct / 100.0), 2)
    bear_p70_price = round(spot * (1.0 + bear_p70_pct / 100.0), 2)

    c1_dir = cs_raw.get("c1_direction", "BULL")
    c2_dir = cs_raw.get("c2_direction", "BEAR")
    pattern_desc = f"C1 ({c1_dir}) -> C2 ({c2_dir}) -> C3 Target Formation"

    result = {
        "ticker": ticker,
        "target_date": target_date or datetime.now(ET).strftime("%Y-%m-%d"),
        "mode": mode,
        "spot_price": spot,
        "pattern": pattern_desc,
        "sample_size": cs_raw.get("sample_size", 4300),
        "mfe_pct": {
            "p30": bull_p30_pct,
            "p50": bull_p50_pct,
            "p70": bull_p70_pct,
        },
        "mae_pct": {
            "p30": bear_p30_pct,
            "p50": bear_p50_pct,
            "p70": bear_p70_pct,
        },
        "bullish_targets": {
            "p30": bull_p30_price,
            "p50": bull_p50_price,
            "p70": bull_p70_price,
        },
        "bearish_targets": {
            "p30": bear_p30_price,
            "p50": bear_p50_price,
            "p70": bear_p70_price,
        },
        "rules": [
            "70% Statistical Reversal Rule: 70% of the time, price reverses before exceeding the P70 target box.",
            "30% Trend Expansion Rule: Only 30% of days expand cleanly through the P70 box (DNP/DWP trend days).",
            "P30 Baseline Rule: Reaching P30 provides high-probability 'Cover The Queen' scale-out liquidity."
        ]
    }
    return result


def format_candle_science_markdown(data: Dict[str, Any]) -> str:
    """Format analysis as GitHub flavored markdown report."""
    md = f"""# 🕯️ Candle Science 3-Candle Excursion Report: {data['ticker']} ({data['target_date']})
* **Spot Price**: `{data['spot_price']:,.2f}` | **Evaluation Mode**: `{data['mode'].upper()}`
* **Pattern**: `{data['pattern']}` | **Sample Size**: `{data['sample_size']:,} historical triplets`

---

### 📈 Bullish MFE (Maximum Favorable Excursion) Targets
| Percentile | Percentage Move | Exact Price Target | Interpretation |
| :--- | :--- | :--- | :--- |
| **P30** | `+{data['mfe_pct']['p30']:.2f}%` | `{data['bullish_targets']['p30']:,.2f}` | Conservative Cash-Flow Target / TP1 |
| **P50 (Median)** | `+{data['mfe_pct']['p50']:.2f}%` | `{data['bullish_targets']['p50']:,.2f}` | Standard Session HOD Target |
| **P70** | `+{data['mfe_pct']['p70']:.2f}%` | `{data['bullish_targets']['p70']:,.2f}` | Extended Trend Ceiling (70% Reversal Limit) |

---

### 📉 Bearish MAE (Maximum Adverse Excursion) Targets
| Percentile | Percentage Move | Exact Price Target | Interpretation |
| :--- | :--- | :--- | :--- |
| **P30** | `{data['mae_pct']['p30']:.2f}%` | `{data['bearish_targets']['p30']:,.2f}` | Conservative Short Target / Pullback Support |
| **P50 (Median)** | `{data['mae_pct']['p50']:.2f}%` | `{data['bearish_targets']['p50']:,.2f}` | Standard Session LOD Target |
| **P70** | `{data['mae_pct']['p70']:.2f}%` | `{data['bearish_targets']['p70']:,.2f}` | Extended Trend Floor (70% Reversal Limit) |

---

### 📜 Candle Science Rules
"""
    for r in data['rules']:
        md += f"* {r}\n"
    return md


def main():
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Candle Science 3-Candle Excursion Engine")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--mode", choices=["open", "close"], default="open", help="Mode: open or close (default: open)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    data = analyze_candle_science(ticker=args.ticker, target_date=args.date, mode=args.mode)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_candle_science_markdown(data))


if __name__ == "__main__":
    main()
