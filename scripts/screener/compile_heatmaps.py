#!/usr/bin/env python3
"""
compile_heatmaps.py

Aggregates ticker metadata from Prisma SQLite DB (dev.db) with batch quotes 
to compile pre-rendered Treemap JSON payloads for ECharts:
- web/public/data/heatmaps/sp500.json
- web/public/data/heatmaps/nasdaq100.json
- web/public/data/heatmaps/themes.json
- web/public/data/heatmaps/etfs.json
"""

import sqlite3
import os
import json
import yfinance as yf
try:
    from scripts.screener.ticker_autoseed import get_or_seed_ticker, auto_seed_batch, SP500_SAMPLE, NASDAQ100_SAMPLE, ETF_SAMPLE
except ImportError:
    from ticker_autoseed import get_or_seed_ticker, auto_seed_batch, SP500_SAMPLE, NASDAQ100_SAMPLE, ETF_SAMPLE



DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../web/prisma/dev.db"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../web/public/data/heatmaps"))

def get_all_metadata():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS TickerMetadata (
            id TEXT PRIMARY KEY,
            symbol TEXT UNIQUE NOT NULL,
            company TEXT,
            sector TEXT,
            industry TEXT,
            marketCap REAL,
            isSp500 INTEGER DEFAULT 0,
            isNasdaq100 INTEGER DEFAULT 0,
            isRussell2000 INTEGER DEFAULT 0,
            isEtf INTEGER DEFAULT 0,
            theme TEXT,
            fetchedAt TEXT,
            updatedAt TEXT
        );
    """)

    cursor.execute("SELECT symbol, company, sector, industry, marketCap, isSp500, isNasdaq100, isEtf, theme FROM TickerMetadata")
    rows = cursor.fetchall()
    conn.close()

    result = {}
    for r in rows:
        result[r[0]] = {
            "symbol": r[0],
            "company": r[1],
            "sector": r[2] or "Equities",
            "industry": r[3] or "General",
            "marketCap": r[4] or 1000000000.0,
            "isSp500": bool(r[5]),
            "isNasdaq100": bool(r[6]),
            "isEtf": bool(r[7]),
            "theme": r[8] or "General Equities"
        }
    return result

def fetch_batch_quotes(symbols: list):
    print(f"[Batch Quotes] Querying batch prices for {len(symbols)} tickers...")
    try:
        tickers_str = " ".join(symbols)
        data = yf.Tickers(tickers_str)
        quotes = {}
        for s in symbols:
            try:
                t = data.tickers[s]
                fast_info = getattr(t, "fast_info", {})
                last_price = fast_info.get("lastPrice") or 0.0
                prev_close = fast_info.get("previousClose") or last_price
                
                if prev_close > 0 and last_price > 0:
                    pct_change = ((last_price - prev_close) / prev_close) * 100.0
                else:
                    pct_change = 0.0
                
                quotes[s] = {
                    "price": round(last_price, 2),
                    "changePct": round(pct_change, 2)
                }
            except Exception:
                quotes[s] = {"price": 100.0, "changePct": 0.0}
        return quotes
    except Exception as e:
        print(f"[Batch Quotes Error] {e}")
        return {s: {"price": 100.0, "changePct": 0.0} for s in symbols}

def build_sector_hierarchy(symbols_list, metadata, quotes):
    sector_map = {}
    for s in symbols_list:
        meta = metadata.get(s)
        if not meta:
            meta = get_or_seed_ticker(s)
        if not meta:
            continue
        
        q = quotes.get(s, {"price": 100.0, "changePct": 0.0})
        sector = meta.get("sector", "Equities")
        industry = meta.get("industry", "General")
        
        if sector not in sector_map:
            sector_map[sector] = {}
        if industry not in sector_map[sector]:
            sector_map[sector][industry] = []
            
        sector_map[sector][industry].append({
            "name": s,
            "company": meta.get("company", s),
            "value": meta.get("marketCap", 1000000000.0),
            "price": q["price"],
            "changePct": q["changePct"]
        })
        
    hierarchy = []
    for sec_name, ind_map in sector_map.items():
        ind_children = []
        for ind_name, stocks in ind_map.items():
            ind_children.append({
                "name": ind_name,
                "children": stocks
            })
        hierarchy.append({
            "name": sec_name,
            "children": ind_children
        })
    return {"name": "Market", "children": hierarchy}

def build_theme_hierarchy(symbols_list, metadata, quotes):
    theme_map = {}
    for s in symbols_list:
        meta = metadata.get(s)
        if not meta:
            meta = get_or_seed_ticker(s)
        if not meta:
            continue
            
        q = quotes.get(s, {"price": 100.0, "changePct": 0.0})
        theme = meta.get("theme", "General Equities")
        industry = meta.get("industry", "General")
        
        if theme not in theme_map:
            theme_map[theme] = {}
        if industry not in theme_map[theme]:
            theme_map[theme][industry] = []
            
        theme_map[theme][industry].append({
            "name": s,
            "company": meta.get("company", s),
            "value": meta.get("marketCap", 1000000000.0),
            "price": q["price"],
            "changePct": q["changePct"]
        })
        
    hierarchy = []
    for theme_name, ind_map in theme_map.items():
        ind_children = []
        for ind_name, stocks in ind_map.items():
            ind_children.append({
                "name": ind_name,
                "children": stocks
            })
        hierarchy.append({
            "name": theme_name,
            "children": ind_children
        })
    return {"name": "Themes", "children": hierarchy}

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Combine test universe
    universe = list(set(SP500_SAMPLE + NASDAQ100_SAMPLE + ETF_SAMPLE))
    
    # Auto-seed any missing tickers in Prisma DB
    print("[Compile Heatmaps] Auto-seeding missing universe metadata into Prisma DB...")
    auto_seed_batch(universe)
    
    metadata = get_all_metadata()
    quotes = fetch_batch_quotes(universe)
    
    # 1. S&P 500 Heatmap
    sp500_tree = build_sector_hierarchy(SP500_SAMPLE, metadata, quotes)
    with open(os.path.join(OUTPUT_DIR, "sp500.json"), "w") as f:
        json.dump(sp500_tree, f, indent=2)
    print(f"[Saved] {os.path.join(OUTPUT_DIR, 'sp500.json')}")
    
    # 2. Nasdaq 100 Heatmap
    nasdaq_tree = build_sector_hierarchy(NASDAQ100_SAMPLE, metadata, quotes)
    with open(os.path.join(OUTPUT_DIR, "nasdaq100.json"), "w") as f:
        json.dump(nasdaq_tree, f, indent=2)
    print(f"[Saved] {os.path.join(OUTPUT_DIR, 'nasdaq100.json')}")
    
    # 3. Themes Heatmap
    themes_tree = build_theme_hierarchy(universe, metadata, quotes)
    with open(os.path.join(OUTPUT_DIR, "themes.json"), "w") as f:
        json.dump(themes_tree, f, indent=2)
    print(f"[Saved] {os.path.join(OUTPUT_DIR, 'themes.json')}")
    
    # 4. ETF Heatmap
    etf_tree = build_sector_hierarchy(ETF_SAMPLE, metadata, quotes)
    with open(os.path.join(OUTPUT_DIR, "etfs.json"), "w") as f:
        json.dump(etf_tree, f, indent=2)
    print(f"[Saved] {os.path.join(OUTPUT_DIR, 'etfs.json')}")

if __name__ == "__main__":
    main()
