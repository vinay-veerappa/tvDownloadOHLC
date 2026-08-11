import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List
from fastmcp import FastMCP

# Add root to sys.path for internal imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# Add context_manager scripts to sys.path for shared schema (B1: single schema owner)
CM_SCRIPTS = os.path.join(BASE_DIR, ".agent", "skills", "context_manager", "scripts")
if CM_SCRIPTS not in sys.path:
    sys.path.insert(0, CM_SCRIPTS)

# Heavy data services (pandas/profiler/candle-science) are imported LAZILY
# inside each tool so server startup stays light.

# Paths
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, ".agent", "memory.db")

# Shared schema + helpers (stdlib + sqlite3 only — preserves startup weight)
from store_schema import (
    USER_MD_PATH,
    ensure_schema,
    get_db_connection,
    fts_search,
    upsert_pref,
    get_prefs,
    render_profile_md,
    add_outcome,
    aggregate_outcomes,
    get_outcome_rows,
    generate_outcome_warnings,
    archive_outcome as _archive_outcome_db,
    discard_outcome as _discard_outcome_db,
    enqueue,
    list_queue,
    approve_queue_item,
    reject_queue_item,
    prune_queue,
    propose_skill_draft,
    maintain_store,
)


class SemanticMemory:
    """Adapter over the shared context_manager schema (content/tags).

    The MCP tools keep their (topic, content, metadata) signature; topic and
    metadata are folded into the single `tags` column on write.
    Schema is owned by store_schema.ensure_schema (B1: single schema owner).
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        ensure_schema(conn)
        conn.close()

    @staticmethod
    def _to_tags(topic, metadata):
        parts = [topic] if topic else []
        if metadata:
            if isinstance(metadata, dict):
                if metadata.get("linked_file"):
                    parts.append(f"linked_file:{metadata['linked_file']}")
                else:
                    parts.append(json.dumps(metadata))
            else:
                parts.append(str(metadata))
        return ", ".join(p for p in parts if p)

    def add(self, category, topic, content, metadata=None):
        tags = self._to_tags(topic, metadata)
        body = f"{topic} | {content}" if topic else content
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO memories (category, content, tags) VALUES (?, ?, ?)",
                (category, body, tags)
            )
        return f"Memory stored under '{category}': {topic}"

    def query(self, search_term):
        """FTS5-first search with LIKE fallback. Returns tuples (cat, content, tags, date)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = fts_search(conn, search_term, limit=10)
            return [(r["category"], r["content"], r["tags"], r["created_at"]) for r in rows]
        finally:
            conn.close()


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
    # Gather all three sources on one connection before deciding what to return.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # 1. Memory results (FTS5-first)
        memory_results = memory.query(query)

        # 2. Profile rows for preference-keyword matches
        profile_lines: List[str] = []
        try:
            prefs = get_prefs(conn)
            pref_matches = [p for p in prefs if query.lower() in p["key"].lower() or query.lower() in p["value"].lower()]
            if pref_matches:
                profile_lines.append("**Profile matches:**")
                for p in pref_matches:
                    profile_lines.append(f"- {p['key']}: {p['value']} (confidence={p['confidence']:.1f})")
        except Exception:
            pass

        # 3. Outcome projection (counts only, no raw PnL)
        outcome_lines: List[str] = []
        try:
            agg = aggregate_outcomes(conn, tag=query, period_days=7)
            for a in agg:
                if a.get("total", 0) > 0:
                    wr = a.get("win_rate_pct")
                    wr_str = f"{wr:.1f}%" if wr is not None else "N/A"
                    outcome_lines.append(
                        f"Outcomes [{a['tag']}]: {a['n_wins']} wins / {a['n_losses']} losses "
                        f"(win-rate {wr_str}) in last 7d"
                    )
        except Exception:
            pass
    finally:
        conn.close()

    # If absolutely nothing matched, say so.
    if not memory_results and not profile_lines and not outcome_lines:
        return f"No memories, profile entries, or outcomes found for '{query}'."

    formatted: List[str] = []
    if profile_lines:
        formatted.append("\n".join(profile_lines))

    for cat, content, tags, date in memory_results:
        # Strip linked_file: prefix when picking display topic
        first_tag = tags.split(",")[0].strip() if tags else ""
        if first_tag.startswith("linked_file:"):
            topic = ""
            for t in tags.split(","):
                t = t.strip()
                if not t.startswith("linked_file:"):
                    topic = t
                    break
        else:
            topic = first_tag
        formatted.append(f"[{cat}] {topic} ({date})\n{content}")

    if outcome_lines:
        formatted.extend(outcome_lines)

    return "\n\n".join(formatted)

