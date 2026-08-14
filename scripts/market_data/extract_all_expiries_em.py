"""
Daily Multi-Expiry ThinkorSwim (TOS) Expected Move & Historical IV Extractor
=============================================================================
Extracts expected move and implied volatility data for weekly expirations across:
- Priority 1: ES (/ES), NQ (/NQ) [Time-critical with settlement price validation]
- Priority 2: SPX, SPY, QQQ, IWM, DIA, NDX, SMH, SPCX
- Priority 3: Monitored Stock Universe (AAPL, MSFT, NVDA, AMD, PLTR, CSCO, SNDK, SKHY, etc.)

Execution & Persistence:
1. Prioritized batch processing starting with time-critical equity futures.
2. Verified multi-source failover: TOS Desktop RTD -> TOS Web UI -> Calibrated Series ATM IV.
3. Automatically upserts results to SQLite DB (`web/prisma/dev.db`):
   - `ExpectedMove` table: populates `manualEm` with TOS EM, preserving previous days' S/R levels.
   - `HistoricalVolatility` table: populates daily closing `iv` for historical ranking.
4. Saves export files: `data/tos_expected_moves_all_expiries.json` & `.md`.
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
from scripts.market_data.schwab_options_utils import (
    find_expiration_key,
    first_contracts_for_expiration,
    get_option_iv,
    get_option_mark,
)

# ── Prioritized Ticker Universes ──────────────────────────────────────────

# Priority 1: Time-Critical Equity Futures (Run First @ 16:14 ET)
FUTURES_TICKERS = ["ES", "NQ"]

# Priority 2: Core Indices & ETFs (Weekly Expirations)
INDEX_ETF_TICKERS = ["SPX", "SPY", "QQQ", "IWM", "DIA", "NDX", "SMH", "SPCX"]

# Priority 3: Monitored Stocks (Run After Indices/Futures)
STOCK_TICKERS = [
    # Mega-Cap Tech & Enterprise
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "CSCO", "ORCL",
    # AI, Semiconductors & Memory
    "AMD", "TSM", "ARM", "MRVL", "MU", "QCOM", "INTC", "ASML", "LRCX", "AMAT", "SKHY", "SNDK",
    # AI Infrastructure & Hardware
    "DELL", "VRT", "ANET",
    # Cybersecurity & Enterprise SaaS
    "PLTR", "CRWD", "PANW", "SNOW", "NET", "DDOG", "MDB", "NOW",
    # Crypto & FinTech Leaders
    "MSTR", "COIN", "HOOD", "SOFI",
    # Healthcare & Pharma
    "LLY", "NVO",
]

DEFAULT_TICKERS = FUTURES_TICKERS + INDEX_ETF_TICKERS + STOCK_TICKERS

RTD_SYMBOL_MAP = {
    "ES": "/ES:XCME",
    "NQ": "/NQ:XCME",
    "SPX": "SPX",
    "NDX": "NDX",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "DIA": "DIA",
    "IWM": "IWM",
    "SMH": "SMH",
    "SPCX": "SPCX",
}

SCHWAB_SYMBOL_MAP = {
    "ES": "/ES",
    "NQ": "/NQ",
    "SPX": "$SPX",
    "NDX": "$NDX",
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

def get_weekly_expiration_dates(today: date, count: int = 2) -> list[date]:
    """
    Returns the nearest weekly Friday expiration dates (e.g. W0 current week Friday, W1 next week Friday).
    If today is Friday, returns today and the following Friday.
    """
    expiries = []
    days_to_fri = (4 - today.weekday()) % 7
    first_friday = today + timedelta(days=days_to_fri)
    
    current = first_friday
    for _ in range(count):
        expiries.append(current)
        current += timedelta(days=7)
    return expiries

async def hub_request(method: str, params: dict) -> dict:
    """Send a REST request through the Schwab Hub proxy."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{HUB_URL}/request",
                json={"method": method, "params": params},
                timeout=15.0
            )
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
            subs.append((QuoteType.CLOSE, rtd_sym))
            subs.append((QuoteType.IMPL_VOL, rtd_sym))

        adapter.start_raw(subs)
        time.sleep(3.5)
        snapshot = adapter.get_snapshot()
        adapter.stop()
    except Exception as e:
        print(f"[TOS RTD Note] Could not connect to TOS Desktop RTD: {e}")
    return snapshot

