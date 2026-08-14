"""
Master TOS Expected Value Extractor for 1:15 PM PST.
Extracts live prices, IVs, and Expected Moves directly from ThinkorSwim Desktop via RTD.
Symbols: ES, NQ, SPX, SPY, QQQ, DIA, IWM.
"""

import asyncio
import json
import math
import sys
import os
import time
from datetime import datetime, date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.streaming.options.tos_rtd.adapter import TOSRTDAdapter, RTDConfig
from scripts.streaming.options.tos_rtd.quote_types import QuoteType
from scripts.streaming.options.gex_calculator import calculate_tos_expected_move

TICKERS_CONFIG = {
    "ES": {"rtd_symbol": "/ES:XCME", "alt_rtd": "/ES", "is_futures": True},
    "NQ": {"rtd_symbol": "/NQ:XCME", "alt_rtd": "/NQ", "is_futures": True},
    "SPX": {"rtd_symbol": "SPX", "alt_rtd": "$SPX", "is_futures": False},
    "SPY": {"rtd_symbol": "SPY", "alt_rtd": "SPY", "is_futures": False},
    "QQQ": {"rtd_symbol": "QQQ", "alt_rtd": "QQQ", "is_futures": False},
    "DIA": {"rtd_symbol": "DIA", "alt_rtd": "DIA", "is_futures": False},
    "IWM": {"rtd_symbol": "IWM", "alt_rtd": "IWM", "is_futures": False},
}

def get_next_friday(d: date) -> date:
    days_ahead = 4 - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)

