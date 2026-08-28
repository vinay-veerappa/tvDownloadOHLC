"""Session Volatility Budget & Checkbook Spending Engine (DRO)

Mickey & Austin Volatility Checkbook Framework:
1. 10-Day Median Daily Range Baseline (DRO).
2. Asia, London & Total Overnight Range Checkbook Spend %.
3. Volatility Regime Classification (Cheap/Coiled vs. Expensive/Overspent).
"""
from __future__ import annotations

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.fused_data_loader import load_fused_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def compute_session_budget(ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45") -> Dict[str, Any]:
    """Computes overnight checkbook spending relative to the 10-day median range."""
    # 1. 10-Day Median Daily Range from 1d Parquet
    daily_file = REPO_ROOT / "data" / f"{ticker}_1d.parquet"
    if not daily_file.exists():
        daily_file = REPO_ROOT / "data" / "historical" / f"{ticker}_1d.parquet"

    df_1d = pd.read_parquet(daily_file)
    if df_1d.index.tz is not None:
        df_1d.index = df_1d.index.tz_convert("US/Eastern")
    else:
        df_1d.index = df_1d.index.tz_localize("UTC").tz_convert("US/Eastern")

    df_1d["session_date"] = [
        (t + timedelta(days=1)).date() if t.hour >= 17 else t.date()
        for t in df_1d.index
    ]

    t_dt = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else datetime.now(ET).date()
    df_1d_prior = df_1d[df_1d["session_date"] < t_dt]

    if len(df_1d_prior) >= 10:
        tail_10 = df_1d_prior.tail(10)
        daily_ranges = tail_10["high"] - tail_10["low"]
        median_10d_range = float(np.median(daily_ranges))
    else:
        median_10d_range = 350.0

    # 2. 1m Data for Session Breakdown
    df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")

    asia_start = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(18, 0)), tz="America/New_York")
    asia_end = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(19, 30)), tz="America/New_York")
    lon_start = pd.Timestamp(datetime.combine(t_dt, time(2, 30)), tz="America/New_York")
    lon_end = pd.Timestamp(datetime.combine(t_dt, time(3, 30)), tz="America/New_York")
    overnight_end = pd.Timestamp(datetime.combine(t_dt, time(8, 30)), tz="America/New_York")

    asia_df = df_1m[(df_1m.index >= asia_start) & (df_1m.index < asia_end)]
    lon_df = df_1m[(df_1m.index >= lon_start) & (df_1m.index < lon_end)]
    overnight_df = df_1m[(df_1m.index >= asia_start) & (df_1m.index <= overnight_end)]

    asia_rng = float(asia_df["high"].max() - asia_df["low"].min()) if not asia_df.empty else 45.0
    lon_rng = float(lon_df["high"].max() - lon_df["low"].min()) if not lon_df.empty else 58.0
    overnight_rng = float(overnight_df["high"].max() - overnight_df["low"].min()) if not overnight_df.empty else 130.0

    overnight_spend_pct = round((overnight_rng / median_10d_range) * 100.0, 1)
    asia_spend_pct = round((asia_rng / median_10d_range) * 100.0, 1)
    lon_spend_pct = round((lon_rng / median_10d_range) * 100.0, 1)

    # Classify Regime
    if overnight_spend_pct < 75.0:
        regime = "COILED / CHEAP VOLATILITY"
        rth_expectation = "Overnight compressed. Full checkbook remains for RTH expansion / Firecracker breakout."
        badge_color = "#10b981"
    elif overnight_spend_pct > 125.0:
        regime = "OVERSPENT / EXPENSIVE VOLATILITY"
        rth_expectation = "Overnight exhausted daily checkbook. Favors R1 Mean-Reversion / False Reversal / Chop."
        badge_color = "#ef4444"
    else:
        regime = "NORMAL VOLATILITY BUDGET"
        rth_expectation = "Standard balanced distribution budget for regular session auction."
        badge_color = "#f59e0b"

    return {
        "ticker": ticker,
        "date": t_dt.strftime("%Y-%m-%d"),
        "10d_median_range_pts": round(median_10d_range, 2),
        "asia_range_pts": round(asia_rng, 2),
        "asia_spend_pct": asia_spend_pct,
        "london_range_pts": round(lon_rng, 2),
        "london_spend_pct": lon_spend_pct,
        "overnight_range_pts": round(overnight_rng, 2),
        "overnight_spend_pct": overnight_spend_pct,
        "regime": regime,
        "rth_expectation": rth_expectation,
        "badge_color": badge_color,
    }


def format_session_budget_markdown(data: Dict[str, Any]) -> str:
    """Format session budget report as GitHub markdown."""
    md = f"""# 💳 Session Volatility Budget & Checkbook Spending Report: {data['ticker']} ({data['date']})
* **10-Day Median Daily Range (DRO Baseline)**: `{data['10d_median_range_pts']:,.2f} pts`
* **Active Volatility Regime**: **{data['regime']}** ({data['overnight_spend_pct']:.1f}% Spent)

---

### 📊 Checkbook Spending Breakdown
| Session Window | Realized Range | % of 10-Day Median | Status |
| :--- | :--- | :--- | :--- |
| **Asia Range (18:00-19:30)** | `{data['asia_range_pts']:,.2f} pts` | `{data['asia_spend_pct']:.1f}%` | {'Overspent' if data['asia_spend_pct']>40 else 'Normal'} |
| **London Range (02:30-03:30)** | `{data['london_range_pts']:,.2f} pts` | `{data['london_spend_pct']:.1f}%` | {'Overspent' if data['london_spend_pct']>45 else 'Normal'} |
| **Total Overnight (18:00-08:30)** | `{data['overnight_range_pts']:,.2f} pts` | **`{data['overnight_spend_pct']:.1f}%`** | **{data['regime']}** |

---

### 🎯 Mickey & Austin RTH Tactical Expectation
* **{data['rth_expectation']}**
"""
    return md


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Session Volatility Budget & Checkbook Spending Engine")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    data = compute_session_budget(ticker=args.ticker, target_date=args.date)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_session_budget_markdown(data))


if __name__ == "__main__":
    main()
