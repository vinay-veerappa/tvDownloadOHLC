"""C7: Day Type Classifier.

Classifies the trading day based on economic calendar events.
Returns day type (CLEAN/CPI/NFP/FOMC/SPECIAL/HOLIDAY), sizing, and killzone/no-trade rules.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

log = logging.getLogger(__name__)

# Event name patterns for classification
_CPI_PATTERNS = ["CPI", "CORE CPI", "CONSUMER PRICE"]
_NFP_PATTERNS = ["NON-FARM PAYROLL", "NFP", "NONFARM PAYROLL"]
_FOMC_PATTERNS = ["FOMC", "FEDERAL OPEN MARKET", "INTEREST RATE DECISION"]
_SPECIAL_PATTERNS = ["JACKSON HOLE", "POWELL", "TREASURY AUCTION", "OPEC", "GEOPOLITICAL"]
_HOLIDAY_PATTERNS = ["HOLIDAY", "CLOSED", "EARLY CLOSE"]


def classify_day_type(events: list[dict], today: date) -> dict:
    """Classify today's day type from economic events.

    Args:
        events: list of event dicts with 'name', 'impact', 'datetime' (epoch ms)
        today: date object for the day to classify
    """
    from scripts.trader.config_loader import get_config
    cfg = get_config()
    day_types_cfg = cfg["day_types"]
    killzones_cfg = cfg["killzones"]
    dead_zones = cfg["dead_zones"]
    no_trade = cfg["no_trade_rules"]

    result = {
        "day_type": "clean",
        "sizing_multiplier": 1.0,
        "events_today": [],
        "killzones": [f"London {killzones_cfg['london_open']['start']}-{killzones_cfg['london_open']['end']}",
                      f"NY {killzones_cfg['ny_open']['start']}-{killzones_cfg['ny_open']['end']}",
                      f"Silver Bullet {killzones_cfg['ny_open']['best']}",
                      f"London Close {killzones_cfg['london_close']['start']}-{killzones_cfg['london_close']['end']}"],
        "no_trade_zones": [f"{d['start']}-{d['end']} ({d['reason']})" for d in dead_zones],
        "no_trade_rules": no_trade,
        "guidance": "",
        "event_time": None,
        "pre_event_buffer": None,
        "post_event_wait": None,
    }

    # Filter to today's events
    today_ms_start = int(datetime(today.year, today.month, today.day).timestamp() * 1000)
    today_ms_end = today_ms_start + 86400000
    todays_events = [e for e in events if e.get("datetime", 0) >= today_ms_start and e.get("datetime", 0) < today_ms_end]

    if not todays_events:
        result["day_type"] = "clean"
        result["sizing_multiplier"] = day_types_cfg["clean"]["sizing"]
        result["guidance"] = "Clean calendar. Standard execution. Silver Bullet 10-11 AM is primary."
        return result

    result["events_today"] = [e.get("name", "Unknown") for e in todays_events]

    # Classify based on event names
    has_high = any(e.get("impact") == "HIGH" for e in todays_events)
    high_events = [e for e in todays_events if e.get("impact") == "HIGH"]

    for e in high_events:
        name = e.get("name", "").upper()
        if any(p in name for p in _CPI_PATTERNS):
            result["day_type"] = "cpi"
            dt = day_types_cfg["cpi"]
            result["sizing_multiplier"] = dt["sizing"]
            result["event_time"] = dt["event_time"]
            result["pre_event_buffer"] = dt["pre_event_buffer"]
            result["post_event_wait"] = dt["post_event_wait"]
            result["guidance"] = dt["morning_note"]
            return result
        if any(p in name for p in _NFP_PATTERNS):
            result["day_type"] = "nfp"
            dt = day_types_cfg["nfp"]
            result["sizing_multiplier"] = dt["sizing"]
            result["event_time"] = dt["event_time"]
            result["pre_event_buffer"] = dt["pre_event_buffer"]
            result["post_event_wait"] = dt["post_event_wait"]
            result["guidance"] = dt["morning_note"]
            return result
        if any(p in name for p in _FOMC_PATTERNS):
            result["day_type"] = "fomc"
            dt = day_types_cfg["fomc"]
            result["sizing_multiplier"] = dt["sizing"]
            result["event_time"] = dt["event_time"]
            result["pre_event_buffer"] = 15
            result["post_event_wait"] = 0  # Wait until resume_after
            result["guidance"] = dt["morning_note"]
            return result

    # Check for special events
    for e in todays_events:
        name = e.get("name", "").upper()
        if any(p in name for p in _SPECIAL_PATTERNS):
            result["day_type"] = "special"
            result["sizing_multiplier"] = day_types_cfg["special"]["sizing"]
            result["guidance"] = day_types_cfg["special"]["note"]
            return result

    # High impact but not classified → special
    if has_high:
        result["day_type"] = "special"
        result["sizing_multiplier"] = day_types_cfg["special"]["sizing"]
        result["guidance"] = f"High impact event: {', '.join(result['events_today'])}. Reduce size."

    return result


def format_day_type_block(data: dict, day_name: str) -> str:
    from scripts.trader.config_loader import get_config
    cfg = get_config()
    dow = cfg["day_of_week"].get(day_name, {})
    lines = ["== DAY TYPE & CALENDAR =="]
    lines.append(f"Day type: {data['day_type'].upper()} | {day_name} — {dow.get('read', '')}")
    lines.append(f"Sizing: {data['sizing_multiplier']:.0%} of normal | Gap fill tendency: {dow.get('fill_rate', 'N/A')}%")
    if data["events_today"]:
        lines.append(f"Events: {', '.join(data['events_today'])}")
        if data["event_time"]:
            lines.append(f"Event time: {data['event_time']} | Pre-buffer: {data['pre_event_buffer']}min | Post-wait: {data['post_event_wait']}min")
    lines.append(f"Killzones: {' | '.join(data['killzones'])}")
    lines.append(f"No-trade: {' | '.join(data['no_trade_zones'])}")
    if data["guidance"]:
        lines.append(f"Guidance: {data['guidance']}")
    return "\n".join(lines)