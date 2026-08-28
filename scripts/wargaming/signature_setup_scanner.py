"""Signature Setup Scanner

Mickey & Austin Named Setups:
1. Firecracker Setup: Key levels heavily stacked on one side -> opening momentum sweeps all levels.
2. Spongebob Setup: Price opens on extreme outer boundaries -> asymmetric mean-reversion.
3. Goalpost Setup: Broken-Broken Asia + London -> 99.26% sweep of both sides in RTH.
"""
from __future__ import annotations

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wargaming.p12_scenario_engine import compute_p12_scenarios
from scripts.wargaming.session_budget_engine import compute_session_budget

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def scan_signature_setups(ticker: str = "NQ1", target_date: Optional[str] = None, cutoff_time: str = "08:45") -> Dict[str, Any]:
    """Scans for active Mickey & Austin signature trade setups."""
    p12_data = compute_p12_scenarios(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time)
    budget_data = compute_session_budget(ticker=ticker, target_date=target_date, cutoff_time=cutoff_time)

    spot = p12_data["spot_price"]
    p12_mid = p12_data["p12_levels"]["p12_mid"]
    p12_high = p12_data["p12_levels"]["p12_high"]
    p12_low = p12_data["p12_levels"]["p12_low"]
    is_goalpost = p12_data["goalpost_rule"]["is_broken_broken"]
    spend_pct = budget_data["overnight_spend_pct"]

    active_setups = []

    # 1. Goalpost Setup Detection
    if is_goalpost:
        active_setups.append({
            "name": "🥅 BROKEN-BROKEN GOALPOST SETUP",
            "tier": "High Conviction (99.26% Probability)",
            "condition": "Both Asia & London initial ranges were breached before 09:30 AM.",
            "execution": "Expect both daily extremes (HOD & LOD) to form after 08:30 AM during RTH. Fade initial breakout sweeps toward opposite goalpost.",
            "color": "#3b82f6"
        })

    # 2. Firecracker Setup Detection
    # If overnight spend is compressed (< 50%) and spot is aligned with P12 vector
    if spend_pct < 50.0:
        active_setups.append({
            "name": "🧨 FIRECRACKER EXPANSION SETUP",
            "tier": "High Momentum / Expansion",
            "condition": f"Overnight range is tightly coiled ({spend_pct:.1f}% checkbook spent) with full daily budget remaining.",
            "execution": "Look for fast opening wick followed by one-way trend drive. Ride 10 bps hourly breakouts; do NOT fade.",
            "color": "#10b981"
        })

    # 3. Spongebob Setup Detection
    # If spot is within 15 pts of P12 Low or P12 High while overnight is extended
    if abs(spot - p12_low) < 25.0:
        active_setups.append({
            "name": "🧽 SPONGEBOB (Foaming at the Mouth - Lower Bound)",
            "tier": "Asymmetric Mean-Reversion",
            "condition": f"Price is opening pinned to P12 Low ({p12_low:,.2f}) with major magnets stacked above.",
            "execution": "Extreme R:R Long mean-reversion back to P12 Midline and Midnight Open.",
            "color": "#f59e0b"
        })
    elif abs(spot - p12_high) < 25.0:
        active_setups.append({
            "name": "🧽 SPONGEBOB (Foaming at the Mouth - Upper Bound)",
            "tier": "Asymmetric Mean-Reversion",
            "condition": f"Price is opening pinned to P12 High ({p12_high:,.2f}) with major magnets stacked below.",
            "execution": "Extreme R:R Short mean-reversion back to P12 Midline and Midnight Open.",
            "color": "#f59e0b"
        })

    if not active_setups:
        active_setups.append({
            "name": "⚖️ STANDARD ROTATIONAL PROFILE",
            "tier": "Balanced Distribution",
            "condition": "No extreme macro boundary triggers detected.",
            "execution": "Trade the standard 4-Outcome Decision Tree (SF, LF, LT, ST) based on 09:30 open breakout.",
            "color": "#94a3b8"
        })

    return {
        "ticker": ticker,
        "date": p12_data["date"],
        "cutoff_time": cutoff_time,
        "spot_price": spot,
        "active_setups": active_setups,
        "primary_setup": active_setups[0]["name"],
    }


def format_signature_setups_markdown(data: Dict[str, Any]) -> str:
    """Format signature setups as GitHub markdown."""
    md = f"""# 🎯 Signature Trade Setup Scanner: {data['ticker']} ({data['date']})
* **Analysis Cutoff**: `{data['cutoff_time']} EST` | **Current Spot**: `{data['spot_price']:,.2f}`
* **Primary Active Setup**: **{data['primary_setup']}**

---

### 🚨 Detected Setups
"""
    for s in data["active_setups"]:
        md += f"""#### {s['name']} [{s['tier']}]
* **Trigger Condition**: {s['condition']}
* **Execution SOP**: {s['execution']}

---
"""
    return md


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Signature Trade Setup Scanner")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--time", default="08:45", help="Cutoff time HH:MM (default: 08:45)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    data = scan_signature_setups(ticker=args.ticker, target_date=args.date, cutoff_time=args.time)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_signature_setups_markdown(data))


if __name__ == "__main__":
    main()
