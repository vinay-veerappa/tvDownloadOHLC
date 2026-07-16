# NinjaTrader MCP Bridge - Documentation

This document describes the architecture, capabilities, and setup of the NinjaTrader Model Context Protocol (MCP) server.

## Overview

The NinjaTrader MCP Bridge allows external applications, such as Python scripts or autonomous agents, to seamlessly interface with NinjaTrader 8. It leverages a Node.js-based MCP server that translates JSON-RPC requests into HTTP requests, which are then handled by a custom C# AddOn running natively inside NinjaTrader.

### Core Architecture

1.  **Client Application**: The Python client (`NinjaTraderClient.py`) or MCP-enabled agent sends standardized requests.
2.  **MCP Server (`nt-mcp-server.js`)**: An intermediary Node.js server that defines the tools and schemas, translating MCP Tool Calls into RESTful HTTP requests.
3.  **NinjaTrader C# AddOn (`McpBridgeAddOn.cs`)**: A custom NinjaTrader AddOn that hosts a local `HttpListener`. It receives requests from the MCP server, interacts with the NinjaTrader Core API (Accounts, Orders, Data), and returns JSON responses.

---

## Capabilities & Tool Reference

The MCP Server exposes several core trading functions as tools.

### 1. Placing Orders (`nt_place_order`)
Creates new entry or exit orders.
- **Support for OCO & Bracket Orders**: You can group orders by providing an `ocoId` (One-Cancels-Other ID) and a unique `name`.
- **Supported Types**: MARKET, LIMIT, STOP_MARKET.
- **Example Usage**:
  ```json
  {
    "account": "Sim101",
    "symbol": "NQ",
    "action": "BUY",
    "quantity": 1,
    "orderType": "LIMIT",
    "limitPrice": 15000,
    "name": "EntryOrder",
    "ocoId": "Group1"
  }
  ```

### 2. Changing Orders (`nt_change_order`)
Modifies working orders in the market without needing to cancel and replace them. This prevents issues like losing queue position or accidental order duplication.
- **Parameters**: `orderId`, `limitPrice`, `stopPrice`, `quantity`.

### 3. Canceling Orders (`nt_cancel_order`)
Cancels working orders.
- **Bulk Cancel**: By passing the `ocoId`, NinjaTrader will cancel all associated orders in that group.

### 4. Flattening Positions (`nt_close_position`)
A critical risk management tool.
- Immediately cancels all working orders for the specified account and instrument.
- Issues an opposite market order to flatten any open positions.

### 5. Market Data (`nt_quote`, `nt_bars`)
Retrieves live quotes and historical bars.
- **Auto-Subscription**: The `nt_quote` endpoint automatically handles subscribing to data feeds (via `EnsureSubscribed` logic in C#) if the symbol isn't already active, preventing "not subscribed" errors.

---

## Recent API Enhancements (Autotrading Features)

The following changes were recently introduced to fully support programmatic autotrading and bracket order management:

1.  **Bracket/OCO Support**: Added `ocoId` and `name` properties to the `nt_place_order` and `nt_cancel_order` schemas to enable tracking and grouped cancellation.
2.  **Order Modification**: Added the `nt_change_order` endpoint (mapped to `/api/order/change`). This uses the native `account.Change(order)` C# method to safely adjust `Quantity`, `LimitPrice`, or `StopPrice`.
3.  **Position Flattening**: Added the `nt_close_position` endpoint (mapped to `/api/position/close`). This uses `account.Flatten()` and safely terminates all associated working orders for the symbol.
4.  **Quote Auto-Subscription**: Updated the C# AddOn to programmatically detect and subscribe to market data if a quote is requested for an inactive symbol.
5.  **Python SDK**: Released `scripts/NinjaTraderClient.py`, providing an OOP wrapper around the MCP endpoints for clean integration.

---

## Setup & Deployment

1.  **Install C# AddOn**:
    - Copy `McpBridgeAddOn.cs` to `Documents\NinjaTrader 8\bin\Custom\AddOns\`.
    - Open NinjaTrader 8 -> New -> NinjaScript Editor -> Right Click -> Compile (or use the `nt_compile` tool).
2.  **Start MCP Server**:
    - Run the Node.js MCP server (ensure port 8080 or configured port is available).
3.  **Client Usage**:
    - Import the `NinjaTraderClient` in your Python environment to begin autotrading.
