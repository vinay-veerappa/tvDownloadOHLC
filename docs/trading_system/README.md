# Unified Trading System Architecture

This directory contains the core architectural designs for the Hub-and-Spoke data streaming model (Schwab & NinjaTrader 8).

## Key Documents
- [Schwab Unified Hub Design](./schwab_unified_hub_design.md): Blueprint for Schwab Hub-and-Spoke L1/L2 streaming.
- [NinjaTrader MCP Specification](https://github.com/vinay-veerappa/nt8-mcp-bridge/blob/fold-mcp-wrapper/docs/ninjatrader-mcp.md): Blueprint for NinjaTrader 8 Unified Hub (`ninjatrader_hub.py`) and 52-tool MCP suite (now in the nt8-mcp-bridge repo).
- [L2 Bookmap Engine](./l2_engine_specs.md): Technical specifications for heatmap and mHVN detection.

## Streaming Hub Services
- **Schwab Unified Hub**: `python scripts/streaming/schwab_hub.py --port 8080` (Broadcasts at `ws://127.0.0.1:8000/ws`)
- **NinjaTrader Unified Hub**: `python scripts/streaming/ninjatrader_hub.py --port 7891` (Broadcasts at `ws://127.0.0.1:7891/ws`)

## Existing Components (Reflected in /docs/indicators)
- [Options Tactical Dashboard](../indicators/Options/README.md)
- [Dealer Levels Indicator](../indicators/Options/DealerLevels.md)
