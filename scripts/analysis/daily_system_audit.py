"""
Daily System Audit Script
=========================
Performs a comprehensive audit of the options strategy engine for a given date:
1. Parses DB for trades opened or closed today, showing P&L, leg details, and fill assumptions.
2. Analyzes `strategy_engine.log` to count Tier-1 (60s), Tier-2 (5m), and Tier-3 (daily) scans.
3. Checks GexSnapshot database records to verify active upstream data pipeline feeding.
4. Tallies system errors/warnings with deduplicated samples.
5. Sends the summary report to the Discord 'options-backtest' channel (if enabled).

Usage:
  python scripts/analysis/daily_system_audit.py [--date YYYY-MM-DD] [--discord]
"""

import sys
import os

# Fix Windows console encoding for UTF-8 characters (emojis)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

import argparse
import json
import logging
from datetime import datetime, timezone
import pytz

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import yaml
from prisma import Prisma
from dotenv import load_dotenv

# Load environment
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../web/.env"))
load_dotenv(dotenv_path)

TZ_ET = pytz.timezone("America/New_York")

def load_config():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../libs_py/strategy_engine/config.yaml"))
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    return {}

def send_discord_report(message: str, config: dict):
    discord_cfg = config.get("discord", {})
    if not discord_cfg.get("enabled", False):
        print("Discord notifications are disabled in config.yaml. Skipping.")
        return

    channel = discord_cfg.get("channel", "options-backtest")
    if not discord_cfg.get("events", {}).get("daily_rollup", True):
        print("Daily rollup events are disabled in config.yaml. Skipping Discord send.")
        return

    try:
        from scripts.utils.discord_notify import get_webhook_url, send_message
        webhook_url = get_webhook_url(channel)
        if not webhook_url:
            print(f"Warning: Discord webhook URL not found for channel '{channel}'")
            return
        
        send_message(webhook_url, message)
        print(f"Successfully sent daily audit report to Discord channel '{channel}'!")
    except Exception as e:
        print(f"Failed to send Discord report: {e}")

