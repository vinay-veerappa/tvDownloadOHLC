---
name: TradingView Wargame Verifier
description: Automates TradingView chart replay navigation, extracts Pine Script study labels/lines/boxes, and performs ground-truth 1-to-1 verification against Matt Mickey & Austin's daily profiler and wargaming engines.
---

# TradingView Wargame Verifier Skill

This skill provides an automated workflow to jump TradingView charts to specific historical trading dates, read Pine Script study labels (`The Daily Profile vTDL`, `Daily Profiler [VxV]`, `Time & Price Ranges V2 Pro`), and verify Python profiler calculations against live chart plots.

## When to Use
- Verifying P12 High/Low/Mid levels against TradingView indicators.
- Validating Candle Science Open/Close mode reads.
- Replaying historical sessions (e.g. 2026-08-03, 2026-07-29) in TradingView Bar Replay mode.
- Performing ground-truth validation across a batch of wargaming dates.

## Workflow & MCP Tools
1. **Health Check**: Call `tradingview/tv_health_check` to confirm CDP connection.
2. **Chart Navigation**: Call `tradingview/chart_scroll_to_date` or `tradingview/replay_start` to set the chart date.
3. **Indicator Extraction**: Call `tradingview/data_get_pine_labels`, `data_get_pine_lines`, and `data_get_pine_boxes`.
4. **Python Comparison**: Execute `python scripts/wargaming/automated_tv_wargame_verifier.py NQ1 <YYYY-MM-DD>`.
5. **Screenshot Audit**: Call `tradingview/capture_screenshot` to save visual verification artifacts.