@mcp.tool()
def link_memory_to_code(topic: str, file_path: str) -> str:
    """
    Creates a link between a memory topic and a specific file in the repository.
    Useful for ensuring the AI checks the 'Second Brain' when editing specific files.
    """
    full_path = os.path.join(BASE_DIR, file_path.replace("/", os.sep))
    if not os.path.exists(full_path):
        return f"Warning: File {file_path} does not exist. Link stored anyway."

    # FTS5 search to find matching rows (B2: ported from LIKE)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        matches = fts_search(conn, topic, limit=20)
        if not matches:
            return f"No memories found for '{topic}' to link."
    finally:
        conn.close()

    # Append the linked file to the tags of matching memories.
    linked_tag = f"linked_file:{file_path}"
    with sqlite3.connect(DB_PATH) as conn:
        for m in matches:
            conn.execute(
                "UPDATE memories SET tags = "
                "CASE WHEN tags IS NULL OR tags = '' THEN ?"
                "     WHEN instr(tags, ?) = 0 THEN tags || ', ' || ?"
                "     ELSE tags END "
                "WHERE id = ?",
                (linked_tag, linked_tag, linked_tag, m["id"])
            )
    return f"Linked {topic} to {file_path} ({len(matches)} memory rows)."


# ---------------------------------------------------------------------------
# P1: render_profile
# ---------------------------------------------------------------------------

@mcp.tool()
def render_profile() -> str:
    """Renders USER.md from user_prefs + select memories. Also writes to .agent/USER.md."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        md = render_profile_md(conn)
    finally:
        conn.close()
    with open(USER_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    return md


# ---------------------------------------------------------------------------
# P2: capture_outcome + recap_outcomes
# ---------------------------------------------------------------------------

@mcp.tool()
def capture_outcome(
    tag: str,
    subject: str,
    outcome: str,
    pnl: float = 0.0,
    ticker: str = None,
    entry_price: float = None,
    exit_price: float = None,
    run_id: str = None,
    symbol: str = None,
    session: str = None,
    verdict: str = None,
    metadata: dict = None,
) -> str:
    """
    Records a trade/run outcome. Consent via call (same pattern as link_memory_to_code).
    The return text is the confirmation surface. Verdict is inferred from outcome text if omitted.
    Pass verdict explicitly (win/loss/flat/mixed) to override inference.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        oid = add_outcome(
            conn, tag, subject, outcome, pnl, ticker, entry_price, exit_price,
            run_id, symbol, session, verdict=verdict, metadata=metadata,
        )
        # read back the verdict and whether it was inferred
        row = conn.execute("SELECT verdict FROM outcomes WHERE id = ?", (oid,)).fetchone()
        stored_verdict = row["verdict"] if row else "?"
    finally:
        conn.close()

    inferred_note = ""
    if verdict is None:
        inferred_note = f" Verdict was inferred as '{stored_verdict}'; pass verdict=... to override."
    return (f"Recorded outcome [{tag}] id={oid} verdict={stored_verdict} "
            f"subject='{subject}' pnl={pnl}.{inferred_note} "
            f"If this was not intended, use discard_outcome(id={oid}).")


@mcp.tool()
def recap_outcomes(period_days: int = 7, tag: str = None, verbose: bool = False) -> str:
    """
    Returns aggregate outcome stats. Default: counts only (no raw PnL).
    verbose=True adds itemized rows including pnl_local.
    Includes Phase-4 loss-rate warnings when a tag's losses exceed 2x its wins.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        agg = aggregate_outcomes(conn, tag=tag, period_days=period_days)
        warnings = generate_outcome_warnings(agg, period_days=period_days)
        out = {"period_days": period_days, "aggregates": agg, "warnings": warnings}
        if verbose:
            rows = get_outcome_rows(conn, tag=tag, period_days=period_days, limit=50)
            out["itemized"] = rows
        return json.dumps(out, indent=2, default=str)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# P2: archive / discard outcomes
# ---------------------------------------------------------------------------

@mcp.tool()
def archive_outcome(outcome_id: int) -> str:
    """Soft-deletes an outcome (sets archived=1). Use to hide bad data without removing it."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        ok = _archive_outcome_db(conn, outcome_id)
    finally:
        conn.close()
    if ok:
        return f"Outcome id={outcome_id} archived."
    return f"Outcome id={outcome_id} not found."


@mcp.tool()
def discard_outcome(outcome_id: int) -> str:
    """Hard-deletes an outcome row. Use when a capture was accidental."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        ok = _discard_outcome_db(conn, outcome_id)
    finally:
        conn.close()
    if ok:
        return f"Outcome id={outcome_id} discarded."
    return f"Outcome id={outcome_id} not found."


# ---------------------------------------------------------------------------
# P3: propose_skill
# ---------------------------------------------------------------------------

@mcp.tool()
def propose_skill(tag: str) -> str:
    """
    Proposes a reusable SKILL.md from repeated successful outcomes on a tag.
    Requires >=3 distinct win run_ids + zero losses in 30d. Never writes a file.
    Returns the draft text if eligible, or a refusal message.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        eligible, msg, qid = propose_skill_draft(conn, tag)
    finally:
        conn.close()
    if eligible:
        return f"Skill proposal drafted (queue id={qid}). Review, edit, then persist via:\n" \
               f"  python scripts/skill_writer.py --name <name> --source <saved_draft_path>\n\n" \
               f"{msg}"
    return msg


