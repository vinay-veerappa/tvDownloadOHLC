import sys
import os
import json
import sqlite3
from datetime import datetime
from fastmcp import FastMCP

# Add root to sys.path for internal imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from api.features.indicators.service import calculate_indicators, get_available_indicators
from api.features.shared.data_loader import load_parquet, get_available_data
from api.features.profiler.service import ProfilerService
from api.features.candle_science.service import CandleScienceService

# Paths
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "mcp", "memory.db")

class SemanticMemory:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL, -- ADR, Nuance, Regime, Lesson
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT, -- JSON extra data
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_topic ON memories(topic)")

    def add(self, category, topic, content, metadata=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO memories (category, topic, content, metadata) VALUES (?, ?, ?, ?)",
                (category, topic, content, json.dumps(metadata) if metadata else None)
            )
        return f"Memory stored under '{category}': {topic}"

    def query(self, search_term):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT category, topic, content, created_at FROM memories WHERE topic LIKE ? OR content LIKE ? LIMIT 10",
                (f"%{search_term}%", f"%{search_term}%")
            )
            return cursor.fetchall()

# Initialize FastMCP server
mcp = FastMCP("DataBridge")
memory = SemanticMemory()

@mcp.tool()
def add_memory(topic: str, content: str, category: str = "ADR", metadata: dict = None) -> str:
    """
    Stores a persistent memory/decision in the 'Second Brain'.
    Categories: ADR (Architecture), Nuance (Strategy catch), Regime (Market context), Lesson.
    """
    return memory.add(category, topic, content, metadata)

@mcp.tool()
def query_memory(query: str) -> str:
    """Searches the Second Brain for relevant architectural decisions or strategy nuances."""
    results = memory.query(query)
    if not results:
        return f"No memories found for '{query}'."
    
    formatted = []
    for cat, topic, content, date in results:
        formatted.append(f"[{cat}] {topic} ({date})\n{content}")
    return "\n\n".join(formatted)

