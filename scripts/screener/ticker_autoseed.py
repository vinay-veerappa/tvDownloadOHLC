import os
import sqlite3
import datetime
import yfinance as yf

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../web/prisma/dev.db"))

THEME_MAPPINGS = {
    "Artificial Intelligence": ["NVDA", "AMD", "MSFT", "GOOGL", "META", "PLTR", "AI", "SMCI", "AVGO", "TSM", "ARM", "ANET", "DELL", "HPE", "VRT"],
    "Cybersecurity": ["CRWD", "PANW", "FTNT", "ZS", "NET", "S", "CHKP", "OKTA", "CYBR", "TENB", "RPD"],
    "Cloud & Enterprise Software": ["AMZN", "MSFT", "GOOGL", "ORCL", "CRM", "NOW", "SNOW", "DDOG", "MDB", "TEAM", "HUBS", "WDAY", "SAP", "INTU", "ADBE"],
    "Semiconductors & Equipment": ["NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM", "MU", "TXN", "AMAT", "LRCX", "KLAC", "ASML", "ADI", "MRVL", "MCHP", "MPWR", "ON"],
    "Electric Vehicles & Auto": ["TSLA", "RIVN", "LCID", "NIO", "XPEV", "GM", "F", "APTV", "BYD", "CHPT", "BLNK", "QS"],
    "Defense & Aerospace": ["LMT", "RTX", "NOC", "GD", "BA", "PLTR", "BAH", "LHX", "HII", "TDG", "HEI", "AXON", "KTOS"],
    "Fintech & Crypto": ["COIN", "HOOD", "SQ", "PYPL", "V", "MA", "MSTR", "MARA", "RIOT", "CLSK", "SOFI", "AFRM"],
    "Healthcare & Biotech": ["LLY", "NVO", "PFE", "JNJ", "UNH", "ABBV", "MRNA", "REGN", "VRTX", "GILD", "BMY", "ISRG", "BDX", "ZTS", "MRK", "TMO", "DHR", "ABT"],
    "Internet & E-Commerce": ["AMZN", "BABA", "PDD", "MELI", "SE", "DASH", "ETSY", "CHWY", "EBAY", "SHOP"],
    "Streaming & Entertainment": ["NFLX", "DIS", "WBD", "PARA", "SPOT", "WMG", "ROKU", "EA", "TTWO"],
    "Retail & Consumer Giants": ["WMT", "COST", "TGT", "HD", "LOW", "TJX", "SBUX", "MCD", "NKE", "LULU", "CMG", "ROST", "DG", "DLTR", "KR"],
    "Energy & Clean Tech": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "FSLR", "ENPH", "SEDG", "CEG"],
    "Banks & Financial Institutions": ["JPM", "BAC", "WFC", "C", "MS", "GS", "SCHW", "BLK", "BX", "KKR", "SPGI", "MCO", "CINF", "PGR", "CB", "TRV"]
}

