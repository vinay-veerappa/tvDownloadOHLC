"""P12 Scenario and Handshake Vector Engine

Mickey & Austin P12 Framework:
1. P12 Directional Vector (Bullish > P12 Mid vs. Bearish < P12 Mid).
2. P12 Midline 88.5%-91.4% Equilibrium Gravity Well & Retest Cutoffs (09:45 / 10:15 ET).
3. 99.26% Broken-Broken Goalpost Extreme Rule.
4. NY Opening Handshake Vector (Agreement vs. Disagreement).
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
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.fused_data_loader import load_fused_data
from scripts.libs_py.profiler.engine import SessionBoxEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def compute_p12_scenarios(ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45") -> Dict[str, Any]:
    """Computes all 5 P12 Scenarios, Handshake vectors, and Goalpost conditions."""
    df_1m = load_fused_data(ticker, timeframe="1m", require_historical=False)
    if df_1m.index.tz is None:
        df_1m.index = df_1m.index.tz_localize("US/Eastern")
    else:
        df_1m.index = df_1m.index.tz_convert("US/Eastern")

    t_dt = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else datetime.now(ET).date()
    c_h, c_m = map(int, cutoff_time.split(":"))
    cutoff_dt = pd.Timestamp(datetime.combine(t_dt, time(c_h, c_m)), tz="America/New_York")
    
    # P12 window: Previous evening 18:00 to 06:00 ET
    p12_start = pd.Timestamp(datetime.combine(t_dt - timedelta(days=1), time(18, 0)), tz="America/New_York")
    p12_end = pd.Timestamp(datetime.combine(t_dt, time(6, 0)), tz="America/New_York")

    p12_df = df_1m[(df_1m.index >= p12_start) & (df_1m.index <= p12_end)]
    if p12_df.empty:
        return {"error": "P12 data not found"}

    p12_h = float(p12_df["high"].max())
    p12_l = float(p12_df["low"].min())
    p12_m = (p12_h + p12_l) / 2.0
    p12_rng = p12_h - p12_l

    # Current spot price at cutoff
    df_cutoff = df_1m[df_1m.index <= cutoff_dt]
    spot = float(df_cutoff["close"].iloc[-1])

    dist_mid_pts = round(spot - p12_m, 2)
    dist_mid_bps = round((dist_mid_pts / p12_m) * 10000.0, 1)

    # 1. P12 Vector
    bias = "BULLISH" if spot >= p12_m else "BEARISH"
    primary_target = p12_h if bias == "BULLISH" else p12_l
    target_prob = 81.7 if bias == "BULLISH" else 68.9

    # 2. Session Broken Status for 99.26% Goalpost Rule
    engine = SessionBoxEngine(df_cutoff, ticker=ticker).process()
    live_sessions = engine.get_live_sessions()
    asia_broken = live_sessions.get("Asia", {}).get("broken", False)
    london_broken = live_sessions.get("London", {}).get("broken", False)
    is_goalpost = bool(asia_broken and london_broken)

    # 3. Handshake Vector (at 09:30 or pre-market)
    handshake = "Agreement (A)" if (bias == "BULLISH" and spot >= p12_m) or (bias == "BEARISH" and spot < p12_m) else "Disagreement (D)"
    handshake_narrative = (
        "Agreement (A): Price trades with overnight momentum. Favors Trend Continuation."
        if handshake == "Agreement (A)"
        else "Disagreement (D): Price trades opposite to overnight bias. High probability Mean-Reversion back to P12 Midline."
    )

    return {
        "ticker": ticker,
        "date": t_dt.strftime("%Y-%m-%d"),
        "cutoff_time": cutoff_time,
        "spot_price": spot,
        "p12_levels": {
            "p12_high": round(p12_h, 2),
            "p12_mid": round(p12_m, 2),
            "p12_low": round(p12_l, 2),
            "p12_range_pts": round(p12_rng, 2),
        },
        "vector": {
            "bias": bias,
            "dist_to_mid_pts": dist_mid_pts,
            "dist_to_mid_bps": dist_mid_bps,
            "primary_target": round(primary_target, 2),
            "target_hit_probability": target_prob,
        },
        "equilibrium_gravity": {
            "midline_touch_probability": 88.5,
            "cutoff_0945": "Initial mean-reversion retest window expected before 09:45 AM ET.",
            "cutoff_1015": "Final mean-reversion statistical expiration cutoff at 10:15 AM ET.",
        },
        "goalpost_rule": {
            "is_broken_broken": is_goalpost,
            "rule_desc": "99.26% Rule: If both Asia & London are broken pre-market, 99.26% of days establish both final HOD & LOD after 08:30 AM during RTH.",
            "status": "🚨 ACTIVE (Goalpost Sweep Expected)" if is_goalpost else "Inactive (Standard Session Flow)",
        },
        "handshake": {
            "type": handshake,
            "narrative": handshake_narrative,
        }
    }


def format_p12_scenarios_markdown(data: Dict[str, Any]) -> str:
    """Format P12 scenarios as GitHub flavored markdown report."""
    lvl = data["p12_levels"]
    v = data["vector"]
    eq = data["equilibrium_gravity"]
    gp = data["goalpost_rule"]
    hs = data["handshake"]

    md = f"""# 🔮 P12 Scenarios & Handshake Vectors Report: {data['ticker']} ({data['date']})
* **Analysis Cutoff**: `{data['cutoff_time']} EST` | **Current Spot**: `{data['spot_price']:,.2f}` | **P12 Bias**: `{v['bias']}`

---

### 📏 1. P12 Reference Levels (18:00 – 06:00 ET)
* **P12 High**: `{lvl['p12_high']:,.2f}` (81.7% Touch Target)
* **P12 Midline**: `{lvl['p12_mid']:,.2f}` (88.5% Core Equilibrium Switch)
* **P12 Low**: `{lvl['p12_low']:,.2f}` (68.9% Touch Target)
* **P12 Range**: `{lvl['p12_range_pts']:,.2f} pts`
* **Current Distance to Midline**: `{v['dist_to_mid_pts']:+.2f} pts` (`{v['dist_to_mid_bps']:+.1f} bps`)

---

### 🧭 2. P12 Directional Vector & Equilibrium Rules
* **Active Directional Vector**: **{v['bias']}** &rarr; Primary Target: `{v['primary_target']:,.2f}` (`{v['target_hit_probability']:.1f}%` Hit Rate).
* **Equilibrium Gravity Well**: `P12 Midline` holds an **{eq['midline_touch_probability']:.1f}% historical touch probability**.
* **Statistical Cutoffs**:
  * *09:45 AM*: {eq['cutoff_0945']}
  * *10:15 AM*: {eq['cutoff_1015']}

---

### 🥅 3. The 99.26% "Goalpost" Broken-Broken Rule
* **Status**: **{gp['status']}**
* **Mickey & Austin Principle**: {gp['rule_desc']}

---

### 🤝 4. NY Opening Handshake Vector
* **Vector Type**: `{hs['type']}`
* **Tactical Application**: {hs['narrative']}
"""
    return md


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="P12 Scenarios & Handshake Vector Engine")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--time", default="08:45", help="Cutoff time HH:MM (default: 08:45)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    data = compute_p12_scenarios(ticker=args.ticker, target_date=args.date, cutoff_time=args.time)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_p12_scenarios_markdown(data))


if __name__ == "__main__":
    main()
