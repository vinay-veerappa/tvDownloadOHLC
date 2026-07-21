# NinjaTrader 8 Model Context Protocol (MCP) — Architecture & Feature Specification

> **Version**: 1.4.0  
> **Status**: Production Architecture & Feature Expansion Specification  
> **Target Audience**: Engineering Team, Quant Researchers, & External Reviewers

---

## 1. Overview & Core Architecture

The **NinjaTrader MCP Bridge** provides a standardized [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) stdio interface, enabling AI agents (Claude, Hermes, ChatGPT, Cursor, Cline) and automated Python/TypeScript clients to control **NinjaTrader 8** locally.

```
+------------------------+        Stdio        +------------------------+       HTTP :7890       +-----------------------------------+
|  AI Agent / Client     | <-----------------> |   nt-mcp-server.js     | <--------------------> |   McpBridgeAddOn.cs               |
|  (Python/JS/Claude)    |   JSON-RPC 2.0      |   (Node.js MCP Relay)  |   Bearer Auth / REST   |   (NinjaTrader 8 Native AddOn)    |
+------------------------+                     +------------------------+                        +-----------------------------------+
```

### Key Architectural Pillars
1. **Zero External Cloud Dependencies**: Runs 100% locally on the user's Windows workspace.
2. **In-Process Hot-Swap Compiler**: Compiles C# NinjaScript source directly via Roslyn without restarting NT8.
3. **Strategy Analyzer Bridge**: Drives GUI Strategy Analyzer windows for backtesting and performance extraction.
4. **Production Safety & Multi-Phase Tooling**: Incorporates local auth, atomic kill-switches, mandatory idempotency, auditability, event streams, and quantitative research tools.

---

## 2. Production Safety, Security & Guardrails

### A. Authentication, Network Isolation & Versioning
* **Localhost Binding**: The HTTP listener (`McpBridgeAddOn.cs`) binds strictly to `127.0.0.1:7890` by default to prevent DNS rebinding attacks and cross-process network sniffing.
* **Bearer Token Authorization**: Requests must include an `Authorization: Bearer <NT8_MCP_TOKEN>` header. The token is generated locally at AddOn startup and shared only with local MCP clients.
* **Semantic Versioning Header**: All HTTP responses include `X-NT8-MCP-Version: 1.4.0` allowing clients to detect breaking changes or capability gaps.

### B. Concurrency, Retries & Mandatory Idempotency
* To prevent duplicate order execution across flaky stdio/HTTP hops, all mutating endpoints (`nt_place_order`, `nt_place_oco_order`, `nt_place_atm_order`, `nt_emergency_flatten`) REQUIRE a client-supplied `idempotencyKey` string in production mode.
* The C# AddOn maintains a rolling 1-hour cache of processed `idempotencyKey` UUIDs. Duplicate submissions return the cached order response without re-submitting to the market.

### C. Atomic Emergency Kill-Switch (`nt_emergency_flatten`)
* Replaces loose compositions of cancel/close calls during market stress.
* **`nt_emergency_flatten`** executes atomically inside a single C# dispatcher block:
  1. Cancels all active/working orders across all specified accounts.
  2. Issues market orders to immediately flatten all open positions.
  3. Activates a temporary account lockout in RiskGuard to block any new order placement for $N$ minutes.

### D. Auditability & Intervention Logging
* Every mutating endpoint logs the complete JSON request payload, user/agent context, timestamp, and resulting `action_id` to an immutable audit file (`interventions.jsonl`). Essential for prop firm compliance and post-mortem analysis.

### E. Roslyn Hot-Swap Compiler & SIM Gating
* Strategy source created via `nt_create_strategy` and compiled via `nt_compile` is automatically tagged as **Unverified**.
* Unverified strategies can only be deployed onto **SIM accounts (`Sim101`)**.
* Deployment to a live brokerage account requires passing `confirmLive: true` along with explicit user confirmation.

---

## 3. Data Contracts, Timezones & Error Model

### A. Explicit UTC Input/Output Timezone Contract
* **Input Parameters**: All input dates and date ranges (e.g. `from`, `to` for backtests, exports, or log queries) MUST be supplied in **UTC (ISO-8601)** (`YYYY-MM-DDTHH:mm:ss.sssZ`).
* **Data Storage & API JSON Payloads**: All timestamp outputs (bars, fills, order events) are returned in **UTC (ISO-8601)**.
* **Session & Macro Windows**: Market session calculations (e.g., 08:30 ET release, 09:30 RTH open, 10:50 ET macro boundary, Midnight Open) are explicitly computed internally in **US Eastern Time (`America/New_York`)** with automatic Daylight Saving Time (DST) handling.

