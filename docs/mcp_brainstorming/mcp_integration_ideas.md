# MCP Integration Brainstorming & Ideas

This document serves as a living record of ideas, use cases, and technical designs for integrating the Model Context Protocol (MCP) into the `tvDownloadOHLC` platform.

## 🌟 Core Concepts

### 1. The "Multi-Broker Command Center"
**Status:** High Priority (Future Proofing)
- **Goal:** Provide a unified AI interface for all brokers (Schwab, Interactive Brokers, Tradovate, etc.).
- **How it helps:** The AI calls `get_current_position()` or `place_order(ticker, size)` without needing to know the underlying API/Broker complexity.
- **MCP Feature:** A set of standardized **Tools** for order management and risk monitoring.

### 2. The "Data Bridge" Server (V1.0 IMPLEMENTED)
- **Goal:** Expose internal quant logic as standardized Tools.
- **Server:** `mcp/data_server.py`
- **Implemented Tools:**
    - `calculate_indicator(ticker, tf, indicators)`: Wraps `api/features/indicators/service.py`.
    - `get_profiler_stats(ticker)`: Wraps `api/features/profiler/service.py`.
    - `get_market_levels(ticker)`: Direct access to GEX/Regime JSON.
    - `get_script_for_task(query)`: **(The Librarian)** Searches 230+ scripts.
    - `get_repo_map()`: High-level architectural navigation.
- **How it helps:** Reduces discovery cost by ~90%.
    - `mcp://data/inventory`: Live view of all available ticker/TF combinations.
    - `mcp://data/latest-levels`: Copy-ready strings for Pine Script/Discord.

### 3. "Smart Discovery" (Token Optimization)
**Status:** [x] Partially Implemented (via CBM-MCP)
- **Goal:** Drastically reduce the number of tokens spent on repository exploration and logic lookup.
- **Implemented:** 
    - [x] **Repo Structural Truth:** Identified all 73 API routes and 11k+ functional dependencies.
    - [x] **Functional Hubs:** Mapped the most critical service layers (e.g., `calculator.ts`).
- **Upcoming Tools:**
    - `get_project_rules(topic)`: Returns mandatory "DOs and DON'Ts" for specific areas.
    - `get_script_for_task(description)`: **(The Librarian)** Uses the `SCRIPTS_CATALOG.md` to find the exact core script needed for a task.
- **How it helps further:** While the structural graph tells us *what* exists, these specialized tools will tell us *why* it exists and *how* to use it according to your standards.

### 4. Codebase Memory MCP (CBM) ([DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp))
**Status:** Highly Recommended (Tier 1)
- **Goal:** Transform the repository into a structural knowledge graph for the AI.
- **How it helps:** Instead of me "guessing" how your Python files connect to your Pine Script or Web UI, CBM indices the **actual code structure** (calls, imports, logic chains).
- **Key Tools:**
    - `get_architecture`: Returns a living map of routes, layers, and entry points.
    - `detect_changes`: Shows the "blast radius" of a change (e.g., "If I change this NQ upsampling logic, what breaks?").
    - `manage_adr`: Keeps a log of Architectural Decisions directly in the graph.
- **Benefit:** Reduces token usage by ~99% for navigation and eliminates the risk of me using "outdated" info from an old `.md` file.

### 5. "Extended Semantic Memory" (The Second Brain)
**Status:** Exploratory (Highly Valuable)
- **Goal:** Store the history of architectural decisions, failed experiments, and market regime contexts.
- **Potential Data Points:**
    - **Decision Log:** "Why did we move from ORB v6 to v7g?" (To avoid false breakouts in low-vol regimes).
    - **Failure Logs:** "ATR 2.5 was too wide for NQ in current IV environment."
    - **Regime Awareness:** Linking strategy performance to specific market conditions (High vs. Low Gamma).
- **MCP Feature:** A **Resource** called `mcp://memory/context` that the AI can query to "remember" past learnings.

## 🛠️ Specialized Use Cases

### Token Usage Optimization (The Efficiency Play)
**Status:** Immediate Value
- **Goal:** Drastically reduce the number of tokens spent on repository exploration.
- **Metrics:** Moving from `view_file` (15k tokens) to `get_strategy_summary()` (300 tokens) provides a **~98% reduction** in discovery overhead.
- **MCP Feature:** Specialized **Tools** that return only the "high-signal" metadata of strategies and datasets.