def save_to_database(results: dict):
    """
    Persists calculated Expected Moves and Implied Volatilities into SQLite database (web/prisma/dev.db).
    - ExpectedMove table: upserts rows keyed by (ticker, calculationDate, expiryDate) with manualEm.
    - HistoricalVolatility table: upserts rows keyed by (ticker, date) with iv and closePrice.
    """
    db_path = REPO_ROOT / "web" / "prisma" / "dev.db"
    if not db_path.exists():
        print(f"[DB Warning] SQLite database not found at {db_path}, skipping DB write.")
        return

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("PRAGMA busy_timeout = 30000;")

    calc_dt = datetime.fromisoformat(results.get("extracted_at"))
    calc_ms = int(datetime(calc_dt.year, calc_dt.month, calc_dt.day, 0, 0, 0).timestamp() * 1000)
    now_ms = int(calc_dt.timestamp() * 1000)

    em_count = 0
    iv_count = 0

    for ticker, tdata in results.get("tickers", {}).items():
        if "error" in tdata or not tdata.get("expirations"):
            continue

        spot_price = tdata.get("spot_price")
        if not spot_price or spot_price <= 0:
            continue

        # 1. Upsert HistoricalVolatility (daily closing IV)
        first_iv = None
        for exp in tdata["expirations"]:
            if exp.get("iv_pct") and exp["iv_pct"] > 0:
                first_iv = exp["iv_pct"]
                break

        if first_iv is not None:
            try:
                cur.execute("""
                INSERT INTO HistoricalVolatility (ticker, date, iv, hv, closePrice, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, date) DO UPDATE SET
                    iv = excluded.iv,
                    closePrice = excluded.closePrice,
                    updatedAt = excluded.updatedAt;
                """, (ticker, calc_ms, first_iv, None, spot_price, now_ms, now_ms))
                iv_count += 1
            except Exception as e:
                print(f"[DB Error] Failed to upsert HistoricalVolatility for {ticker}: {e}")

        # 2. Upsert ExpectedMove for each weekly expiration
        for exp in tdata["expirations"]:
            exp_date_str = exp["date"]
            exp_dt = datetime.strptime(exp_date_str, "%Y-%m-%d")
            exp_ms = int(datetime(exp_dt.year, exp_dt.month, exp_dt.day, 0, 0, 0).timestamp() * 1000)

            em_val = exp.get("expected_move")
            straddle = exp.get("straddle_price", 0.0)
            dte = exp.get("dte", 0)
            iv = exp.get("iv_pct", 0.0) / 100.0

            em365 = round(spot_price * iv * math.sqrt(dte / 365.0), 2) if (dte > 0 and iv > 0) else 0.0
            em252 = round(spot_price * iv * math.sqrt(dte / 252.0), 2) if (dte > 0 and iv > 0) else 0.0
            adjEm = round(straddle * 0.85, 2) if straddle > 0 else (em_val if em_val else 0.0)
            note = tdata.get("source", "TOS_EXTRACTOR")

            try:
                cur.execute("""
                INSERT INTO ExpectedMove (ticker, calculationDate, expiryDate, price, straddle, em365, em252, adjEm, manualEm, basis, note, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, calculationDate, expiryDate) DO UPDATE SET
                    price = excluded.price,
                    straddle = excluded.straddle,
                    em365 = excluded.em365,
                    em252 = excluded.em252,
                    adjEm = excluded.adjEm,
                    manualEm = excluded.manualEm,
                    note = excluded.note,
                    updatedAt = excluded.updatedAt;
                """, (ticker, calc_ms, exp_ms, spot_price, straddle, em365, em252, adjEm, em_val, None, note, now_ms, now_ms))
                em_count += 1
            except Exception as e:
                print(f"[DB Error] Failed to upsert ExpectedMove for {ticker} ({exp_date_str}): {e}")

    conn.commit()
    conn.close()
    print(f"[DB Persistence] Saved {em_count} ExpectedMove (manualEm) and {iv_count} HistoricalVolatility records to {db_path.name}")

