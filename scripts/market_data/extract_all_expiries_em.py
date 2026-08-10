"""
Multi-Expiry ThinkorSwim (TOS) Expected Move Extractor
======================================================
Extracts expected move data for ALL expiration dates starting from today
up to and including the next Friday's expiration date for:
ES, NQ, SPX, SPY, QQQ, DIA, IWM.

Source Logic:
1. Checks if TOS Desktop (thinkorswim.exe) is running -> Captures data from TOS Desktop via RTD COM.
2. If TOS Desktop is NOT running -> Launches ThinkorSwim Web (trade.thinkorswim.com) via Playwright to extract UI values.
3. Fallback to Schwab API / Hub proxy if needed.

Scheduled to run at 4:15 PM EST (16:15 ET) on every last trading day of the week,
or executable on-demand via CLI / AGY skill.
"""

import argparse
import asyncio
import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.streaming.options.config import HUB_URL
from scripts.streaming.options.gex_calculator import calculate_tos_expected_move
from scripts.streaming.options.tos_rtd.adapter import TOSRTDAdapter, RTDConfig
from scripts.streaming.options.tos_rtd.quote_types import QuoteType
from scripts.market_data.tos_web_ui_extractor import extract_tos_ui_expected_moves, PROFILE_DIR
from scripts.market_data.schwab_options_utils import (
    find_expiration_key,
    first_contracts_for_expiration,
    get_option_iv,
    get_option_mark,
    normalize_option_chain_symbol,
)

DEFAULT_TICKERS = ["ES", "NQ", "SPX", "SPY", "QQQ", "DIA", "IWM"]
RTD_SYMBOL_MAP = {
    "ES": "/ES:XCME",
    "NQ": "/NQ:XCME",
    "SPX": "SPX",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "DIA": "DIA",
    "IWM": "IWM",
}

def is_tos_desktop_running() -> bool:
    """Check if ThinkorSwim Desktop application (thinkorswim.exe) is actively running."""
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            name = p.info.get('name')
            if name and 'thinkorswim' in name.lower():
                return True
    except Exception as e:
        print(f"[Check] Exception checking process list: {e}")
    return False

def get_next_friday(d: date) -> date:
    """Returns the next Friday's date. If today is Friday, returns the following Friday."""
    days_ahead = 4 - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)

def get_expiration_dates_range(start_date: date, end_date: date) -> list[date]:
    """Generates all daily dates from start_date to end_date (inclusive)."""
    dates = []
    curr = start_date
    while curr <= end_date:
        dates.append(curr)
        curr += timedelta(days=1)
    return dates

async def hub_request(method: str, params: dict) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{HUB_URL}/request", json={"method": method, "params": params}, timeout=15.0)
            if resp.status_code == 200:
                res = resp.json()
                return {"status": "success", "data": res} if "status" not in res else res
            return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def fetch_live_tos_rtd_snapshot(tickers: list[str]) -> dict:
    """Fetch live quotes and IVs from TOS Desktop RTD COM if running."""
    snapshot = {}
    try:
        config = RTDConfig()
        adapter = TOSRTDAdapter(config)
        subs = []
        for sym in tickers:
            rtd_sym = RTD_SYMBOL_MAP.get(sym, sym)
            subs.append((QuoteType.LAST, rtd_sym))
            subs.append((QuoteType.MARK, rtd_sym))
            subs.append((QuoteType.IMPL_VOL, rtd_sym))

        adapter.start_raw(subs)
        time.sleep(3.0)
        snapshot = adapter.get_snapshot()
        adapter.stop()
    except Exception as e:
        print(f"[TOS RTD Note] Could not connect to TOS Desktop RTD: {e}")
    return snapshot

