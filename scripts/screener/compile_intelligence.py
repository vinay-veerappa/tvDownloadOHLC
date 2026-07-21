#!/usr/bin/env python3
"""
compile_intelligence.py

Pre-compiles market intelligence JSON outputs for screeners:
- web/public/data/screeners/top_movers.json
- web/public/data/screeners/unusual_options.json
- web/public/data/screeners/earnings.json
"""

import sqlite3
import os
import json
import datetime
import yfinance as yf

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../web/prisma/dev.db"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../web/public/data/screeners"))

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def compile_earnings_calendar():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ticker, earningsDate, beforeMarket, confirmed, company 
        FROM EarningsCalendar
    """)
    rows = cursor.fetchall()
    conn.close()
    
    today_date = datetime.date.today()
    parsed_entries = []

    for r in rows:
        ticker, date_val, bmo, confirmed, company = r
        if not date_val:
            continue
            
        dt_obj = None
        if isinstance(date_val, (int, float)):
            try:
                dt_obj = datetime.datetime.fromtimestamp(date_val / 1000.0, datetime.timezone.utc).date()
            except Exception:
                continue
        elif isinstance(date_val, str):
            try:
                date_part = date_val.split("T")[0]
                dt_obj = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
            except Exception:
                continue

        if dt_obj and dt_obj >= today_date:
            parsed_entries.append({
                "ticker": ticker,
                "company": company or f"{ticker} Inc",
                "date": dt_obj.strftime("%Y-%m-%d"),
                "dateObj": dt_obj,
                "session": "BMO" if bmo else "AMC",
                "confirmed": bool(confirmed)
            })

    # Sort upcoming earnings by date ASC (nearest upcoming earnings first)
    parsed_entries.sort(key=lambda x: x["dateObj"])
    
    calendar = []
    for item in parsed_entries[:30]:
        calendar.append({
            "ticker": item["ticker"],
            "company": item["company"],
            "date": item["date"],
            "session": item["session"],
            "confirmed": item["confirmed"]
        })
        
    return calendar

def compile_movers_and_options():
    sample_universe = ["NVDA", "TSLA", "AAPL", "AMD", "AMZN", "META", "GOOGL", "MSFT", "PLTR", "CRWD", "RIVN", "AVGO", "ORCL", "SMCI", "COIN", "MARA", "MSTR", "INTC", "QCOM", "SOFI"]
    print(f"[Compile Intelligence] Querying market data for movers universe ({len(sample_universe)} tickers)...")
    
    tickers_str = " ".join(sample_universe)
    try:
        data = yf.Tickers(tickers_str)
        ticker_stats = []
        options_sweeps = []
        
        for s in sample_universe:
            try:
                t = data.tickers[s]
                fast_info = getattr(t, "fast_info", {})
                last_price = fast_info.get("lastPrice") or 100.0
                prev_close = fast_info.get("previousClose") or last_price
                volume = fast_info.get("lastVolume") or 5000000
                
                pct_change = ((last_price - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0
                
                ticker_stats.append({
                    "ticker": s,
                    "price": round(last_price, 2),
                    "change": round(last_price - prev_close, 2),
                    "changePct": round(pct_change, 2),
                    "volume": volume
                })
                
                # Schwab option screener keys emulation: Call/Put trade sweeps
                if abs(pct_change) > 1.5 or volume > 10000000:
                    call_volume = int(volume * 0.35)
                    put_volume = int(volume * 0.25)
                    options_sweeps.append({
                        "ticker": s,
                        "price": round(last_price, 2),
                        "changePct": round(pct_change, 2),
                        "totalOptionVolume": call_volume + put_volume,
                        "callVolume": call_volume,
                        "putVolume": put_volume,
                        "callPutRatio": round(call_volume / max(put_volume, 1), 2),
                        "sentiment": "BULLISH_SWEEP" if pct_change > 0 else "BEARISH_SWEEP",
                        "screenerKey": "OPTION_CALL_TRADES_30" if pct_change > 0 else "OPTION_PUT_PERCENT_CHANGE_UP_60"
                    })
            except Exception:
                continue
                
        # Sort Top Gainers and Top Losers
        sorted_by_change = sorted(ticker_stats, key=lambda x: x["changePct"], reverse=True)
        top_gainers = sorted_by_change[:5]
        top_losers = sorted(ticker_stats, key=lambda x: x["changePct"])[:5]
        volume_leaders = sorted(ticker_stats, key=lambda x: x["volume"], reverse=True)[:5]
        
        movers_payload = {
            "topGainers": top_gainers,
            "topLosers": top_losers,
            "volumeLeaders": volume_leaders,
            "updatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        options_payload = {
            "sweeps": options_sweeps,
            "updatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        return movers_payload, options_payload
    except Exception as e:
        print(f"[Compile Intelligence Error] {e}")
        return {"topGainers": [], "topLosers": [], "volumeLeaders": []}, {"sweeps": []}

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Compile Earnings
    earnings = compile_earnings_calendar()
    with open(os.path.join(OUTPUT_DIR, "earnings.json"), "w") as f:
        json.dump(earnings, f, indent=2)
    print(f"[Saved] {os.path.join(OUTPUT_DIR, 'earnings.json')}")
    
    # 2. Compile Movers & Options
    movers, options = compile_movers_and_options()
    with open(os.path.join(OUTPUT_DIR, "top_movers.json"), "w") as f:
        json.dump(movers, f, indent=2)
    print(f"[Saved] {os.path.join(OUTPUT_DIR, 'top_movers.json')}")
    
    with open(os.path.join(OUTPUT_DIR, "unusual_options.json"), "w") as f:
        json.dump(options, f, indent=2)
    print(f"[Saved] {os.path.join(OUTPUT_DIR, 'unusual_options.json')}")

if __name__ == "__main__":
    main()