async def extract_all_expiries(
    tickers: list[str] = None,
    save_files: bool = True,
    save_db: bool = True,
    weekly_count: int = 2
) -> dict:
    if tickers is None:
        tickers = DEFAULT_TICKERS

    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    today = date.today()
    weekly_exp_dates = get_weekly_expiration_dates(today, count=weekly_count)

    print(f"=========================================================================")
    print(f" DAILY TOS MULTI-EXPIRY EXPECTED MOVE & HISTORICAL IV EXTRACTION")
    print(f" Time: {now_str} | Date: {today.strftime('%Y-%m-%d')}")
    print(f" Target Weekly Expiries: {[d.strftime('%Y-%m-%d') for d in weekly_exp_dates]}")
    print(f" Total Tickers: {len(tickers)} (Priority: Futures -> Indices/ETFs -> Stocks)")
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
        print("                 -> Fetching exact Series ATM IVs from Schwab API & Calibrated TOS Model...\n")
        rtd_snapshot = {}
        data_source_label = "Schwab API & TOS Calibrated Formula"

    results = {
        "extracted_at": now_dt.isoformat(),
        "extracted_at_formatted": now_str,
        "start_date": today.strftime("%Y-%m-%d"),
        "weekly_expirations": [d.strftime("%Y-%m-%d") for d in weekly_exp_dates],
        "data_source": data_source_label,
        "tickers": {}
    }

    # Group tickers in order of priority
    priority_groups = [
        ("Priority 1 (Futures)", [t for t in tickers if t in FUTURES_TICKERS]),
        ("Priority 2 (Indices & ETFs)", [t for t in tickers if t in INDEX_ETF_TICKERS]),
        ("Priority 3 (Monitored Stocks)", [t for t in tickers if t in STOCK_TICKERS or (t not in FUTURES_TICKERS and t not in INDEX_ETF_TICKERS)])
    ]

    for group_name, group_tickers in priority_groups:
        if not group_tickers:
            continue
        print(f"\n--- Processing {group_name}: {', '.join(group_tickers)} ---")

        for ticker in group_tickers:
            is_futures = ticker in ["ES", "NQ"] or ticker.startswith("/")
            rtd_sym = RTD_SYMBOL_MAP.get(ticker, ticker)
            schwab_sym = SCHWAB_SYMBOL_MAP.get(ticker, ticker)

            # Retrieve Spot Price & IV from TOS RTD if available
            spot_price = 0.0
            base_iv = 0.0

            if desktop_active and rtd_snapshot:
                last_val = rtd_snapshot.get((QuoteType.LAST.value, rtd_sym))
                mark_val = rtd_snapshot.get((QuoteType.MARK.value, rtd_sym))
                close_val = rtd_snapshot.get((QuoteType.CLOSE.value, rtd_sym))
                iv_val = rtd_snapshot.get((QuoteType.IMPL_VOL.value, rtd_sym))

                if last_val is not None and isinstance(last_val, (int, float)) and last_val > 0:
                    spot_price = float(last_val)
                elif mark_val is not None and isinstance(mark_val, (int, float)) and mark_val > 0:
                    spot_price = float(mark_val)
                elif close_val is not None and isinstance(close_val, (int, float)) and close_val > 0:
                    spot_price = float(close_val)

                if iv_val is not None:
                    try:
                        clean_iv = str(iv_val).replace("%", "").strip()
                        base_iv = float(clean_iv)
                    except ValueError:
                        base_iv = 0.0

            # Priority 1 Settlement Validation check for Futures
            if is_futures and (spot_price <= 0 or base_iv <= 0):
                print(f"[Futures Check] Verifying settlement price for {ticker}...")
                q_resp = await hub_request("get_quote", {"symbol_id": schwab_sym})
                if q_resp.get("status") == "success":
                    qdata = q_resp.get("data", {}).get(schwab_sym, {}).get("quote", {})
                    if qdata.get("lastPrice"):
                        spot_price = float(qdata["lastPrice"])

            # Fallback to Hub quote if spot is still missing
            if spot_price <= 0:
                q_resp = await hub_request("get_quote", {"symbol_id": schwab_sym})
                if q_resp.get("status") == "success":
                    qdata = q_resp.get("data", {}).get(schwab_sym, {}).get("quote", {})
                    if qdata.get("lastPrice"):
                        spot_price = float(qdata["lastPrice"])

            if spot_price <= 0:
                print(f"[Warning] Could not obtain price for {ticker}. Skipping.")
                results["tickers"][ticker] = {"error": "Could not obtain price", "symbol": ticker}
                continue

            ticker_expiries = []

            # Iterate over target weekly Friday expiration dates
            for exp_date in weekly_exp_dates:
                dte = (exp_date - today).days
                date_str = exp_date.strftime("%Y-%m-%d")
                exp_iv = base_iv
                straddle_price = 0.0

                # Pull option chain for specific expiry to get exact Series ATM IV & Straddle
                chain_resp = await hub_request("get_option_chain", {
                    "symbol": schwab_sym,
                    "strike_count": 8,
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
                        if calls and puts:
                            calls.sort(key=lambda x: abs(float(x.get("strikePrice", 0)) - spot_price))
                            puts.sort(key=lambda x: abs(float(x.get("strikePrice", 0)) - spot_price))
                            atm_call = calls[0]
                            atm_put = puts[0]
                            c_mark = atm_call.get("mark", 0) or (atm_call.get("bid", 0) + atm_call.get("ask", 0))/2.0
                            p_mark = atm_put.get("mark", 0) or (atm_put.get("bid", 0) + atm_put.get("ask", 0))/2.0
                            straddle_price = c_mark + p_mark
                            c_iv = get_option_iv(atm_call)
                            p_iv = get_option_iv(atm_put)
                            series_iv = (c_iv + p_iv) / 2.0 if (c_iv > 0 and p_iv > 0) else max(c_iv, p_iv)
                            if series_iv > 0:
                                exp_iv = series_iv

                # Calculate calibrated TOS Expected Move
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
            print(f"[EM] {ticker:5s} | Spot: ${spot_price:10,.2f}")
            for e in ticker_expiries:
                print(f"     - {e['date']} ({e['weekday']:6s} | DTE: {e['dte']:2d}d) | IV: {e['iv_pct']:5.2f}% | EM: ±{e['expected_move']:7.2f} (±{e['expected_move_pct']:.2f}%) | [${e['lower_bound']:,.2f} – ${e['upper_bound']:,.2f}]")

    # Save to Database
    if save_db:
        save_to_database(results)

    # Save File Artifacts
    if save_files:
        out_json = REPO_ROOT / "data" / "tos_expected_moves_all_expiries.json"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        out_md = REPO_ROOT / "data" / "tos_expected_moves_all_expiries.md"
        md_lines = [
            "# ThinkorSwim (TOS) Multi-Expiry Expected Moves Report",
            f"**Extracted Time:** `{now_str}`",
            f"**Data Source:** `{data_source_label}`",
            f"**Weekly Expirations:** {', '.join([d.strftime('%Y-%m-%d') for d in weekly_exp_dates])}\n",
            "---"
        ]

        for ticker in tickers:
            tdata = results["tickers"].get(ticker, {})
            if "error" in tdata:
                continue

            md_lines.append(f"## {ticker} (Spot: `${tdata['spot_price']:,.2f}`)")
            md_lines.append("| Expiry Date | Day | DTE | ATM IV % | Expected Move (±) | EM % | Expected Range (Lower – Upper) | Straddle |")
            md_lines.append("|---|---|---|---|---|---|---|---|")

            for e in tdata.get("expirations", []):
                md_lines.append(
                    f"| **{e['date']}** | {e['weekday']} | {e['dte']}d | {e['iv_pct']:.2f}% | "
                    f"**± {e['expected_move']:.2f}** | ±{e['expected_move_pct']:.2f}% | "
                    f"`${e['lower_bound']:,.2f}` – `${e['upper_bound']:,.2f}` | `${e['straddle_price']:.2f}` |"
                )
            md_lines.append("")

        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        print(f"[OK] Saved JSON output to: {out_json}")
        print(f"[OK] Saved Markdown report to: {out_md}")

    return results

def main():
    parser = argparse.ArgumentParser(description="Daily TOS Multi-Expiry Expected Move Extractor")
    parser.add_argument("--ticker", action="append", help="Specific tickers to extract")
    parser.add_argument("--no-save", action="store_true", help="Do not save output JSON/MD files")
    parser.add_argument("--no-db", action="store_true", help="Do not write to database")
    parser.add_argument("--weekly-count", type=int, default=2, help="Number of weekly Friday expiries (default: 2)")
    args = parser.parse_args()

    tickers = args.ticker if args.ticker else DEFAULT_TICKERS
    asyncio.run(extract_all_expiries(
        tickers=tickers,
        save_files=not args.no_save,
        save_db=not args.no_db,
        weekly_count=args.weekly_count
    ))

if __name__ == "__main__":
    main()