def run_extraction_115():
    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    today = date.today()
    next_friday = get_next_friday(today)
    dte_next = (next_friday - today).days

    print(f"=========================================================================")
    print(f" THINKORSWIM (ToS) EXPECTED VALUES EXTRACTION AT {now_str}")
    print(f" Target Expiry (Next Friday): {next_friday.strftime('%Y-%m-%d')} (DTE: {dte_next}d)")
    print(f" Target Expiry (Today 0DTE):  {today.strftime('%Y-%m-%d')} (DTE: 0d)")
    print(f"=========================================================================")

    config = RTDConfig()
    adapter = TOSRTDAdapter(config)

    # Subscriptions for all 7 symbols
    subs = []
    for sym, cfg in TICKERS_CONFIG.items():
        for rtd_s in set([cfg["rtd_symbol"], cfg["alt_rtd"]]):
            subs.append((QuoteType.LAST, rtd_s))
            subs.append((QuoteType.MARK, rtd_s))
            subs.append((QuoteType.IMPL_VOL, rtd_s))

    adapter.start_raw(subs)
    time.sleep(3.5)

    snapshot = adapter.get_snapshot()
    adapter.stop()

    print(f"Received {len(snapshot)} live RTD data points from ThinkorSwim Desktop.\n")

    results = {
        "extracted_at": now_dt.isoformat(),
        "extracted_at_formatted": now_str,
        "next_expiry": next_friday.strftime("%Y-%m-%d"),
        "dte_next": dte_next,
        "tickers": {}
    }

    for ticker, cfg in TICKERS_CONFIG.items():
        primary = cfg["rtd_symbol"]
        alt = cfg["alt_rtd"]
        is_futures = cfg["is_futures"]

        # Parse snapshot
        last_val = (
            snapshot.get(f"{primary}:LAST") or snapshot.get(f"{alt}:LAST") or
            snapshot.get(f"{primary}:MARK") or snapshot.get(f"{alt}:MARK") or 0.0
        )
        iv_val = (
            snapshot.get(f"{primary}:IMPL_VOL") or snapshot.get(f"{alt}:IMPL_VOL") or 0.0
        )

        spot = float(last_val)
        iv_pct = float(iv_val)

        # Calculate TOS Expected Move for Next Friday Expiry
        em_next = calculate_tos_expected_move(
            spot_price=spot,
            expiry_date_str=next_friday.strftime("%Y-%m-%d"),
            expiry_volatility=iv_pct,
            is_futures=is_futures
        ) if spot > 0 and iv_pct > 0 else 0.0

        # Calculate TOS Expected Move for Today (0DTE)
        em_today = calculate_tos_expected_move(
            spot_price=spot,
            expiry_date_str=today.strftime("%Y-%m-%d"),
            expiry_volatility=iv_pct,
            is_futures=is_futures
        ) if spot > 0 and iv_pct > 0 else 0.0

        lower_next = spot - em_next if em_next > 0 else 0.0
        upper_next = spot + em_next if em_next > 0 else 0.0

        lower_today = spot - em_today if em_today > 0 else 0.0
        upper_today = spot + em_today if em_today > 0 else 0.0

        tinfo = {
            "symbol": ticker,
            "rtd_symbol": primary,
            "is_futures": is_futures,
            "spot_price": round(spot, 2),
            "implied_volatility_pct": round(iv_pct, 2),
            "next_expiry": {
                "date": next_friday.strftime("%Y-%m-%d"),
                "dte": dte_next,
                "expected_move": round(em_next, 2),
                "lower_bound": round(lower_next, 2),
                "upper_bound": round(upper_next, 2),
            },
            "today_0dte": {
                "date": today.strftime("%Y-%m-%d"),
                "dte": 0,
                "expected_move": round(em_today, 2),
                "lower_bound": round(lower_today, 2),
                "upper_bound": round(upper_today, 2),
            },
            "data_source": "ThinkorSwim Desktop COM RTD Feed"
        }

        results["tickers"][ticker] = tinfo
        print(f"  {ticker:5s} | Spot: ${spot:10,.2f} | IV: {iv_pct:5.2f}% | EM (Aug 14): ±{em_next:7.2f} [${lower_next:,.2f} - ${upper_next:,.2f}]")

    # Write Output JSON
    out_json = REPO_ROOT / "data" / "tos_expected_values_115_pst.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    # Write Output Markdown
    out_md = REPO_ROOT / "data" / "tos_expected_values_115_pst.md"
    md_lines = [
        f"# ThinkorSwim (ToS) Expected Values Report",
        f"**Extracted Time:** `{now_str}` (1:15 PM PST)",
        f"**Data Source:** ThinkorSwim Desktop Application (COM RTD Direct Feed)\n",
        f"### Next Weekly Expiry ({next_friday.strftime('%Y-%m-%d')}, DTE: {dte_next}d)\n",
        f"| Ticker | Spot Price | TOS ATM IV | Expected Move (±) | Expected Lower | Expected Upper |",
        f"|---|---|---|---|---|---|"
    ]

    for ticker in ["ES", "NQ", "SPX", "SPY", "QQQ", "DIA", "IWM"]:
        t = results["tickers"].get(ticker, {})
        spot = f"${t.get('spot_price', 0):,.2f}"
        iv = f"{t.get('implied_volatility_pct', 0):.2f}%"
        next_exp = t.get("next_expiry", {})
        em = f"**± {next_exp.get('expected_move', 0):.2f}**"
        l_val = f"${next_exp.get('lower_bound', 0):,.2f}"
        u_val = f"${next_exp.get('upper_bound', 0):,.2f}"
        md_lines.append(f"| **{ticker}** | {spot} | {iv} | {em} | {l_val} | {u_val} |")

    md_lines.append(f"\n### Today 0DTE Expiry ({today.strftime('%Y-%m-%d')})\n")
    md_lines.append(f"| Ticker | Spot Price | TOS ATM IV | 0DTE Expected Move (±) | 0DTE Lower | 0DTE Upper |")
    md_lines.append(f"|---|---|---|---|---|---|")

    for ticker in ["ES", "NQ", "SPX", "SPY", "QQQ", "DIA", "IWM"]:
        t = results["tickers"].get(ticker, {})
        spot = f"${t.get('spot_price', 0):,.2f}"
        iv = f"{t.get('implied_volatility_pct', 0):.2f}%"
        td_exp = t.get("today_0dte", {})
        em = f"**± {td_exp.get('expected_move', 0):.2f}**"
        l_val = f"${td_exp.get('lower_bound', 0):,.2f}"
        u_val = f"${td_exp.get('upper_bound', 0):,.2f}"
        md_lines.append(f"| **{ticker}** | {spot} | {iv} | {em} | {l_val} | {u_val} |")

    md_lines.append("\n---\n*Extracted directly from open ThinkorSwim Desktop process using TOS RTD COM streaming engine.*")

    with open(out_md, "w") as f:
        f.write("\n".join(md_lines))

    print(f"\nSaved Markdown report to: {out_md}")
    return results

if __name__ == "__main__":
    run_extraction_115()
