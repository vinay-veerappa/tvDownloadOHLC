import os
import sys
import sqlite3
import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, List, Any, Optional

ET = ZoneInfo("America/New_York")

DB_CANDIDATE_PATHS = [
    Path(__file__).parent.parent.parent / "web" / "prisma" / "dev.db",
    Path(__file__).parent.parent.parent / "prisma" / "dev.db",
    Path("web/prisma/dev.db"),
    Path("prisma/dev.db"),
]

def get_db_path() -> Optional[Path]:
    """Find local SQLite Prisma database if available."""
    for p in DB_CANDIDATE_PATHS:
        if p.exists():
            return p
    return None

def fetch_events_from_db(target_date: datetime.date) -> List[Dict[str, Any]]:
    """Retrieve economic events from local SQLite dev.db for target_date."""
    db_path = get_db_path()
    if not db_path:
        return []

    start_dt = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=ET)
    end_dt = datetime.datetime.combine(target_date, datetime.time.max, tzinfo=ET)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    events = []
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, datetime, name, impact, country, forecast, previous, actual
            FROM EconomicEvent
            WHERE datetime >= ? AND datetime <= ?
            ORDER BY datetime ASC
            """,
            (start_ms, end_ms),
        )
        rows = cur.fetchall()
        conn.close()

        for r in rows:
            dt_ms = r[1]
            dt_et = datetime.datetime.fromtimestamp(dt_ms / 1000, tz=ET)
            name = str(r[2]).strip()
            impact = str(r[3] or "LOW").strip().upper()
            country = str(r[4] or "USD").strip().upper()
            forecast = r[5]
            previous = r[6]
            actual = r[7]

            # Filter for US relevant events
            if country not in ["USD", "US", ""]:
                continue

            events.append({
                "id": r[0],
                "time_et": dt_et.strftime("%H:%M"),
                "time_str": dt_et.strftime("%H:%M ET"),
                "datetime_et": dt_et,
                "name": name,
                "impact": impact,
                "country": country,
                "forecast": forecast,
                "previous": previous,
                "actual": actual,
            })
    except Exception as e:
        pass

    return events


def fetch_live_events_fallback(target_date: datetime.date) -> List[Dict[str, Any]]:
    """Fallback fetch via Investing.com or ForexFactory if local DB is empty."""
    try:
        from scripts.market_data.fetch_economic_calendar import fetch_events, save_events
        events = fetch_events(target_date, target_date)
        if events:
            try:
                save_events(events)
            except Exception:
                pass
            return fetch_events_from_db(target_date)
    except Exception:
        pass
    return []


def compute_economic_news_context(target_date: Optional[datetime.date] = None) -> Dict[str, Any]:
    """
    Computes comprehensive economic news context, timing windows, manipulation alerts,
    and tactical execution rules for the daily wargaming playbook.
    """
    if target_date is None:
        target_date = datetime.datetime.now(ET).date()

    # 1. Fetch Events
    events = fetch_events_from_db(target_date)
    if not events:
        events = fetch_live_events_fallback(target_date)

    # 2. Bucket Events by Key Macro Windows
    pre_market = []       # <= 09:00 ET (08:30 CPI, NFP, etc.)
    open_drive_0945 = []  # 09:40 - 09:50 ET (S&P Flash PMI)
    morning_1000 = []     # 09:55 - 10:10 ET (ISM, JOLTS, Cons Conf, New Home Sales)
    late_morning = []     # 10:15 - 12:00 ET (Crude Inventories, Fed Speakers, Auctions)
    afternoon_1400 = []   # 13:50 - 14:45 ET (FOMC Rate Decision, Fed Chair)
    other_events = []

    for ev in events:
        t_str = ev["time_et"]
        h, m = map(int, t_str.split(":"))
        total_mins = h * 60 + m

        if total_mins <= 9 * 60:
            pre_market.append(ev)
        elif 9 * 60 + 40 <= total_mins <= 9 * 60 + 50:
            open_drive_0945.append(ev)
        elif 9 * 60 + 55 <= total_mins <= 10 * 60 + 10:
            morning_1000.append(ev)
        elif 10 * 60 + 15 <= total_mins <= 12 * 60:
            late_morning.append(ev)
        elif 13 * 60 + 50 <= total_mins <= 14 * 60 + 45:
            afternoon_1400.append(ev)
        else:
            other_events.append(ev)

    # 3. Determine High/Medium Flags
    def has_high(ev_list): return any(e["impact"] == "HIGH" for e in ev_list)
    def has_medium(ev_list): return any(e["impact"] in ["HIGH", "MEDIUM"] for e in ev_list)

    has_0830_high = has_high(pre_market)
    has_0945_high = has_high(open_drive_0945)
    has_0945_med = has_medium(open_drive_0945)
    has_1000_high = has_high(morning_1000)
    has_1000_med = has_medium(morning_1000)
    has_1400_high = has_high(afternoon_1400)

    # 4. Classify News Regime
    if has_0945_med and has_1000_med:
        news_regime = "DOUBLE_BARREL_NEWS_CATALYST (09:45 + 10:00 AM EST)"
        risk_level = "HIGH"
    elif has_1000_high:
        news_regime = "10:00 AM HIGH-IMPACT ANCHOR (ISM / JOLTS / Consumer Conf)"
        risk_level = "HIGH"
    elif has_0945_high or has_0945_med:
        news_regime = "09:45 AM HIGH-IMPACT ANCHOR (S&P Flash PMI)"
        risk_level = "MODERATE_HIGH"
    elif has_1400_high:
        news_regime = "14:00 PM FOMC / FED POLICY CATALYST"
        risk_level = "VERY_HIGH"
    elif has_0830_high:
        news_regime = "08:30 AM PRE-MARKET MACRO RELEASE (CPI / NFP / Jobless Claims)"
        risk_level = "MODERATE"
    else:
        news_regime = "CLEAN AUCTION (No High-Impact 09:45/10:00 AM Catalysts)"
        risk_level = "NORMAL"

    # 5. Formulate Tactical Guidance & Manipulation Alerts
    guidance = []
    
    if has_0945_med or has_1000_med:
        guidance.append(
            "⚠️ **PRE-NEWS MANIPULATION ALERT (09:30–09:59 EST)**: When high-impact news is scheduled at 09:45 or 10:00 AM, "
            "institutional algorithms routinely engineer false breakouts and liquidity sweeps in the 09:30–09:44 window to accumulate inventory. "
            "Expect choppy, two-way traps before the true expansion candle prints."
        )

    if has_0945_med:
        events_0945_names = ", ".join([f"`{e['name']}` ({e['impact']})" for e in open_drive_0945 if e['impact'] in ['HIGH', 'MEDIUM']])
        guidance.append(
            f"🎯 **09:45 AM Release Window**: {events_0945_names}. "
            "The initial 0-5 Box (09:30–09:35) breakout may be a fakeout. The 09:45 statistical cutoff rule requires observing whether the "
            "09:45 news candle confirms direction or produces an instant V-reversal."
        )

    if has_1000_med:
        events_1000_names = ", ".join([f"`{e['name']}` ({e['impact']})" for e in morning_1000 if e['impact'] in ['HIGH', 'MEDIUM']])
        guidance.append(
            f"🚀 **10:00 AM Institutional Ignition**: {events_1000_names}. "
            "The 10:00 AM release candle aligns with **Step 3 (10:00 AM Candle Sweep)** and **Step 4 (10:00 Q1 InStat 10:00–10:14)** of the Reversal Counter. "
            "Do NOT front-run 10:00 AM news. Let the 10:00 AM news candle sweep the 09:00 AM extreme and establish displacement before committing full size."
        )

    if not has_0945_med and not has_1000_med:
        guidance.append(
            "✅ **Clean Execution Window**: No major 09:45 or 10:00 AM economic releases on the docket. "
            "Standard 0-5 Box momentum (10 bps filter) and the canonical 09:45 AM P12/Midnight retest cutoff rules apply with full baseline statistical validity."
        )

    return {
        "date": target_date.isoformat(),
        "total_events": len(events),
        "news_regime": news_regime,
        "risk_level": risk_level,
        "has_0830_high": has_0830_high,
        "has_0945_high": has_0945_high,
        "has_0945_med": has_0945_med,
        "has_1000_high": has_1000_high,
        "has_1000_med": has_1000_med,
        "has_1400_high": has_1400_high,
        "windows": {
            "pre_market_0830": pre_market,
            "open_drive_0945": open_drive_0945,
            "morning_macro_1000": morning_1000,
            "late_morning": late_morning,
            "afternoon_1400": afternoon_1400,
            "other": other_events,
        },
        "tactical_guidance": guidance,
    }


def format_economic_news_markdown(news_ctx: Dict[str, Any]) -> str:
    """Format economic news context into a clean Markdown component for wargaming reports."""
    regime = news_ctx["news_regime"]
    guidance = news_ctx["tactical_guidance"]
    windows = news_ctx["windows"]

    lines = [
        f"### 📰 ECONOMIC CALENDAR & NEWS CATALYSTS: `{regime}`",
    ]

    # Print high/medium events
    key_events = []
    for w_name, w_events in [("Pre-Market (08:30)", windows["pre_market_0830"]),
                             ("Open Drive (09:45)", windows["open_drive_0945"]),
                             ("Morning Macro (10:00)", windows["morning_macro_1000"]),
                             ("Late Morning (10:30-11:30)", windows["late_morning"]),
                             ("Afternoon (14:00)", windows["afternoon_1400"])]:
        notable = [e for e in w_events if e["impact"] in ["HIGH", "MEDIUM"]]
        for e in notable:
            badge = "🔴 HIGH" if e["impact"] == "HIGH" else "🟠 MED"
            fc = f" (Forecast: {e['forecast']})" if e['forecast'] else ""
            prev = f" (Prev: {e['previous']})" if e['previous'] else ""
            key_events.append(f"* **{e['time_str']}** — `[{badge}]` **{e['name']}**{fc}{prev}")

    if key_events:
        lines.append("\n**Scheduled High & Medium Impact Catalysts:**")
        lines.extend(key_events)
    else:
        lines.append("\n*No High or Medium impact economic releases scheduled during RTH today.*")

    lines.append("\n**Tactical News Manipulation & Execution Rules:**")
    for g in guidance:
        lines.append(f"* {g}")

    return "\n".join(lines)