@mcp.tool()
def bootstrap_memory() -> str:
    """Initializes the memory with known foundations from the brainstorming phase."""
    seeds = [
        # Architecture
        ("ADR", "MCP Architecture", "Platform transitioned to AI-Native using CBM-MCP and custom DataBridge."),
        ("Nuance", "Token Efficiency", "Structural Graph (36k nodes) reduces navigation tokens by ~90%."),
        ("Nuance", "Data Access", "Indicators and Market Levels are now served via MCP tools to bypass file parsing."),
        # Shell Gotchas (Windows/PowerShell)
        ("Shell", "curl", "Always use `curl.exe -i` on Windows to avoid interactive Invoke-WebRequest prompts."),
        ("Shell", "ls", "Use `Get-ChildItem` for reliable file listing; be wary of `ls` alias limits."),
        ("Shell", "rm", "Use `Remove-Item -Force -Recurse` for clean deletions."),
        ("Shell", "mv", "Use `Move-Item -Force` for reliable moves, especially across different drives."),
        ("Shell", "paths", "schema.prisma is at web/prisma/schema.prisma NOT in root prisma/ directory."),
        ("Shell", "multiline-args", "Avoid multiline strings in PowerShell CLI args; use single-line strings instead."),
        # Data Cards
        ("DataCard", "NQ1", "Parquet OHLCV. Timeframes: 1m,5m,15m,1h,4h,1d,1W. Columns: [time,open,high,low,close,volume]. Timezone: US/Eastern. Source: TradingView."),
        ("DataCard", "ES1", "Parquet OHLCV. Timeframes: 1m,5m,15m,1h,4h,1d,1W. Same schema as NQ1. Source: TradingView."),
        ("DataCard", "all_tickers", "Futures: NQ1,ES1,RTY1,YM1,GC1,CL1. ETFs: QQQ,SPY,IWM,GLD,TLT. Equities: AAPL,NVDA,MSFT,META,TSLA,AMZN,GOOGL,AMD,PLTR. Indices: NDX,SPX,RUT,DJI. Vols: VIX,VVIX."),
        ("DataCard", "json_files", "Per-ticker derived files: _profiler.json, _hod_lod.json, _daily_hod_lod.json, _opening_range.json, _level_touches.json, _range_dist.json, _ny_levels_stats.json."),
        # Schema Cards
        ("SchemaCard", "Trade", "Core journal model. Key fields: id,ticker,entryDate,exitDate,entryPrice,exitPrice,quantity,direction(LONG/SHORT),status(OPEN/CLOSED/PENDING),pnl,notes,metadata(JSON). Relations: account,strategy,playbook,marketCondition."),
        ("SchemaCard", "MacroSnapshot", "Institutional options dashboard model. Fields: id,ticker,timestamp,tradingDate,spotPrice,macroCallWall,macroPutWall,zeroGamma,anomalies(JSON),dominantNodes(JSON). Unique on [ticker,tradingDate]."),
        ("SchemaCard", "Analysis", "Daily pre-market context model. Fields: date(unique),sentiment,bias,notes,keyLevels,profilerSnapshot,candleScienceSnapshot. Relations: charts,wargames."),
        ("SchemaCard", "GexSnapshot", "Intraday GEX timeseries. Fields: ticker,timestamp,tradingDate,totalGex,gexRegime,spotPrice,gammaMagnet,pinStrike. Index on [ticker,tradingDate]."),
        # DevOps Runner Cards
        ("DevOps", "Ports", "Frontend: 3000 | FastAPI: 8000 | MCP: Dynamic. Check .env for GEX_PORT overrides."),
        ("DevOps", "Commands", "Web: `npm run dev` (in /web) | Backend: `fastapi dev api/main.py` | DataBridge: `python mcp/data_server.py`."),
        # Incident Records (The "Never Again" List)
        ("Incident", "Prisma Path", "ALWAYS run `npx prisma generate` inside the `web/` directory. Schema is at `web/prisma/schema.prisma`."),
        ("Incident", "API Types", "POST /candle-science/calculate requires STRICT integers for min_ticks. 1.0 will fail with 422; use 1."),
        ("Incident", "MCP Args", "FastMCP `call` CLI fails on multiline strings. Always use single-line single-quoted strings for manual tool testing."),
        # Shell Enforcement (Windows/PowerShell Standard)
        ("Shell", "Enforcement", "THIS IS A WINDOWS/POWERSHELL ENVIRONMENT. NEVER use Unix commands (grep, ls, rm, mv). USE: Select-String, Get-ChildItem, Remove-Item -Force, Move-Item -Force."),
        ("Shell", "paths", "schema.prisma is at web/prisma/schema.prisma NOT in root prisma/ directory."),
        ("Shell", "multiline-args", "Avoid multiline strings in PowerShell CLI args; use single-line strings instead."),
        # Library & Domain Manuals (Foundational Knowledge)
        ("Lib", "SchwabAPI", "Use `schwabdev`. Client init requires `app_key, app_secret, callback_url`. KEY STEP: call `linked_accounts()` to get `hashValue` for account/order calls. Orders use strict JSON mappings from the Guide."),
        ("Lib", "PineScript", "TradingView v6 standard: Use //@version=6. ALWAYS use UDTs (User Defined Types) for entities with 3+ fields. NEVER delete historical drawings (boxes/lines) — only update live ones or trim based on max count."),
        ("Lib", "FastAPI", "Project standard: Feature-First. Routers go in `api/features/{name}/router.py`. Mount in `api/main.py`."),
        ("Lib", "Prisma", "Use `db.macroSnapshot.upsert` with `ticker_tradingDate` compound unique index for daily options data."),
        ("Domain", "ICT", "Core Logic: Killzones (London: 02-05, NYAM: 09:30-11:00). Bias Stacking = HTF Sweep + LTF CISD (Change in State of Delivery). SMT Divergence = Crack in correlation between NQ, ES, YM."),
        ("Data", "Inventory", "Derived Data at `/data/derived/`. Use `ict_nwog_ndog.json` for gaps, `NQ1_daily_classification.parquet` for bias, and `hourly_quarter_stats_NQ1.json` for intraday probabilities. DON'T RE-CALC!"),
    ]
    for cat, topic, content in seeds:
        memory.add(cat, topic, content)
    return "Second Brain bootstrapped with foundational knowledge."