### B. Pagination, Cursor Offsets & Payload Rules
* `nt_bars`, `nt_fill_events`, and `nt_orders` support **limit + offset** pagination parameters (`limit`, `offset`, `cursor`) to allow reliable, chunked extractions.
* `nt_bars` JSON payloads are capped at **5,000 bars** per request. Multi-year minute bar ingestion MUST use `nt_export_bars` (streaming directly to CSV on disk).

### C. Standardized Error Model
All tool responses follow a predictable JSON schema:
```json
{
  "success": false,
  "code": "ORDER_REJECTED",
  "message": "Order rejected by broker: insufficient buying power",
  "details": {
    "account": "Sim101",
    "symbol": "NQ 09-26",
    "rejectReason": "MarginViolation",
    "timestamp": "2026-07-21T19:45:00.000Z"
  }
}
```

### D. Historical Data Download Engine & Edge Case Handling (`nt_export_bars`)
The historical data engine in `McpBridgeAddOn.cs` handles deep multi-year historical queries and vendor edge cases:

* **Arbitrary Date Ranges & Depth (20+ Years)**: Accepts explicit UTC `from` and `to` ISO date parameters. Pulls any depth available from the connected data vendor (Tradovate, Kinetick, Rithmic, Interactive Brokers, IQFeed).
* **Flexible Timeframe Resolution**: Supports `Minute`, `Day`, `Second`, `Tick`, `Volume`, and `Range` periods with any integer `periodValue` (e.g. 1m, 5m, 15m, 1h, 1d, 1000 volume, 10 range).
* **Continuous Contract Adjustment Policies (`merge`)**:
  * **`DoNotMerge`**: Downloads the single specific contract (e.g., `NQ 09-26`).
  * **`MergeNonBackAdjusted`**: Continuous contract series stitched across front months with **unadjusted real historical prices**.
  * **`MergeBackAdjusted`**: Continuous series back-adjusted across historical roll gap offsets.
* **On-Demand Vendor Backfill Trigger**: If local NinjaTrader cache is missing historical data for the requested window, `BarsRequest` automatically initiates an asynchronous backfill request to the connected data provider.
* **Edge Case & Failure Recovery**:
  * **Backfill Timeout Control (`timeoutSec`)**: Configurable timeout (default 180s, extendable for multi-decade pulls).
  * **Expired Contract Auto-Resolution**: Expired futures contracts resolve automatically without requiring an active market data subscription.
  * **Data Provenance & Gap Registry**: The `nt8_ingest/` pipeline tags all downloaded bars with vendor provenance and logs feed outage holes into `nt8_data_gaps`.

---

## 4. Complete Tool Reference

### Phase 1 — Account Management, Live Trading & Quotes
| Tool Name | Endpoint | Description |
| :--- | :--- | :--- |
| `nt_health` | `GET /api/health` | Check NT8 AddOn connection, version, auth, and dev mode status. |
| `nt_accounts` | `GET /api/account` | List accounts, cash balances, buying power, and total equity. |
| `nt_positions` | `GET /api/positions` | Query open market positions with live P&L per account. |
| `nt_orders` | `GET /api/orders` | List active/working orders with pagination (`limit`, `offset`). |
| `nt_place_order` | `POST /api/order` | Place Market, Limit, StopMarket, StopLimit, or MIT orders with mandatory `idempotencyKey`. |
| `nt_change_order` | `POST /api/order/change` | Modify active working order parameters (quantity, limit price, stop price). |
| `nt_cancel_order` | `POST /api/order/cancel` | Cancel an order by order ID or group OCO ID. |
| `nt_cancel_all_orders` | `POST /api/orders/cancel-all` | Panic cancellation of all working orders across accounts. |
| `nt_close_position` | `POST /api/position/close` | Flatten a position and cancel working orders for a symbol. |
| `nt_emergency_flatten`| `POST /api/emergency-flatten`| **Atomic Kill-Switch**: Cancel all orders, flatten positions, and engage RiskGuard lockout. |
| `nt_quote` | `GET /api/quote?symbol=` | Real-time quote stream (bid, ask, last, volume, daily high/low) with auto-subscription. |
| `nt_bars` | `GET /api/bars?...` | Fetch historical OHLCV bars with pagination (`limit`, `offset`) capped at 5,000 rows. |
| `nt_search` | `GET /api/search?query=` | Search available instrument master records by symbol or description. |

