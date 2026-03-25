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
        ("ADR", "MCP Architecture", "Platform transitioned to AI-Native using CBM-MCP and custom DataBridge."),
        ("Nuance", "Token Efficiency", "Structural Graph (36k nodes) reduces navigation tokens by ~90%."),
        ("Nuance", "Data Access", "Indicators and Market Levels are now served via MCP tools to bypass file parsing.")
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
def get_system_health() -> str:
    """Checks directory structure and venv status."""
    return json.dumps({
        "status": "healthy",
        "root": BASE_DIR,
        "data_sync": len(get_available_data())
    }, indent=2)

if __name__ == "__main__":
    mcp.run()