@mcp.tool()
def link_memory_to_code(topic: str, file_path: str) -> str:
    """
    Creates a link between a memory topic and a specific file in the repository.
    Useful for ensuring the AI checks the 'Second Brain' when editing specific files.
    """
    full_path = os.path.join(BASE_DIR, file_path.replace("/", os.sep))
    if not os.path.exists(full_path):
        return f"Warning: File {file_path} does not exist. Link stored anyway."
    
    # Store this as metadata or a separate linkage? 
    # For now, we'll just update the memory entry with the file path in metadata.
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE memories SET metadata = json_insert(ifnull(metadata, '{}'), '$.linked_file', ?) WHERE topic = ?",
            (file_path, topic)
        )
    return f"Linked {topic} to {file_path}."

# Paths
INVENTORY_PATH = os.path.join(BASE_DIR, "DATA_INVENTORY.md")
LEVELS_JSON_PATH = os.path.join(DATA_DIR, "daily_levels.json")

@mcp.tool()
def calculate_indicator(ticker: str, timeframe: str, indicators: list[str]) -> str:
    """
    Calculates technical indicators for a ticker/timeframe using historical Parquet data.
    Example: ticker="ES1", timeframe="5m", indicators=["vwap", "sma_20"]
    """
    df = load_parquet(ticker, timeframe)
    if df is None:
        return f"Error: Data not found for {ticker} {timeframe}"
    
    results = calculate_indicators(df, indicators)
    # Return as JSON for AI parsing
    output = {
        "ticker": ticker,
        "timeframe": timeframe,
        "time": df['time'].tolist()[-10:], # Last 10 timestamps
        "indicators": {k: v[-10:] for k, v in results.items()} # Last 10 values
    }
    return json.dumps(output, indent=2)

@mcp.tool()
def get_profiler_stats(ticker: str, days: int = 50) -> str:
    """
    Gets session-based profiler statistics and probabilities for a ticker.
    Analyzes Open/High/Low/Close relative to previous sessions.
    """
    result = ProfilerService.analyze_profiler_stats(ticker, days=days)
    return json.dumps(result, indent=2)

@mcp.tool()
def calculate_candle_science(ticker: str, timeframe: str, filters: dict = None) -> str:
    """
    Executes Candle Science statistical analysis using the Filter-then-Compute methodology.
    Returns probabilities for 3-candle patterns based on provided filters.
    """
    result = CandleScienceService.calculate_stats(ticker, timeframe, filters)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_prediction(session: str, context: dict) -> str:
    """
    Predicts session outcomes based on prior session status.
    session: 'asia' or 'london'
    context: {'prev_ny1': 'Long True', 'prev_ny2': 'Short False', 'asia_status': 'Any'}
    """
    if session.lower() == 'asia':
        res = ProfilerService.get_asia_prediction(context.get('prev_ny1'), context.get('prev_ny2'))
    elif session.lower() == 'london':
        res = ProfilerService.get_london_prediction(context.get('prev_ny2'), context.get('asia_status'))
    else:
        return "Unknown session. Use 'asia' or 'london'."
    return json.dumps(res, indent=2)

@mcp.tool()
def get_market_levels(ticker: str) -> str:
    """Retrieves structured GEX/Gamma levels for a ticker (e.g., 'ES', 'NQ')."""
    if not os.path.exists(LEVELS_JSON_PATH):
        return "Levels data not found."
    with open(LEVELS_JSON_PATH, "r") as f:
        data = json.load(f)
    
    # The JSON has a 'market_structure' list
    market_structure = data.get("market_structure", [])
    ticker_upper = ticker.upper()
    
    for item in market_structure:
        if item.get("asset") == ticker_upper or item.get("cash_ticker") == ticker_upper:
            return json.dumps(item, indent=2)
            
    return f"Ticker {ticker} not found in market_structure. Available: {', '.join([x.get('asset') for x in market_structure])}"