### AI Liquidity Monitoring (Bookmap Co-Pilot)
- **Tool:** `mcp.get_liquidity_anomalies()`
- **Result:** Highlights massive icebergs or liquidity pulls directly to the AI, which then alerts the user.

### Pine ↔ Python Bridge (The "Logic Hub")
- **Tool:** `mcp.sync_pine_with_python()`
- **Result:** Ensures that your TradingView indicator logic and your Python backend logic are always harmonized.

### Automated Backtest "Dry-Run" (The Sandbox)
- **Tool:** `mcp.validate_strategy_sample(strategy_name)`
- **Result:** Runs strategy logic against a tiny sample (100 rows) to catch type errors (numpy/pandas) before a full run.

### Git History "Smart Summary" (The Historian)
- **Tool:** `mcp.get_last_refactors(ticker/feature)`
- **Result:** Returns just the relevant commit messages and diff summaries for a specific ticker or feature. Avoids parsing thousands of lines of `git log`.

## 🌍 Publicly Available MCP Servers (External)

These are servers built by the community that can be "plugged in" to give the AI extra superpowers.

### 1. Finance & Execution
- **Interactive Brokers / Tradovate / Schwab:** (Planned) Custom bridges for your specific brokers.

### 2. Search & News
- **ArXiv Search ([andybrandt/mcp-simple-arxiv](https://github.com/andybrandt/mcp-simple-arxiv))**: **Free.** Research for new alpha/indicator papers.
- **Alcove ([epicsagas/alcove](https://github.com/epicsagas/alcove))**: **Free.** Private doc search.

### 3. Knowledge & Visualization
- **Alcove ([epicsagas/alcove](https://github.com/epicsagas/alcove))**: **Free.** Private doc search.
- **AntV Charts ([antvis/mcp-server-chart](https://github.com/antvis/mcp-server-chart))**: **Free.** Allows the AI to generate high-quality visual charts for backtest results or GEX profiles.

## 🏗️ Structural Truth (Current System State)
> [!IMPORTANT]
> The following is derived directly from the code's call graph (36k nodes).

### Core API Entry Points (Candidates for MCP Tools)
These routes are the primary way the frontend interacts with the quant logic. Exposing these via an MCP "Bridge" server will allow the AI to trigger calculations without reading source code.

- **Indicators:** `POST /calculate`, `POST /calculate-v2`, `POST /calculate-from-file`
- **Market Stats:** `GET /stats/profiler/{ticker}`, `GET /stats/hod-lod/{ticker}`, `GET /stats/range-dist/{ticker}`
- **Predictions:** `GET /stats/prediction/asia`, `GET /stats/prediction/london`
- **Sessions:** `GET /{ticker}` (Session-based volume/price levels)

### Data Dependencies
- **Dominant Flow:** `scripts` -> `web` (904 calls), `scripts` -> `lightweight-charts` (562 calls).
- **Service Hubs:** `web/lib/candle-science/calculator.ts` is the central math engine for the frontend.

## 📉 Token Efficiency Analysis: Why MCP Wins
Today, to understand how a "calculate" request works, the AI must:
1. `list_dir api/routers` (~100 tokens)
2. `view_file api/features/indicators/router.py` (~4,000 tokens)
3. `view_file api/features/indicators/service.py` (~3,000 tokens)
4. Total: **~7,100 tokens per investigation.**

**With CBM-MCP & Custom Tools:**
1. `get_architecture(aspects=['routes'])` (~300 tokens)
2. `get_code_snippet(node_id='calculate')` (~500 tokens)
3. Total: **~800 tokens.**
**Savings: ~88% reduction in overhead per technical query.**

## 🗺️ Implementation Roadmap

### Phase 3: Platform Standardization (COMPLETED)
- [x] **Subdirectory Hierarchy:** Defined strict nesting rules and snake_case conventions.
- [x] **Script Rehoming:** 100% of `.py` and `.pine` scripts moved from `docs/` to `scripts/`.
- [x] **Documentation Sync:** `README` and `ROADMAP` promoted to V1.0.

### Phase 4: Visualization & Monitoring (Upcoming)
- [ ] **AntV Charts Bridge:** AI-driven generation of PnL/GEX charts.
- [ ] **Unified Dash:** Real-time monitoring via the Data Bridge.
