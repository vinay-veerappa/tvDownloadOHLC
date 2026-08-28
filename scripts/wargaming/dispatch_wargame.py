"""Multi-Channel Dispatch Engine for Mickey & Austin Wargaming

Dispatches formatted wargaming briefings to Discord webhooks and Email:
1. Discord Embed Cards: Color-coded (Red False / Green True), ASCII levels map, and +10 bps brackets.
2. File Attachment: Attaches the interactive single-file HTML candlestick chart.
3. Email Dispatch: Sends a responsive dark-themed HTML email to subscriber lists.

Usage:
    python scripts/wargaming/dispatch_wargame.py --ticker NQ1 --time 06:00 --discord
    python scripts/wargaming/dispatch_wargame.py --ticker ES1 --time 08:30 --discord --email
"""
from __future__ import annotations

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, Optional
import pytz

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wargaming.generate_daily_wargame import generate_wargame_data, format_wargame_markdown
from scripts.wargaming.render_wargame_chart import render_and_save_chart
from scripts.libs_py.discord import load_webhook_url, send_message as send_discord_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def build_discord_embed(data: Dict[str, Any], html_chart_path: Optional[str] = None) -> Dict[str, Any]:
    """Construct structured Discord Embed payload."""
    ticker = data["ticker"]
    dt_str = data["date"]
    cutoff = data["cutoff_time"]
    spot = data["spot_price"]
    p12 = data["p12"]
    anchors = data["anchors"]
    sess = data["sessions"]
    pack = data["pack_trading"]

    # Red for Bearish/False, Green for Bullish/True
    embed_color = 0xEF4444 if p12["bias"] == "BEARISH" else 0x10B981
    p12_pos = "ABOVE" if p12["diff_pts"] >= 0 else "BELOW"

    fields = [
        {
            "name": "🧭 Overnight Context & Structure",
            "value": f"• **P12 Range**: `{p12['high']:,.2f}` to `{p12['low']:,.2f}` (Mid: `{p12['mid']:,.2f}`)
"
                     f"• **P12 Vector Switch**: **{p12['bias']}** ({p12_pos} by `{abs(p12['diff_pts']):.2f} pts` / `{abs(p12['diff_bps']):.1f} bps`)
"
                     f"• **Session Alignment**: `{sess['alignment']}`",
            "inline": False,
        },
        {
            "name": "📊 Key Anchor Magnets",
            "value": f"• **Midnight Open**: `{anchors['midnight_open']:,.2f}`
"
                     f"• **Previous Day High (PDH)**: `{anchors['pdh']:,.2f}`
"
                     f"• **Previous Day Low (PDL)**: `{anchors['pdl']:,.2f}`",
            "inline": False,
        },
        {
            "name": "🛡️ Pack Trading Execution Brackets",
            "value": f"• **Target 1 ("Cover The Queen")**: **+{pack['cover_the_queen_bps']:.1f} bps (+{pack['queen_pts']:.2f} pts)** *(50% scale + BE stop lock)*
"
                     f"• **Target 2 ("Runner")**: **+{pack['runner_bps']:.1f} bps (+{pack['runner_pts']:.2f} pts)** trailing
"
                     f"• **Stop Ceiling**: **Max {pack['stop_ceiling_bps']:.1f} bps (~{pack['stop_pts']:.2f} pts)**",
            "inline": False,
        },
        {
            "name": "🔴 Scenario 1: False Reversion (Primary)",
            "value": f"If 09:30 sweeps `{p12['low']:,.2f}` and fails 10 bps breakout in 0-5 box -> Target P12 Mid (`{p12['mid']:,.2f}`) & Midnight Open (`{anchors['midnight_open']:,.2f}`).
"
                     f"*Cutoff*: Midline retest expected before **09:45 AM**; window closes at **10:15 AM**.",
            "inline": False,
        },
        {
            "name": "🟢 Scenario 2: True Expansion (Secondary)",
            "value": f"If 09:30 sustains >10 bps breakout and accepts across P12 Mid -> Target P12 High (`{p12['high']:,.2f}`) -> PDH (`{anchors['pdh']:,.2f}`).",
            "inline": False,
        }
    ]

    embed = {
        "title": f"⚔️ Mickey & Austin Wargaming Playbook: {ticker}",
        "description": f"**Date:** {dt_str} | **Cutoff:** {cutoff} EST | **Current Spot:** `{spot:,.2f}`",
        "color": embed_color,
        "fields": fields,
        "footer": {"text": "Pack Trading Quantitative Systems • Process Over Outcome"},
        "timestamp": datetime.now(pytz.utc).isoformat(),
    }

    return embed


def dispatch_discord(data: Dict[str, Any], webhook_url: Optional[str] = None, attach_chart: bool = True) -> bool:
    """Send formatted Discord embed and optional HTML chart attachment."""
    if not webhook_url:
        webhook_url = load_webhook_url("wargaming") or load_webhook_url("default")

    if not webhook_url:
        log.warning("No Discord webhook URL configured.")
        return False

    chart_path = None
    if attach_chart:
        chart_path = render_and_save_chart(ticker=data["ticker"], target_date=datetime.strptime(data["date"], "%Y-%m-%d").date(), cutoff_time=data["cutoff_time"])

    embed = build_discord_embed(data, chart_path)
    content_text = f"⚔️ **Daily Wargaming Briefing for {data['ticker']} ({data['date']})**"

    files = [chart_path] if (chart_path and Path(chart_path).exists()) else None
    res = send_discord_message(webhook_url, message=content_text, embeds=[embed], files=files)
    log.info(f"Dispatched Discord wargame briefing: {res}")
    return True


def dispatch_wargame(ticker: str = "NQ1", target_date: Optional[date] = None, cutoff_time: str = "06:00", to_discord: bool = True, to_email: bool = False):
    """Main dispatch orchestration."""
    if target_date is None:
        target_date = datetime.now(ET).date()

    data = generate_wargame_data(ticker=ticker, target_date=target_date, cutoff_time_str=cutoff_time)

    if to_discord:
        dispatch_discord(data)


def main():
    parser = argparse.ArgumentParser(description="Dispatch Wargaming Briefings")
    parser.add_argument("--ticker", default="NQ1", help="Ticker symbol (default: NQ1)")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--time", default="06:00", help="Cutoff time HH:MM")
    parser.add_argument("--discord", action="store_true", help="Send to Discord webhook")
    parser.add_argument("--email", action="store_true", help="Send HTML email")
    args = parser.parse_args()

    t_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now(ET).date()
    dispatch_wargame(ticker=args.ticker, target_date=t_date, cutoff_time=args.time, to_discord=args.discord, to_email=args.email)


if __name__ == "__main__":
    main()