@mcp.tool()
def get_script_for_task(query: str) -> str:
    """
    Finds relevant scripts for a task by searching the SCRIPTS_CATALOG.md.
    Example: query="upsampling", query="indicator calculation", query="ninja import"
    """
    catalog_path = os.path.join(BASE_DIR, "docs", "SCRIPTS_CATALOG.md")
    if not os.path.exists(catalog_path):
        return "Scripts catalog not found."
    
    with open(catalog_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Simple search for relevant lines in the markdown tables
    matches = []
    query_lower = query.lower()
    for line in content.split("\n"):
        if "|" in line and query_lower in line.lower():
            matches.append(line.strip())
            
    if not matches:
        return f"No scripts found matching '{query}'. Try a broader term."
        
    return "Relevant scripts from catalog:\n" + "\n".join(matches)

@mcp.tool()
def get_repo_map() -> str:
    """Returns a high-level map of the repository structure and responsibilities."""
    # This is a curated map to avoid massive listing
    repo_map = {
        "api/": "FastAPI backend, routers, and core services for indicators/profiler.",
        "web/": "Next.js frontend dashboard and UI components.",
        "data/": "Storage for Parquet files, JSON levels, and CSV imports.",
        "scripts/": "Hundreds of utility scripts for data processing, backtesting, and maintenance.",
        "docs/": "Architecture, protocol, and script documentation.",
        "mcp/": "Model Context Protocol servers and integration tools."
    }
    return json.dumps(repo_map, indent=2)

@mcp.tool()
def check_data_freshness(ticker: str = "NQ1") -> str:
    """
    Checks the latest timestamp in live storage vs current time.
    Helps determine if the streaming spoke or hub is lagging.
    """
    # Standardize ticker to live format
    live_map = {"NQ1": "-NQ", "ES1": "-ES", "YM1": "-YM", "RTY1": "-RTY", "CL1": "-CL", "GC1": "-GC"}
    safe_ticker = live_map.get(ticker, ticker)
    
    live_path = os.path.join(DATA_DIR, "live", f"live_storage_{safe_ticker}.parquet")
    if not os.path.exists(live_path):
        return f"Error: Live storage file for {ticker} not found at {live_path}"
    
    try:
        import pandas as pd
        df = pd.read_parquet(live_path)
        if df.empty:
            return f"Error: Live storage for {ticker} is empty."
            
        last_ts = pd.to_datetime(df['time'].max(), unit='ms') # Assuming ms based on stream_chart logic
        now = datetime.utcnow()
        gap_mins = (now - last_ts).total_seconds() / 60
        
        status = "✅ CURRENT" if gap_mins < 15 else "❌ STALE"
        return json.dumps({
            "ticker": ticker,
            "last_timestamp_utc": last_ts.isoformat(),
            "now_utc": now.isoformat(),
            "gap_minutes": round(gap_mins, 2),
            "status": status
        }, indent=2)
    except Exception as e:
        return f"Technical Error checking freshness: {str(e)}"

@mcp.tool()
def get_detailed_data_status() -> str:
    """Returns a comprehensive report of all tickers in data/ and data/live/ with their last modified times and row counts."""
    report = {"history": {}, "live": {}}
    
    # Check History
    for f in os.listdir(DATA_DIR):
        if f.endswith(".parquet") and "_" in f:
            path = os.path.join(DATA_DIR, f)
            stats = os.stat(path)
            report["history"][f] = {
                "size_kb": round(stats.st_size / 1024, 2),
                "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
            }
            
    # Check Live
    live_dir = os.path.join(DATA_DIR, "live")
    if os.path.exists(live_dir):
        for f in os.listdir(live_dir):
            if f.startswith("live_storage_") and f.endswith(".parquet"):
                path = os.path.join(live_dir, f)
                stats = os.stat(path)
                report["live"][f] = {
                    "size_kb": round(stats.st_size / 1024, 2),
                    "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
                }
                
    return json.dumps(report, indent=2)

if __name__ == "__main__":
    mcp.run()