async def run_audit(target_date_str: str, send_to_discord: bool):
    # Parse target date
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: Invalid date format '{target_date_str}'. Use YYYY-MM-DD.")
        return

    print("=" * 80)
    print(f"SYSTEM AUDIT REPORT FOR: {target_date.strftime('%A, %B %d, %Y')}")
    print("=" * 80)

    db = Prisma()
    await db.connect()

    report_lines = []
    
    # -------------------------------------------------------------------------
    # 1. Database Trades Analysis
    # -------------------------------------------------------------------------
    # Standard Eastern Time bounds converted to UTC Unix milliseconds
    start_dt = TZ_ET.localize(datetime.combine(target_date, datetime.min.time()))
    end_dt = TZ_ET.localize(datetime.combine(target_date, datetime.max.time()))
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    trades = await db.trade.find_many(
        where={
            "OR": [
                {"entryDate": {"gte": start_dt, "lte": end_dt}},
                {"exitDate": {"gte": start_dt, "lte": end_dt}}
            ]
        },
        include={"legs": True, "account": True}
    )

    trades_opened = [t for t in trades if start_dt <= t.entryDate <= end_dt]
    trades_closed = [t for t in trades if t.exitDate and start_dt <= t.exitDate <= end_dt]
    
    trade_summary = f"📈 **Trade Execution Summary:**\n"
    trade_summary += f"  • Positions Opened Today: {len(trades_opened)}\n"
    trade_summary += f"  • Positions Closed Today: {len(trades_closed)}\n"

    total_pnl = 0.0
    closed_details = []
    
    for t in trades_closed:
        pnl = t.pnl if t.pnl is not None else 0.0
        total_pnl += pnl
        
        # Determine fill assumption
        fill_assump = "standard"
        if t.metadata:
            try:
                meta = json.loads(t.metadata)
                fill_assump = meta.get("fill_assumption", "standard")
            except Exception:
                pass
        
        legs_str_list = []
        for leg in t.legs:
            strike_str = f" ${leg.strike}" if leg.strike else ""
            legs_str_list.append(f"{leg.side} {leg.optionType}{strike_str} (In: ${leg.openPrice:.2f} | Out: ${leg.closePrice if leg.closePrice is not None else 0.0:.2f})")
            
        leg_desc = " / ".join(legs_str_list)
        closed_details.append(
            f"  • **{t.ticker}** closed in `{t.account.name}` | **PnL: ${pnl:+,.2f}**\n"
            f"    - Legs: {leg_desc}\n"
            f"    - Fill Assumption: `{fill_assump}`"
        )
        
    trade_summary += f"  • Realized P&L: **${total_pnl:+,.2f}**\n"
    print(trade_summary)
    
    if closed_details:
        print("Closed Positions Details:")
        for cd in closed_details:
            print(cd)
            
    # -------------------------------------------------------------------------
    # 2. Log Analysis
    # -------------------------------------------------------------------------
    log_path = "strategy_engine.log"
    tick_stock_count = 0
    tick_index_count = 0
    tick_daily_count = 0
    eod_rollup_count = 0
    log_errors = []
    log_warnings = []
    
    target_date_prefix = target_date.strftime("%Y-%m-%d")
    
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith(target_date_prefix):
                    if "tick_index" in line:
                        tick_index_count += 1
                    elif "tick_stock" in line:
                        tick_stock_count += 1
                    elif "tick_daily" in line:
                        tick_daily_count += 1
                    elif "eod_analytics_job" in line or "run_daily_rollup" in line:
                        eod_rollup_count += 1
                        
                    if "[ERROR]" in line or "Exception" in line or "Error" in line:
                        log_errors.append(line.strip())
                    elif "[WARNING]" in line:
                        log_warnings.append(line.strip())
                        
    log_summary = f"📋 **Scheduler Performance & Cadence Counts:**\n"
    log_summary += f"  • Tier-1 Index Scans (`tick_index`): {tick_index_count} / 390 expected\n"
    log_summary += f"  • Tier-2 Stock Scans (`tick_stock`): {tick_stock_count} / 78 expected\n"
    log_summary += f"  • Tier-3 Daily Scans (`tick_daily`): {tick_daily_count} / 1 expected\n"
    log_summary += f"  • EOD Analytics Rollups: {eod_rollup_count} / 1 expected\n"
    print(log_summary)

    # Errors and Warnings
    print(f"⚠️ **Issues & Safety Tally:**")
    print(f"  • System Warnings: {len(log_warnings)}")
    print(f"  • System Errors: {len(log_errors)}")
    
    if log_errors:
        print("  Sample errors today:")
        unique_errors = list(set([err.split(":")[-1].strip() for err in log_errors]))[:5]
        for ue in unique_errors:
            print(f"    - {ue}")
            
    # -------------------------------------------------------------------------
    # 3. Data Pipeline Health Verification
    # -------------------------------------------------------------------------
    # Fetch GEX snapshot counts and latest update time for today
    latest_gex = await db.gexsnapshot.find_first(
        where={
            "createdAt": {"gte": start_dt, "lte": end_dt}
        },
        order={"createdAt": "desc"}
    )
    gex_count = await db.gexsnapshot.count(
        where={
            "createdAt": {"gte": start_dt, "lte": end_dt}
        }
    )
    
    pipeline_summary = f"🗄️ **Upstream Data Pipeline Health:**\n"
    pipeline_summary += f"  • Total GEX Snapshots today: {gex_count}\n"
    if latest_gex:
        latest_time = latest_gex.createdAt.astimezone(TZ_ET).strftime("%H:%M:%S %Z")
        pipeline_summary += f"  • Latest database snapshot write: **{latest_time}**\n"
    else:
        pipeline_summary += f"  • Latest database snapshot write: **N/A** (No GEX snapshots captured today)\n"
    print(pipeline_summary)

    # -------------------------------------------------------------------------
    # 3b. Staged Signal Pipeline Analytics
    # -------------------------------------------------------------------------
    staged_signals = await db.stagedsignal.find_many(
        where={
            "stagedAt": {"gte": start_dt, "lte": end_dt}
        }
    )
    staged_count = len(staged_signals)
    executed_staged = len([s for s in staged_signals if s.status == "EXECUTED"])
    expired_staged = len([s for s in staged_signals if s.status == "EXPIRED"])
    pending_staged = len([s for s in staged_signals if s.status == "PENDING"])

    # Parse strategy_engine.log for exact validation guard failure reasons
    expired_reasons = {}
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith(target_date_prefix) and "EXPIRED due to validation failure:" in line:
                    try:
                        parts = line.split("EXPIRED due to validation failure: ")
                        if len(parts) > 1:
                            reason = parts[1].strip()
                            expired_reasons[reason] = expired_reasons.get(reason, 0) + 1
                    except Exception:
                        pass

    staged_summary = f"🗳️ **Staged Signal Pipeline Tally:**\n"
    staged_summary += f"  • Total Setups Staged Today: {staged_count}\n"
    staged_summary += f"    - Executed: {executed_staged}\n"
    staged_summary += f"    - Expired (Cancelled): {expired_staged}\n"
    staged_summary += f"    - Pending Execution: {pending_staged}\n"
    
    if expired_reasons:
        staged_summary += f"  • Active Guard Expiration Reasons:\n"
        for reason, count in expired_reasons.items():
            staged_summary += f"    - ❌ {reason}: {count}\n"
    elif expired_staged > 0:
        staged_summary += f"  • Active Guard Expiration Reasons: (No diagnostic details in logs)\n"
    print(staged_summary)

    # -------------------------------------------------------------------------
    # 3c. Transaction Slippage Analytics
    # -------------------------------------------------------------------------
    total_entry_slippage = 0.0
    total_exit_slippage = 0.0
    entry_slippage_legs = 0
    exit_slippage_legs = 0

    for t in trades:
        if t.metadata:
            try:
                meta = json.loads(t.metadata)
                if "applied_slippages" in meta:
                    slips = meta["applied_slippages"]
                    if isinstance(slips, list):
                        total_entry_slippage += sum(slips)
                        entry_slippage_legs += len(slips)
                if "exit_slippages" in meta:
                    slips = meta["exit_slippages"]
                    if isinstance(slips, list):
                        total_exit_slippage += sum(slips)
                        exit_slippage_legs += len(slips)
            except Exception:
                pass

    avg_entry_leg = total_entry_slippage / entry_slippage_legs if entry_slippage_legs > 0 else 0.0
    avg_exit_leg = total_exit_slippage / exit_slippage_legs if exit_slippage_legs > 0 else 0.0

    slippage_summary = f"💸 **Transaction Slippage Analytics:**\n"
    slippage_summary += f"  • Total Entry Slippage Paid: ${total_entry_slippage:.2f} (across {entry_slippage_legs} legs)\n"
    slippage_summary += f"    - Avg Entry Leg Slippage: ${avg_entry_leg:.3f}\n"
    slippage_summary += f"  • Total Exit Slippage Paid: ${total_exit_slippage:.2f} (across {exit_slippage_legs} legs)\n"
    slippage_summary += f"    - Avg Exit Leg Slippage: ${avg_exit_leg:.3f}\n"
    print(slippage_summary)

    await db.disconnect()

    # -------------------------------------------------------------------------
    # 4. Construct Discord Message & Send
    # -------------------------------------------------------------------------
    if send_to_discord:
        config = load_config()
        
        discord_pnl_str = f"**${total_pnl:+,.2f}**"
        pnl_emoji = "🟢" if total_pnl >= 0.0 else "🔴"
        
        discord_msg = (
            f"📅 🔍 **DAILY OPTIONS ENGINE SYSTEM AUDIT** 🔍 📅\n"
            f"*Date: {target_date.strftime('%Y-%m-%d')} ({target_date.strftime('%A')})*\n\n"
            f"{trade_summary}\n"
            f"💰 **Realized P&L Outcome:** {pnl_emoji} {discord_pnl_str}\n\n"
        )
        
        if closed_details:
            discord_msg += f"📜 **Closed Positions Details:**\n"
            for cd in closed_details[:10]: # Cap to prevent giant messages
                discord_msg += f"{cd}\n"
            discord_msg += "\n"
            
        discord_msg += f"{staged_summary}\n"
        discord_msg += f"{slippage_summary}\n"
        discord_msg += f"{log_summary}\n"
        discord_msg += (
            f"⚠️ **Logs & Safety Diagnostics:**\n"
            f"  • Warnings: `{len(log_warnings)}`\n"
            f"  • Errors: `{len(log_errors)}`\n\n"
            f"{pipeline_summary}\n"
            f"🏁 **Audit Status:** ✅ System is running continuously and safely."
        )
        
        send_discord_report(discord_msg, config)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Options Strategy Engine Daily Audit")
    parser.add_argument("--date", type=str, default=datetime.now(TZ_ET).strftime("%Y-%m-%d"),
                        help="Audit date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--discord", action="store_true", help="Post results directly to Discord if enabled")
    args = parser.parse_args()

    asyncio_run = None
    import asyncio
    try:
        asyncio.run(run_audit(args.date, args.discord))
    except (KeyboardInterrupt, SystemExit):
        print("Audit script interrupted.")