SP500_SAMPLE = [
    # Technology - Software, Chips, Hardware, Services
    "AAPL", "MSFT", "NVDA", "AVGO", "AMD", "ADBE", "CSCO", "CRM", "INTU", "QCOM", "TXN", "AMAT", "NOW", "LRCX", "ADI", "MU", "KLAC", "PANW", "SNPS", "CDNS", "ORCL", "IBM", "ACN", "FI", "FIS", "CRWD", "FTNT", "ZS", "NET", "SNOW", "DDOG", "DELL", "HPE", "SMCI", "ANET", "ARM", "MRVL", "MCHP", "ON",
    # Financials - Banks, Credit, Capital Markets, Insurance
    "JPM", "V", "MA", "BAC", "WFC", "MS", "GS", "C", "BLK", "SPGI", "AXP", "CB", "PGR", "SCHW", "MMC", "AON", "CINF", "MET", "PRU", "TRV", "MCO", "BX", "KKR", "APO", "COF", "DFS", "PYPL", "SQ", "HOOD", "COIN", "SOFI",
    # Healthcare - Pharma, Biotech, Medical Devices, Services
    "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "PFE", "DHR", "ISRG", "AMGN", "ELV", "SYK", "VRTX", "BMY", "MDT", "GILD", "CI", "REGN", "ZTS", "BDX", "MRNA", "NVO", "RMD", "IDXX", "EW", "BAX", "GEHC", "ALGN",
    # Consumer Cyclical - E-Commerce, Autos, Retail, Travel, Restaurants
    "AMZN", "TSLA", "HD", "MCD", "LOW", "BKNG", "NKE", "SBUX", "TJX", "ORLY", "AZO", "LULU", "MAR", "HLT", "CMG", "GM", "F", "APTV", "DHI", "LEN", "PDD", "BABA", "MELI", "RIVN", "NIO", "LCID", "DASH", "ROST", "EXPE", "ABNB", "RCL", "CCL", "NCLH",
    # Communication Services - Internet, Entertainment, Telecom
    "GOOGL", "GOOG", "META", "NFLX", "TMUS", "DIS", "CMCSA", "VZ", "T", "EA", "TTWO", "OMC", "IPG", "CHTR", "DISH", "WBD", "PARA", "ROKU", "SPOT",
    # Industrials - Defense, Machinery, Transport, Railroads, Construction
    "GE", "CAT", "UNP", "HON", "BA", "RTX", "DE", "LMT", "ADP", "ETN", "ITW", "WM", "GD", "NOC", "CSX", "NSC", "EMR", "PH", "FDX", "UPS", "TDG", "HEI", "AXON", "CERR", "URI", "PWR", "JCI", "TT", "CARR",
    # Consumer Defensive - Discount Stores, Beverages, Tobacco, Staples
    "WMT", "PG", "COST", "KO", "PEP", "PM", "MO", "MDLZ", "CL", "TGT", "KMB", "GIS", "STZ", "ADM", "SYY", "DG", "DLTR", "K", "HSY", "KR", "KFT", "TAP", "EL", "CHD",
    # Energy - Oil & Gas, Equipment, Refining, Pipelines
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES", "HAL", "KMI", "WMB", "DVN", "FANG", "BKR", "APA", "MRO", "TRGP", "OKE",
    # Utilities - Electric, Gas, Multi-Utilities, Clean Energy
    "NEE", "SO", "DUK", "CEG", "SRE", "AEP", "D", "EXC", "XEL", "ED", "PEG", "WEC", "AWK", "EIX", "ES", "PCG", "FE", "PPL", "CMS", "CNP",
    # Real Estate - REITs, Data Centers, Industrial, Cell Towers
    "PLD", "AMT", "EQIX", "CCI", "PSA", "O", "SPG", "WELL", "DLR", "VICI", "AVB", "EQR", "WY", "SBAC", "INVH", "BXP", "ARE", "MAA", "UDR", "CPT",
    # Basic Materials - Specialty Chemicals, Metals, Mining, Steel
    "LIN", "APD", "ECL", "SHW", "NEM", "FCX", "CTVA", "DOW", "DD", "NUE", "ALB", "PPG", "VMC", "MLM", "IFF", "STLD", "CLF", "X", "AA"
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
            return "Cloud & Enterprise Software"
        if "Semiconductor" in (industry or ""):
            return "Semiconductors & Equipment"
    elif sector == "Aerospace & Defense":
        return "Defense & Aerospace"
    elif sector == "Automotive" or "Auto" in (industry or ""):
        return "Electric Vehicles & Auto"
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

    cursor.execute("SELECT symbol, company, sector, industry, marketCap, isSp500, isNasdaq100, isEtf, theme FROM TickerMetadata WHERE symbol = ?", (symbol,))
    row = cursor.fetchone()

    if row and not force_update:
        conn.close()
        return {
            "symbol": row[0],
            "company": row[1],
            "sector": row[2] or "Equities",
            "industry": row[3] or "General",
            "marketCap": row[4] or 1000000000.0,
            "isSp500": bool(row[5]),
            "isNasdaq100": bool(row[6]),
            "isEtf": bool(row[7]),
            "theme": row[8] or "General Equities"
        }

    # Fetch from Yahoo Finance
    try:
        print(f"[Auto-Seed] Fetching metadata for missing ticker: {symbol}...")
        ticker_obj = yf.Ticker(symbol)
        info = ticker_obj.info or {}

        company = info.get("longName") or info.get("shortName") or symbol
        sector = info.get("sector") or "Equities"
        industry = info.get("industry") or "General"
        market_cap = float(info.get("marketCap") or 1000000000.0)

        is_sp500 = 1 if symbol in SP500_SAMPLE else 0
        is_nasdaq100 = 1 if symbol in NASDAQ100_SAMPLE else 0
        is_etf = 1 if symbol in ETF_SAMPLE or info.get("quoteType") == "ETF" else 0
        theme = identify_theme(symbol, sector, industry)

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec_id = f"tm_{symbol.lower()}_{int(datetime.datetime.now().timestamp())}"

        cursor.execute("""
            INSERT INTO TickerMetadata (id, symbol, company, sector, industry, marketCap, isSp500, isNasdaq100, isEtf, theme, fetchedAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                company=excluded.company,
                sector=excluded.sector,
                industry=excluded.industry,
                marketCap=excluded.marketCap,
                isSp500=excluded.isSp500,
                isNasdaq100=excluded.isNasdaq100,
                isEtf=excluded.isEtf,
                theme=excluded.theme,
                updatedAt=excluded.updatedAt
        """, (rec_id, symbol, company, sector, industry, market_cap, is_sp500, is_nasdaq100, is_etf, theme, now_str, now_str))

        conn.commit()
        conn.close()

        return {
            "symbol": symbol,
            "company": company,
            "sector": sector,
            "industry": industry,
            "marketCap": market_cap,
            "isSp500": bool(is_sp500),
            "isNasdaq100": bool(is_nasdaq100),
            "isEtf": bool(is_etf),
            "theme": theme
        }
    except Exception as e:
        print(f"[Auto-Seed Error] Failed to seed ticker {symbol}: {e}")
        conn.close()
        return None

def auto_seed_batch(symbols):
    results = {}
    for s in symbols:
        meta = get_or_seed_ticker(s)
        if meta:
            results[s] = meta
    return results

if __name__ == "__main__":
    print(f"Auto-seeding expanded universe ({len(SP500_SAMPLE)} tickers)...")
    auto_seed_batch(SP500_SAMPLE)
    print("Done auto-seeding universe.")