@mcp.tool()
def reject_skill_proposal(queue_id: int) -> str:
    """Marks a queued skill proposal as rejected. Rejected proposals are pruned after 30d."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        row = reject_queue_item(conn, queue_id)
    finally:
        conn.close()
    if row:
        return f"Skill proposal id={queue_id} rejected."
    return f"Skill proposal id={queue_id} not found."


# ---------------------------------------------------------------------------
# P4: maintenance
# ---------------------------------------------------------------------------

@mcp.tool()
def maintain_memory_store(dry_run: bool = False, render_profile: bool = False) -> str:
    """
    Periodic maintenance for the memory store.

    - Applies confidence decay to stale user_prefs rows (>90d inactive, -0.1 per 30d, floor 0.2).
    - Prunes unapproved skill proposals older than 30 days.
    - Optionally re-renders USER.md.

    Set dry_run=True to preview changes without writing.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        report = maintain_store(conn, render=render_profile, dry_run=dry_run)
    finally:
        conn.close()
    return json.dumps(report, indent=2, default=str)


# Paths
INVENTORY_PATH = os.path.join(BASE_DIR, "DATA_INVENTORY.md")
LEVELS_JSON_PATH = os.path.join(DATA_DIR, "daily_levels.json")

@mcp.tool()
def calculate_indicator(ticker: str, timeframe: str, indicators: list[str]) -> str:
    """
    Calculates technical indicators for a ticker/timeframe using historical Parquet data.
    Example: ticker="ES1", timeframe="5m", indicators=["vwap", "sma_20"]
    """
    from api.features.shared.data_loader import load_parquet
    from api.features.indicators.service import calculate_indicators

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
    Analyzes historical sessions from the pre-computed JSON.
    """
    from scripts.libs_py.profiler import ProfilerData, ProfilerStats

    try:
        data = ProfilerData.load(ticker)
        # Calculate stats for the last N sessions
        # (A day usually has 4 sessions, so days*4 is approximate)
        subset = data.sessions[-(days*4):]
        res = ProfilerStats.compute(subset)
        
        # Remove raw session list from output to keep it compact for the LLM
        if "all_sessions" in res:
             del res["all_sessions"]
             
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error loading profiler stats: {str(e)}"

@mcp.tool()
def get_profiler_combinations(
    ticker: str, 
    target_session: str, 
    filters: dict = None, 
    broken_filter: bool = None, 
    intra_state: str = "Any"
) -> str:
    """
    Returns probabilities for a target session based on a specific combination of prior session profiles.
    Example: ticker="NQ1", target_session="London", filters={"asia_status": "Long False"}
    
    Filters keys should match keys in ProfilerData.get_trading_day_context():
    ['prev_ny1_status', 'prev_ny2_status', 'prev_asia_status', 'prev_lon_status', 'asia_status', 'lon_status', 'ny1_status']
    """
    from scripts.libs_py.profiler import ProfilerData, ProfilerFilter, ProfilerStats

    try:
        data = ProfilerData.load(ticker)
        # ProfilerFilter expects context as a dict
        matched = ProfilerFilter.filter(data, target_session, filters or {}, broken_filter=broken_filter, intra_state=intra_state)
        res = ProfilerStats.compute(matched)
        
        if "all_sessions" in res:
             del res["all_sessions"]
             
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error computing profiler combinations: {str(e)}"

@mcp.tool()
def calculate_candle_science(ticker: str, timeframe: str, filters: dict = None) -> str:
    """
    Executes Candle Science statistical analysis using the Filter-then-Compute methodology.
    Returns probabilities for 3-candle patterns based on provided filters.
    """
    from api.features.candle_science.service import CandleScienceService

    result = CandleScienceService.calculate_stats(ticker, timeframe, filters)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_prediction(session: str, ticker: str = "NQ1") -> str:
    """
    Predicts session outcomes based on current institutional state (from Parquet source of truth).
    Determines Asia, London, or NY probabilities given the already-completed sessions today.
    """
    session_map = {"asia": "Asia", "london": "London", "ny1": "NY1", "ny2": "NY2"}
    target = session_map.get(session.lower())
    if not target:
        return "Invalid session. Use 'asia', 'london', 'ny1', or 'ny2'."

    try:
        from scripts.libs_py.profiler import ProfilerData, ProfilerFilter, ProfilerStats
        from scripts.libs_py.profiler import get_live_context

        # 1. Get current LIVE state from Parquet (Source of truth)
        context = get_live_context(ticker)
        
        # 2. Filter historical JSON by this context
        data = ProfilerData.load(ticker)
        matched = ProfilerFilter.filter(data, target, context)
        res = ProfilerStats.compute(matched)
        
        # 3. Add context to output so the LLM knows what we filtered by
        output = {
            "prediction_for": target,
            "current_context": context,
            "matched_historical_days": res.get("count"),
            "probabilities": res.get("distribution_pct"),
            "timing": res.get("timing"),
            "range": res.get("range"),
            "hit_rates": res.get("hit_rates")
        }
        return json.dumps(output, indent=2)
    except Exception as e:
        return f"Prediction failed: {str(e)}"

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