### Phase 2 — Strategy Development & Backtesting
| Tool Name | Endpoint | Description |
| :--- | :--- | :--- |
| `nt_list_strategies` | `GET /api/strategies` | List NinjaScript strategy source `.cs` files in `bin\Custom\Strategies`. |
| `nt_strategy_source` | `GET /api/strategy/source?name=` | Read raw NinjaScript C# source code. |
| `nt_create_strategy` | `POST /api/strategy/create` | Write NinjaScript C# source file into `bin\Custom\Strategies`. |
| `nt_compile` | `POST /api/compile` | Hot-swap compile NinjaScript in-process via Roslyn (**no NT8 restart required**). |
| `nt_backtest` | `POST /api/backtest` | Run Strategy Analyzer backtests over symbol, UTC date range, timeframe, and parameters. |

### Phase 3 — Historical Data Ingest & Archive
| Tool Name | Endpoint | Description |
| :--- | :--- | :--- |
| `nt_export_bars` | `POST /api/bars/export` | Download & export raw historical OHLCV bars to CSV (continuous or single contract). |
| `nt_get_export` | `GET /api/export?name=` | Fetch generated export CSV file content over network. |

### Phase 4 — Strategy Deployment & Real-Time Monitoring
| Tool Name | Endpoint | Description |
| :--- | :--- | :--- |
| `nt_deploy_strategy` | `POST /api/strategy/deploy` | Deploy & enable compiled strategy onto an open chart (SIM-first safety). |
| `nt_stop_strategy` | `POST /api/strategy/stop` | Disable & remove running strategy from chart, optionally flattening open positions. |
| `nt_strategy_status` | `GET /api/strategy/running` | Query state (Realtime/Historical), instrument, timeframe, and position of running strategies. |
| `nt_set_strategy_param` | `POST /api/strategy/param` | Modify inputs on a RUNNING strategy live without restarting. |

---

## 5. Unbound v1.1.0 AddOn Endpoints (Immediate MCP Tool Bindings)

The C# AddOn (`McpBridgeAddOn.cs`) currently implements the following REST endpoints which are queued for registration into `nt-mcp-server.js`:

1. **`nt_capture_chart` (`GET /api/chart/capture?symbol=`)**  
   Renders NinjaTrader WPF chart windows into high-res base64 PNG images using `RenderTargetBitmap`.

2. **`nt_open_chart` (`POST /api/chart/open`)**  
   Programmatically opens chart windows/tabs for a specified symbol and timeframe.

3. **`nt_get_logs` (`GET /api/logs?tab=&lines=`)**  
   Tails NT8 Output tab logs, Strategy Analyzer logs, or `interventions.jsonl` audit files.

4. **`nt_fill_events` (`GET /api/events/fills?count=&limit=&offset=`)**  
   Queries execution history across accounts (`account.Executions`) with pagination for fill audit and slippage calculation.

5. **`nt_inspect_strategy` (`GET /api/strategy/inspect?name=`)**  
   Reflects over compiled strategy assemblies to extract parameter names, types, default values, and metadata.

6. **`nt_riskguard_state` & `nt_riskguard_fsm` (`GET /api/riskguard/*`)**  
   Reads live RiskGuard FSM state (Flat, InPosition, SoftStop, HardStop, Lockout), intraday peak equity drawdown, and daily loss limit snapshots.

7. **`nt_place_oco_order` (`POST /api/order/oco`)**  
   Places atomic paired OCO (One-Cancels-Other) limit/stop orders with mandatory `idempotencyKey`.

---

## 6. Phased Feature Expansion Pipeline (v1.4 Roadmap)

