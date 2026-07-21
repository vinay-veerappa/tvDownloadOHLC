#!/usr/bin/env python3
"""
ticker_autoseed.py

On-demand auto-seeder for TickerMetadata in Prisma SQLite DB (dev.db).
Checks if a ticker exists in TickerMetadata; if missing, fetches its sector, industry, 
market cap, index memberships, and theme tags via yfinance / Schwab API, and persists it.
"""

import sqlite3
import os
import sys
import datetime
import yfinance as yf

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../web/prisma/dev.db"))

THEME_MAPPINGS = {
    "Artificial Intelligence": ["NVDA", "AMD", "MSFT", "GOOGL", "META", "PLTR", "AI", "SMCI", "AVGO", "TSM"],
    "Cybersecurity": ["CRWD", "PANW", "FTNT", "ZS", "NET", "S", "CHKP"],
    "Cloud Computing": ["AMZN", "MSFT", "GOOGL", "ORCL", "CRM", "NOW", "SNOW", "DDOG"],
    "Electric Vehicles": ["TSLA", "RIVN", "LCID", "NIO", "XPEV", "BYD"],
    "Defense & Aerospace": ["LMT", "RTX", "NOC", "GD", "BA", "PLTR", "BAH", "LHX", "HII"],
    "Semiconductors": ["NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM", "MU", "TXN", "AMAT", "LRCX"],
    "Fintech & Crypto": ["COIN", "HOOD", "SQ", "PYPL", "V", "MA", "MSTR", "MARA", "RIOT"],
    "Healthcare & Biotech": ["LLY", "NVO", "PFE", "JNJ", "UNH", "ABBV", "MRNA", "REGN"]
}

SP500_SAMPLE = [
    # Technology
    "AAPL", "MSFT", "NVDA", "AVGO", "AMD", "ADBE", "CSCO", "CRM", "INTU", "QCOM", "TXN", "AMAT", "NOW", "LRCX", "ADI", "MU", "KLAC", "PANW", "SNPS", "CDNS", "ORCL", "IBM", "ACN", "FI", "FIS",
    # Financials
    "JPM", "V", "MA", "BAC", "WFC", "MS", "GS", "C", "BLK", "SPGI", "AXP", "CB", "PGR", "SCHW", "MMC", "AON", "CINF", "MET", "PRU", "TRV",
    # Healthcare
    "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "PFE", "DHR", "ISRG", "AMGN", "ELV", "SYK", "VRTX", "BMY", "MDT", "GILD", "CI", "REGN", "ZTS",
    # Consumer Cyclical
    "AMZN", "TSLA", "HD", "MCD", "LOW", "BKNG", "NKE", "SBUX", "TJX", "ORLY", "AZO", "LULU", "MAR", "HLT", "CMG", "GM", "F", "APTV", "DHI", "LEN",
    # Communication Services
    "GOOGL", "GOOG", "META", "NFLX", "TMUS", "DIS", "CMCSA", "VZ", "T", "EA", "TTWO", "OMC", "IPG", "CHTR",
    # Industrials
    "GE", "CAT", "UNP", "HON", "BA", "RTX", "DE", "LMT", "ADP", "ETN", "ITW", "WM", "GD", "NOC", "CSX", "NSC", "EMR", "PH", "FDX", "UPS",
    # Consumer Defensive
    "WMT", "PG", "COST", "KO", "PEP", "PM", "MO", "MDLZ", "CL", "TGT", "KMB", "GIS", "STZ", "ADM", "SYY", "DG", "DLTR", "K", "HSY", "KR",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES", "HAL", "KMI", "WMB", "DVN", "FANG", "BKR",
    # Utilities
    "NEE", "SO", "DUK", "CEG", "SRE", "AEP", "D", "EXC", "XEL", "ED", "PEG", "WEC", "AWK", "EIX", "ES",
    # Real Estate
    "PLD", "AMT", "EQIX", "CCI", "PSA", "O", "SPG", "WELL", "DLR", "VICI", "AVB", "EQR", "WY", "SBAC", "INVH",
    # Basic Materials
    "LIN", "APD", "ECL", "SHW", "NEM", "FCX", "CTVA", "DOW", "DD", "NUE", "ALB", "PPG", "VMC", "MLM", "IFF"
]
NASDAQ100_SAMPLE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "COST", "ASML", "AMD", "NFLX", "AZN", "PEP", "ADBE", "CSCO", "TMUS", "QCOM", "INTU", "TXN", "AMAT", "CMCSA", "HON", "AMGN", "NOW", "ISRG", "LRCX", "BKNG", "PANW", "VRTX", "ADP", "MU", "REGN", "MDLZ", "SNPS", "CDNS", "KLAC", "PDD", "MELI", "PYPL", "CRWD", "INTC", "CSX", "LULU", "ORLY", "CTAS", "MAR", "WDAY", "MNST", "ROST"]
ETF_SAMPLE = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "SMH", "IGV", "ARKK", "SOXX", "XBI", "GDX", "TLT"]

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def identify_theme(symbol, sector, industry):
    symbol_upper = symbol.upper()
    for theme, tickers in THEME_MAPPINGS.items():
        if symbol_upper in tickers:
            return theme
    if sector == "Technology":
        if "Software" in (industry or ""):
            return "Cloud Computing"
        if "Semiconductor" in (industry or ""):
            return "Semiconductors"
    elif sector == "Aerospace & Defense":
        return "Defense & Aerospace"
    elif sector == "Automotive" or "Auto" in (industry or ""):
        return "Electric Vehicles"
    return sector or "General Equities"