async def extract_all_expiries(tickers: list[str] = None, save_files: bool = True) -> dict:
    if tickers is None:
        tickers = DEFAULT_TICKERS

    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    today = date.today()
    next_friday = get_next_friday(today)
    exp_dates = get_expiration_dates_range(today, next_friday)

    print(f"=========================================================================")
    print(f" MULTI-EXPIRY TOS EXPECTED MOVE EXTRACTION AT {now_str}")
    print(f" Start Date (Today): {today.strftime('%Y-%m-%d')}")
    print(f" End Date (Next Friday): {next_friday.strftime('%Y-%m-%d')} ({len(exp_dates)} calendar days / expiries)")
    print(f" Tickers: {', '.join(tickers)}")
    print(f"=========================================================================\n")

    desktop_active = is_tos_desktop_running()
    web_results = {}

    if desktop_active:
        print("[PRIMARY SOURCE] ThinkorSwim Desktop Application is RUNNING.")
        print("               -> Capturing data directly from TOS Desktop via RTD COM stream...\n")
        rtd_snapshot = fetch_live_tos_rtd_snapshot(tickers)
        data_source_label = "ThinkorSwim Desktop Application (COM RTD Stream)"
    else:
        print("[FALLBACK SOURCE] ThinkorSwim Desktop Application is NOT running.")
        print("                 -> Opening ThinkorSwim Web UI (trade.thinkorswim.com) via Playwright context...\n")
        rtd_snapshot = {}
        data_source_label = "ThinkorSwim Web UI (trade.thinkorswim.com)"
        try:
            web_results = await extract_tos_ui_expected_moves(
                tickers=tickers,
                headless=True,
                save_json=False,
                wait_time_ms=6000
            )
        except Exception as e:
            print(f"[Web TOS Note] Playwright Web TOS extraction warning: {e}")

    results = {
        "extracted_at": now_dt.isoformat(),
        "extracted_at_formatted": now_str,
        "start_date": today.strftime("%Y-%m-%d"),
        "end_date": next_friday.strftime("%Y-%m-%d"),
        "total_days_in_scope": len(exp_dates),
        "desktop_running": desktop_active,
        "primary_source": data_source_label,
        "tickers": {}
    }

    for ticker in tickers:
        is_futures = ticker in ["ES", "NQ"]
        rtd_sym = RTD_SYMBOL_MAP.get(ticker, ticker)
        
        # Spot price from RTD if available
        rtd_last = rtd_snapshot.get(f"{rtd_sym}:LAST") or rtd_snapshot.get(f"{rtd_sym}:MARK")
        rtd_iv = rtd_snapshot.get(f"{rtd_sym}:IMPL_VOL")

        spot_price = float(rtd_last) if rtd_last else 0.0
        base_iv = float(rtd_iv) if rtd_iv else 0.0

        # Fallback spot from Web TOS or Hub
        if spot_price <= 0 and ticker in web_results.get("tickers", {}):
            spot_price = float(web_results["tickers"][ticker].get("spot_price") or 0.0)

        if spot_price <= 0:
            quote_sym = normalize_option_chain_symbol(ticker)
            q_resp = await hub_request("get_quotes", {"symbols": [quote_sym]})
            if q_resp.get("status") == "success":
                qdata = q_resp.get("data", {})
                for k, v in qdata.items():
                    if isinstance(v, dict) and "quote" in v:
                        spot_price = float(v["quote"].get("lastPrice", 0) or v["quote"].get("closePrice", 0))
                        if spot_price > 0:
                            break

        if spot_price <= 0:
            print(f"[WARN] {ticker:5s}: Unable to retrieve spot price.")
            results["tickers"][ticker] = {"symbol": ticker, "error": "No spot price available"}
            continue

        ticker_expiries = []

        # Iterate over all dates up to next Friday
        for exp_date in exp_dates:
            dte = (exp_date - today).days
            date_str = exp_date.strftime("%Y-%m-%d")

            exp_iv = base_iv
            straddle_price = 0.0

            # If Hub available, attempt chain fetch for specific expiry
            if base_iv <= 0 or is_futures:
                chain_resp = await hub_request("get_option_chain", {
                    "symbol": ticker,
                    "strike_count": 10,
                    "strategy": "ANALYTICAL",
                    "from_date": date_str,
                    "to_date": date_str
                })

                if chain_resp.get("status") == "success":
                    cdata = chain_resp.get("data", {})
                    call_map = cdata.get("callExpDateMap", {})
                    put_map = cdata.get("putExpDateMap", {})
                    exp_key = find_expiration_key(call_map, exp_date)

                    if exp_key:
                        calls = first_contracts_for_expiration(call_map, exp_key)
                        puts = first_contracts_for_expiration(put_map, exp_key)
                        calls.sort(key=lambda x: abs(float(x.get("strikePrice", 0)) - spot_price))
                        puts.sort(key=lambda x: abs(float(x.get("strikePrice", 0)) - spot_price))

                        if calls and puts:
                            atm_call = calls[0]
                            atm_put = puts[0]
                            straddle_price = get_option_mark(atm_call) + get_option_mark(atm_put)
                            c_iv = get_option_iv(atm_call)
                            p_iv = get_option_iv(atm_put)
                            chain_iv = (c_iv + p_iv) / 2.0 if (c_iv > 0 and p_iv > 0) else max(c_iv, p_iv)
                            if chain_iv > 0:
                                exp_iv = chain_iv

            # Calculate TOS Expected Move formula
            em_val = calculate_tos_expected_move(
                spot_price=spot_price,
                expiry_date_str=date_str,
                expiry_volatility=exp_iv,
                is_futures=is_futures
            ) if exp_iv > 0 else (straddle_price * 0.85 if straddle_price > 0 else 0.0)

            em_pct = (em_val / spot_price * 100.0) if spot_price > 0 else 0.0
            lower = spot_price - em_val if em_val > 0 else 0.0
            upper = spot_price + em_val if em_val > 0 else 0.0

            ticker_expiries.append({
                "date": date_str,
                "dte": dte,
                "weekday": exp_date.strftime("%A"),
                "iv_pct": round(exp_iv, 2),
                "expected_move": round(em_val, 2),
                "expected_move_pct": round(em_pct, 2),
                "lower_bound": round(lower, 2),
                "upper_bound": round(upper, 2),
                "straddle_price": round(straddle_price, 2)
            })

        results["tickers"][ticker] = {
            "symbol": ticker,
            "rtd_symbol": rtd_sym,
            "is_futures": is_futures,
            "spot_price": round(spot_price, 2),
            "expirations_count": len(ticker_expiries),
            "expirations": ticker_expiries,
            "source": data_source_label
        }

        # Console Summary
        print(f"[EM] {ticker:5s} | Spot: ${spot_price:10,.2f} | {len(ticker_expiries)} Expiries up to {next_friday}")
        for e in ticker_expiries:
            print(f"     - {e['date']} ({e['weekday']:9s} | DTE: {e['dte']}d) | IV: {e['iv_pct']:5.2f}% | EM: +-{e['expected_move']:7.2f} (+-{e['expected_move_pct']:.2f}%) | [${e['lower_bound']:,.2f} - ${e['upper_bound']:,.2f}]")
        print()

    if save_files:
        # Save JSON
        out_json = REPO_ROOT / "data" / "tos_expected_moves_all_expiries.json"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        # Save Markdown Report
        out_md = REPO_ROOT / "data" / "tos_expected_moves_all_expiries.md"
        md_lines = [
            "# ThinkorSwim (TOS) Multi-Expiry Expected Moves Report",
            f"**Extracted Time:** `{now_str}`",
            f"**Data Source:** `{data_source_label}`",
            f"**Scope Range:** `{today.strftime('%Y-%m-%d')}` to `{next_friday.strftime('%Y-%m-%d')}` (Up to Next Friday Expiry)\n",
            "---"
        ]

        for ticker in tickers:
            tdata = results["tickers"].get(ticker, {})
            if "error" in tdata:
                md_lines.append(f"## {ticker}\n*Error: {tdata['error']}*\n")
                continue

            md_lines.append(f"## {ticker} (Spot: `${tdata['spot_price']:,.2f}`)")
            md_lines.append("| Expiry Date | Day | DTE | ATM IV % | Expected Move (±) | EM % | Expected Range (Lower – Upper) |")
            md_lines.append("|---|---|---|---|---|---|---|")

            for e in tdata.get("expirations", []):
                d_str = f"**{e['date']}**" if e['date'] == next_friday.strftime('%Y-%m-%d') else e['date']
                md_lines.append(
                    f"| {d_str} | {e['weekday']} | {e['dte']}d | {e['iv_pct']:.2f}% | "
                    f"**± {e['expected_move']:.2f}** | ±{e['expected_move_pct']:.2f}% | "
                    f"`${e['lower_bound']:,.2f}` – `${e['upper_bound']:,.2f}` |"
                )
            md_lines.append("")

        md_lines.append(f"\n> **Extraction Protocol:** Primary detection checked TOS Desktop (`thinkorswim.exe`). Source used: `{data_source_label}`. Scope spans all dates from today through next Friday's expiry.")

        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        print(f"[OK] Saved JSON output to: {out_json}")
        print(f"[OK] Saved Markdown report to: {out_md}")

    return results

def main():
    parser = argparse.ArgumentParser(description="Multi-Expiry TOS Expected Move Extractor")
    parser.add_argument("--ticker", action="append", help="Tickers to extract (default: ES, NQ, SPX, SPY, QQQ, DIA, IWM)")
    parser.add_argument("--no-save", action="store_true", help="Do not save output JSON/MD files")
    args = parser.parse_args()

    tickers = args.ticker if args.ticker else DEFAULT_TICKERS
    asyncio.run(extract_all_expiries(tickers=tickers, save_files=not args.no_save))

if __name__ == "__main__":
    main()