```
                                  v1.4+ EXPANSION ROADMAP PIPELINE
                                  
+---------------------------------------------------------------------------------------------------+
| Phase 5: Enhanced Observability & Debugging                                                       |
|   - nt_chart_snapshot (PNG + visual markers, price lines, indicators)                             |
|   - nt_indicator_values (deep series + running strategy collection)                              |
|   - nt_strategy_debug (trace logs & variable state dumps)                                         |
+---------------------------------------------------------------------------------------------------+
| Phase 6: Advanced Research & Quant Optimization                                                   |
|   - nt_optimize & nt_walk_forward (Bayesian/Gaussian, Pareto fronts, run_id provenance)            |
|   - nt_portfolio_backtest (multi-symbol, correlation matrix, portfolio allocation)                 |
|   - nt_synthetic_data (stress scenarios: COVID crash, 2008 shock, volatility scaling)             |
|   - nt_signal_backtest (lightweight what-if signal evaluation)                                   |
+---------------------------------------------------------------------------------------------------+
| Phase 7: Automation & Workflow Execution                                                          |
|   - nt_script_execute (sandboxed C# snippet execution)                                            |
|   - nt_schedule / nt_task (scheduled tasks & event triggers)                                      |
|   - nt_trade_journal (full CRUD, auto-tagging, export to TraderSync/TradesViz/CSV)               |
|   - nt_alert / nt_webhook (persistent price/indicator alerts & webhooks)                          |
+---------------------------------------------------------------------------------------------------+
| Phase 8: Risk, Compliance & Prop Firm Suite                                                       |
|   - nt_riskguard_config (dynamic trailing DD, volatility limits, time windows)                    |
|   - nt_compliance_report (one-click prop firm / broker report generation)                         |
|   - nt_multi_account_orchestrator (multi-account hedging & execution)                            |
|   - nt_subscribe (SSE real-time event stream channel for fills, FSM transitions, errors)           |
+---------------------------------------------------------------------------------------------------+
```

### Phase 5 — Enhanced Observability & Debugging
* **`nt_chart_snapshot`**: Accepts overlay markers (`markers: [{ time, price, label, color }]`), price lines, and indicator visibility options. Returns high-res PNG + structured JSON metadata for AI visual reasoning.
* **`nt_indicator_values`**: Queries time-series values for built-in or custom indicators, or pulls live values directly from a running strategy's indicator collection.
* **`nt_strategy_debug`**: Generates execution trace logs, bar-by-bar variable dumps, and exception stack traces for strategy debugging.

### Phase 6 — Advanced Research & Quant Optimization
* **`nt_optimize` & `nt_walk_forward`**: Supports Grid, Genetic, and Bayesian/Gaussian Process optimization. Returns Pareto fronts for multi-objective optimization (Sharpe + MaxDD + Profit Factor) and pins run provenance via `run_id`.
* **`nt_portfolio_backtest`**: Executes simultaneous multi-symbol backtests with correlation matrix calculation and portfolio-level risk metrics.
* **`nt_synthetic_data`**: Generates stress scenarios (e.g. 2008 crash, 2020 COVID shock, gap up/down volatility scaling) to test strategy robustness.
* **`nt_signal_backtest`**: Lightweight "what-if" testing of pure entry/exit signal rules without full NinjaScript strategy overhead.

### Phase 7 — Automation & Workflow Execution
* **`nt_script_execute`**: Sandboxed execution of arbitrary C# utility snippets (e.g. position sizing calculations, custom news filters).
* **`nt_schedule` / `nt_task`**: Time-based or event-based task scheduling (e.g. "re-optimize every Sunday at 18:00 ET", "flatten if loss > X").
* **`nt_trade_journal`**: Full CRUD trade journal database inside NT8 with macro window auto-tagging and export to TraderSync, TradesViz, or CSV.
* **`nt_alert` / `nt_webhook`**: Create persistent price/indicator alerts triggering local flattening, SMS/email, or webhooks.

### Phase 8 — Risk, Compliance & Prop Firm Suite
* **`nt_riskguard_config`**: Dynamic configuration of trailing drawdown rules, volatility-based position caps, correlation circuit breakers, and blackout windows.
* **`nt_compliance_report`**: One-click generation of prop firm / broker compliance reports (daily P&L, trade list, max exposure).
* **`nt_multi_account_orchestrator`**: Coordinated order routing and hedging across multiple accounts.
* **`nt_subscribe`**: Server-Sent Events (SSE) channel streaming real-time order fills, RiskGuard FSM state transitions, and strategy errors to connected clients.

---
*Document maintained by Quantitative Trading Architecture Team.*