def get_or_seed_ticker(symbol: str, force_update: bool = False):
    symbol = symbol.upper().strip()
    conn = get_db_connection()
    cursor = conn.cursor()

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

    if not force_update:
        cursor.execute("SELECT symbol, company, sector, industry, marketCap, theme FROM TickerMetadata WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return {
                "symbol": row[0],
                "company": row[1],
                "sector": row[2],
                "industry": row[3],
                "marketCap": row[4],
                "theme": row[5]
            }

    print(f"[Auto-Seed] Fetching metadata for missing ticker: {symbol}...")
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        
        company = info.get("shortName") or info.get("longName") or f"{symbol} Corp"
        sector = info.get("sector") or ("ETF" if info.get("quoteType") == "ETF" else "Equities")
        industry = info.get("industry") or sector
        market_cap = info.get("marketCap") or info.get("totalAssets") or 0.0
        
        is_sp500 = 1 if symbol in SP500_SAMPLE else 0
        is_nasdaq100 = 1 if symbol in NASDAQ100_SAMPLE else 0
        is_etf = 1 if info.get("quoteType") == "ETF" or symbol in ETF_SAMPLE else 0
        theme = identify_theme(symbol, sector, industry)
        
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        row_id = f"tm_{symbol.lower()}_{int(datetime.datetime.now().timestamp())}"

        cursor.execute("""
            INSERT INTO TickerMetadata 
            (id, symbol, company, sector, industry, marketCap, isSp500, isNasdaq100, isRussell2000, isEtf, theme, fetchedAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                company = excluded.company,
                sector = excluded.sector,
                industry = excluded.industry,
                marketCap = excluded.marketCap,
                isSp500 = excluded.isSp500,
                isNasdaq100 = excluded.isNasdaq100,
                isEtf = excluded.isEtf,
                theme = excluded.theme,
                updatedAt = excluded.updatedAt;
        """, (row_id, symbol, company, sector, industry, market_cap, is_sp500, is_nasdaq100, is_etf, theme, now_str, now_str))

        conn.commit()
        conn.close()

        return {
            "symbol": symbol,
            "company": company,
            "sector": sector,
            "industry": industry,
            "marketCap": market_cap,
            "theme": theme
        }
    except Exception as e:
        print(f"[Auto-Seed Error] Error auto-seeding {symbol}: {e}")
        conn.close()
        return None

def auto_seed_batch(symbols: list):
    results = {}
    for s in symbols:
        res = get_or_seed_ticker(s)
        if res:
            results[s] = res
    return results

if __name__ == "__main__":
    test_symbols = ["AAPL", "NVDA", "PLTR", "CRWD", "SPY", "TSLA"]
    print(f"Testing auto-seeder for {test_symbols}...")
    res = auto_seed_batch(test_symbols)
    print(f"[Auto-Seed] Auto-seeded {len(res)} tickers into Prisma DB.")
