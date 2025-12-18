# Research: Schwabdev Library Analysis

This document summarizes findings from exploring the [Schwabdev](https://github.com/tylerebowers/Schwabdev) repository, specifically focusing on its approach to token management and streaming.

## 🎯 Key Takeaways

### 1. Robust Token Management
- **SQLite Persistence**: Stores tokens in an SQLite database (`tokens.db`) rather than a simple JSON file. This allows for cleaner management of multiple accounts and historical metadata.
- **Security**: Supports optional encryption for the token database using `cryptography.fernet`.
- **Automated Refresh**: The `Tokens` class proactively monitors expiration and handles background refreshes.
- **Reference**: [`schwabdev/tokens.py`](https://github.com/tylerebowers/Schwabdev/blob/main/schwabdev/tokens.py)

### 2. Reliable Streaming Engine
- **Automatic Re-subscription**: This is a critical feature. If the WebSocket connection drops, the library automatically reconnects and re-subscribes to all previously active data streams.
- **Async Efficiency**: Built on `asyncio` and `websockets`, optimized for high-throughput market data.
- **Flexible Callbacks**: Supports both synchronous and asynchronous message processors.
- **Error Handling**: Implements exponential backoff for reconnections.
- **Reference**: [`schwabdev/stream.py`](https://github.com/tylerebowers/Schwabdev/blob/main/schwabdev/stream.py)

### 3. Architecture & API Coverage
- **Modular Design**: Very clean separation between token handling, streaming, and REST API calls.
- **Comprehensive API**: High-level wrappers for Level 1 Equities, Options, Futures, and Historical Data.
- **Auth Hooks**: Includes a `call_on_auth` hook to notify users when browser-based MFA/Login is required.

---

## 💡 Potential Improvements for Our Project

Based on this research, we should consider implementing the following in our `stream_chart.py` and auth setup:

1.  **Re-subscription Logic**: Currently, if our streamer drops, it might not automatically re-subscribe to the specific symbols it was watching. We can adapt the pattern from `Schwabdev`'s `stream.py` to keep a list of active subscriptions for auto-restoration.
2.  **SQLite Ticker Management**: Moving from `live_chart.json` and `live_storage.parquet` to an SQLite backend for the "Hot Buffer" could simplify multi-ticker management.
3.  **Background Refresh**: Ensuring our `get_client()` logic is as proactive as their `Tokens` class to prevent session timeouts during long-running streaming sessions.

---
*Date of Research: 2025-12-17*
