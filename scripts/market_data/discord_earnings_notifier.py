"""
discord_earnings_notifier.py
=============================
Queries upcoming earnings from the database, formats a friendly, metrics-rich
briefing (expected moves, volatility edge, index movers, short float, etc.),
and posts it to Discord. Supports post-earnings RECAP reports.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.libs_py.discord import (
    load_webhook_url as _shared_load_webhook_url,
    send_payload as _shared_send_payload,
)

try:
    import yfinance as yf
except ImportError:
    yf = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("discord_earnings")

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "web" / "prisma" / "dev.db"
DISCORD_WEBHOOKS_PATH = REPO_ROOT / "discord_webhooks.json"

# --- Constants ---
EDGE_RICH_THRESHOLD = 1.8
EDGE_FAIR_THRESHOLD = 0.9

# Configurable static lookup for significant SPX/NDX constituents
INDEX_MOVERS = {
    "AAPL": "NDX/SPX-mover",
    "MSFT": "NDX/SPX-mover",
    "NVDA": "NDX/SPX-mover",
    "AMZN": "NDX/SPX-mover",
    "META": "NDX/SPX-mover",
    "GOOGL": "NDX/SPX-mover",
    "AVGO": "NDX/SPX-mover",
    "TSLA": "NDX/SPX-mover",
    "COST": "NDX/SPX-mover",
    "NFLX": "NDX-mover",
    "AMD": "NDX-mover",
    "QCOM": "NDX-mover",
    "PEP": "NDX-mover",
    "ADBE": "NDX-mover",
    "LLY": "SPX-mover",
    "JPM": "SPX-mover",
    "UNH": "SPX-mover",
    "XOM": "SPX-mover",
    "V": "SPX-mover",
    "PG": "SPX-mover",
    "MA": "SPX-mover",
}


# --- Core Analytics Functions ---

def parse_reactions(reactions_str: str) -> list[float]:
    """Extract absolute float percentage values from the reactions string."""
    matches = re.findall(r"([+-]?\d+(?:\.\d+)?)\s*%", reactions_str)
    return [abs(float(m) / 100.0) for m in matches]


def calculate_vol_edge(priced_move_pct: float | None, reactions_str: str) -> tuple[float | None, float | None, str, str]:
    """
    Computes the edge ratio of priced move vs historical realized average.
    Returns (edge_ratio, avg_abs_realized, emoji_marker, tier_label)
    """
    if priced_move_pct is None or not reactions_str or reactions_str == "N/A":
        return None, None, "⚪", "UNKNOWN"

    realized_moves = parse_reactions(reactions_str)
    if not realized_moves:
        return None, None, "⚪", "UNKNOWN"

    avg_abs_realized = sum(realized_moves) / len(realized_moves)
    if avg_abs_realized == 0:
        return None, None, "⚪", "UNKNOWN"

    edge_ratio = round(priced_move_pct / avg_abs_realized, 4)

    if edge_ratio >= EDGE_RICH_THRESHOLD:
        marker = "🟢"
        tier = "RICH (sell-premium candidate)"
    elif edge_ratio >= EDGE_FAIR_THRESHOLD:
        marker = "🟡"
        tier = "FAIR"
    else:
        marker = "🔵"
        tier = "CHEAP (buy-premium / respect the tail)"

    return edge_ratio, avg_abs_realized, marker, tier


def calculate_straddle_breakevens(spot: float, call_mid: float, put_mid: float) -> tuple[float, float, float, float]:
    """
    Computes long straddle breakevens.
    Returns (straddle_cost, lower_be, upper_be, priced_move_pct)
    """
    straddle_cost = call_mid + put_mid
    priced_move_pct = straddle_cost / spot if spot > 0 else 0.0
    lower_be = spot - straddle_cost
    upper_be = spot + straddle_cost
    return straddle_cost, lower_be, upper_be, priced_move_pct


def calculate_iv_rank(current_iv: float | None, high_52w: float | None, low_52w: float | None) -> float | None:
    """
    Computes 52-week IV Rank.
    TODO: Integrate a secondary provider for trailing 52-week IV range as yfinance lacks complete history.
    """
    if current_iv is None or high_52w is None or low_52w is None:
        return None
    range_52w = high_52w - low_52w
    if range_52w == 0:
        return 0.0
    return (current_iv - low_52w) / range_52w * 100.0


def calculate_expected_move_levels(spot: float, priced_move_pct: float) -> tuple[float, float]:
    """Computes expected-move price levels (spot - move * 0.85, spot + move * 0.85)"""
    move_dist = spot * priced_move_pct * 0.85
    return spot - move_dist, spot + move_dist


# --- Helpers & Notifiers ---

def _load_webhook_url(target_key: str) -> str | None:
    """Look up the Discord webhook URL for ``target_key``.

    Thin shim over :func:`scripts.libs_py.discord.load_webhook_url`
    that preserves the historical return-None-on-missing contract
    (the in-line `requests.post` call sites use ``if not webhook_url
    and not dry_run`` to bail, so we must return ``None`` on
    missing).
    """
    return _shared_load_webhook_url(
        target_key,
        webhooks_path=DISCORD_WEBHOOKS_PATH,
    )


def _get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_ticker_metadata(tickers: list[str], ticker_earnings_dates: dict[str, datetime]) -> dict[str, dict[str, Any]]:
    """Fetch company name, short interest, options expected move, consensus, and history."""
    if not tickers or yf is None:
        return {}

    metadata = {}
    log.info(f"Fetching enhanced quantitative metadata for {len(tickers)} tickers from yfinance...")
    
    for t in tickers:
        log.info(f"Processing ticker {t}...")
        try:
            ticker = yf.Ticker(t)
            info = ticker.info
            
            # Casey's General Store string cleanup
            company = info.get("shortName") or info.get("longName") or t
            if "Caseys General Stores" in company:
                company = company.replace("Caseys General Stores", "Casey's General Store")
            elif "Caseys General" in company:
                company = company.replace("Caseys General", "Casey's General Store")

            short_float = info.get("shortPercentOfFloat") or 0.0
            rec = info.get("recommendationKey") or "Hold"
            
            target = info.get("targetMeanPrice")
            current = info.get("currentPrice") or info.get("regularMarketPrice") or 1.0
            premium = (target / current - 1) if target and current else 0.0

            # Data Validations (Sanity Checks)
            market_cap = info.get("marketCap", 0.0) or 0.0
            revenue = info.get("totalRevenue", 0.0) or 0.0
            if market_cap > 0 and market_cap < 1e6:
                log.warning(f"Sanity Check: {t} market cap looks implausibly small: ${market_cap:,.0f}")
            if revenue > 0 and revenue < 1e5:
                log.warning(f"Sanity Check: {t} revenue looks implausibly small: ${revenue:,.0f}")
            
            # Warn when consensus is BUY/STRONG_BUY and target premium < -10%,
            # or when consensus is SELL/STRONG_SELL and target premium > +10%
            if rec.upper() in ["BUY", "STRONG_BUY"] and premium < -0.10:
                log.warning(f"Stale Analyst Warning for {t}: Rating is {rec} but target premium is negative: {premium:+.1%}")
            elif rec.upper() in ["SELL", "STRONG_SELL"] and premium > 0.10:
                log.warning(f"Stale Analyst Warning for {t}: Rating is {rec} but target premium is positive: {premium:+.1%}")

            # 1. Expected Move from ATM Option Chain
            straddle_cost = None
            lower_be = None
            upper_be = None
            straddle_move = None
            
            try:
                expiries = ticker.options
                if expiries:
                    underlying_price = current
                    if underlying_price:
                        # Fetch nearest expiry to calculate baseline priced_move_pct
                        nearest_chain = ticker.option_chain(expiries[0])
                        n_calls, n_puts = nearest_chain.calls, nearest_chain.puts
                        closest_n_call = n_calls.iloc[(n_calls['strike'] - underlying_price).abs().argsort()[:1]]
                        closest_n_put = n_puts.iloc[(n_puts['strike'] - underlying_price).abs().argsort()[:1]]
                        n_call_mid = (closest_n_call['bid'].values[0] + closest_n_call['ask'].values[0]) / 2
                        n_put_mid = (closest_n_put['bid'].values[0] + closest_n_put['ask'].values[0]) / 2
                        nearest_straddle = n_call_mid + n_put_mid
                        nearest_move_pct = nearest_straddle / underlying_price
                        
                        # Find first expiry on or after earnings_date
                        target_expiry = expiries[0]
                        t_earnings_date = ticker_earnings_dates.get(t)
                        if t_earnings_date:
                            if isinstance(t_earnings_date, datetime):
                                t_earnings_date = t_earnings_date.date()
                            for exp in expiries:
                                exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
                                if exp_date >= t_earnings_date:
                                    target_expiry = exp
                                    break
                        
                        log.info(f"Targeting options expiry {target_expiry} for earnings date {t_earnings_date}")
                        opt_chain = ticker.option_chain(target_expiry)
                        calls, puts = opt_chain.calls, opt_chain.puts
                        
                        closest_call = calls.iloc[(calls['strike'] - underlying_price).abs().argsort()[:1]]
                        closest_put = puts.iloc[(puts['strike'] - underlying_price).abs().argsort()[:1]]
                        call_mid = (closest_call['bid'].values[0] + closest_call['ask'].values[0]) / 2
                        put_mid = (closest_put['bid'].values[0] + closest_put['ask'].values[0]) / 2
                        
                        straddle_cost = call_mid + put_mid
                        
                        # Compute breakevens strictly as spot +/- straddle_cost
                        lower_be = underlying_price - straddle_cost
                        upper_be = underlying_price + straddle_cost
                        
                        # Derive priced_move_pct = straddle_cost / spot
                        straddle_move = straddle_cost / underlying_price
                        
                        # Print intermediate values to the log for easy verification
                        log.info(
                            f"RECONCILIATION: {t} | Spot: {underlying_price:.2f} | "
                            f"ATM Call Mid: {call_mid:.2f} | ATM Put Mid: {put_mid:.2f} | "
                            f"Straddle Cost: {straddle_cost:.2f} | Derived Move: {straddle_move:.2%}"
                        )
                        
                        # Reconciliation warning: compare post-earnings derived move against nearest expiry baseline
                        if abs(straddle_move - nearest_move_pct) > 0.005:
                            log.warning(
                                f"Reconciliation Warning for {t}: priced_move_pct ({straddle_move:.2%}) "
                                f"diverges from nearest expiry move ({nearest_move_pct:.2%}) by > 0.5%"
                            )
            except Exception as opt_err:
                log.warning(f"Could not compute option expected move for {t}: {opt_err}")

            # 2. Expected Numbers from Calendar
            eps_est = None
            rev_est = None
            try:
                cal = ticker.calendar
                eps_est = cal.get("Earnings Average")
                rev_est = cal.get("Revenue Average")
            except Exception:
                pass

            # 3. Historical reactions (up to 8 dates)
            reactions = []
            try:
                dates_df = ticker.earnings_dates
                if dates_df is not None and not dates_df.empty:
                    # Index 0 is the upcoming one, check 1 to 8
                    for date_idx in dates_df.index[1:9]:
                        edate = date_idx.date()
                        start_w = edate - timedelta(days=4)
                        end_w = edate + timedelta(days=5)
                        h = ticker.history(start=start_w, end=end_w)
                        ts = [idx for idx in h.index if idx.date() >= edate]
                        if ts:
                            pos = h.index.get_loc(ts[0])
                            price_day_of = h['Close'].iloc[pos]
                            price_next = h['Close'].iloc[pos + 1]
                            ret = (price_next / price_day_of - 1)
                            # Explicitly label move type as 1d% (close-to-close)
                            reactions.append(f"{edate.strftime('%b%y')} (1d%): {ret:+.1%}")
            except Exception as hist_err:
                log.warning(f"Could not compute historical reactions for {t}: {hist_err}")

            # 4. IV Rank (fallback to None)
            iv_rank_val = None
            
            metadata[t] = {
                "company": company,
                "short_float": short_float,
                "recommendation": rec.upper(),
                "target_premium": premium,
                "expected_move": straddle_move,
                "straddle_cost": straddle_cost,
                "lower_be": lower_be,
                "upper_be": upper_be,
                "eps_est": eps_est,
                "rev_est": rev_est,
                "reactions": ", ".join(reactions) if reactions else "N/A",
                "iv_rank": iv_rank_val,
                "spot": current
            }
        except Exception as e:
            log.error(f"Failed to fetch metadata for {t}: {e}")
            metadata[t] = {
                "company": t,
                "short_float": 0.0,
                "recommendation": "HOLD",
                "target_premium": 0.0,
                "expected_move": None,
                "straddle_cost": None,
                "lower_be": None,
                "upper_be": None,
                "eps_est": None,
                "rev_est": None,
                "reactions": "N/A",
                "iv_rank": None,
                "spot": 1.0
            }

    return metadata


def _format_revenue(val: float | None) -> str:
    if val is None or not val:
        return "N/A"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    if val >= 1e6:
        return f"${val/1e6:.1f}M"
    return f"${val:,.0f}"


def build_eod_payload(events: list[dict], date_target: date, metadata: dict) -> dict:
    bmo_list = []
    amc_list = []

    # Map events to structured dicts containing their calculated edge ratios
    processed_events = []
    for ev in events:
        ticker = ev["ticker"]
        meta = metadata.get(ticker, {})
        edge_ratio, avg_abs_realized, marker, tier = calculate_vol_edge(meta.get("expected_move"), meta.get("reactions", ""))
        processed_events.append({
            "ev": ev,
            "meta": meta,
            "edge": edge_ratio or 0.0,
            "marker": marker,
            "tier": tier,
            "avg_abs_realized": avg_abs_realized
        })

    # Sort BMO/AMC categories by mispricing magnitude abs(edge - 1.0) descending.
    # Rich-vs-cheap ties broken by higher edge first.
    bmo_events = [p for p in processed_events if p["ev"]["beforeMarket"]]
    amc_events = [p for p in processed_events if not p["ev"]["beforeMarket"]]
    
    bmo_events.sort(key=lambda x: (abs(x["edge"] - 1.0), x["edge"]), reverse=True)
    amc_events.sort(key=lambda x: (abs(x["edge"] - 1.0), x["edge"]), reverse=True)

    for p in bmo_events:
        ticker = p["ev"]["ticker"]
        meta = p["meta"]
        spot = meta.get("spot", 1.0)
        
        move_str = f"±{meta['expected_move']:.1%}" if meta.get("expected_move") else "N/A"
        
        # Squeeze Potential: Drop short interest when < 15%
        short_val = meta.get("short_float", 0.0)
        short_str = f" | Short Float: `{short_val*100:.1f}%`" if short_val >= 0.15 else ""
        
        eps_str = f"${meta['eps_est']:.2f}" if meta.get("eps_est") is not None else "N/A"
        rev_str = _format_revenue(meta.get("rev_est"))
        premium_str = f"{meta['target_premium']:+.1%}" if meta.get("target_premium") else "N/A"
        
        # Expected Move levels (derived from spot * priced_move_pct)
        em_lower, em_upper = calculate_expected_move_levels(spot, meta.get("expected_move", 0.0) or 0.0)
        em_levels_str = f"EM: {move_str} → {em_lower:,.2f} / {em_upper:,.2f}" if meta.get("expected_move") else "EM: N/A"
        
        # Straddle cost & breakevens (derived from actual straddle cost)
        straddle_cost = meta.get("straddle_cost")
        if straddle_cost is not None:
            lower_be = spot - straddle_cost
            upper_be = spot + straddle_cost
            straddle_str = f"Straddle: ${straddle_cost:.2f} | BE: {lower_be:,.2f} / {upper_be:,.2f}"
        else:
            straddle_str = "Straddle: N/A"
        
        # Edge String
        edge_text = ""
        if p["edge"] > 0:
            edge_text = f"  Edge: {p['marker']} **{p['tier']}** — `{move_str}` priced vs `{p['avg_abs_realized']:.1%}` avg realized ({p['edge']:.1f}x)\n"

        # Index weight flag
        idx_flag = f" ⭐ **{INDEX_MOVERS[ticker]}**" if ticker in INDEX_MOVERS else ""

        desc = (
            f"• **{ticker}** ({meta.get('company', ticker)}){idx_flag}\n"
            f"{edge_text}"
            f"  {em_levels_str}{short_str}\n"
            f"  {straddle_str}\n"
            f"  Estimates: EPS `{eps_str}` | Rev `{rev_str}`\n"
            f"  Consensus: `{meta.get('recommendation', 'HOLD')}` (Target Prem: `{premium_str}`)\n"
            f"  Reactions: *{meta.get('reactions', 'N/A')}*\n"
        )
        bmo_list.append(desc)

    for p in amc_events:
        ticker = p["ev"]["ticker"]
        meta = p["meta"]
        spot = meta.get("spot", 1.0)
        
        move_str = f"±{meta['expected_move']:.1%}" if meta.get("expected_move") else "N/A"
        
        # Squeeze Potential: Drop short interest when < 15%
        short_val = meta.get("short_float", 0.0)
        short_str = f" | Short Float: `{short_val*100:.1f}%`" if short_val >= 0.15 else ""
        
        eps_str = f"${meta['eps_est']:.2f}" if meta.get("eps_est") is not None else "N/A"
        rev_str = _format_revenue(meta.get("rev_est"))
        premium_str = f"{meta['target_premium']:+.1%}" if meta.get("target_premium") else "N/A"
        
        # Expected Move levels (derived from spot * priced_move_pct)
        em_lower, em_upper = calculate_expected_move_levels(spot, meta.get("expected_move", 0.0) or 0.0)
        em_levels_str = f"EM: {move_str} → {em_lower:,.2f} / {em_upper:,.2f}" if meta.get("expected_move") else "EM: N/A"
        
        # Straddle cost & breakevens (derived from actual straddle cost)
        straddle_cost = meta.get("straddle_cost")
        if straddle_cost is not None:
            lower_be = spot - straddle_cost
            upper_be = spot + straddle_cost
            straddle_str = f"Straddle: ${straddle_cost:.2f} | BE: {lower_be:,.2f} / {upper_be:,.2f}"
        else:
            straddle_str = "Straddle: N/A"
        
        # Edge String
        edge_text = ""
        if p["edge"] > 0:
            edge_text = f"  Edge: {p['marker']} **{p['tier']}** — `{move_str}` priced vs `{p['avg_abs_realized']:.1%}` avg realized ({p['edge']:.1f}x)\n"

        # Index weight flag
        idx_flag = f" ⭐ **{INDEX_MOVERS[ticker]}**" if ticker in INDEX_MOVERS else ""

        desc = (
            f"• **{ticker}** ({meta.get('company', ticker)}){idx_flag}\n"
            f"{edge_text}"
            f"  {em_levels_str}{short_str}\n"
            f"  {straddle_str}\n"
            f"  Estimates: EPS `{eps_str}` | Rev `{rev_str}`\n"
            f"  Consensus: `{meta.get('recommendation', 'HOLD')}` (Target Prem: `{premium_str}`)\n"
            f"  Reactions: *{meta.get('reactions', 'N/A')}*\n"
        )
        amc_list.append(desc)

    fields = []
    if bmo_list:
        fields.append({
            "name": "🌅 Before Market Open (BMO) Releases",
            "value": "\n".join(bmo_list),
            "inline": False
        })
    if amc_list:
        fields.append({
            "name": "🌆 After Market Close (AMC) Releases",
            "value": "\n".join(amc_list),
            "inline": False
        })

    if not fields:
        fields.append({
            "name": "Notice",
            "value": "No major earnings events scheduled.",
            "inline": False
        })

    embed = {
        "title": f"📅 Pre-Market Earnings Prep — {date_target.strftime('%A, %b %d, %Y')}",
        "description": "Tactical volatility briefings and priced-in expected moves.",
        "color": 0x4B0082,
        "fields": fields,
        "footer": {
            "text": "TCM Options Pipeline • Sourced via Yahoo Finance Options"
        },
        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
    }

    return {"embeds": [embed]}


def build_eow_payload(events: list[dict], start_date: date, end_date: date, metadata: dict) -> dict:
    by_day = {}
    for ev in events:
        dt = ev["earningsDate"].date()
        if dt not in by_day:
            by_day[dt] = []
        by_day[dt].append(ev)

    fields = []
    for dt in sorted(by_day.keys()):
        day_events = by_day[dt]
        
        # Sort weekly events by mispricing magnitude abs(edge - 1.0) descending.
        # Rich-vs-cheap ties broken by higher edge first.
        processed_day = []
        for ev in day_events:
            ticker = ev["ticker"]
            meta = metadata.get(ticker, {})
            edge_ratio, avg_abs_realized, marker, tier = calculate_vol_edge(meta.get("expected_move"), meta.get("reactions", ""))
            processed_day.append({
                "ev": ev,
                "meta": meta,
                "edge": edge_ratio or 0.0,
                "marker": marker,
                "tier": tier
            })
        processed_day.sort(key=lambda x: (abs(x["edge"] - 1.0), x["edge"]), reverse=True)
        
        lines = []
        for p in processed_day:
            ticker = p["ev"]["ticker"]
            meta = p["meta"]
            timing_icon = "🌅" if p["ev"]["beforeMarket"] else "🌆"
            move_str = f"±{meta['expected_move']:.1%}" if meta.get("expected_move") else "N/A"
            
            # Squeeze Potential: Drop short interest when < 15%
            short_val = meta.get("short_float", 0.0)
            short_str = f" | Short: `{short_val*100:.1f}%`" if short_val >= 0.15 else ""
            
            # Edge tag
            edge_str = f" | Edge: {p['marker']} ({p['edge']:.1f}x)" if p["edge"] > 0 else ""
            
            # Index weight flag
            idx_flag = " ⭐" if ticker in INDEX_MOVERS else ""
            
            lines.append(f"{timing_icon}{idx_flag} **{ticker}** | Priced Move: `{move_str}`{short_str}{edge_str} | Rec: `{meta.get('recommendation', 'HOLD')}`")
            
        fields.append({
            "name": f"📆 {dt.strftime('%A, %b %d')}",
            "value": "\n".join(lines),
            "inline": False
        })

    embed = {
        "title": f"📅 Weekly Earnings Calendar ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})",
        "description": "Weekly roadmap of priced-in volatility curves & float dynamics.",
        "color": 0x4B0082,
        "fields": fields,
        "footer": {
            "text": "TCM Options Pipeline • Sourced via Yahoo Finance Options"
        },
        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
    }

    return {"embeds": [embed]}


def run_recap(channel_key: str, custom_date: str | None = None, dry_run: bool = False):
    webhook_url = _load_webhook_url(channel_key)
    if not webhook_url and not dry_run:
        log.error(f"Webhook key '{channel_key}' not found. Aborting.")
        return

    ref_date = datetime.strptime(custom_date, "%Y-%m-%d").date() if custom_date else datetime.now().date()
    log.info(f"Running Post-Earnings Recap for date: {ref_date}")

    events = []
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        start_str = f"{ref_date.isoformat()}T00:00:00.000+00:00"
        end_str = f"{ref_date.isoformat()}T23:59:59.999+00:00"
        cursor.execute(
            "SELECT ticker, beforeMarket FROM EarningsCalendar WHERE earningsDate >= ? AND earningsDate <= ? ORDER BY ticker ASC",
            (start_str, end_str)
        )
        rows = cursor.fetchall()
        for r in rows:
            events.append({
                "ticker": r["ticker"],
                "beforeMarket": bool(r["beforeMarket"])
            })
        conn.close()
    except Exception as e:
        log.error(f"Failed to fetch recap events: {e}")
        return

    if not events:
        log.info("No earnings releases recorded for this date range in the local database.")
        return

    log.info(f"Calculating post-earnings performance for {len(events)} symbols...")
    recap_lines = []
    
    for ev in events:
        t = ev["ticker"]
        try:
            ticker = yf.Ticker(t)
            info = ticker.info
            
            start_w = ref_date - timedelta(days=4)
            end_w = ref_date + timedelta(days=5)
            h = ticker.history(start=start_w, end=end_w)
            
            ts = [idx for idx in h.index if idx.date() >= ref_date]
            if not ts:
                continue
                
            pos = h.index.get_loc(ts[0])
            price_prev = h['Close'].iloc[pos - 1]
            price_open = h['Open'].iloc[pos]
            price_close = h['Close'].iloc[pos]
            
            gap_pct = (price_open / price_prev - 1)
            actual_move = (price_close / price_prev - 1)
            
            dates_df = ticker.earnings_dates
            reported_eps = "N/A"
            surprise_pct = "N/A"
            if dates_df is not None and not dates_df.empty:
                matching_rows = dates_df[dates_df.index.map(lambda idx: idx.date() == ref_date)]
                if not matching_rows.empty:
                    reported_eps = f"${matching_rows['Reported EPS'].values[0]:.2f}" if matching_rows['Reported EPS'].values[0] is not None else "N/A"
                    surprise_pct = f"{matching_rows['Surprise(%)'].values[0]:+.1f}%" if matching_rows['Surprise(%)'].values[0] is not None else "N/A"

            # ATM straddle calculation
            opt_exp_move = 0.08
            try:
                expiries = ticker.options
                if expiries:
                    target_expiry = expiries[0]
                    for exp in expiries:
                        exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
                        if exp_date >= ref_date:
                            target_expiry = exp
                            break
                    chain = ticker.option_chain(target_expiry)
                    calls, puts = chain.calls, chain.puts
                    closest_call = calls.iloc[(calls['strike'] - price_close).abs().argsort()[:1]]
                    closest_put = puts.iloc[(puts['strike'] - price_close).abs().argsort()[:1]]
                    call_mid = (closest_call['bid'].values[0] + closest_call['ask'].values[0]) / 2
                    put_mid = (closest_put['bid'].values[0] + closest_put['ask'].values[0]) / 2
                    straddle_cost = call_mid + put_mid
                    opt_exp_move = straddle_cost / price_close if price_close > 0 else 0.0
            except Exception:
                pass
            
            move_type = "🌅 BMO" if ev["beforeMarket"] else "🌆 AMC"
            over_under = "🔥 Exceeded" if abs(actual_move) > opt_exp_move else "🧊 Crushed (Under)"
            
            recap_lines.append(
                f"• **{t}** ({move_type})\n"
                f"  Actual Return: `{actual_move:+.1%}` (Gap: `{gap_pct:+.1%}`)\n"
                f"  Options Priced: `±{opt_exp_move:.1%}` | Result: **{over_under}**\n"
                f"  Reported EPS: `{reported_eps}` | Surprise: `{surprise_pct}`\n"
            )
        except Exception as e:
            log.error(f"Failed to calculate recap for {t}: {e}")

    if not recap_lines:
        log.info("Could not calculate recap metrics for any tickers.")
        return

    embed = {
        "title": f"🏆 Post-Earnings Recap — {ref_date.strftime('%A, %b %d, %Y')}",
        "description": "Comparing actual realized moves vs. options priced-in expected moves.",
        "color": 0xFF8C00,
        "fields": [
            {
                "name": "📊 Earnings Performance & Volatility Mismatch",
                "value": "\n".join(recap_lines),
                "inline": False
            }
        ],
        "footer": {
            "text": "TCM Options Pipeline • Sourced via Yahoo Finance Options"
        },
        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
    }
    
    payload = {"embeds": [embed]}

    if dry_run:
        log.info("Dry run enabled. Post-Earnings Recap Preview:")
        print(json.dumps(payload, indent=2))
        return

    ok = _shared_send_payload(webhook_url, payload)
    if ok:
        log.info("Successfully posted post-earnings recap to Discord.")
    else:
        log.error("Failed to deliver post-earnings recap to Discord.")


def run_notify(mode: str, channel_key: str, custom_date: str | None = None, dry_run: bool = False):
    if mode == "RECAP":
        run_recap(channel_key, custom_date, dry_run)
        return

    webhook_url = _load_webhook_url(channel_key)
    if not webhook_url and not dry_run:
        log.error(f"Discord webhook URL not found for key '{channel_key}'. Aborting.")
        return

    if custom_date:
        ref_date = datetime.strptime(custom_date, "%Y-%m-%d").date()
    else:
        ref_date = (datetime.now() + timedelta(days=1)).date()
        if mode == "EOD" and ref_date.weekday() >= 5:
            days_to_add = 7 - ref_date.weekday()
            ref_date = ref_date + timedelta(days=days_to_add)

    log.info(f"Targeting earnings notifications for mode '{mode}' starting at {ref_date}")

    events = []
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        if mode == "EOD":
            start_str = f"{ref_date.isoformat()}T00:00:00.000+00:00"
            end_str = f"{ref_date.isoformat()}T23:59:59.999+00:00"
            cursor.execute(
                "SELECT ticker, earningsDate, beforeMarket FROM EarningsCalendar WHERE earningsDate >= ? AND earningsDate <= ? ORDER BY beforeMarket DESC, ticker ASC",
                (start_str, end_str)
            )
            rows = cursor.fetchall()
            for r in rows:
                dt = datetime.fromisoformat(r["earningsDate"].replace("Z", "+00:00"))
                events.append({
                    "ticker": r["ticker"],
                    "earningsDate": dt,
                    "beforeMarket": bool(r["beforeMarket"])
                })
            start_range = ref_date
            end_range = ref_date
        else:
            start_range = ref_date
            end_range = ref_date + timedelta(days=6)
            start_str = f"{start_range.isoformat()}T00:00:00.000+00:00"
            end_str = f"{end_range.isoformat()}T23:59:59.999+00:00"
            cursor.execute(
                "SELECT ticker, earningsDate, beforeMarket FROM EarningsCalendar WHERE earningsDate >= ? AND earningsDate <= ? ORDER BY earningsDate ASC, beforeMarket DESC, ticker ASC",
                (start_str, end_str)
            )
            rows = cursor.fetchall()
            for r in rows:
                dt = datetime.fromisoformat(r["earningsDate"].replace("Z", "+00:00"))
                events.append({
                    "ticker": r["ticker"],
                    "earningsDate": dt,
                    "beforeMarket": bool(r["beforeMarket"])
                })
        conn.close()
    except Exception as e:
        log.error(f"Failed to fetch from SQLite: {e}")
        return

    if not events:
        log.info("No earnings events found in local database for this date range.")
        return

    log.info(f"Retrieved {len(events)} events from local database.")

    # Fetch enriched metadata in a batch
    tickers = [ev["ticker"] for ev in events]
    ticker_earnings_dates = {ev["ticker"]: ev["earningsDate"] for ev in events}
    metadata = _fetch_ticker_metadata(tickers, ticker_earnings_dates)

    # Build payload
    if mode == "EOD":
        payload = build_eod_payload(events, ref_date, metadata)
    else:
        payload = build_eow_payload(events, start_range, end_range, metadata)

    # Delivery
    if dry_run:
        log.info("Dry run enabled. Discord Payload Preview:")
        print(json.dumps(payload, indent=2))
        return

    ok = _shared_send_payload(webhook_url, payload)
    if ok:
        log.info("Successfully posted earnings briefing to Discord.")
    else:
        log.error("Failed to deliver earnings briefing to Discord.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deliver earnings calendar updates to Discord.")
    parser.add_argument("--mode", choices=["EOD", "EOW", "RECAP"], default="EOD", help="Mode: EOD (daily), EOW (weekly), or RECAP (post-earnings).")
    parser.add_argument("--channel", default="test_channel", help="Discord webhook channel key from configuration.")
    parser.add_argument("--date", help="Custom reference date YYYY-MM-DD (overrides default tomorrow/next week start).")
    parser.add_argument("--dry-run", action="store_true", help="Print the payload instead of sending it to Discord.")
    args = parser.parse_args()

    run_notify(args.mode, args.channel, args.date, args.dry_run)
